"""SQLite storage: schema, connection helper and the curated seed."""
import os
import sqlite3

from .textnorm import norm

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SEED_VERSION = "2"  # bump when authors.txt / books.txt / norm() change: curated rows are rebuilt

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authors(
  key     TEXT PRIMARY KEY,
  en      TEXT NOT NULL,
  ar      TEXT NOT NULL,
  years   TEXT NOT NULL DEFAULT '',
  tokens  TEXT NOT NULL DEFAULT '',
  origin  TEXT NOT NULL DEFAULT 'w',
  ord     INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS books(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  gid        INTEGER,
  title      TEXT NOT NULL,
  title_ar   TEXT NOT NULL DEFAULT '',
  author_key TEXT NOT NULL DEFAULT '',
  author_en  TEXT NOT NULL DEFAULT '',
  author_ar  TEXT NOT NULL DEFAULT '',
  cat        TEXT NOT NULL,
  origin     TEXT NOT NULL,
  lang       TEXT NOT NULL DEFAULT '',
  curated    INTEGER NOT NULL DEFAULT 0,
  htid       TEXT,
  ws         TEXT,
  ord        INTEGER NOT NULL,
  search     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cover_cache(
  book_id INTEGER PRIMARY KEY,
  url     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS site_stats(
  key TEXT PRIMARY KEY,
  n   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS daily_visitors(
  day     TEXT NOT NULL,
  visitor TEXT NOT NULL,
  PRIMARY KEY(day, visitor)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS daily_views(
  day     TEXT NOT NULL,
  visitor TEXT NOT NULL,
  book_id INTEGER NOT NULL,
  PRIMARY KEY(day, visitor, book_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS search_votes(
  q       TEXT NOT NULL,
  visitor TEXT NOT NULL,
  PRIMARY KEY(q, visitor)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS period_visitors(
  period  TEXT NOT NULL,
  visitor TEXT NOT NULL,
  PRIMARY KEY(period, visitor)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS book_stats(
  book_id INTEGER PRIMARY KEY,
  views   INTEGER NOT NULL DEFAULT 0,
  likes   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_book_views ON book_stats(views DESC);
CREATE TABLE IF NOT EXISTS book_likes(
  book_id INTEGER NOT NULL,
  visitor TEXT NOT NULL,
  PRIMARY KEY(book_id, visitor)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS searches(
  q    TEXT PRIMARY KEY,
  n    INTEGER NOT NULL DEFAULT 1,
  last TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_searches_n ON searches(n DESC);
CREATE INDEX IF NOT EXISTS ix_books_cat_ord ON books(cat, ord);   -- a category page comes out already in order
CREATE INDEX IF NOT EXISTS ix_books_lang_ord ON books(lang, ord);
CREATE INDEX IF NOT EXISTS ix_books_author ON books(author_key);
CREATE INDEX IF NOT EXISTS ix_books_ord ON books(ord);
CREATE INDEX IF NOT EXISTS ix_books_curated ON books(curated);
"""


def db_path() -> str:
    return os.environ.get("WARRAQ_DB") or os.path.join(os.path.dirname(__file__), "..", "data", "warraq.db")


def connect(path: str = "") -> sqlite3.Connection:
    path = path or db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(books)")}
    if "htid" not in cols:  # database created by an older version
        conn.execute("ALTER TABLE books ADD COLUMN htid TEXT")
    if "ws" not in cols:  # Arabic Wikisource page name (added with the Wikisource import)
        conn.execute("ALTER TABLE books ADD COLUMN ws TEXT")
    # (cat) and (lang) alone are covered by the (cat, ord) and (lang, ord) indexes: about 30 MB saved
    conn.execute("DROP INDEX IF EXISTS ix_books_cat")
    conn.execute("DROP INDEX IF EXISTS ix_books_lang")
    conn.commit()
    fix_author_names(conn)
    seed_period_visitors(conn)
    ensure_fts(conn)


def seed_period_visitors(conn: sqlite3.Connection) -> None:
    """Once: visitors already counted in the last days also count for this month and this year."""
    if conn.execute("SELECT 1 FROM meta WHERE key='periods_seeded'").fetchone():
        return
    from .stats import _today
    day = _today()
    for period in (day[:7], day[:4]):
        conn.execute("INSERT OR IGNORE INTO period_visitors(period,visitor) SELECT ?, visitor FROM daily_visitors WHERE day LIKE ?",
                     (period, period + "%"))
        n = conn.execute("SELECT COUNT(*) FROM period_visitors WHERE period=?", (period,)).fetchone()[0]
        conn.execute("INSERT INTO site_stats(key,n) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET n=MAX(n, excluded.n)",
                     ("visitors:" + period, n))
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('periods_seeded','1')")
    conn.commit()


# Full-text index over books.search. The trigram tokenizer answers `search LIKE '%word%'` from an index
# instead of reading a million rows. detail=none keeps no word positions: a third of the size (about 100 MB
# instead of 310 for a million books) with exactly the same LIKE results.
FTS_VERSION = "2"  # 1 = first index with positions (detail=full), 2 = the light one
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(search, content='books', content_rowid='id', tokenize='trigram', detail=none);
CREATE TRIGGER IF NOT EXISTS books_fts_ai AFTER INSERT ON books BEGIN
  INSERT INTO books_fts(rowid, search) VALUES (new.id, new.search);
END;
CREATE TRIGGER IF NOT EXISTS books_fts_ad AFTER DELETE ON books BEGIN
  INSERT INTO books_fts(books_fts, rowid, search) VALUES ('delete', old.id, old.search);
END;
CREATE TRIGGER IF NOT EXISTS books_fts_au AFTER UPDATE OF search ON books BEGIN
  INSERT INTO books_fts(books_fts, rowid, search) VALUES ('delete', old.id, old.search);
  INSERT INTO books_fts(rowid, search) VALUES (new.id, new.search);
END;
"""


def ensure_fts(conn: sqlite3.Connection) -> bool:
    """Create the index once (about a minute for a million books); False if this SQLite lacks FTS5/trigram.
    A database with the older, larger index is converted and compacted (VACUUM) once."""
    if fts_ready(conn):
        return True
    old = conn.execute("SELECT 1 FROM meta WHERE key='fts'").fetchone()
    try:
        conn.executescript("""
            DROP TRIGGER IF EXISTS books_fts_ai; DROP TRIGGER IF EXISTS books_fts_ad; DROP TRIGGER IF EXISTS books_fts_au;
            DROP TABLE IF EXISTS books_fts;""" + FTS_SCHEMA)
        conn.execute("INSERT INTO books_fts(books_fts) VALUES('rebuild')")
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('fts',?)", (FTS_VERSION,))
        conn.commit()
    except sqlite3.OperationalError:  # very old SQLite: search keeps using LIKE
        conn.rollback()
        return False
    if old:
        conn.execute("VACUUM")  # give the space of the old index back to the disk
    return True


def fts_ready(conn: sqlite3.Connection) -> bool:
    return bool(conn.execute("SELECT 1 FROM meta WHERE key='fts' AND value=?", (FTS_VERSION,)).fetchone())


def fix_author_names(conn: sqlite3.Connection) -> None:
    """One-off repair of names imported before catalog.fix_name_order existed ('H. M. Sir Elliot')."""
    if conn.execute("SELECT 1 FROM meta WHERE key='names_fixed'").fetchone():
        return
    from .catalog import fix_name_order
    rows = conn.execute("SELECT id, author_en FROM books WHERE author_en LIKE '% Sir %' OR author_en LIKE '% Mrs %'"
                        " OR author_en LIKE '% Mrs. %' OR author_en LIKE '% Jr. %' OR author_en LIKE '% Jr %'"
                        " OR author_en LIKE '% Sr. %'").fetchall()
    conn.executemany("UPDATE books SET author_en=? WHERE id=?",
                     [(fix_name_order(r["author_en"]), r["id"]) for r in rows if fix_name_order(r["author_en"]) != r["author_en"]])
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('names_fixed','1')")
    conn.commit()


NOT_AUTHORS = ("various", "anonymous", "unknown", "unknown author", "anonymous & folk tradition")


def author_total(conn: sqlite3.Connection, books: int) -> int:
    """Distinct author names in the whole catalogue (not only the curated ones).
    Takes seconds on a million books, so it is kept in `meta` with the book count it was made for
    and only recounted when that count changes (after an import)."""
    row = conn.execute("SELECT value FROM meta WHERE key='author_total'").fetchone()
    if row and row["value"].split(":")[0] == str(books):
        return int(row["value"].split(":")[1])
    n = conn.execute(
        "SELECT COUNT(DISTINCT rtrim(lower(trim(author_en)), '.,; ')) FROM books"
        " WHERE trim(author_en)!='' AND lower(trim(author_en)) NOT IN (%s)" % ",".join("?" * len(NOT_AUTHORS)),
        NOT_AUTHORS).fetchone()[0]
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('author_total',?)", ("%d:%d" % (books, n),))
    conn.commit()
    return n


def seed_curated(conn: sqlite3.Connection) -> int:
    """Load the hand-picked authors and books. Idempotent for the same SEED_VERSION."""
    have = conn.execute("SELECT 1 FROM books WHERE curated=1 LIMIT 1").fetchone()
    ver = conn.execute("SELECT value FROM meta WHERE key='seed_version'").fetchone()
    if have and ver and ver["value"] == SEED_VERSION:
        return 0
    if have:  # older seed: rebuild curated rows (imported books are untouched)
        conn.execute("DELETE FROM cover_cache WHERE book_id IN (SELECT id FROM books WHERE curated=1)")
        conn.execute("DELETE FROM books WHERE curated=1")

    authors = {}
    with open(os.path.join(DATA_DIR, "authors.txt"), encoding="utf-8") as f:
        for i, line in enumerate(l.rstrip("\n") for l in f if l.strip()):
            p = line.split("|")
            key, en, ar, years = p[0], p[1], p[2], p[3]
            tokens = p[4] if len(p) > 4 else ""
            origin = "a" if len(p) > 5 and p[5] == "a" else "w"
            authors[key] = (en, ar, origin)
            conn.execute(
                "INSERT OR REPLACE INTO authors(key,en,ar,years,tokens,origin,ord) VALUES(?,?,?,?,?,?,?)",
                (key, en, ar, years, tokens, origin, i),
            )

    n = 0
    with open(os.path.join(DATA_DIR, "books.txt"), encoding="utf-8") as f:
        for i, line in enumerate(l.rstrip("\n") for l in f if l.strip()):
            key, cat, title, title_ar = line.split("|")
            en, ar, origin = authors[key]
            conn.execute(
                "INSERT INTO books(gid,title,title_ar,author_key,author_en,author_ar,cat,origin,lang,curated,ord,search)"
                " VALUES(NULL,?,?,?,?,?,?,?,?,1,?,?)",
                (title, title_ar, key, en, ar, cat, origin, "ar" if origin == "a" else "en", i,
                 norm(" ".join([title, title_ar, en, ar]))),
            )
            n += 1
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('seed_version',?)", (SEED_VERSION,))
    conn.commit()
    return n