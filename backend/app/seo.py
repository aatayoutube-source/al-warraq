"""Search-engine side of the site: crawlable category and author pages, the home page's head tags,
robots.txt, the main sitemap, and IndexNow (instant indexing on Bing, Yandex, Seznam...).

    python -m app.seo indexnow            # tell IndexNow about the home, category and author pages
    python -m app.seo indexnow --books    # ... and every book page as well (in batches of 10,000)

Settings (environment): SITE_URL (the public address, needed for absolute links), INDEXNOW_KEY,
GOOGLE_SITE_VERIFICATION, BING_SITE_VERIFICATION, YANDEX_VERIFICATION.
"""
import json
import math
import os
import sys
import urllib.request
from urllib.parse import quote

from . import legal
from .catalog import CATEGORIES
from .pages import BRAND, CSS, LOGO_SVG, SEARCH_ICON, T, _authors, book_author, book_title, canonical_path, esc, legal_links

PER_PAGE = 60
MAX_PAGES = 200  # category pages go this deep; the sitemaps list every single book anyway

S = {
    "ar": {
        "cat_h": "كتب {c} مجانية", "cat_d": "{n} كتاباً مجانياً في تصنيف «{c}» من الكتب التي سقط عنها حق النشر، تقرؤها كاملة من مصادرها المفتوحة.",
        "auth_h": "كتب {a}", "auth_d": "{n} من أعمال {a} مجانية في الملك العام، تقرؤها كاملة من مصادرها المفتوحة.",
        "cats": "التصنيفات", "authors": "مؤلفون مشهورون", "prev": "السابق", "next": "التالي", "page": "صفحة {p}",
        "open": "تصفّح في المكتبة", "home_t": "مكتبة الوراق | كتب مجانية وقصائد عربية في الملك العام",
    },
    "en": {
        "cat_h": "Free {c} books", "cat_d": "{n} free public-domain books in “{c}”, readable in full at their open sources.",
        "auth_h": "Books by {a}", "auth_d": "{n} public-domain works by {a}, free to read at their open sources.",
        "cats": "Categories", "authors": "Famous authors", "prev": "Previous", "next": "Next", "page": "page {p}",
        "open": "Browse in the library", "home_t": "Al-Warraq Library | Free public-domain books and Arabic poetry",
    },
}

EXTRA_CSS = """
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 4px}
.chips a{background:var(--card);border:1.5px solid var(--line);border-radius:12px;padding:5px 14px;text-decoration:none;color:var(--ink);font-size:.9rem}
.chips a:hover,.chips a[aria-current]{border-color:var(--brand-2);color:var(--brand)}
.pager{display:flex;justify-content:space-between;gap:12px;margin:22px 0}
.pager a{background:var(--card);border:1.5px solid var(--line);border-radius:12px;padding:8px 18px;text-decoration:none}
h1{margin-top:22px}
"""


def verification_meta() -> str:
    tags = []
    for env, name in (("GOOGLE_SITE_VERIFICATION", "google-site-verification"), ("BING_SITE_VERIFICATION", "msvalidate.01"),
                      ("YANDEX_VERIFICATION", "yandex-verification")):
        if os.environ.get(env):
            tags.append('<meta name="%s" content="%s">' % (name, esc(os.environ[env])))
    return "\n".join(tags)


def _ld(obj) -> str:
    return '<script type="application/ld+json">%s</script>' % json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _alternates(base: str, path: str, extra: str = "") -> str:
    """hreflang links: Arabic is the main language of the site, English is ?lang=en."""
    ar = base + path + (("?" + extra) if extra else "")
    en = base + path + "?lang=en" + (("&" + extra) if extra else "")
    return ('<link rel="alternate" hreflang="ar" href="%s">\n<link rel="alternate" hreflang="en" href="%s">\n'
            '<link rel="alternate" hreflang="x-default" href="%s">' % (esc(ar), esc(en), esc(ar)))


# ---------- the home page: the same file, with the tags only the server can know ----------

_home = {"mtime": 0, "html": ""}


def home_html(frontend_dir: str, base: str, ui: str = "ar") -> str:
    path = os.path.join(frontend_dir, "index.html")
    mtime = os.path.getmtime(path)
    if mtime != _home["mtime"]:
        with open(path, encoding="utf-8") as f:
            _home.update(mtime=mtime, html=f.read())
    canon = base + ("/?lang=en" if ui == "en" else "/")
    head = "\n".join([
        '<link rel="canonical" href="%s">' % esc(canon),
        _alternates(base, "/"),
        '<meta property="og:url" content="%s">' % esc(canon),
        '<meta property="og:image" content="%s/og-image.png">' % esc(base),
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">',
        '<meta property="og:locale" content="%s">' % ("en_US" if ui == "en" else "ar_AR"),
        '<meta name="twitter:image" content="%s/og-image.png">' % esc(base),
        verification_meta(),
        _ld({"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "@id": base + "/#site", "url": base + "/", "name": BRAND["ar"], "alternateName": BRAND["en"],
             "inLanguage": ["ar", "en"], "publisher": {"@id": base + "/#org"},
             "potentialAction": {"@type": "SearchAction", "target": base + "/?q={search_term_string}",
                                 "query-input": "required name=search_term_string"}},
            {"@type": "Organization", "@id": base + "/#org", "name": BRAND["ar"], "alternateName": BRAND["en"], "url": base + "/",
             "logo": base + "/icon-512.png"},
        ]}),
    ])
    links = " ".join('<a href="/category/%s">%s</a>' % (k, esc(v["ar"])) for k, v in CATEGORIES.items())
    return _home["html"].replace("<!--SEO:HEAD-->", head).replace("<!--SEO:CATS-->", links)


# ---------- category and author pages (plain HTML: every crawler can read and follow them) ----------

def _shell(ui, base, path, title, desc, body, ld, page=1, extra_q="", extra_css=""):
    t = T[ui]
    canon = base + path + "?" + "&".join(x for x in (("lang=en" if ui == "en" else ""), ("page=%d" % page if page > 1 else "")) if x)
    canon = canon.rstrip("?")
    other = "en" if ui == "ar" else "ar"
    return """<!doctype html>
<html lang="{ui}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
{alts}
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:site_name" content="{brand}">
<meta property="og:image" content="{base}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Alexandria:wght@700;800&family=Amiri:wght@400;700&family=Fraunces:opsz,wght@9..144,700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap">
{ld}
<style>{css}{extra}</style>
</head>
<body>
<header class="bar"><div class="wrap"><a class="brand" href="/">{logo}<span>{brand}</span></a>
<form class="sbox" action="/#browse" method="get" role="search">{icon}<input type="search" name="q" placeholder="{ph}" aria-label="{ph}"><button type="submit">{search}</button></form>
<nav><a href="/#browse">{all}</a><a href="{toggle}" hreflang="{other}">{other_lang}</a></nav></div></header>
<main class="wrap">
{body}
<footer>{legal}<p>{note}</p></footer>
</main>
</body>
</html>
""".format(ui=ui, dir=t["dir"], title=esc(title), desc=esc(desc), canon=esc(canon), alts=_alternates(base, path),
           brand=esc(BRAND[ui]), base=esc(base), ld=ld, css=CSS, extra=EXTRA_CSS + extra_css, logo=LOGO_SVG, icon=SEARCH_ICON,
           ph=esc(t["ph"]), search=esc(t["search"]), all=esc(t["all"]), other=other, other_lang=esc(t["other_lang"]),
           toggle=esc(path + ("?lang=en" if other == "en" else "")), body=body, note=esc(t["note"]), legal=legal_links(ui))


def _book_list(conn, rows, ui) -> str:
    authors = _authors(conn)
    items = []
    for r in rows:
        a = book_author(r, ui, authors)
        items.append('<li><a href="%s">%s%s</a></li>' % (esc(canonical_path(r)), esc(book_title(r, ui)), ("<small>%s</small>" % esc(a)) if a else ""))
    return '<ul class="rel">%s</ul>' % "".join(items)


def _pager(path, ui, page, pages) -> str:
    s, lang = S[ui], ("lang=en&" if ui == "en" else "")
    prev = '<a rel="prev" href="%s?%spage=%d">%s</a>' % (path, lang, page - 1, s["prev"]) if page > 1 else "<span></span>"
    nxt = '<a rel="next" href="%s?%spage=%d">%s</a>' % (path, lang, page + 1, s["next"]) if page < pages else "<span></span>"
    return '<nav class="pager">%s%s</nav>' % (prev, nxt)


def _breadcrumbs(base, ui, name, path) -> dict:
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": T[ui]["home"], "item": base + "/"},
        {"@type": "ListItem", "position": 2, "name": name, "item": base + path}]}


def category_page(conn, key: str, base: str, ui: str = "ar", page: int = 1):
    if key not in CATEGORIES:
        return None
    total = conn.execute("SELECT COUNT(*) FROM books WHERE cat=?", (key,)).fetchone()[0]
    pages = max(1, min(MAX_PAGES, math.ceil(total / PER_PAGE)))
    if page < 1 or page > pages:
        return None
    rows = conn.execute("SELECT * FROM books WHERE cat=? ORDER BY ord LIMIT ? OFFSET ?", (key, PER_PAGE, (page - 1) * PER_PAGE)).fetchall()
    s, name = S[ui], CATEGORIES[key][ui]
    path = "/category/" + key
    title = s["cat_h"].format(c=name) + ((" — " + s["page"].format(p=page)) if page > 1 else "") + " | " + BRAND[ui]
    desc = s["cat_d"].format(n="{:,}".format(total), c=name)
    chips = "".join('<a href="/category/%s%s"%s>%s</a>' % (k, "?lang=en" if ui == "en" else "", ' aria-current="page"' if k == key else "", esc(v[ui]))
                    for k, v in CATEGORIES.items())
    body = ('<p class="crumbs"><a href="/">%s</a> / %s</p><h1>%s</h1><p class="desc">%s <a href="/?cat=%s#browse">%s</a></p>'
            '<nav class="chips" aria-label="%s">%s</nav>%s%s'
            % (esc(T[ui]["home"]), esc(name), esc(s["cat_h"].format(c=name)), esc(desc), key, esc(s["open"]), esc(s["cats"]), chips,
               _book_list(conn, rows, ui), _pager(path, ui, page, pages)))
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": title, "description": desc, "url": base + path, "inLanguage": ui,
         "isPartOf": {"@id": base + "/#site"}},
        _breadcrumbs(base, ui, name, path)]})
    return _shell(ui, base, path, title, desc, body, ld, page)


def author_page(conn, key: str, base: str, ui: str = "ar", page: int = 1):
    a = conn.execute("SELECT * FROM authors WHERE key=?", (key,)).fetchone()
    if not a:
        return None
    total = conn.execute("SELECT COUNT(*) FROM books WHERE author_key=?", (key,)).fetchone()[0]
    pages = max(1, min(MAX_PAGES, math.ceil(total / PER_PAGE)))
    if page < 1 or page > pages:
        return None
    rows = conn.execute("SELECT * FROM books WHERE author_key=? ORDER BY ord LIMIT ? OFFSET ?", (key, PER_PAGE, (page - 1) * PER_PAGE)).fetchall()
    s, name = S[ui], (a["ar"] if ui == "ar" and a["ar"] else a["en"])
    path = "/author/" + quote(key)
    title = s["auth_h"].format(a=name) + ((" (%s)" % a["years"]) if a["years"] else "") + ((" — " + s["page"].format(p=page)) if page > 1 else "") + " | " + BRAND[ui]
    desc = s["auth_d"].format(n="{:,}".format(total), a=name)
    others = conn.execute("SELECT key, en, ar FROM authors ORDER BY ord LIMIT 40").fetchall()
    chips = "".join('<a href="/author/%s%s">%s</a>' % (quote(o["key"]), "?lang=en" if ui == "en" else "", esc(o["ar"] if ui == "ar" else o["en"]))
                    for o in others if o["key"] != key)
    body = ('<p class="crumbs"><a href="/">%s</a> / %s</p><h1>%s</h1><p class="desc">%s <a href="/?ak=%s#browse">%s</a></p>%s%s'
            '<h2>%s</h2><nav class="chips">%s</nav>'
            % (esc(T[ui]["home"]), esc(name), esc(s["auth_h"].format(a=name)), esc(desc), esc(quote(key)), esc(s["open"]),
               _book_list(conn, rows, ui), _pager(path, ui, page, pages), esc(s["authors"]), chips))
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "ProfilePage", "name": title, "url": base + path, "inLanguage": ui,
         "mainEntity": {"@type": "Person", "name": a["en"], "alternateName": a["ar"]}},
        _breadcrumbs(base, ui, name, path)]})
    return _shell(ui, base, path, title, desc, body, ld, page)


# ---------- robots.txt and the main sitemap ----------

def robots_txt(base: str) -> str:
    # the home page fills itself from /api/*: crawlers must be able to read it to see the books
    # AdSense's crawler gets its own group: nothing on the site is closed to it
    return ("User-agent: Mediapartners-Google\nAllow: /\n\n"
            "User-agent: *\nAllow: /\nDisallow: /api/hit\nDisallow: /api/like/\nDisallow: /api/track/\n"
            "Disallow: /admin/\nDisallow: /docs\nDisallow: /redoc\nSitemap: %s/sitemap.xml\n" % base)


def main_urls(conn, base: str):
    urls = [base + "/", base + "/?lang=en"]
    for p in legal.PAGES:
        urls += [base + "/" + p, base + "/" + p + "?lang=en"]
    for k in CATEGORIES:
        urls += [base + "/category/" + k, base + "/category/" + k + "?lang=en"]
    for r in conn.execute("SELECT key FROM authors ORDER BY ord"):
        urls += [base + "/author/" + quote(r["key"]), base + "/author/" + quote(r["key"]) + "?lang=en"]
    return urls


def sitemap_main(conn, base: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n'
            % "\n".join("<url><loc>%s</loc></url>" % esc(u) for u in main_urls(conn, base)))


# ---------- IndexNow: Bing, Yandex, Seznam, Naver... learn about new pages within minutes ----------

def indexnow(conn, base: str, key: str, with_books: bool = False, log=print) -> int:
    urls = main_urls(conn, base)
    if with_books:
        urls += [base + canonical_path(r) for r in conn.execute("SELECT id, title, title_ar, lang, origin FROM books ORDER BY id")]
    host = base.split("://", 1)[-1].split("/")[0]
    sent = 0
    for i in range(0, len(urls), 10000):
        body = json.dumps({"host": host, "key": key, "keyLocation": "%s/%s.txt" % (base, key), "urlList": urls[i:i + 10000]}).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=60) as r:
            log("IndexNow: %d URLs -> HTTP %d" % (len(urls[i:i + 10000]), r.status))
        sent += len(urls[i:i + 10000])
    return sent


def main() -> int:
    from . import db
    if len(sys.argv) < 2 or sys.argv[1] != "indexnow":
        print(__doc__)
        return 1
    base = os.environ.get("SITE_URL", "").strip().rstrip("/")
    key = os.environ.get("INDEXNOW_KEY", "").strip()
    if not base.startswith("https://") or not key:
        print("Set SITE_URL (https://...) and INDEXNOW_KEY first; the server must be live at SITE_URL.", file=sys.stderr)
        return 1
    conn = db.connect()
    print("sent", indexnow(conn, base, key, "--books" in sys.argv), "URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
