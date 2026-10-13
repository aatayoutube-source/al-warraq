"""Import the works of Arabic Wikisource (ويكي مصدر): about 40,000 classical poems plus books,
letters, religious and legal texts, all free to read there.

    python -m app.wikisource            # or: python -m app.importer --no-gutenberg --wikisource

The list comes from Wikidata (every item with a page on ar.wikisource.org), which also gives the
author. Only titles, authors and the page name are stored; each book links to its Wikisource page.
Safe to run again: it replaces the rows from the previous Wikisource import.
"""
import http.client
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from .textnorm import norm

WS_KIND = 3  # books.curated value for Wikisource rows (0 Gutenberg, 1 hand-picked, 2 HathiTrust)
WORKS_ORD_BASE = 90_000      # books and other works: listed right after the hand-picked ones
POEMS_ORD_BASE = 3_000_000   # single poems: after everything else, grouped by poet
SPARQL = "https://query.wikidata.org/sparql"
UA = "AlWarraqLibrary/1.0 (public-domain book index; importer)"

# Wikidata "instance of" -> category ('' = decide from the form of the work or the title)
TYPES = {
    "Q7725634": "", "Q3331189": "", "Q47461344": "", "Q571": "", "Q57933693": "", "Q17537576": "", "Q234460": "",
    "Q49848": "", "Q1002697": "", "Q1749541": "",
    "Q234262": "rel", "Q179461": "rel", "Q29154430": "rel",
    "Q820655": "pol", "Q7755": "pol", "Q7748": "pol", "Q131569": "pol", "Q877358": "pol", "Q29883540": "pol",
    "Q2076487": "pol", "Q67011165": "pol", "Q1691434": "pol", "Q3011948": "pol", "Q1414472": "pol", "Q79700418": "pol",
    "Q314128": "pol", "Q625298": "pol", "Q922203": "pol", "Q1330251": "pol", "Q46337": "pol", "Q52947181": "pol",
    "Q133492": "bio", "Q215495": "bio", "Q699": "chi", "Q23691": "poe",
}
FORMS = {"Q5185279": "poe", "Q12106333": "poe", "Q49084": "nov", "Q8261": "nov", "Q25379": "dra"}
POEM = "poe"

# category from words in an Arabic title (first match wins)
AR_RULES = [
    ("poe", ["ديوان", "قصيده", "قصائد", "اشعار", "شعر", "معلقه", "اراجيز", "الفيه"]),
    ("rel", ["القران", "سوره", "تفسير", "حديث", "الحديث", "فقه", "الفقه", "صحيح", "سنن", "مسند", "العقيده", "التوحيد", "الصلاه", "الانجيل", "سفر", "رساله الي"]),
    ("his", ["تاريخ", "التاريخ", "الكامل في", "طبقات", "اخبار", "فتوح", "مروج"]),
    ("bio", ["سيره", "السيره", "ترجمه", "مذكرات", "رسائل", "رساله"]),
    ("tra", ["رحله", "الرحله", "رحلات", "البلدان", "جغرافيا"]),
    ("phi", ["فلسفه", "الفلسفه", "منطق", "المنطق", "تهافت", "الاخلاق", "حكمه"]),
    ("med", ["طب", "الطب", "القانون في الطب", "الادويه", "العلاج"]),
    ("mat", ["حساب", "الجبر", "هندسه", "الفلك", "النجوم"]),
    ("pol", ["دستور", "قانون", "نظام", "معاهده", "اتفاقيه", "اعلان", "قرار", "ميثاق", "السياسه"]),
    ("nov", ["روايه", "قصه", "قصص", "حكايه", "مقامات", "ليله"]),
    ("dra", ["مسرحيه"]),
]


def ar_category(title: str) -> str:
    words = " " + norm(title) + " "
    for cat, keys in AR_RULES:
        if any((" " + k + " ") in words or words.startswith(" " + k) for k in keys):
            return cat
    return "gen"


def _query() -> str:
    values = " ".join("wd:" + q for q in TYPES)
    return """SELECT ?item ?page ?label ?type ?form ?aar ?aen WHERE {
 VALUES ?type { %s }
 ?sl schema:isPartOf <https://ar.wikisource.org/>; schema:about ?item; schema:name ?page .
 ?item wdt:P31 ?type .
 OPTIONAL { ?item rdfs:label ?label FILTER(lang(?label)="ar") }
 OPTIONAL { ?item wdt:P7937 ?form }
 OPTIONAL { ?item wdt:P50 ?a .
   OPTIONAL { ?a rdfs:label ?aar FILTER(lang(?aar)="ar") }
   OPTIONAL { ?a rdfs:label ?aen FILTER(lang(?aen)="en") } }
}""" % values


def _term(cell: str) -> str:
    """One SPARQL TSV cell -> plain value: <iri> -> iri, "text"@ar -> text."""
    cell = cell.strip()
    if cell.startswith("<") and cell.endswith(">"):
        return cell[1:-1]
    if cell.startswith('"'):
        cell = cell[1:cell.rfind('"')]
        return re.sub(r'\\(.)', lambda m: {"t": "\t", "n": " ", "r": " "}.get(m.group(1), m.group(1)), cell)
    return cell


def parse_tsv(text: str) -> list:
    lines = text.split("\n")
    names = [h.strip().lstrip("?") for h in lines[0].split("\t")]
    return [dict(zip(names, (_term(c) for c in line.split("\t")))) for line in lines[1:] if line.strip()]


def fetch_bindings(tries: int = 4) -> list:
    """Rows as {variable: value}. TSV is about five times smaller than SPARQL JSON for these ~45,000 rows."""
    body = urllib.parse.urlencode({"query": _query()}).encode()
    for attempt in range(tries):
        req = urllib.request.Request(SPARQL, data=body, headers={"User-Agent": UA, "Accept": "text/tab-separated-values"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return parse_tsv(r.read().decode("utf-8"))
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError):  # Wikidata is often briefly busy
            if attempt == tries - 1:
                raise
            time.sleep(15 * (attempt + 1))


def _v(b, k) -> str:
    return (b.get(k) or "").strip()


def parse(bindings) -> list:
    """One record per Wikidata item: dict(page, title, author_ar, author_en, cat)."""
    items = {}
    for b in bindings:
        qid = _v(b, "item").rsplit("/", 1)[-1]
        page = _v(b, "page")
        if not qid or not page or "/" in page:  # sub-pages are chapters of a work already listed
            continue
        rec = items.get(qid)
        if rec is None:
            title = _v(b, "label") or page
            title = re.sub(r"\s+", " ", title)[:140]
            rec = items[qid] = {"page": page, "title": title, "author_ar": "", "author_en": "", "cat": ""}
        if not rec["author_ar"] and not rec["author_en"]:
            rec["author_ar"], rec["author_en"] = _v(b, "aar"), _v(b, "aen")
        cat = FORMS.get(_v(b, "form").rsplit("/", 1)[-1]) or TYPES.get(_v(b, "type").rsplit("/", 1)[-1], "")
        if cat and (not rec["cat"] or cat == POEM):
            rec["cat"] = cat
    out = []
    for rec in items.values():
        if not rec["cat"]:
            # a verse used as a title carries its vowel marks; book titles do not (al-Ma'arri's poems lack a "form")
            rec["cat"] = POEM if len(_HARAKAT.findall(rec["title"])) >= 3 else ar_category(rec["title"])
        out.append(rec)
    # an untyped work by someone who wrote almost only poems is one more poem
    per_author = {}
    for rec in out:
        n = per_author.setdefault(rec["author_ar"] or rec["author_en"], [0, 0])
        n[0] += 1
        n[1] += rec["cat"] == POEM
    for rec in out:
        total, poems = per_author.get(rec["author_ar"] or rec["author_en"], (0, 0))
        if rec["cat"] == "gen" and (rec["author_ar"] or rec["author_en"]) and poems >= 20 and poems >= 0.8 * total:
            rec["cat"] = POEM
    return out


_HARAKAT = re.compile("[ً-ْ]")


def _author_keys(conn) -> dict:
    """Exact (normalised) names of the hand-picked authors -> key. No partial matching:
    'Ibn al-Rumi' must not become 'Rumi'."""
    keys = {}
    for r in conn.execute("SELECT key, en, ar, tokens FROM authors"):
        for name in [r["en"], r["ar"]] + r["tokens"].split(","):
            n = norm(name)
            if n:
                keys.setdefault(n, r["key"])
    return keys


def import_records(conn, records) -> dict:
    keys = _author_keys(conn)
    info = {r["key"]: (r["en"], r["ar"]) for r in conn.execute("SELECT key, en, ar FROM authors")}
    curated = {}
    for r in conn.execute("SELECT id, title, title_ar, author_key FROM books WHERE curated=1 AND author_key!=''"):
        for t in (r["title"], r["title_ar"]):
            if norm(t):
                curated.setdefault((r["author_key"], norm(t)), r["id"])

    conn.execute("UPDATE books SET ws=NULL WHERE curated=1")
    conn.execute("DELETE FROM cover_cache WHERE book_id IN (SELECT id FROM books WHERE curated=?)", (WS_KIND,))
    conn.execute("DELETE FROM books WHERE curated=?", (WS_KIND,))

    # works first (by title), then poems grouped by poet, best-known poets (most poems) first
    per_poet = {}
    for rec in records:
        if rec["cat"] == POEM:
            per_poet[rec["author_ar"] or rec["author_en"]] = per_poet.get(rec["author_ar"] or rec["author_en"], 0) + 1
    def known(r):
        return keys.get(norm(r["author_ar"])) or keys.get(norm(r["author_en"]))
    works = sorted((r for r in records if r["cat"] != POEM),
                   key=lambda r: (not known(r), not (r["author_ar"] or r["author_en"]), r["cat"] == "pol", norm(r["title"])))
    poems = sorted((r for r in records if r["cat"] == POEM),
                   key=lambda r: (-per_poet.get(r["author_ar"] or r["author_en"], 0), r["author_ar"] or r["author_en"], norm(r["title"])))

    links, inserts, seen = [], [], set()
    for base, group in ((WORKS_ORD_BASE, works), (POEMS_ORD_BASE, poems)):
        for i, rec in enumerate(group):
            key = keys.get(norm(rec["author_ar"])) or keys.get(norm(rec["author_en"])) or ""
            a_en, a_ar = info[key] if key else (rec["author_en"], rec["author_ar"])
            hit = curated.get((key, norm(rec["title"]))) if key else None
            if hit:  # same book as a hand-picked one: give it the direct reading link instead of a duplicate
                links.append((rec["page"], hit))
                continue
            dup = norm(rec["title"]) + "|" + norm(a_ar or a_en)
            if dup in seen:
                continue
            seen.add(dup)
            inserts.append((rec["page"], rec["title"], rec["title"], key, a_en or a_ar, a_ar, rec["cat"], base + i,
                            norm(rec["title"] + " " + a_en + " " + a_ar)))

    conn.executemany("UPDATE books SET ws=? WHERE id=?", links)
    conn.executemany(
        "INSERT INTO books(gid,htid,ws,title,title_ar,author_key,author_en,author_ar,cat,origin,lang,curated,ord,search)"
        " VALUES(NULL,NULL,?,?,?,?,?,?,?,'a','ar',%d,?,?)" % WS_KIND, inserts)
    conn.commit()
    poems_n = sum(1 for r in inserts if r[6] == POEM)
    return {"wikisource_added": len(inserts), "poems": poems_n, "works": len(inserts) - poems_n, "linked": len(links)}


def run(conn) -> dict:
    return import_records(conn, parse(fetch_bindings()))


def main() -> int:
    from . import db
    conn = db.connect()
    db.init_db(conn)
    db.seed_curated(conn)
    try:
        print("Wikisource:", run(conn))
    except Exception as e:  # network, Wikidata timeout...
        print("Wikisource import failed: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
