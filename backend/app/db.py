"""SQLite storage: schema, connection helper and the curated seed.

Two kinds of data: the catalogue (books, authors; big and the same for everyone) and the site's own
numbers (visitors, views, likes, searches; small and precious). By default both live in one file.
With STATS_DB set, the numbers go to their own small file, attached as "st": the catalogue can then be
re-downloaded on every start (DB_URL) while the counters stay on a small persistent disk.
"""
import gzip
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.request

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
  ext        TEXT,
  info       TEXT,
  ord        INTEGER NOT NULL,
  search     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cover_cache(
  book_id INTEGER PRIMARY KEY,
  url     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_books_cat_ord ON books(cat, ord);   -- a category page comes out already in order
CREATE INDEX IF NOT EXISTS ix_books_lang_ord ON books(lang, ord);
CREATE INDEX IF NOT EXISTS ix_books_author ON books(author_key);
CREATE INDEX IF NOT EXISTS ix_books_ord ON books(ord);
CREATE INDEX IF NOT EXISTS ix_books_curated_cat ON books(curated, cat);  -- a source's books per category, from the index alone
"""

STATS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stats_meta(
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS contact_messages(
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      INTEGER NOT NULL,
  name    TEXT NOT NULL,
  email   TEXT NOT NULL,
  topic   TEXT NOT NULL,
  message TEXT NOT NULL,
  lang    TEXT NOT NULL DEFAULT 'ar',
  visitor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_contact_visitor ON contact_messages(visitor, ts);
"""
STATS_TABLES = ("stats_meta", "site_stats", "daily_visitors", "daily_views", "search_votes", "period_visitors",
                "book_stats", "book_likes", "searches", "contact_messages")


_usable = {}  # configured path -> path actually used


def usable_path(path: str, what: str = "database") -> str:
    """The configured file if its folder can be created and written, otherwise a file of the same name in the
    system's temporary folder, with a warning: a mistyped path must not keep the whole site from starting."""
    if path in _usable:
        return _usable[path]
    folder = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(folder, exist_ok=True)
        ok = os.access(folder, os.W_OK)
    except OSError:
        ok = False
    use = path
    if not ok:
        use = os.path.join(tempfile.gettempdir(), "warraq", os.path.basename(path) or "warraq.db")
        os.makedirs(os.path.dirname(use), exist_ok=True)
        print("WARNING: cannot write the %s at %s (check WARRAQ_DB / STATS_DB); using %s instead"
              % (what, os.path.abspath(path), use), file=sys.stderr)
    _usable[path] = use
    return use


def db_path() -> str:
    configured = os.environ.get("WARRAQ_DB", "").strip() or os.path.join(os.path.dirname(__file__), "..", "data", "warraq.db")
    return usable_path(configured, "books database")


def connect(path: str = "") -> sqlite3.Connection:
    path = path or db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    stats = os.environ.get("STATS_DB", "").strip()
    if stats:  # the site's counters in their own file (see the module doc)
        conn.execute("ATTACH DATABASE ? AS st", (usable_path(stats, "statistics database"),))
        conn.execute("PRAGMA st.journal_mode=WAL")
    return conn


def _stats_attached(conn) -> bool:
    return any(r[1] == "st" for r in conn.execute("PRAGMA database_list"))


def init_stats(conn: sqlite3.Connection) -> None:
    if not _stats_attached(conn):
        conn.executescript(STATS_SCHEMA)
        return
    conn.executescript(STATS_SCHEMA.replace("CREATE TABLE IF NOT EXISTS ", "CREATE TABLE IF NOT EXISTS st.")
                       .replace("CREATE INDEX IF NOT EXISTS ", "CREATE INDEX IF NOT EXISTS st."))
    # numbers kept in the catalogue file by an older setup move to the stats file (unqualified names would find them first)
    for t in STATS_TABLES:
        if conn.execute("SELECT 1 FROM main.sqlite_master WHERE type='table' AND name=?", (t,)).fetchone():
            conn.execute("INSERT OR IGNORE INTO st.%s SELECT * FROM main.%s" % (t, t))
            conn.execute("DROP TABLE main.%s" % t)
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    init_stats(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(books)")}
    if "htid" not in cols:  # database created by an older version
        conn.execute("ALTER TABLE books ADD COLUMN htid TEXT")
    if "ws" not in cols:  # Arabic Wikisource page name (added with the Wikisource import)
        conn.execute("ALTER TABLE books ADD COLUMN ws TEXT")
    if "ext" not in cols:  # the book's id at Safahat or Open Library (modern.py)
        conn.execute("ALTER TABLE books ADD COLUMN ext TEXT")
    if "info" not in cols:  # publisher, year, pages, subjects (JSON) for those books
        conn.execute("ALTER TABLE books ADD COLUMN info TEXT")
    # (cat) and (lang) alone are covered by the (cat, ord) and (lang, ord) indexes: about 30 MB saved
    conn.execute("DROP INDEX IF EXISTS ix_books_curated")  # (curated, cat) above serves it
    conn.execute("DROP INDEX IF EXISTS ix_books_cat")
    conn.execute("DROP INDEX IF EXISTS ix_books_lang")
    conn.commit()
    fix_author_names(conn)
    seed_period_visitors(conn)
    ensure_fts(conn)


def seed_period_visitors(conn: sqlite3.Connection) -> None:
    """Once: visitors already counted in the last days also count for this month and this year."""
    if conn.execute("SELECT 1 FROM stats_meta WHERE key='periods_seeded'").fetchone():
        return
    from .stats import _today
    day = _today()
    for period in (day[:7], day[:4]):
        conn.execute("INSERT OR IGNORE INTO period_visitors(period,visitor) SELECT ?, visitor FROM daily_visitors WHERE day LIKE ?",
                     (period, period + "%"))
        n = conn.execute("SELECT COUNT(*) FROM period_visitors WHERE period=?", (period,)).fetchone()[0]
        conn.execute("INSERT INTO site_stats(key,n) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET n=MAX(n, excluded.n)",
                     ("visitors:" + period, n))
    conn.execute("INSERT OR REPLACE INTO stats_meta(key,value) VALUES('periods_seeded','1')")
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


def book_total(conn: sqlite3.Connection) -> int:
    """Books in the catalogue: single poems (Wikisource, curated=3) are poems, not books."""
    return (conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
            - conn.execute("SELECT COUNT(*) FROM books WHERE curated=3").fetchone()[0])


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


# a book with none of these has no page to read it on: the site could only send people searching elsewhere
UNREADABLE = "(gid IS NULL OR gid=0) AND (htid IS NULL OR htid='') AND (ws IS NULL OR ws='') AND (ext IS NULL OR ext='')"


def prune_unreadable(conn: sqlite3.Connection) -> int:
    """Removes the books the site cannot open (hand-picked titles that no import could match to a copy), and the
    books of Arabic Wikisource, whose pages are mostly empty shells (its single poems are complete and stay).
    Only once the catalogue has been imported: before that every hand-picked book is still waiting for its link."""
    if not conn.execute("SELECT 1 FROM books WHERE curated<>1 LIMIT 1").fetchone():
        return 0
    conn.execute("UPDATE books SET ws=NULL WHERE ws<>'' AND curated<>3")  # hand-picked books linked to a Wikisource page
    ids = [r[0] for r in conn.execute("SELECT id FROM books WHERE " + UNREADABLE + " OR (curated=3 AND cat<>'poe')")]
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        marks = ",".join("?" * len(chunk))
        for table in ("cover_cache", "book_stats", "book_likes"):
            conn.execute("DELETE FROM %s WHERE book_id IN (%s)" % (table, marks), chunk)
        conn.execute("DELETE FROM books WHERE id IN (%s)" % marks, chunk)
    conn.commit()
    return len(ids)


# ---------- a ready-made catalogue (DB_URL): the whole library in a minute instead of a long import ----------

def needs_download(path: str, url: str) -> bool:
    """True when the file is missing or was not made from this URL."""
    if not url:
        return False
    if not os.path.exists(path):
        return True
    try:
        c = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        row = c.execute("SELECT value FROM meta WHERE key='books_url'").fetchone()
        c.close()
        return not row or row[0] != url
    except sqlite3.Error:
        return True


def download_books(url: str, path: str, log=print) -> None:
    """Stream the catalogue (plain or .gz) to disk 4 MB at a time and put it in place of the old one."""
    part = path + ".part"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    for suffix in ("", "-wal", "-shm"):  # free the space first: small disks cannot hold the old and the new file
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    req = urllib.request.Request(url, headers={"User-Agent": "AlWarraqLibrary/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(part, "wb") as f:
            src = gzip.GzipFile(fileobj=r) if url.split("?")[0].endswith(".gz") else r
            done, step = 0, 100 * 2 ** 20
            while True:
                chunk = src.read(4 * 2 ** 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if done >= step:
                    log("  %d MB" % (done // 2 ** 20))
                    step += 100 * 2 ** 20
        with open(part, "rb") as f:
            if f.read(16) != b"SQLite format 3\x00":
                raise IOError("the downloaded file is not an SQLite database")
        os.replace(part, path)
    finally:
        if os.path.exists(part):
            os.remove(part)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('books_url',?)", (url,))
    c.commit()
    c.close()
