"""Anonymous site statistics: visitors, searches, book views and likes.

Privacy: no IP address or user agent is stored. A visitor is a salted hash (kept only to avoid
counting the same person twice per day / liking twice) and old daily hashes are deleted.
"""
import hashlib
import os
import re
import secrets
import time

from .textnorm import norm

BOT = re.compile(r"bot|crawl|spider|slurp|bing|facebookexternalhit|preview|monitor|uptime|curl|wget|python-requests|headless", re.I)
KEEP_DAYS = 3


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _salt(conn) -> str:
    r = conn.execute("SELECT value FROM meta WHERE key='salt'").fetchone()
    if r:
        return r["value"]
    s = secrets.token_hex(16)
    conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('salt',?)", (s,))
    conn.commit()
    return conn.execute("SELECT value FROM meta WHERE key='salt'").fetchone()["value"]


def is_bot(request) -> bool:
    return bool(BOT.search(request.headers.get("user-agent", "") or ""))


def visitor_id(conn, request) -> str:
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    return hashlib.sha256((_salt(conn) + "|" + ip + "|" + ua).encode()).hexdigest()[:24]


def _bump(conn, key: str, by: int = 1) -> None:
    conn.execute("INSERT INTO site_stats(key,n) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET n=n+?", (key, by, by))


def track_visitor(conn, request) -> bool:
    """Counts one visit per visitor per day. Returns True when it was a new visitor today."""
    if is_bot(request):
        return False
    day = _today()
    cur = conn.execute("INSERT OR IGNORE INTO daily_visitors(day,visitor) VALUES(?,?)", (day, visitor_id(conn, request)))
    new = cur.rowcount > 0
    if new:
        _bump(conn, "visitors")
        conn.execute("DELETE FROM daily_visitors WHERE day < date(?, ?)", (day, "-%d day" % KEEP_DAYS))
    conn.commit()
    return new


def add_view(conn, request, book_id: int) -> None:
    if is_bot(request):
        return
    conn.execute("INSERT INTO book_stats(book_id,views) VALUES(?,1) ON CONFLICT(book_id) DO UPDATE SET views=views+1", (book_id,))
    _bump(conn, "views")
    conn.commit()


def log_search(conn, request, q: str) -> bool:
    q = " ".join(norm(q).split())[:80]
    if len(q) < 2 or is_bot(request):
        return False
    conn.execute("INSERT INTO searches(q,n,last) VALUES(?,1,?) ON CONFLICT(q) DO UPDATE SET n=n+1, last=excluded.last",
                 (q, time.strftime("%Y-%m-%d", time.gmtime())))
    _bump(conn, "searches")
    # keep the table small: drop rarely used queries when it grows
    if conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0] > 20000:
        conn.execute("DELETE FROM searches WHERE n=1 AND q IN (SELECT q FROM searches WHERE n=1 ORDER BY last LIMIT 5000)")
    conn.commit()
    return True


def book_numbers(conn, book_id: int):
    r = conn.execute("SELECT views, likes FROM book_stats WHERE book_id=?", (book_id,)).fetchone()
    return (r["views"], r["likes"]) if r else (0, 0)


def has_liked(conn, request, book_id: int) -> bool:
    return bool(conn.execute("SELECT 1 FROM book_likes WHERE book_id=? AND visitor=?", (book_id, visitor_id(conn, request))).fetchone())


def toggle_like(conn, request, book_id: int):
    """Returns (liked, total_likes)."""
    v = visitor_id(conn, request)
    if conn.execute("SELECT 1 FROM book_likes WHERE book_id=? AND visitor=?", (book_id, v)).fetchone():
        conn.execute("DELETE FROM book_likes WHERE book_id=? AND visitor=?", (book_id, v))
        conn.execute("UPDATE book_stats SET likes=MAX(likes-1,0) WHERE book_id=?", (book_id,))
        _bump(conn, "likes", -1)
        liked = False
    else:
        conn.execute("INSERT INTO book_likes(book_id,visitor) VALUES(?,?)", (book_id, v))
        conn.execute("INSERT INTO book_stats(book_id,likes) VALUES(?,1) ON CONFLICT(book_id) DO UPDATE SET likes=likes+1", (book_id,))
        _bump(conn, "likes")
        liked = True
    conn.commit()
    return liked, book_numbers(conn, book_id)[1]


def summary(conn) -> dict:
    n = {r["key"]: r["n"] for r in conn.execute("SELECT key, n FROM site_stats")}
    today = conn.execute("SELECT COUNT(*) FROM daily_visitors WHERE day=?", (_today(),)).fetchone()[0]
    return {
        "books": conn.execute("SELECT COUNT(*) FROM books").fetchone()[0],
        "visitors": n.get("visitors", 0), "visitors_today": today,
        "searches": n.get("searches", 0), "views": n.get("views", 0), "likes": max(n.get("likes", 0), 0),
    }


def top_viewed(conn, limit: int = 12):
    return conn.execute(
        "SELECT b.*, s.views AS _views, s.likes AS _likes FROM book_stats s JOIN books b ON b.id=s.book_id "
        "WHERE s.views>0 ORDER BY s.views DESC, s.likes DESC LIMIT ?", (limit,)).fetchall()


def top_searches(conn, limit: int = 12):
    return [r["q"] for r in conn.execute("SELECT q FROM searches ORDER BY n DESC, last DESC LIMIT ?", (limit,))]