"""Al-Warraq API (FastAPI + SQLite) that also serves the frontend."""
import math
import mimetypes
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from urllib.parse import quote, unquote

from . import covers, db, legal, modern, pages, ranking, research, security, seo, stats, wikisource
from .catalog import ARABIC_CAT, CATEGORIES
from .textnorm import norm

mimetypes.add_type("application/manifest+json", ".webmanifest")  # not known to every OS
SORTS = {"def", "t", "a"}
_meta_cache = {}  # db path -> (expires, payload)
_fts = {}  # db path -> full-text index available
COUNT_CAP = 10000  # counts stop here; the site shows "more than 10,000"
DENSE = COUNT_CAP  # a search matching more books than this is answered by an ordered scan, not the index
MAX_OFFSET = 100_000  # deeper pages cost a long scan and no reader scrolls that far
MAX_WORDS = 8  # words of a search that are used


def _fts_on(conn) -> bool:
    path = db.db_path()
    if not _fts.get(path):
        _fts[path] = db.fts_ready(conn)
    return _fts[path]


def _fts_count(conn, words, cap: int) -> int:
    """Books holding every word (substring), counted through the index up to cap."""
    like = " AND ".join("search LIKE ?" for _ in words)
    return conn.execute("SELECT COUNT(*) FROM (SELECT 1 FROM books_fts WHERE " + like + " LIMIT ?)",
                        ["%" + w + "%" for w in words] + [cap]).fetchone()[0]


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
        "x": r["ext"], "k": r["curated"],  # Safahat / Open Library: the book's id there (modern.py)
    }


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        conn = db.connect()
        db.init_db(conn)
        db.seed_curated(conn)
        db.prune_unreadable(conn)
        conn.close()
        yield

    # the interactive API docs (/docs, /redoc, /openapi.json) are a map of every endpoint: not on the public site
    # unless API_DOCS=1 (for development)
    docs = os.environ.get("API_DOCS", "") == "1"
    app = FastAPI(title="Al-Warraq Library API", version="2.0.0", lifespan=lifespan, docs_url="/docs" if docs else None,
                  redoc_url="/redoc" if docs else None, openapi_url="/openapi.json" if docs else None)
    app.add_middleware(GZipMiddleware, minimum_size=800)

    @app.middleware("http")
    async def revalidate_site_files(request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-cache")
        else:  # crawlers may read the API (the home page needs it) but must not list it in results
            response.headers.setdefault("X-Robots-Tag", "noindex")
        return response

    security.install(app)  # rate limits, same-origin POSTs, security headers
    hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
    if hosts:  # e.g. ALLOWED_HOSTS=library.example.com: other Host headers are refused
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.get("/api/health")
    def health(conn=Depends(get_conn)):
        conn.execute("SELECT 1 FROM books LIMIT 1").fetchone()  # the database answers; nothing else is told
        return {"ok": True}

    @app.get("/api/meta")
    def meta(conn=Depends(get_conn)):
        hit = _meta_cache.get(db.db_path())
        if hit and hit[0] > time.time():
            return hit[1]
        payload = build_meta(conn)
        _meta_cache[db.db_path()] = (time.time() + 30, payload)
        return payload

    def build_meta(conn):
        # a single poem (Wikisource) is counted as a poem, never as a book
        ws = wikisource.WS_KIND
        # every row per category straight from the (cat, ord) index, minus the poems (few rows, their own index):
        # filtering the big count on "curated" would read the whole table instead
        poems = {r["cat"]: r["n"] for r in conn.execute("SELECT cat, COUNT(*) n FROM books WHERE curated=? GROUP BY cat", (ws,))}
        counts = {r["cat"]: r["n"] - poems.get(r["cat"], 0) for r in conn.execute("SELECT cat, COUNT(*) n FROM books GROUP BY cat")}
        all_poems = sum(poems.values())
        poems[ARABIC_CAT] = all_poems  # every one of them is Arabic
        counts[ARABIC_CAT] = conn.execute("SELECT COUNT(*) FROM books WHERE lang='ar'").fetchone()[0] - all_poems
        cats = [{"key": k, "hue": v["hue"], "en": v["en"], "ar": v["ar"], "count": counts.get(k, 0), "poems": poems.get(k, 0)}
                for k, v in CATEGORIES.items()]
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
        total = db.book_total(conn)  # books only: poems are counted apart
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
        if cat == ARABIC_CAT:  # every Arabic book, whatever its topic
            where.append("lang='ar'")
        elif cat:
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
        query = " ".join(words)
        long_words = [w for w in words if len(w) >= 3]  # the trigram index needs 3+ characters per word
        only_text = not filtered and len(long_words) == len(words)  # a plain search, every word 3+ letters
        hits = None  # how many books match, when the index could tell
        fts_where, fts_args = "", []
        dense = rank = False
        if long_words and _fts_on(conn):
            n = _fts_count(conn, long_words, DENSE + 1)
            if n <= DENSE:  # rare words: fetch exactly the matching rows through the index
                hits = n
                rank = sort == "def"  # few enough to put the best matches first
                # almost nothing found: a rare word may be misspelt by a letter, or carry an article the title lacks
                wide = {}
                if rank and n < ranking.FEW:
                    for w in long_words:
                        if (len(wide) < ranking.MAX_WIDE and len(w) <= ranking.MAX_WIDE_LEN
                                and _fts_count(conn, [w], ranking.FEW) < ranking.FEW):
                            wide[w] = [w] + ranking.variants(w)
                plain = [w for w in long_words if w not in wide]
                parts = []
                for pats in wide.values():
                    parts.append("id IN (" + " UNION ".join("SELECT rowid FROM books_fts WHERE search LIKE ?" for _ in pats) + ")")
                    fts_args += ["%" + p + "%" for p in pats]
                if wide:  # the rare word's few books lead; the other words are checked on them alone ("the" is everywhere)
                    parts += ["search LIKE ?" for _ in plain]
                elif plain:
                    parts.append("id IN (SELECT rowid FROM books_fts WHERE " + " AND ".join("search LIKE ?" for _ in plain) + ")")
                fts_args += ["%" + w + "%" for w in plain]
                fts_where = " AND ".join(parts)
                where.append(fts_where); args += fts_args
                words = [w for w in words if len(w) < 3]
            else:  # very common words ("the"): matches are everywhere, so walking the list in order finds a page at once
                dense = True
        for w in words:
            where.append("search LIKE ?"); args.append("%" + w + "%")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        if rank:  # every match is known: the best ones first, the order kept for the next pages
            ids, poems, near, capped = ranking.ranked(conn, (db.db_path(), clause, tuple(args), query), clause, args,
                                                      query, long_words, wide)
            page = list(ids[offset:offset + limit])
            got = {r["id"]: r for r in conn.execute("SELECT * FROM books WHERE id IN (%s)" % ",".join("?" * len(page)), page)} if page else {}
            first = not offset
            return {"total": (COUNT_CAP if capped else len(ids)) if first else None, "capped": capped,
                    "poems": poems if first and not capped else None, "near": near if first else None, "offset": offset,
                    "items": [book_json(got[i]) for i in page if i in got]}
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
        elif only_text and hits is not None:  # the index already counted them
            total = hits
        elif only_text and dense:  # more than DENSE books: "more than 10,000"
            total, capped = COUNT_CAP, True
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
        # how many of them are single poems, told apart when that is cheap. Every poem is Arabic, in "poe", by an
        # Arab author: those filters either rule poems out or say nothing, so the table itself is never read
        poems = None
        ws = wikisource.WS_KIND
        if total is not None and not capped and not words:
            if (cat and cat not in (ARABIC_CAT, "poe")) or (bl and bl.lower() != "ar") or org == "w":
                poems = 0
            elif au:  # one poet of the poetry section: the rows were just read for the total
                poems = conn.execute("SELECT COUNT(*) FROM books" + clause + " AND curated=?", args + [ws]).fetchone()[0]
            else:
                pw, pa = ["curated=?"], [ws]
                if ak:
                    pw.append("author_key=?"); pa.append(ak)
                if fts_where:
                    pw.append(fts_where); pa += fts_args
                poems = conn.execute("SELECT COUNT(*) FROM books WHERE " + " AND ".join(pw), pa).fetchone()[0]
        return {"total": total, "capped": capped, "poems": poems, "offset": offset, "items": [book_json(r) for r in rows]}

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

    @app.get("/ads.txt", include_in_schema=False)
    def ads_txt():
        return PlainTextResponse(pages.ads_txt())

    @app.get("/robots.txt", include_in_schema=False)
    def robots(request: Request):
        return PlainTextResponse(seo.robots_txt(pages.site_base(request)))

    frontend = os.environ.get("FRONTEND_DIR") or os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

    @app.get("/", include_in_schema=False)
    def home(request: Request, lang: str = Query("", max_length=5)):
        """index.html plus what only the server knows: canonical links, structured data, verification tags."""
        if not os.path.isfile(os.path.join(frontend, "index.html")):
            raise HTTPException(404, "not found")
        return HTMLResponse(seo.home_html(frontend, pages.site_base(request), "en" if lang == "en" else "ar"))

    @app.get("/category/{key}", include_in_schema=False)
    def category(key: str, request: Request, lang: str = Query("", max_length=5), page: int = Query(1, ge=1, le=seo.MAX_PAGES),
                 conn=Depends(get_conn)):
        body = seo.category_page(conn, key, pages.site_base(request), "en" if lang == "en" else "ar", page)
        return HTMLResponse(body) if body else HTMLResponse(pages.not_found_html("en" if lang == "en" else "ar"), status_code=404)

    @app.get("/author/{key}", include_in_schema=False)
    def author(key: str, request: Request, lang: str = Query("", max_length=5), page: int = Query(1, ge=1, le=seo.MAX_PAGES),
               conn=Depends(get_conn)):
        body = seo.author_page(conn, key, pages.site_base(request), "en" if lang == "en" else "ar", page)
        return HTMLResponse(body) if body else HTMLResponse(pages.not_found_html("en" if lang == "en" else "ar"), status_code=404)

    # ---------- about, privacy, terms, contact (legal.py) ----------
    def _ui(lang):
        return "en" if lang == "en" else "ar"

    @app.get("/about", include_in_schema=False)
    def about(request: Request, lang: str = Query("", max_length=5), conn=Depends(get_conn)):
        m = meta(conn)
        n = {"books": m["total"], "poems": m["poem_total"], "authors": m["author_total"], "langs": m["lang_total"],
             "cats": sum(1 for c in m["categories"] if c["count"]),
             "modern": conn.execute("SELECT COUNT(*) FROM books WHERE curated IN (?, ?)", modern.KINDS).fetchone()[0]}
        return HTMLResponse(legal.page_html("about", pages.site_base(request), _ui(lang), numbers=n))

    @app.get("/privacy", include_in_schema=False)
    def privacy(request: Request, lang: str = Query("", max_length=5)):
        return HTMLResponse(legal.page_html("privacy", pages.site_base(request), _ui(lang)))

    @app.get("/terms", include_in_schema=False)
    def terms(request: Request, lang: str = Query("", max_length=5)):
        return HTMLResponse(legal.page_html("terms", pages.site_base(request), _ui(lang)))

    @app.get("/contact", include_in_schema=False)
    def contact(request: Request, lang: str = Query("", max_length=5), sent: int = Query(0, ge=0, le=1), conn=Depends(get_conn)):
        return HTMLResponse(legal.page_html("contact", pages.site_base(request), _ui(lang), conn=conn, sent=bool(sent)))

    @app.post("/contact", include_in_schema=False)
    async def contact_send(request: Request, lang: str = Query("", max_length=5), conn=Depends(get_conn)):
        ui = _ui(lang)
        if int(request.headers.get("content-length") or 0) > 20000:
            return PlainTextResponse("message too large", status_code=413)
        ok, err, values = legal.submit(conn, request, legal.parse_form(await request.body()), ui)
        if ok:  # post/redirect/get: reloading the thank-you page does not send the message again
            return RedirectResponse(legal.link("contact", ui) + ("&" if ui == "en" else "?") + "sent=1", status_code=303)
        return HTMLResponse(legal.page_html("contact", pages.site_base(request), ui, conn=conn, values=values, error=err),
                            status_code=400)

    @app.get("/admin/messages", include_in_schema=False)
    def admin_messages(request: Request, conn=Depends(get_conn)):
        if not legal.admin_password():  # no password set: the page does not exist
            return HTMLResponse(pages.not_found_html("ar"), status_code=404)
        if not legal.admin_ok(request):
            return PlainTextResponse("login required", status_code=401,
                                     headers={"WWW-Authenticate": 'Basic realm="warraq", charset="UTF-8"'})
        return HTMLResponse(legal.admin_html(conn), headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})

    indexnow_key = os.environ.get("INDEXNOW_KEY", "").strip()
    if indexnow_key:  # IndexNow checks that the key file is served by the site itself
        @app.get("/%s.txt" % indexnow_key, include_in_schema=False)
        def indexnow_key_file():
            return PlainTextResponse(indexnow_key)

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap(request: Request, conn=Depends(get_conn)):
        return Response(pages.sitemap_index(conn, pages.site_base(request)), media_type="application/xml")

    @app.get("/sitemap-main.xml", include_in_schema=False)
    def sitemap_main(request: Request, conn=Depends(get_conn)):
        return Response(seo.sitemap_main(conn, pages.site_base(request)), media_type="application/xml")

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
            return HTMLResponse(pages.not_found_html("en" if lang == "en" else "ar"), status_code=404)
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

    def _page_request(request) -> bool:  # a person's browser asking for a page, not the site's own API
        return request.method in ("GET", "HEAD") and not request.url.path.startswith("/api/")

    @app.exception_handler(StarletteHTTPException)
    async def missing_page(request, exc):
        """Unknown addresses (the static files answer them) get the designed 404 page; the API keeps JSON."""
        if exc.status_code == 404 and _page_request(request):
            return HTMLResponse(pages.not_found_html("en" if request.query_params.get("lang") == "en" else "ar"), status_code=404)
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def bad_address(request, exc):
        """/book/abc or ?page=0 on a page: that page does not exist. The API still explains what was wrong."""
        if _page_request(request):
            return HTMLResponse(pages.not_found_html("en" if request.query_params.get("lang") == "en" else "ar"), status_code=404)
        return JSONResponse({"detail": jsonable_encoder(exc.errors())}, status_code=422)

    if os.path.isdir(frontend):
        app.mount("/", StaticFiles(directory=frontend, html=True), name="site")
    return app


app = create_app()