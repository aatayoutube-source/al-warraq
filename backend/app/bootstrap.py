"""Runs before the server starts (Docker entrypoint): create tables, seed, import once."""
import os
import sys

from . import db, importer


def main() -> int:
    conn = db.connect()
    db.init_db(conn)
    seeded = db.seed_curated(conn)
    print("Curated books seeded: %d" % seeded)
    imported = conn.execute("SELECT COUNT(*) FROM books WHERE curated=0").fetchone()[0]
    if os.environ.get("AUTO_IMPORT", "1") == "1" and imported == 0:
        limit = int(os.environ.get("IMPORT_LIMIT", "0"))  # 0 = all of Gutenberg
        langs = [x for x in os.environ.get("IMPORT_LANGS", "").split(",") if x.strip()]
        try:
            print("Importing Gutenberg catalog (limit %s)..." % (limit or "all"))
            res = importer.run(conn, limit, langs)
            print("Import done:", res)
        except Exception as e:  # never block the server from starting
            print("Import skipped (%s). Run `python -m app.importer` later." % e, file=sys.stderr)
    hathi_file = os.environ.get("HATHI_FILE", "")
    has_hathi = conn.execute("SELECT 1 FROM books WHERE curated=2 LIMIT 1").fetchone()
    if hathi_file and os.path.exists(hathi_file) and not has_hathi:
        try:
            from . import hathi
            print("Importing HathiTrust file", hathi_file)
            print(hathi.import_hathi(conn, hathi_file, int(os.environ.get("HATHI_LIMIT", "1000000"))))
        except Exception as e:
            print("HathiTrust import skipped (%s)." % e, file=sys.stderr)
    if has_hathi:
        from . import hathi
        moved = hathi.recategorize(conn)  # once: databases imported before the title classifier existed
        if moved:
            print("HathiTrust books given a category: %d" % moved)
    has_ws = conn.execute("SELECT 1 FROM books WHERE curated=3 LIMIT 1").fetchone()
    if os.environ.get("AUTO_WIKISOURCE", "1") == "1" and not has_ws:
        try:
            from . import wikisource
            print("Importing Arabic Wikisource...")
            print(wikisource.run(conn))
        except Exception as e:  # needs internet; the site works without it
            print("Wikisource import skipped (%s). Run `python -m app.wikisource` later." % e, file=sys.stderr)
    total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    print("Books in database: %d" % total)
    print("Authors in database: %d" % db.author_total(conn, total))  # counted now so the first page load is fast
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())