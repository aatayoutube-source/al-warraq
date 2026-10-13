"""Book cover lookup.

Gutenberg books have a deterministic cover URL that the browser loads directly.
For everything else (and when a Gutenberg cover is missing) the browser asks
GET /api/cover/{id}; we look the book up on Open Library once, cache the answer
in SQLite for every future visitor, and never hit their API faster than ~1/second.
"""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

OL_SEARCH = "https://openlibrary.org/search.json"
UA = "AlWarraqLibrary/1.0 (public-domain book index)"
MIN_GAP = 0.9  # seconds between Open Library requests
LOCK_WAIT = 2.0  # longest a request waits for its turn

_lock = threading.Lock()
_last = [0.0]


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


fetch_json = _http_json  # replaced in tests


def enabled() -> bool:
    return os.environ.get("COVERS_ONLINE", "1") == "1"


def lookup(title: str, author: str) -> str:
    """Return a cover image URL for the book, or '' when Open Library has none."""
    title = re.split(r"[;:]", title or "")[0].strip()[:120]
    if not title:
        return ""
    params = {"title": title, "limit": 5, "fields": "cover_i,title,author_name"}
    if author:
        params["author"] = author
    data = fetch_json(OL_SEARCH + "?" + urllib.parse.urlencode(params))
    for doc in data.get("docs", []):
        cid = doc.get("cover_i")
        if cid:
            return "https://covers.openlibrary.org/b/id/%d-M.jpg" % int(cid)
    return ""


def resolve(conn, book_id: int):
    """Cached cover URL, '' (known: none), or None (book unknown / lookup failed, try again later)."""
    row = conn.execute("SELECT url FROM cover_cache WHERE book_id=?", (book_id,)).fetchone()
    if row:
        return row["url"]
    book = conn.execute("SELECT title, author_en, ws, gid, htid FROM books WHERE id=?", (book_id,)).fetchone()
    if not book or not enabled():
        return None
    if book["ws"] and not book["gid"] and not book["htid"]:
        return ""  # Wikisource texts (mostly single poems) have no printed cover: keep the designed one
    # one lookup at a time, politely spaced; a request that cannot get its turn soon gives up instead of
    # holding a server worker (many such requests at once would otherwise freeze the whole site)
    if not _lock.acquire(timeout=LOCK_WAIT):
        return None
    try:
        row = conn.execute("SELECT url FROM cover_cache WHERE book_id=?", (book_id,)).fetchone()
        if row:
            return row["url"]
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            url = lookup(book["title"], book["author_en"])
        except Exception:
            _last[0] = time.time()
            return None
        _last[0] = time.time()
    finally:
        _lock.release()
    conn.execute("INSERT OR REPLACE INTO cover_cache(book_id,url) VALUES(?,?)", (book_id, url))
    conn.commit()
    return url
