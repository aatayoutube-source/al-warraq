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
import json
import re
import sys
import time
import urllib.parse
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


def recategorize(conn, csv_path: str = "") -> int:
    """Gives the Gutenberg books already in the database the categories of today's rules (a new category such
    as horror) without importing them again: their ids, and so their addresses, likes and views, stay.
    Hand-picked books keep the category chosen for them, except that a genre (horror, crime and mystery) wins:
    Frankenstein and Dracula belong with the horror books."""
    if csv_path:
        with open(csv_path, encoding="utf-8", errors="replace", newline="") as f:
            data = f.read()
    else:
        data = fetch(CATALOG_URL)
    wanted = {gid: cat for _score, gid, _t, _a, _l, cat in parse_catalog(data, 0, set())}
    # one pass over the Gutenberg rows, then updates by id: "WHERE gid=?" has no index and would scan the table each time
    changes = [(wanted[r["gid"]], r["id"]) for r in conn.execute("SELECT id, gid, cat, curated FROM books WHERE curated IN (0, 1) AND gid>0")
               if wanted.get(r["gid"], r["cat"]) != r["cat"] and (r["curated"] == 0 or wanted[r["gid"]] in ("hor", "mys"))]
    conn.executemany("UPDATE books SET cat=? WHERE id=?", changes)
    conn.commit()
    return len(changes)


# horror: the most downloaded first (Gutendex reads Gutenberg's download counts), and the scanned HathiTrust
# books whose titles say so in so many words
GUTENDEX = "https://gutendex.com/books/"
HORROR_TOPICS = ("horror", "ghost stories", "vampires", "supernatural", "gothic fiction", "haunted", "werewolves")
POPULAR_HORROR_ORD_BASE = 99_000  # before the rest of Gutenberg (100,000+)
HORROR_TITLES = re.compile(r"\b(ghost stor(y|ies)|tales of (terror|horror|the supernatural|the uncanny)|horror stories|weird tales|"
                           r"uncanny (tales|stories)|tales of mystery and imagination|the vampyre|vampires?|werewol(f|ves)|"
                           r"haunted hous(e|es)|histoires extraordinaires|gespenstergeschichten)\b", re.I)
NOT_HORROR = re.compile(r"\bbats?\b|bibliograph|catalogue|index of|politic|tammany|of the continent|press|history|histoire de|dakota", re.I)
# "vampire bats" are zoology, a "political vampire" is politics, a town history with "its ghost stories" is history
MYSTERY_TITLES = re.compile(r"\b(detective stor(y|ies)|mystery stories|murder mystery|sherlock holmes|crime stories)\b", re.I)


def rank_horror(conn, pages: int = 4, fetch_json=None, pause: float = 1.0) -> int:
    """Orders the horror category by Gutenberg downloads: Dracula and Frankenstein come before the obscure."""
    fetch_json = fetch_json or (lambda url: json.loads(fetch(url)))

    def patient(url):  # Gutendex is a free service that is often busy: wait and try again, then give up on that topic
        for wait in (15, 45, 90):
            try:
                return fetch_json(url)
            except Exception as e:
                print("Gutendex busy (%s), trying again in %d s" % (e, wait), file=sys.stderr)
                time.sleep(wait * (pause > 0))
        return None

    downloads = {}
    for topic in HORROR_TOPICS:
        url = GUTENDEX + "?" + urllib.parse.urlencode({"topic": topic})
        for _ in range(pages):
            data = patient(url)
            if data is None:
                break
            for b in data.get("results", []):
                downloads[b["id"]] = max(downloads.get(b["id"], 0), b.get("download_count") or 0)
            url = data.get("next")
            if not url:
                break
            time.sleep(pause)
    ids = {r["gid"]: r["id"] for r in conn.execute("SELECT id, gid FROM books WHERE cat='hor' AND gid>0")}
    ranked = [g for g in sorted(downloads, key=lambda g: -downloads[g]) if g in ids][:999]
    conn.executemany("UPDATE books SET ord=? WHERE id=?", [(POPULAR_HORROR_ORD_BASE + i, ids[g]) for i, g in enumerate(ranked)])
    conn.commit()
    return len(ranked)


def recategorize_hathi_titles(conn) -> dict:
    """HathiTrust books are known only by their titles: those that say horror or detective stories outright move there."""
    moves = {"hor": [], "mys": []}
    for r in conn.execute("SELECT id, title, cat FROM books WHERE curated=2"):
        t = r["title"] or ""
        if r["cat"] != "hor" and HORROR_TITLES.search(t) and not NOT_HORROR.search(t):
            moves["hor"].append(r["id"])
        elif r["cat"] == "hor" and NOT_HORROR.search(t):  # put there by a looser rule: out again
            moves.setdefault("gen", []).append(r["id"])
        elif r["cat"] not in ("hor", "mys") and MYSTERY_TITLES.search(t):
            moves["mys"].append(r["id"])
    for cat, ids in moves.items():
        conn.executemany("UPDATE books SET cat=? WHERE id=?", [(cat, i) for i in ids])
    conn.commit()
    return {k: len(v) for k, v in moves.items()}


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
    ap.add_argument("--rank-horror", action="store_true", help="only order the horror books by Gutenberg downloads (Gutendex)")
    ap.add_argument("--recategorize", action="store_true", help="only re-sort the Gutenberg books already imported into today's"
                    " categories (keeps their ids); uses --csv when given")
    args = ap.parse_args()
    if args.rank_horror:
        conn = db.connect()
        print("Horror books ordered by downloads: %d" % rank_horror(conn))
        return 0
    if args.recategorize:
        conn = db.connect()
        db.init_db(conn)
        print("Gutenberg books moved to another category: %d" % recategorize(conn, args.csv))
        print("HathiTrust books moved by their titles:", recategorize_hathi_titles(conn))
        print("Horror books ordered by downloads: %d" % rank_horror(conn))
        return 0

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