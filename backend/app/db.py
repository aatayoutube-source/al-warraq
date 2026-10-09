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
  ord        INTEGER NOT NULL,
  search     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cover_cache(
  book_id INTEGER PRIMARY KEY,
  url     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_books_cat ON books(cat);
CREATE INDEX IF NOT EXISTS ix_books_author ON books(author_key);
CREATE INDEX IF NOT EXISTS ix_books_ord ON books(ord);
CREATE INDEX IF NOT EXISTS ix_books_curated ON books(curated);
CREATE INDEX IF NOT EXISTS ix_books_lang ON books(lang);
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
    conn.commit()


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
