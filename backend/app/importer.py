"""Import the official Project Gutenberg catalog (about 75,000 books) into the database.

    python -m app.importer                  # everything
    python -m app.importer --limit 20000    # only the first 20,000 (best-ranked)
    python -m app.importer --lang en,ar,fr  # only these languages
    python -m app.importer --csv pg_catalog.csv      # file you already downloaded

Project Gutenberg works are public domain under US law; check your own country's law.
"""
import argparse
import csv
import io
import sys
import urllib.request

from . import db
from .catalog import CATEGORIES, categorize, clean_author, clean_title
from .textnorm import norm

CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
IMPORTED_ORD_BASE = 100_000


def fetch(url: str) -> str:
    print("Downloading", url, "...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "warraq-importer/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_catalog(data: str, limit: int, langs: set):
    """Return ranked rows. limit <= 0 means no limit."""
    rows = []
    for rec in csv.DictReader(io.StringIO(data, newline="")):
        if (rec.get("Type") or "").strip() != "Text":
            continue
        try:
            gid = int((rec.get("Text#") or "").strip())
        except ValueError:
            continue
        title = clean_title(rec.get("Title"))
        if not title:
            continue
        lang_list = [x.strip().lower() for x in (rec.get("Language") or "").split(";") if x.strip()]
        lang = lang_list[0] if lang_list else "en"
        if langs and lang not in langs:
            continue
        author = clean_author(rec.get("Authors") or "")
        shelves = rec.get("Bookshelves") or ""
        cat = categorize(rec.get("Subjects") or "", shelves)
        # Rank: Arabic first, then books with a named author and a bookshelf, then older (classic) ids.
        score = (4 if lang == "ar" else 0)
        score += 2 if author and author.lower() not in ("anonymous", "various") else 0
        score += 2 if shelves.strip() else 0
        rows.append((-score, gid, title, author, lang, cat))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows[:limit] if limit and limit > 0 else rows


class AuthorIndex:
    """Match a Gutenberg author string to one of our known authors by whole-word phrases."""

    def __init__(self, conn):
        self.info = {}
        self.by_first = {}
        for r in conn.execute("SELECT key, tokens, en, ar, origin FROM authors ORDER BY ord"):
            self.info[r["key"]] = (r["en"], r["ar"], r["origin"])
            phrases = [norm(t) for t in r["tokens"].split(",") if norm(t)]
            ar = norm(r["ar"])
            if ar:
                phrases.append(ar)
            for ph in phrases:
                words = tuple(ph.split())
                self.by_first.setdefault(words[0], []).append((r["key"], words))

    def match(self, name: str):
        words = norm(name).split()
        for i, w in enumerate(words):
            for key, ph in self.by_first.get(w, ()):
                if tuple(words[i:i + len(ph)]) == ph:
                    return key
        return None


def import_rows(conn, rows) -> dict:
    """Replace all previously imported books with `rows`.

    Curated books stay; when an imported book is an edition of a curated one
    (same author, title equal or starting with the curated title) the curated
    book simply gains its Gutenberg id, so it gets direct reading links and a cover.
    """
    index = AuthorIndex(conn)

    curated = {}  # author_key -> list of [id, norm_title, norm_title_ar]
    for r in conn.execute("SELECT id, title, title_ar, author_key FROM books WHERE curated=1"):
        curated.setdefault(r["author_key"], []).append([r["id"], norm(r["title"]), norm(r["title_ar"])])

    conn.execute("UPDATE books SET gid=NULL WHERE curated=1")
    conn.execute("DELETE FROM books WHERE curated=0")

    def is_edition(nt: str, ct: str) -> bool:
        return bool(ct) and (nt == ct or nt.startswith(ct + " "))

    linked_ids, links, inserts = set(), [], []
    for rank, (_, gid, title, author, lang, cat) in enumerate(rows):
        key = index.match(author) if author else None
        nt = norm(title)
        if key:
            hit = next((c for c in curated.get(key, ()) if c[0] not in linked_ids and (is_edition(nt, c[1]) or is_edition(nt, c[2]))), None)
            if hit:
                linked_ids.add(hit[0])
                links.append((gid, hit[0]))
                continue
        if key:
            a_en, a_ar, origin = index.info[key]
        else:
            a_en, a_ar, origin = author, "", "w"
        if lang == "ar":
            origin = "a"
        inserts.append((gid, title, key or "", a_en, a_ar, cat if cat in CATEGORIES else "nov", origin, lang,
                        IMPORTED_ORD_BASE + rank, norm(title + " " + a_en + " " + a_ar)))

    conn.executemany("UPDATE books SET gid=? WHERE id=?", links)
    conn.executemany(
        "INSERT INTO books(gid,title,title_ar,author_key,author_en,author_ar,cat,origin,lang,curated,ord,search)"
        " VALUES(?,?,'',?,?,?,?,?,?,0,?,?)",
        inserts,
    )
    conn.execute("DELETE FROM cover_cache WHERE book_id NOT IN (SELECT id FROM books)")
    conn.commit()
    return {"added": len(inserts), "linked": len(links)}


def run(conn, limit=0, langs=None, csv_path="") -> dict:
    if csv_path:
        with open(csv_path, encoding="utf-8", errors="replace", newline="") as f:
            data = f.read()
    else:
        data = fetch(CATALOG_URL)
    rows = parse_catalog(data, limit, set(langs or []))
    return import_rows(conn, rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="max books, 0 = all (default)")
    ap.add_argument("--lang", default="", help="comma list, e.g. en,ar,fr (default: all)")
    ap.add_argument("--csv", default="", help="path to a downloaded pg_catalog.csv")
    ap.add_argument("--hathi", default="", help="path to a HathiTrust hathi_full_*.txt(.gz) file (adds up to --hathi-limit more books),"
                    " or 'auto' to download the newest one")
    ap.add_argument("--hathi-limit", type=int, default=1000000, help="max HathiTrust books, 0 = all (default 1000000)")
    ap.add_argument("--no-gutenberg", action="store_true", help="skip Gutenberg (only import the --hathi file)")
    ap.add_argument("--wikisource", action="store_true", help="also import Arabic Wikisource (about 43,000 works, needs internet)")
    args = ap.parse_args()

    conn = db.connect()
    db.init_db(conn)
    db.seed_curated(conn)
    langs = [x.strip().lower() for x in args.lang.split(",") if x.strip()]
    if not args.no_gutenberg:
        try:
            res = run(conn, args.limit, langs, args.csv)
            print("Gutenberg: %(added)d books added, %(linked)d curated books linked." % res)
        except Exception as e:  # network, DNS, bad file...
            print("Gutenberg import failed: %s" % e, file=sys.stderr)
            print("Download %s manually and run again with --csv pg_catalog.csv" % CATALOG_URL, file=sys.stderr)
            return 1
    if args.hathi:
        from . import hathi
        try:
            if args.hathi == "auto":
                import os
                print("HathiTrust:", hathi.auto_import(conn, os.path.dirname(os.path.abspath(db.db_path())), args.hathi_limit))
            else:
                print("HathiTrust:", hathi.import_hathi(conn, args.hathi, args.hathi_limit, set(langs)))
        except Exception as e:
            print("HathiTrust import failed: %s" % e, file=sys.stderr)
            return 1
    if args.wikisource:
        from . import wikisource
        try:
            print("Wikisource:", wikisource.run(conn))
        except Exception as e:
            print("Wikisource import failed: %s" % e, file=sys.stderr)
            return 1
    total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    print("Total books in database: %d" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())