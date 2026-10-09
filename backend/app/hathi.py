"""Import public-domain books from a HathiTrust "hathifile" (hundreds of thousands of titles).

Download one file from https://www.hathitrust.org/hathifiles (the monthly "full" file,
named like hathi_full_YYYYMMDD.txt.gz, about 1 GB compressed), then run:

    python -m app.importer --hathi hathi_full_20260101.txt.gz --hathi-limit 450000

Only records that HathiTrust marks as full view anywhere in the world
(access = allow, rights = pd) and as books are kept. The file is read twice in
a streaming fashion, so memory stays low. HathiTrust holds the scans; this
library only stores titles, authors and the link to read each book there.
"""
import gzip
import re
import sys
from collections import Counter

from .catalog import CATEGORIES, categorize, clean_author
from .textnorm import norm

IMPORTED_ORD_BASE = 1_000_000
HATHI_KIND = 2  # books.curated value used for HathiTrust rows (0 = Gutenberg, 1 = hand-picked)

LANG2 = {
    "eng": "en", "ara": "ar", "fre": "fr", "ger": "de", "spa": "es", "ita": "it", "por": "pt", "dut": "nl",
    "rus": "ru", "lat": "la", "gre": "el", "grc": "grc", "per": "fa", "tur": "tr", "heb": "he", "chi": "zh",
    "jpn": "ja", "swe": "sv", "dan": "da", "nor": "no", "fin": "fi", "pol": "pl", "hun": "hu", "cze": "cs",
    "urd": "ur", "hin": "hi", "san": "sa", "kor": "ko", "rum": "ro", "bul": "bg", "ukr": "uk", "cat": "ca",
    "wel": "cy", "ice": "is", "arm": "hy", "geo": "ka", "ben": "bn", "tam": "ta", "mal": "ml", "sco": "sco",
}

_TRAIL = re.compile(r"[\s/:;,=.\-]+$")


def open_text(path):
    if path.lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="")
    return open(path, encoding="utf-8", errors="replace", newline="")


def clean_title(raw: str) -> str:
    t = (raw or "").split(" / ")[0]
    t = re.sub(r"\s+", " ", t)
    t = _TRAIL.sub("", t).strip()
    return t[:140]


def clean_ht_author(raw: str) -> str:
    return clean_author(re.sub(r"\.\s*$", "", (raw or "").strip()))


def scan(path, langs=frozenset()):
    """Yield (score, htid, bib_key, title, author, lang2) once per bib record, in file order."""
    seen = set()
    with open_text(path) as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 26 or p[1] != "allow" or p[2] != "pd" or p[19] != "BK":
                continue
            bib = p[3]
            if bib in seen:
                continue
            title = clean_title(p[11])
            if len(title) < 2:
                continue
            lang3 = p[18].strip().lower()
            lang = LANG2.get(lang3, lang3 or "und")
            if langs and lang not in langs and lang3 not in langs:
                continue
            seen.add(bib)
            author = clean_ht_author(p[25])
            score = (6 if lang == "ar" else 0) + (2 if author else 0) + (1 if lang == "en" else 0) + (1 if len(title) >= 8 else 0)
            yield score, p[0], bib, title, author, lang


def import_hathi(conn, path, limit=450000, langs=frozenset(), log=print):
    from .importer import AuthorIndex  # local import: avoids a cycle with importer.py

    # pass 1: how many records per score, to find the cut-off score for `limit`
    counts = Counter(r[0] for r in scan(path, langs))
    total = sum(counts.values())
    log("HathiTrust: %d public-domain books found" % total)
    if limit and limit > 0 and total > limit:
        acc, cutoff = 0, 0
        for sc in sorted(counts, reverse=True):
            acc += counts[sc]
            if acc >= limit:
                cutoff = sc
                break
        quota = limit - sum(n for sc, n in counts.items() if sc > cutoff)
    else:
        cutoff, quota = -1, total

    # titles already present (Gutenberg, hand-picked): skip duplicates
    existing = {norm(r["title"]) + "|" + norm(r["author_en"]) for r in conn.execute("SELECT title, author_en FROM books WHERE curated!=?", (HATHI_KIND,))}
    index = AuthorIndex(conn)
    conn.execute("DELETE FROM books WHERE curated=?", (HATHI_KIND,))
    conn.execute("DELETE FROM cover_cache WHERE book_id NOT IN (SELECT id FROM books)")

    sql = ("INSERT INTO books(gid,htid,title,title_ar,author_key,author_en,author_ar,cat,origin,lang,curated,ord,search)"
           " VALUES(NULL,?,?,'',?,?,?,?,?,?,%d,?,?)" % HATHI_KIND)
    batch, added, skipped = [], 0, 0
    for score, htid, _bib, title, author, lang in scan(path, langs):
        if score < cutoff or (score == cutoff and quota <= 0):
            continue
        dup = norm(title) + "|" + norm(author)
        if dup in existing:
            skipped += 1
            continue
        existing.add(dup)
        if score == cutoff:
            quota -= 1
        key = index.match(author) if author else None
        if key:
            a_en, a_ar, origin = index.info[key]
        else:
            a_en, a_ar, origin = author, "", "w"
        if lang == "ar":
            origin = "a"
        cat = categorize(title, "", default="gen")
        batch.append((htid, title, key or "", a_en, a_ar, cat if cat in CATEGORIES else "gen", origin, lang,
                      IMPORTED_ORD_BASE + added, norm(title + " " + a_en + " " + a_ar)))
        added += 1
        if len(batch) >= 20000:
            conn.executemany(sql, batch)
            batch.clear()
            log("  ... %d books" % added)
    if batch:
        conn.executemany(sql, batch)
    conn.commit()
    return {"hathi_added": added, "hathi_duplicates_skipped": skipped}
