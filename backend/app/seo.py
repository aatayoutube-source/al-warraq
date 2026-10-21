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

from . import content, legal, modern
from .wikisource import WS_KIND
from .catalog import ARABIC_CAT, CATEGORIES
from .pages import (ARTICLES_NAME, BRAND, CSS, INFEED_AT, INFEED_MIN, LOGO_SVG, SEARCH_ICON, T, UI_LANGS, _authors, ad_head, ad_unit,
                    analytics_head, book_author, book_title, canonical_path, esc, infeed_meta, infeed_unit, lang_switcher, legal_links, site_head)

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
        "intro_h": "ما هي مكتبة الوراق؟", "arts_h": "من مقالات المكتبة", "arts_all": "كل المقالات",
        "cat_about": "عن هذا التصنيف", "auth_about": "عن المؤلف",
        "arts_t": "مقالات مكتبة الوراق: أدلة القراءة والكتب والشعراء", "arts_d": "مقالات أصلية من مكتبة الوراق: أدلة لقراءة الكتب في الملك العام، ومداخل إلى الشعر العربي والروايات الكلاسيكية وتاريخ المكتبات.",
        "arts_lead": "مقالات نكتبها لتعينك على الاختيار والقراءة: أدلة عملية، ومداخل إلى كتّاب وأعمال، وصفحات من تاريخ الكتاب العربي.",
        "minutes": "{n} دقائق قراءة", "more_arts": "مقالات أخرى", "arts_lang": "",
    },
    "en": {
        "cat_h": "Free {c} books", "cat_d": "{n} in “{c}”, free and in the public domain, readable in full at their open sources.",
        "n_books": "{n} books", "n_poems": " and {p} poems",
        "auth_h": "Books by {a}", "auth_d": "{n} public-domain works by {a}, free to read at their open sources.",
        "cat_hm": "{c} books", "cat_dm": "{n} in “{c}”: public-domain books to read free, and modern Arabic books with links to their pages at legal sources.",
        "auth_dm": "{n} works by {a} at Al-Warraq Library, with links to their open and legal sources.",
        "cats": "Categories", "authors": "Famous authors", "prev": "Previous", "next": "Next", "page": "page {p}",
        "open": "Browse in the library", "home_t": "Al-Warraq Library | Free public-domain books and Arabic poetry",
        "intro_h": "What is Al-Warraq Library?", "arts_h": "From the library's articles", "arts_all": "All articles",
        "cat_about": "About this category", "auth_about": "About the author",
        "arts_t": "Al-Warraq Library articles: reading guides, books and poets", "arts_d": "Original articles from Al-Warraq Library (in Arabic): guides to public-domain books, Arabic poetry, classic novels and the history of libraries.",
        "arts_lead": "Articles we write to help you choose and read: practical guides, introductions to writers and works, and pages from the history of the Arabic book.",
        "minutes": "{n} min read", "more_arts": "More articles", "arts_lang": "The articles are written in Arabic.",
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
    """hreflang links for all supported UI languages; Arabic is x-default."""
    links = []
    for lang in UI_LANGS:
        q = ("?lang=" + lang + (("&" + extra) if extra else "")) if lang != "ar" else (("?" + extra) if extra else "")
        url = base + path + q
        links.append('<link rel="alternate" hreflang="%s" href="%s">' % (lang, esc(url)))
    ar_url = base + path + (("?" + extra) if extra else "")
    links.append('<link rel="alternate" hreflang="x-default" href="%s">' % esc(ar_url))
    return "\n".join(links)


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
    if ui != "ar":
        s = S.get(ui, S["en"])
        dir_ = T[ui]["dir"] if ui in T else "ltr"
        html = html.replace('<html lang="ar" dir="rtl">', '<html lang="%s" dir="%s">' % (ui, dir_), 1)
        if "home_t" in s:
            html = re.sub(r"<title>[^<]*</title>", lambda m: "<title>%s</title>" % esc(s["home_t"]), html, count=1)
        if "home_d" in s:
            for attr, value in (('name="description"', s["home_d"]), ('property="og:description"', s["home_d"]),
                                ('property="og:title"', s.get("home_og", s["home_d"])), ('name="twitter:title"', s.get("home_og", s["home_d"]))):
                html = re.sub(r'<meta %s content="[^"]*">' % attr, lambda m, a=attr, v=value: '<meta %s content="%s">' % (a, esc(v)), html, count=1)
        html = _LHREF.sub(lambda m, u=ui: ' href="%s?lang=%s" data-lhref="%s"' % (m.group(2), u, m.group(2)), html)
        html = html.replace('id="langBtn" type="button" aria-label="Language">EN<', 'id="langBtn" type="button" aria-label="العربية">ع<', 1)
    _home[ui] = (key, html)
    return html


def with_nonce(page: str, nonce: str) -> str:
    """Every script of the page carries the response's nonce: the only scripts its Content-Security-Policy runs."""
    return page.replace("<script", '<script nonce="%s"' % esc(nonce)) if nonce else page


def _home_intro(ui: str) -> str:
    """What the library is (its own words) and its latest articles, for the home page."""
    s = S.get(ui, S["en"])
    q = ("?lang=" + ui) if ui != "ar" else ""
    paras = content.home(ui) or content.home("en")
    arts = content.articles()[:6]
    if not paras and not arts:
        return ""
    out = '<div class="intro" data-srv-lang="%s">' % ui
    if paras:
        out += "<h2>%s</h2>%s" % (esc(s.get("intro_h", "")), content.paragraphs(paras))
    if arts:
        out += '<div class="intro-arts"><h3>%s</h3><ul>%s</ul><a class="intro-all" href="/articles%s">%s</a></div>' % (
            esc(s.get("arts_h", "")), "".join('<li><a href="/articles/%s" lang="ar">%s</a></li>' % (esc(a["slug"]), esc(a["title"])) for a in arts),
            q, esc(s.get("arts_all", "")))
    return out + "</div>"


def home_html(frontend_dir: str, base: str, ui: str = "ar", nonce: str = "", search: bool = False) -> str:
    canon = base + ("/?lang=" + ui if ui != "ar" else "/")
    og_locale = {"ar": "ar_AR", "en": "en_US", "fr": "fr_FR", "es": "es_ES", "pt": "pt_BR", "zh": "zh_CN", "ja": "ja_JP"}.get(ui, "en_US")
    head = "\n".join([
        '<link rel="canonical" href="%s">' % esc(canon),
        _alternates(base, "/"),
        '<meta property="og:url" content="%s">' % esc(canon),
        '<meta property="og:image" content="%s/og-image.png">' % esc(base),
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">',
        '<meta property="og:locale" content="%s">' % og_locale,
        '<meta name="twitter:image" content="%s/og-image.png">' % esc(base),
        verification_meta(),
        analytics_head(),
        ad_head() if nonce else "",
        infeed_meta() if nonce else "",
        _ld({"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "@id": base + "/#site", "url": base + "/", "name": BRAND["ar"], "alternateName": BRAND["en"],
             "inLanguage": list(UI_LANGS), "publisher": {"@id": base + "/#org"},
             "potentialAction": {"@type": "SearchAction", "target": base + "/?q={search_term_string}",
                                 "query-input": "required name=search_term_string"}},
            {"@type": "Organization", "@id": base + "/#org", "name": BRAND["ar"], "alternateName": BRAND["en"], "url": base + "/",
             "logo": base + "/icon-512.png"},
        ]}),
    ])
    lang_q = ("?lang=" + ui) if ui != "ar" else ""
    links = " ".join('<a href="/category/%s%s">%s</a>' % (k, lang_q, esc(v.get(ui, v["en"]))) for k, v in CATEGORIES.items())
    ad = '<div class="wrap">%s</div>' % ad_unit(ui) if nonce and ad_unit(ui) else ""
    page = (_home_template(frontend_dir, ui).replace("<!--SEO:HEAD-->", head).replace("<!--SEO:CATS-->", links)
            .replace("<!--SEO:AD-->", ad).replace("<!--SEO:INTRO-->", _home_intro(ui)))
    if search:  # /?q=...: the same page showing search results, not a page of its own for search engines
        page = page.replace('<meta name="robots" content="index,follow">', '<meta name="robots" content="noindex,follow">', 1)
    return with_nonce(page, nonce)


# ---------- category and author pages (plain HTML: every crawler can read and follow them) ----------

def _shell(ui, base, path, title, desc, body, ld, page=1, extra_q="", extra_css="", nonce="", robots="", canonical="",
           alternates=True):
    t = T[ui]
    q_parts = []
    if ui != "ar":
        q_parts.append("lang=" + ui)
    if page > 1:
        q_parts.append("page=%d" % page)
    canon = base + path + ("?" + "&".join(q_parts) if q_parts else "")
    canon = canonical or canon
    return """<!doctype html>
<html lang="{ui}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
{adsense}
{ad_head}
{robots}<link rel="canonical" href="{canon}">
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
<nav><a href="/#browse">{all}</a>{sw}</nav></div></header>
<main class="wrap">
{body}
<footer>{legal}<p>{note}</p></footer>
</main>
</body>
</html>
""".format(ui=ui, dir=t["dir"], title=esc(title), desc=esc(desc), canon=esc(canon), alts=_alternates(base, path) if alternates else "",
           robots=('<meta name="robots" content="%s">\n' % esc(robots)) if robots else "",
           brand=esc(BRAND.get(ui, BRAND["en"])), base=esc(base), ld=ld, css=CSS, extra=EXTRA_CSS + extra_css, logo=LOGO_SVG, icon=SEARCH_ICON,
           ph=esc(t["ph"]), search=esc(t["search"]), all=esc(t["all"]), sw=lang_switcher(ui),
           body=body.replace("<!--SEO:AD-->", ad_unit(ui) if nonce else "").replace("<!--SEO:FEED-->", infeed_unit(ui) if nonce else ""),
           note=esc(t["note"]), legal=legal_links(ui), adsense=site_head(), ad_head=ad_head() if nonce else "")


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
    s, lang = S.get(ui, S["en"]), (("lang=%s&" % ui) if ui != "ar" else "")
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
            '<nav class="chips" aria-label="%s">%s</nav>%s<!--SEO:AD-->%s%s'
            % (esc(T[ui]["home"]), esc(name), esc(s["cat_h"].format(c=name)), esc(desc), key, esc(s["open"]), esc(s["cats"]), chips,
               _text_section(s["cat_about"], content.category(key, ui)) if page == 1 else "",
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
    bio = content.author(key, ui)
    body = ('<p class="crumbs"><a href="/">%s</a> / %s</p><h1>%s</h1><p class="desc">%s <a href="/?ak=%s#browse">%s</a></p>%s<!--SEO:AD-->%s%s'
            '<h2>%s</h2><nav class="chips">%s</nav>'
            % (esc(T[ui]["home"]), esc(name), esc(s["auth_h"].format(a=name)), esc(desc), esc(quote(key)), esc(s["open"]),
               _text_section(s["auth_about"], bio) if page == 1 else "",
               _book_list(conn, rows, ui), _pager(path, ui, page, pages), esc(s["authors"]), chips))
    person = {"@type": "Person", "name": a["en"], "alternateName": a["ar"]}
    if bio:
        person["description"] = _plain_text(bio[0])
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "ProfilePage", "name": title, "url": base + path, "inLanguage": ui, "mainEntity": person},
        _breadcrumbs(base, ui, name, path)]})
    robots = "" if author_indexable(conn, key, ui) else "noindex,follow"
    return with_nonce(_shell(ui, base, path, title, desc, body, ld, page, nonce=nonce if not robots else "", robots=robots), nonce)


def _text_section(heading: str, paras) -> str:
    return '<section class="intro"><h2>%s</h2>%s</section>' % (esc(heading), content.paragraphs(paras)) if paras else ""


def _plain_text(text: str) -> str:
    return " ".join(re.sub(r"\*\*([^*]+)\*\*", r"\1", re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)).split())


def author_indexable(conn, key: str, ui: str = "ar") -> bool:
    """An author page stands on its own with a biography, or with a first page of titles long enough to read
    (content.MIN_WORDS); otherwise THIN_NOINDEX keeps it out of search results, the sitemap and ads."""
    if not content.thin_noindex() or content.author(key, ui):
        return True
    rows = conn.execute("SELECT title, title_ar FROM books WHERE author_key=? ORDER BY ord LIMIT ?", (key, PER_PAGE)).fetchall()
    return content.words([book_title(r, ui) for r in rows]) >= content.MIN_WORDS


# ---------- articles (written in Arabic; the frame follows the visitor's language) ----------

ARTICLE_CSS = """
.post{max-width:760px}.post h1{margin:14px 0 6px;font:800 clamp(1.6rem,4vw,2.2rem)/1.5 "Alexandria","IBM Plex Sans Arabic",sans-serif}
.post .meta{color:var(--muted);font-size:.9rem;margin:0 0 10px}.post .lead{font-size:1.1rem;margin:0 0 16px}
.post h2{margin:30px 0 10px;font-size:1.35rem}.post h3{margin:22px 0 8px;font-size:1.12rem}
.post p,.post li{line-height:2}.post ul,.post ol{padding-inline-start:22px}.post li{margin:5px 0}
.post .verse{margin:16px 0;padding:14px 18px;border-inline-start:4px solid var(--brand-2);background:var(--card);border-radius:12px;font-family:"Amiri",serif;font-size:1.12rem}
.post .verse p{margin:4px 0;line-height:1.9}
.arts{list-style:none;margin:16px 0;padding:0;display:grid;gap:12px}
.arts li{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 18px}
.arts a{font-weight:700;font-size:1.08rem;text-decoration:none}.arts p{margin:6px 0 0;color:var(--muted)}.arts small{color:var(--muted)}
.intro{max-width:820px}.intro p+p{margin-top:.6em}
"""


def _minutes(words: int) -> int:
    return max(2, round(words / 200))


def articles_page(base: str, ui: str, nonce: str = "") -> str:
    s, q = S[ui], ("?lang=en" if ui == "en" else "")
    arts = content.articles()
    items = "".join(
        '<li><a href="/articles/%s%s" lang="ar">%s</a><p lang="ar">%s</p><small>%s · %s</small></li>'
        % (esc(a["slug"]), q, esc(a["title"]), esc(a.get("description", "")), esc(a.get("date", "")),
           esc(s["minutes"].format(n=_minutes(a["words"])))) for a in arts)
    name = ARTICLES_NAME[ui]
    body = ('<p class="crumbs"><a href="/%s">%s</a> / %s</p><h1>%s</h1><p class="desc">%s %s</p><ul class="arts">%s</ul><!--SEO:AD-->'
            % (q, esc(T[ui]["home"]), esc(name), esc(name), esc(s["arts_lead"]), esc(s["arts_lang"]), items))
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": s["arts_t"], "description": s["arts_d"], "url": base + "/articles", "inLanguage": "ar",
         "isPartOf": {"@id": base + "/#site"},
         "mainEntity": {"@type": "ItemList", "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "url": base + "/articles/" + a["slug"], "name": a["title"]} for i, a in enumerate(arts)]}},
        _breadcrumbs(base, ui, name, "/articles")]})
    return with_nonce(_shell(ui, base, "/articles", s["arts_t"] + " | " + BRAND[ui], s["arts_d"], body, ld, nonce=nonce,
                             extra_css=ARTICLE_CSS), nonce)


def article_page(slug: str, base: str, ui: str, nonce: str = ""):
    a = content.article(slug)
    if not a:
        return None
    s, q = S[ui], ("?lang=en" if ui == "en" else "")
    html_body = content.render(a["body"])
    # one ad after the second section, one at the end: well apart from the title, three at most on the page
    parts = html_body.split("<h2>")
    if len(parts) > 3:
        html_body = "<h2>".join(parts[:3]) + "<!--SEO:AD--><h2>" + "<h2>".join(parts[3:])
    others = [o for o in content.articles() if o["slug"] != slug][:5]
    more = ('<section class="intro"><h2>%s</h2><ul class="arts">%s</ul></section>' % (esc(s["more_arts"]), "".join(
        '<li><a href="/articles/%s%s" lang="ar">%s</a></li>' % (esc(o["slug"]), q, esc(o["title"])) for o in others))) if others else ""
    url = base + "/articles/" + slug
    body = ('<p class="crumbs"><a href="/%s">%s</a> / <a href="/articles%s">%s</a> / <span lang="ar">%s</span></p>'
            '<article class="post" lang="ar" dir="rtl"><h1>%s</h1><p class="meta">%s · %s</p><p class="lead">%s</p>%s</article><!--SEO:AD-->%s'
            % (q, esc(T[ui]["home"]), q, esc(ARTICLES_NAME[ui]), esc(a["title"]), esc(a["title"]), esc(a.get("date", "")),
               esc(S["ar"]["minutes"].format(n=_minutes(a["words"]))), esc(a.get("description", "")), html_body, more))
    org = {"@type": "Organization", "@id": base + "/#org", "name": BRAND["ar"], "url": base + "/",
           "logo": {"@type": "ImageObject", "url": base + "/icon-512.png"}}
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "Article", "@id": url + "#article", "headline": a["title"], "description": a.get("description", ""),
         "datePublished": a.get("date", ""), "dateModified": a.get("updated", a.get("date", "")), "inLanguage": "ar",
         "author": org, "publisher": org, "mainEntityOfPage": url, "image": base + "/og-image.png", "wordCount": a["words"]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": T["ar"]["home"], "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": ARTICLES_NAME["ar"], "item": base + "/articles"},
            {"@type": "ListItem", "position": 3, "name": a["title"], "item": url}]}]})
    # one text in Arabic: the Arabic address is the page search engines keep, whatever the frame's language
    return with_nonce(_shell(ui, base, "/articles/" + slug, a["title"] + " | " + BRAND["ar"], a.get("description", ""), body, ld,
                             nonce=nonce, extra_css=ARTICLE_CSS, canonical=url, alternates=False), nonce)


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
        if p not in legal.THIN_PAGES:  # the forms (contact, takedown) are not pages to find in a search engine
            urls += [base + "/" + p, base + "/" + p + "?lang=en"]
    urls.append(base + "/articles")
    urls += [base + "/articles/" + a["slug"] for a in content.articles()]
    for k in CATEGORIES:
        urls += [base + "/category/" + k, base + "/category/" + k + "?lang=en"]
    for r in conn.execute("SELECT key FROM authors a WHERE EXISTS (SELECT 1 FROM books WHERE author_key=a.key) ORDER BY ord"):
        for ui, q in (("ar", ""), ("en", "?lang=en")):
            if author_indexable(conn, r["key"], ui):
                urls.append(base + "/author/" + quote(r["key"]) + q)
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
