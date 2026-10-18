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
import re
import sys
import urllib.request
from urllib.parse import quote

from . import legal, modern
from .wikisource import WS_KIND
from .catalog import ARABIC_CAT, CATEGORIES
from .pages import (BRAND, CSS, INFEED_AT, INFEED_MIN, LOGO_SVG, SEARCH_ICON, T, _authors, ad_head, ad_unit, adsense_meta,
                    book_author, book_title, canonical_path, esc, infeed_meta, infeed_unit, legal_links)

PER_PAGE = 60
MAX_PAGES = 200  # category pages go this deep; the sitemaps list every single book anyway

S = {
    "ar": {
        "cat_h": "كتب {c} مجانية", "cat_d": "{n} في تصنيف «{c}»، مجانية سقط عنها حق النشر، تقرؤها كاملة من مصادرها المفتوحة.",
        "n_books": "{n} كتاباً", "n_poems": " و{p} قصيدة",
        "auth_h": "كتب {a}", "auth_d": "{n} من أعمال {a} مجانية في الملك العام، تقرؤها كاملة من مصادرها المفتوحة.",
        "cat_hm": "كتب {c}", "cat_dm": "{n} في تصنيف «{c}»: كتب سقط عنها حق النشر تقرؤها مجاناً، وكتب عربية حديثة نوصلك إلى صفحاتها لدى مصادرها القانونية.",
        "auth_dm": "{n} من أعمال {a} في مكتبة الوراق، نوصلك إليها في مصادرها المفتوحة والقانونية.",
        "cats": "التصنيفات", "authors": "مؤلفون مشهورون", "prev": "السابق", "next": "التالي", "page": "صفحة {p}",
        "open": "تصفّح في المكتبة", "home_t": "مكتبة الوراق | كتب مجانية وقصائد عربية في الملك العام",
    },
    "en": {
        "cat_h": "Free {c} books", "cat_d": "{n} in “{c}”, free and in the public domain, readable in full at their open sources.",
        "n_books": "{n} books", "n_poems": " and {p} poems",
        "auth_h": "Books by {a}", "auth_d": "{n} public-domain works by {a}, free to read at their open sources.",
        "cat_hm": "{c} books", "cat_dm": "{n} in “{c}”: public-domain books to read free, and modern Arabic books with links to their pages at legal sources.",
        "auth_dm": "{n} works by {a} at Al-Warraq Library, with links to their open and legal sources.",
        "cats": "Categories", "authors": "Famous authors", "prev": "Previous", "next": "Next", "page": "page {p}",
        "open": "Browse in the library", "home_t": "Al-Warraq Library | Free public-domain books and Arabic poetry",
        "home_og": "Al-Warraq Library | مكتبة الوراق",
        "home_d": "Al-Warraq Library (مكتبة الوراق): over a million free public-domain books, Arabic poetry and modern Arabic "
                  "books, with covers and categories, linked to their legal sources.",
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

_home = {}  # ui -> (file times, index.html with that language's words in place)
# app.js keeps the interface strings (const T = {ar: {...}, en: {...}}): the server reads them there, one source
_STRING = re.compile(r"^ +(\w+): '((?:[^'\\]|\\.)*)',?$", re.M)
_DATA_I = re.compile(r'(<([a-z0-9]+)[^>]*? data-i="(\w+)"[^>]*>)([^<]*)(</\2>)')
_DATA_IPH = re.compile(r' data-iph="(\w+)"')
_DATA_IARL = re.compile(r' data-iarl="(\w+)"(?: aria-label="[^"]*")?')
_LHREF = re.compile(r' href="([^"]*)" data-lhref="([^"]*)"')


def ui_strings(frontend_dir: str) -> dict:
    """{"ar": {...}, "en": {...}}: the interface strings of app.js, the very words its script puts in the page."""
    with open(os.path.join(frontend_dir, "app.js"), encoding="utf-8") as f:
        src = f.read()
    table = src[src.index("const T = {"):]
    out = {}
    for ui in ("ar", "en"):
        start = table.index("\n        %s: {" % ui)
        end = table.index("\n        }", start)
        out[ui] = {k: v.replace("\\'", "'") for k, v in _STRING.findall(table[start:end])}
    return out


def _home_template(frontend_dir: str, ui: str) -> str:
    """index.html with its words already in place for that language. A crawler reads the page before (or without)
    running the script: /?lang=en must be English in its very HTML (language, title, headings), not an empty shell
    with the Arabic title, or English searches have nothing to find."""
    paths = [os.path.join(frontend_dir, n) for n in ("index.html", "app.js")]
    key = tuple(os.path.getmtime(p) for p in paths if os.path.exists(p))
    hit = _home.get(ui)
    if hit and hit[0] == key:
        return hit[1]
    with open(paths[0], encoding="utf-8") as f:
        html = f.read()
    try:
        t = ui_strings(frontend_dir)[ui]
    except (OSError, ValueError):  # no script beside the page: the words are left to it
        t = {}
    if t:
        html = _DATA_I.sub(lambda m: m.group(1) + (esc(t[m.group(3)]) if m.group(3) in t else m.group(4)) + m.group(5), html)
        html = _DATA_IPH.sub(lambda m: m.group(0) + (' placeholder="%s" aria-label="%s"' % ((esc(t[m.group(1)]),) * 2)
                                                     if m.group(1) in t else ""), html)
        html = _DATA_IARL.sub(lambda m: ' data-iarl="%s" aria-label="%s"' % (m.group(1), esc(t.get(m.group(1), ""))), html)
        html = re.sub(r'(id="filtBtn"[^>]*>)(</button>)', lambda m: m.group(1) + esc(t.get("filters", "")) + m.group(2), html)
    if ui == "en":
        s = S["en"]
        html = html.replace('<html lang="ar" dir="rtl">', '<html lang="en" dir="ltr">', 1)
        html = re.sub(r"<title>[^<]*</title>", lambda m: "<title>%s</title>" % esc(s["home_t"]), html, count=1)
        for attr, value in (('name="description"', s["home_d"]), ('property="og:description"', s["home_d"]),
                            ('property="og:title"', s["home_og"]), ('name="twitter:title"', s["home_og"])):
            html = re.sub(r'<meta %s content="[^"]*">' % attr, lambda m: '<meta %s content="%s">' % (attr, esc(value)), html, count=1)
        html = _LHREF.sub(lambda m: ' href="%s?lang=en" data-lhref="%s"' % (m.group(2), m.group(2)), html)
        html = html.replace('id="langBtn" type="button" aria-label="Language">EN<', 'id="langBtn" type="button" aria-label="العربية">ع<', 1)
    _home[ui] = (key, html)
    return html


def with_nonce(page: str, nonce: str) -> str:
    """Every script of the page carries the response's nonce: the only scripts its Content-Security-Policy runs."""
    return page.replace("<script", '<script nonce="%s"' % esc(nonce)) if nonce else page


def home_html(frontend_dir: str, base: str, ui: str = "ar", nonce: str = "") -> str:
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
        ad_head() if nonce else "",
        infeed_meta() if nonce else "",
        _ld({"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "@id": base + "/#site", "url": base + "/", "name": BRAND["ar"], "alternateName": BRAND["en"],
             "inLanguage": ["ar", "en"], "publisher": {"@id": base + "/#org"},
             "potentialAction": {"@type": "SearchAction", "target": base + "/?q={search_term_string}",
                                 "query-input": "required name=search_term_string"}},
            {"@type": "Organization", "@id": base + "/#org", "name": BRAND["ar"], "alternateName": BRAND["en"], "url": base + "/",
             "logo": base + "/icon-512.png"},
        ]}),
    ])
    links = " ".join('<a href="/category/%s%s">%s</a>' % (k, "?lang=en" if ui == "en" else "", esc(v[ui])) for k, v in CATEGORIES.items())
    ad = '<div class="wrap">%s</div>' % ad_unit(ui) if nonce and ad_unit(ui) else ""
    page = _home_template(frontend_dir, ui).replace("<!--SEO:HEAD-->", head).replace("<!--SEO:CATS-->", links).replace("<!--SEO:AD-->", ad)
    return with_nonce(page, nonce)


# ---------- category and author pages (plain HTML: every crawler can read and follow them) ----------

def _shell(ui, base, path, title, desc, body, ld, page=1, extra_q="", extra_css="", nonce=""):
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
{adsense}
{ad_head}
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
           toggle=esc(path + ("?lang=en" if other == "en" else "")),
           body=body.replace("<!--SEO:AD-->", ad_unit(ui) if nonce else "").replace("<!--SEO:FEED-->", infeed_unit(ui) if nonce else ""),
           note=esc(t["note"]), legal=legal_links(ui), adsense=adsense_meta(), ad_head=ad_head() if nonce else "")


def _book_list(conn, rows, ui) -> str:
    authors = _authors(conn)
    items = []
    for r in rows:
        a = book_author(r, ui, authors)
        items.append('<li><a href="%s">%s%s</a></li>' % (esc(canonical_path(r)), esc(book_title(r, ui)), ("<small>%s</small>" % esc(a)) if a else ""))
    if len(items) >= INFEED_MIN:  # the in-feed ad's place, filled by _shell on pages that show ads
        items.insert(INFEED_AT, "<!--SEO:FEED-->")
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


def _has_modern(conn, cond: str, arg) -> bool:
    """Whether some of these books are modern ones under copyright (Safahat / Open Library)."""
    return bool(conn.execute("SELECT 1 FROM books WHERE " + cond + " AND curated IN (?, ?) LIMIT 1", (arg,) + modern.KINDS).fetchone())


def category_page(conn, key: str, base: str, ui: str = "ar", page: int = 1, nonce: str = ""):
    if key not in CATEGORIES:
        return None
    # the Arabic category is every book written in Arabic, not a topic
    cond, arg = ("lang=?", "ar") if key == ARABIC_CAT else ("cat=?", key)
    total = conn.execute("SELECT COUNT(*) FROM books WHERE " + cond, (arg,)).fetchone()[0]
    pages = max(1, min(MAX_PAGES, math.ceil(total / PER_PAGE)))
    if page < 1 or page > pages:
        return None
    rows = conn.execute("SELECT * FROM books WHERE " + cond + " ORDER BY ord LIMIT ? OFFSET ?", (arg, PER_PAGE, (page - 1) * PER_PAGE)).fetchall()
    s, name = S[ui], CATEGORIES[key][ui]
    path = "/category/" + key
    if _has_modern(conn, cond, arg):  # not every book here is free: say so
        s = dict(s, cat_h=s["cat_hm"], cat_d=s["cat_dm"])
    title = s["cat_h"].format(c=name) + ((" — " + s["page"].format(p=page)) if page > 1 else "") + " | " + BRAND[ui]
    # every poem is Arabic and in "poe": counted from the index alone
    poems = conn.execute("SELECT COUNT(*) FROM books WHERE curated=?", (WS_KIND,)).fetchone()[0] if key in (ARABIC_CAT, "poe") else 0
    n = s["n_books"].format(n="{:,}".format(total - poems)) + (s["n_poems"].format(p="{:,}".format(poems)) if poems else "")
    desc = s["cat_d"].format(n=n, c=name)
    chips = "".join('<a href="/category/%s%s"%s>%s</a>' % (k, "?lang=en" if ui == "en" else "", ' aria-current="page"' if k == key else "", esc(v[ui]))
                    for k, v in CATEGORIES.items())
    body = ('<p class="crumbs"><a href="/">%s</a> / %s</p><h1>%s</h1><p class="desc">%s <a href="/?cat=%s#browse">%s</a></p>'
            '<nav class="chips" aria-label="%s">%s</nav><!--SEO:AD-->%s%s'
            % (esc(T[ui]["home"]), esc(name), esc(s["cat_h"].format(c=name)), esc(desc), key, esc(s["open"]), esc(s["cats"]), chips,
               _book_list(conn, rows, ui), _pager(path, ui, page, pages)))
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": title, "description": desc, "url": base + path, "inLanguage": ui,
         "isPartOf": {"@id": base + "/#site"}},
        _breadcrumbs(base, ui, name, path)]})
    return with_nonce(_shell(ui, base, path, title, desc, body, ld, page, nonce=nonce), nonce)


def author_page(conn, key: str, base: str, ui: str = "ar", page: int = 1, nonce: str = ""):
    a = conn.execute("SELECT * FROM authors WHERE key=?", (key,)).fetchone()
    if not a:
        return None
    total = conn.execute("SELECT COUNT(*) FROM books WHERE author_key=?", (key,)).fetchone()[0]
    pages = max(1, min(MAX_PAGES, math.ceil(total / PER_PAGE)))
    if not total or page < 1 or page > pages:
        return None
    rows = conn.execute("SELECT * FROM books WHERE author_key=? ORDER BY ord LIMIT ? OFFSET ?", (key, PER_PAGE, (page - 1) * PER_PAGE)).fetchall()
    s, name = S[ui], (a["ar"] if ui == "ar" and a["ar"] else a["en"])
    if _has_modern(conn, "author_key=?", key):
        s = dict(s, auth_d=s["auth_dm"])
    path = "/author/" + quote(key)
    title = s["auth_h"].format(a=name) + ((" (%s)" % a["years"]) if a["years"] else "") + ((" — " + s["page"].format(p=page)) if page > 1 else "") + " | " + BRAND[ui]
    desc = s["auth_d"].format(n="{:,}".format(total), a=name)
    others = conn.execute("SELECT key, en, ar FROM authors ORDER BY ord LIMIT 40").fetchall()
    chips = "".join('<a href="/author/%s%s">%s</a>' % (quote(o["key"]), "?lang=en" if ui == "en" else "", esc(o["ar"] if ui == "ar" else o["en"]))
                    for o in others if o["key"] != key)
    body = ('<p class="crumbs"><a href="/">%s</a> / %s</p><h1>%s</h1><p class="desc">%s <a href="/?ak=%s#browse">%s</a></p><!--SEO:AD-->%s%s'
            '<h2>%s</h2><nav class="chips">%s</nav>'
            % (esc(T[ui]["home"]), esc(name), esc(s["auth_h"].format(a=name)), esc(desc), esc(quote(key)), esc(s["open"]),
               _book_list(conn, rows, ui), _pager(path, ui, page, pages), esc(s["authors"]), chips))
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "ProfilePage", "name": title, "url": base + path, "inLanguage": ui,
         "mainEntity": {"@type": "Person", "name": a["en"], "alternateName": a["ar"]}},
        _breadcrumbs(base, ui, name, path)]})
    return with_nonce(_shell(ui, base, path, title, desc, body, ld, page, nonce=nonce), nonce)


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
    for r in conn.execute("SELECT key FROM authors a WHERE EXISTS (SELECT 1 FROM books WHERE author_key=a.key) ORDER BY ord"):
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
