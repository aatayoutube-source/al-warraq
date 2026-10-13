"""Al-Warraq API (FastAPI + SQLite) that also serves the frontend."""
import math
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from urllib.parse import quote, unquote

from . import covers, db, pages, research, security, stats, wikisource
from .catalog import CATEGORIES
from .textnorm import norm

SORTS = {"def", "t", "a"}
_meta_cache = {}  # db path -> (expires, payload)
_fts = {}  # db path -> full-text index available
DENSE = 20000  # a search matching more books than this is answered by an ordered scan, not the index
COUNT_CAP = 10000  # counts read from the table stop here; the site shows "more than 10,000"
MAX_OFFSET = 100_000  # deeper pages cost a long scan and no reader scrolls that far
MAX_WORDS = 8  # words of a search that are used


def _fts_on(conn) -> bool:
    path = db.db_path()
    if not _fts.get(path):
        _fts[path] = db.fts_ready(conn)
    return _fts[path]


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def book_json(r) -> dict:
    return {
        "id": r["id"], "gid": r["gid"], "hid": r["htid"], "ws": r["ws"], "t": r["title"], "ta": r["title_ar"],
        "ak": r["author_key"], "a": r["author_en"], "aa": r["author_ar"],
        "c": r["cat"], "o": r["origin"], "lg": r["lang"],
    }


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        conn = db.connect()
        db.init_db(conn)
        db.seed_curated(conn)
        conn.close()
        yield

    app = FastAPI(title="Al-Warraq Library API", version="2.0.0", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=800)

    @app.middleware("http")
    async def revalidate_site_files(request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    security.install(app)  # rate limits, same-origin POSTs, security headers
    hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
    if hosts:  # e.g. ALLOWED_HOSTS=library.example.com: other Host headers are refused
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.get("/api/health")
    def health(conn=Depends(get_conn)):
        n = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        return {"ok": True, "books": n}

    @app.get("/api/meta")
    def meta(conn=Depends(get_conn)):
        hit = _meta_cache.get(db.db_path())
        if hit and hit[0] > time.time():
            return hit[1]
        payload = build_meta(conn)
        _meta_cache[db.db_path()] = (time.time() + 30, payload)
        return payload

    def build_meta(conn):
        counts = {r["cat"]: r["n"] for r in conn.execute("SELECT cat, COUNT(*) n FROM books GROUP BY cat")}
        cats = [{"key": k, "hue": v["hue"], "en": v["en"], "ar": v["ar"], "count": counts.get(k, 0)} for k, v in CATEGORIES.items()]
        authors = [
            {"key": r["key"], "en": r["en"], "ar": r["ar"], "years": r["years"], "origin": r["origin"],
             "count": r["n"], "cat": r["cat"] or "nov"}
            for r in conn.execute(
                "SELECT a.*, COUNT(b.id) n,"
                " (SELECT cat FROM books WHERE author_key=a.key ORDER BY ord LIMIT 1) cat"
                " FROM authors a JOIN books b ON b.author_key=a.key GROUP BY a.key ORDER BY a.ord"
            )
        ]
        languages = [
            {"code": r["lang"], "count": r["n"]}
            for r in conn.execute("SELECT lang, COUNT(*) n FROM books WHERE lang NOT IN ('', 'und', 'mul', 'zxx') GROUP BY lang ORDER BY n DESC")
        ]
        total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        # Arabic poetry from Wikisource: the poets with the most poems, for the home page
        poets = [
            {"ar": r["author_ar"], "en": r["author_en"], "ak": r["author_key"], "count": r["n"]}
            for r in conn.execute(
                "SELECT author_ar, author_en, author_key, COUNT(*) n FROM books WHERE curated=? AND cat='poe' AND author_ar!=''"
                " GROUP BY author_ar ORDER BY n DESC LIMIT 18", (wikisource.WS_KIND,))
        ]
        poem_total = conn.execute("SELECT COUNT(*) FROM books WHERE curated=? AND cat='poe'", (wikisource.WS_KIND,)).fetchone()[0]
        # every language is counted; the filter menu only lists the 80 biggest
        return {"total": total, "author_total": db.author_total(conn, total), "categories": cats, "authors": authors,
                "lang_total": len(languages), "languages": languages[:80], "poets": poets, "poem_total": poem_total}

    @app.get("/api/books")
    def books(
        q: str = Query("", max_length=200), cat: str = Query("", max_length=10), org: str = Query("", max_length=2),
        ak: str = Query("", max_length=60), au: str = Query("", max_length=150), bl: str = Query("", max_length=12),
        sort: str = "def", ui: str = Query("ar", max_length=5),
        offset: int = Query(0, ge=0, le=MAX_OFFSET), limit: int = Query(60, ge=1, le=200),
        conn=Depends(get_conn),
    ):
        if sort not in SORTS:
            raise HTTPException(400, "bad sort")
        where, args = [], []
        if cat:
            where.append("cat=?"); args.append(cat)
        if org in ("a", "w"):
            where.append("origin=?"); args.append(org)
        if ak:
            where.append("author_key=?"); args.append(ak)
        if au:  # exact author name (poets of the Arabic poetry section)
            where.append("(author_ar=? OR author_en=?)"); args += [au, au]
        if bl:
            where.append("lang=?"); args.append(bl.lower())
        filtered = bool(where)
        words = norm(q).split()[:MAX_WORDS]
        long_words = [w for w in words if len(w) >= 3]  # the trigram index needs 3+ characters per word
        fts = None
        if long_words and _fts_on(conn):
            fts = " AND ".join('"%s"' % w.replace('"', '""') for w in long_words)
            hits = conn.execute("SELECT COUNT(*) FROM (SELECT 1 FROM books_fts WHERE books_fts MATCH ? LIMIT ?)",
                                (fts, DENSE + 1)).fetchone()[0]
            if hits <= DENSE:  # rare words: fetch exactly the matching rows through the index
                where.append("id IN (SELECT rowid FROM books_fts WHERE books_fts MATCH ?)"); args.append(fts)
                words = [w for w in words if len(w) < 3]
            # very common words ("the"): matches are everywhere, so walking the list in order finds a page at once
        for w in words:
            where.append("search LIKE ?"); args.append("%" + w + "%")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        if sort == "t":
            order = "CASE WHEN ?='ar' AND title_ar!='' THEN title_ar ELSE title END COLLATE NOCASE, ord"
            oargs = [ui]
        elif sort == "a":
            order = "CASE WHEN ?='ar' AND author_ar!='' THEN author_ar ELSE author_en END COLLATE NOCASE, ord"
            oargs = [ui]
        else:
            order, oargs = "ord", []
        # counting 500k rows is the slow part: only the first page needs it (the client keeps the total)
        capped = False
        if offset:
            total = None
        elif fts and not filtered and len(long_words) == len(norm(q).split()[:MAX_WORDS]):
            # only a text search (every word 3+ letters): the index alone knows how many books match
            total = conn.execute("SELECT COUNT(*) FROM books_fts WHERE books_fts MATCH ?", (fts,)).fetchone()[0]
        elif words:  # LIKE has to read the table: stop counting once the answer is "a lot"
            total = conn.execute("SELECT COUNT(*) FROM (SELECT 1 FROM books" + clause + " LIMIT ?)", args + [COUNT_CAP + 1]).fetchone()[0]
            capped = total > COUNT_CAP
            total = min(total, COUNT_CAP)
        else:
            total = conn.execute("SELECT COUNT(*) FROM books" + clause, args).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM books" + clause + " ORDER BY " + order + " LIMIT ? OFFSET ?",
            args + oargs + [limit, offset],
        ).fetchall()
        return {"total": total, "capped": capped, "offset": offset, "items": [book_json(r) for r in rows]}

    @app.post("/api/hit")
    def hit(request: Request, conn=Depends(get_conn)):
        """Called once per page load by the site; counts one visitor per day."""
        return {"new": stats.track_visitor(conn, request)}

    @app.get("/api/stats")
    def site_stats(conn=Depends(get_conn)):
        key = ("stats", db.db_path())
        hit_ = _meta_cache.get(key)
        if hit_ and hit_[0] > time.time():
            return hit_[1]
        payload = stats.summary(conn)
        payload["top_books"] = [dict(book_json(r), views=r["_views"], likes=r["_likes"]) for r in stats.top_viewed(conn, 12)]
        payload["top_searches"] = stats.top_searches(conn, 12)
        _meta_cache[key] = (time.time() + 15, payload)
        return payload

    @app.post("/api/track/search")
    def track_search(request: Request, q: str = Query("", max_length=120), conn=Depends(get_conn)):
        return {"logged": stats.log_search(conn, request, q)}

    @app.post("/api/like/{book_id}")
    def like(book_id: int, request: Request, conn=Depends(get_conn)):
        if stats.is_bot(request) or not conn.execute("SELECT 1 FROM books WHERE id=?", (book_id,)).fetchone():
            raise HTTPException(404, "not found")
        liked, total = stats.toggle_like(conn, request, book_id)
        _meta_cache.pop(("stats", db.db_path()), None)
        return {"liked": liked, "likes": total}

    @app.get("/api/shelf")
    def shelf(count: int = Query(12, ge=1, le=60), conn=Depends(get_conn)):
        """Well-known books for the home page. Prefers ones that already have a Gutenberg id (real cover)."""
        rows = conn.execute("SELECT * FROM books WHERE curated=1 ORDER BY (gid IS NULL), ord").fetchall()
        if not rows:
            return {"items": []}
        n = len(rows)
        if rows[0]["gid"]:  # one book per author, so the shelf is not five plays by the same writer
            firsts, rest, seen_a = [], [], set()
            for r in rows:
                (rest if r["author_key"] in seen_a or not r["gid"] else firsts).append(r)
                seen_a.add(r["author_key"])
            pick = (firsts + rest)[:count]
        else:
            pick = [rows[(i * 7 + 3) % n] for i in range(count)]
        seen, out = set(), []
        for r in pick:
            if r["id"] not in seen:
                seen.add(r["id"]); out.append(book_json(r))
        return {"items": out}

    @app.get("/api/cover/{book_id}")
    def cover(book_id: int, conn=Depends(get_conn)):
        """Open Library cover for a book (cached). {"url": null} when unknown or temporarily unavailable."""
        url = covers.resolve(conn, book_id)
        return {"url": url or None}

    @app.get("/api/research")
    def research_links(domain: str = "med", q: str = Query("", max_length=120)):
        if domain not in research.TOPICS:
            raise HTTPException(400, "domain must be 'med' or 'eng'")
        return research.build(domain, q)

    @app.get("/api/papers")
    def research_papers(domain: str = "med", q: str = Query("", max_length=120)):
        """Real open-access papers on the topic (OpenAlex), shown inside the research desk."""
        if domain not in research.TOPICS:
            raise HTTPException(400, "domain must be 'med' or 'eng'")
        try:
            return research.papers(domain, q)
        except Exception:  # OpenAlex unreachable or slow: the desk still shows the source links
            return {"query": q, "translated": False, "total": 0, "items": [], "error": True}

    @app.get("/robots.txt", include_in_schema=False)
    def robots(request: Request):
        return PlainTextResponse("User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: %s/sitemap.xml\n" % pages.site_base(request))

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap(request: Request, conn=Depends(get_conn)):
        return Response(pages.sitemap_index(conn, pages.site_base(request)), media_type="application/xml")

    @app.get("/sitemap-main.xml", include_in_schema=False)
    def sitemap_main(request: Request):
        return Response(pages.sitemap_main(pages.site_base(request)), media_type="application/xml")

    @app.get("/sitemap-books-{page}.xml", include_in_schema=False)
    def sitemap_books(page: int, request: Request, conn=Depends(get_conn)):
        pages_n = math.ceil(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] / pages.SITEMAP_PAGE)
        body = pages.sitemap_books(conn, pages.site_base(request), page) if 1 <= page <= pages_n else None
        if body is None:
            return PlainTextResponse("not found", status_code=404)
        return Response(body, media_type="application/xml")

    def _book_page(book_id: int, slug: str, request: Request, lang: str, conn):
        row = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        if not row:
            return HTMLResponse(pages.not_found_html(lang if lang in ("ar", "en") else "en"), status_code=404)
        canon = pages.canonical_path(row)
        if "/book/%d/%s" % (book_id, quote(unquote(slug))) != canon if slug else True:
            target = canon + (("?lang=" + lang) if lang in ("ar", "en") else "")
            return RedirectResponse(target, status_code=301)
        stats.track_visitor(conn, request)
        stats.add_view(conn, request, book_id)
        nonce = secrets.token_urlsafe(16)  # only this page's own scripts may run
        return HTMLResponse(pages.render_book(conn, row, pages.site_base(request), lang,
                                              stats.book_numbers(conn, book_id), stats.has_liked(conn, request, book_id), nonce),
                            headers={"Content-Security-Policy": security.BOOK_CSP.format(nonce=nonce)})

    @app.get("/book/{book_id}", include_in_schema=False)
    def book_short(book_id: int, request: Request, lang: str = "", conn=Depends(get_conn)):
        return _book_page(book_id, "", request, lang, conn)

    @app.get("/book/{book_id}/{slug}", include_in_schema=False)
    def book_full(book_id: int, slug: str, request: Request, lang: str = Query("", max_length=5), conn=Depends(get_conn)):
        return _book_page(book_id, slug, request, lang, conn)

    @app.exception_handler(HTTPException)
    async def http_error(_req, exc):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    frontend = os.environ.get("FRONTEND_DIR") or os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
    if os.path.isdir(frontend):
        app.mount("/", StaticFiles(directory=frontend, html=True), name="site")
    return app


app = create_app()