"""Server-rendered page for every book (/book/<id>/<slug>) plus the sitemaps that list them.

Search engines get real HTML (title, description, JSON-LD, related books), and visitors get a
readable details page with the best reading links.
"""
import html
import json
import math
import os
import re
import time
from urllib.parse import quote

from .catalog import CATEGORIES
from .textnorm import norm

BRAND = {"ar": "مكتبة الوراق", "en": "Al-Warraq Library"}
SITEMAP_PAGE = 40000  # URLs per sitemap file (Google allows 50,000)

LANG_NAMES = {
    "en": ("English", "الإنجليزية"), "ar": ("Arabic", "العربية"), "fr": ("French", "الفرنسية"),
    "de": ("German", "الألمانية"), "es": ("Spanish", "الإسبانية"), "it": ("Italian", "الإيطالية"),
    "pt": ("Portuguese", "البرتغالية"), "ru": ("Russian", "الروسية"), "nl": ("Dutch", "الهولندية"),
    "la": ("Latin", "اللاتينية"), "fi": ("Finnish", "الفنلندية"), "sv": ("Swedish", "السويدية"),
    "da": ("Danish", "الدنماركية"), "no": ("Norwegian", "النرويجية"), "pl": ("Polish", "البولندية"),
    "hu": ("Hungarian", "المجرية"), "cs": ("Czech", "التشيكية"), "zh": ("Chinese", "الصينية"),
    "ja": ("Japanese", "اليابانية"), "tr": ("Turkish", "التركية"), "el": ("Greek", "اليونانية"),
    "he": ("Hebrew", "العبرية"), "fa": ("Persian", "الفارسية"), "sa": ("Sanskrit", "السنسكريتية"),
    "ko": ("Korean", "الكورية"), "ro": ("Romanian", "الرومانية"), "ca": ("Catalan", "الكتالانية"),
}

T = {
    "ar": {
        "by": "المؤلف", "cat": "التصنيف", "lang": "اللغة", "src": "المصدر", "read": "اقرأ الكتاب",
        "find": "ابحث عن الكتاب", "more_author": "المزيد من كتب هذا المؤلف", "more_cat": "كتب أخرى من التصنيف نفسه",
        "ph": "ابحث بعنوان كتاب أو اسم مؤلف", "search": "بحث",
        "home": "الرئيسية", "all": "كل الكتب", "views": "مشاهدة", "likes": "إعجاب", "like": "أعجبني", "liked": "أعجبك", "similar": "كتب تشبه هذا الكتاب", "free": "كتاب مجاني ومسقط عنه حق النشر",
        "note": "الموقع فهرس يدلّك على المصادر المفتوحة ولا يستضيف الكتب. الكتب هنا في الملكية العامة في الولايات المتحدة، وقد يختلف وضعها في بلدك.",
        "page_gut": "صفحة الكتاب في Gutenberg", "page_ht": "HathiTrust", "arch": "Internet Archive", "ol": "Open Library",
        "other_lang": "English", "other_code": "en", "notfound": "لم نجد هذا الكتاب", "dir": "rtl",
        "src_gut": "مشروع غوتنبرغ", "src_ht": "مكتبة HathiTrust", "src_ws": "ويكي مصدر", "src_idx": "فهرس الوراق",
        "about": "نبذة عن الكتاب", "about_author": "نبذة عن المؤلف", "wiki": "المصدر: ويكيبيديا",
        "about_txt": "«{t}» كتاب {a}ضمن تصنيف «{c}»، مكتوب باللغة {l}. هو من الكتب الموجودة في الملكية العامة، فيمكنك قراءته مجاناً من المصدر المفتوح عبر الأزرار أعلاه، وإن أعجبك فاضغط «أعجبني» لتساعد غيرك على اكتشافه. وفي الأسفل كتب مشابهة قد تعجبك.",
        "about_by": "للمؤلف {a} ",
        "desc": "{t} {a}— كتاب مجاني ({l}، {c}). اقرأه أو ابحث عن نسخه المجانية من المصادر المفتوحة.",
    },
    "en": {
        "by": "Author", "cat": "Category", "lang": "Language", "src": "Source", "read": "Read the book",
        "find": "Find the book", "more_author": "More books by this author", "more_cat": "More in this category",
        "ph": "Search a title or an author", "search": "Search",
        "home": "Home", "all": "All books", "views": "views", "likes": "likes", "like": "Like", "liked": "Liked", "similar": "Similar books", "free": "Free public-domain book",
        "note": "This site is an index that points to open sources; it does not host the books. Books listed here are in the public domain in the United States and may be protected in your country.",
        "page_gut": "Gutenberg book page", "page_ht": "HathiTrust", "arch": "Internet Archive", "ol": "Open Library",
        "other_lang": "العربية", "other_code": "ar", "notfound": "Book not found", "dir": "ltr",
        "src_gut": "Project Gutenberg", "src_ht": "HathiTrust", "src_ws": "Wikisource", "src_idx": "Al-Warraq index",
        "about": "About this book", "about_author": "About the author", "wiki": "Source: Wikipedia",
        "about_txt": "\u201c{t}\u201d is a book {a}in the \u201c{c}\u201d category, written in {l}. It is in the public domain, so you can read it for free from the open source using the buttons above. If you enjoyed it, press Like to help others find it. Similar books are listed below.",
        "about_by": "by {a} ",
        "desc": "{t} {a}— free public-domain book ({l}, {c}). Read it online or find free editions from open sources.",
    },
}

CSS = """
:root{--bg:#F5F9FF;--card:#fff;--ink:#0E1B33;--muted:#5B6B86;--line:#E1EAF6;--brand:#1A6FDF;--brand-2:#5BC0FF;--brand-ink:#fff;--soft:#E3F0FF;--rose:#F0487E;--rose-soft:#FFE9F1;--btn:linear-gradient(135deg,#3E9BFF,#1A6FDF);--grad:linear-gradient(135deg,#5BC0FF,#1A6FDF 52%,#FF6B9A);--shadow:0 1px 2px rgba(14,27,51,.05),0 12px 32px -16px rgba(26,72,140,.3)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 "Readex Pro",system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif}
a{color:var(--brand)}
.wrap{max-width:980px;margin:0 auto;padding:0 16px}
.bar{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 80%,transparent);backdrop-filter:saturate(1.6) blur(14px);-webkit-backdrop-filter:saturate(1.6) blur(14px);border-bottom:1px solid var(--line)}
.bar .wrap{display:flex;align-items:center;gap:12px;min-height:62px}
.brand{display:flex;align-items:center;gap:9px;font:700 1.15rem/1 "Reem Kufi","Readex Pro",sans-serif;color:var(--ink);text-decoration:none;flex:none}
.brand svg{filter:drop-shadow(0 5px 12px rgba(26,111,223,.35));transition:transform .4s cubic-bezier(.34,1.56,.64,1)}.brand:hover svg{transform:rotate(-6deg) scale(1.06)}
.brand .lg-q{transform-box:view-box;transform-origin:25px 19px;animation:qw 3.2s ease-in-out infinite}@keyframes qw{30%{transform:rotate(-9deg)}60%{transform:rotate(5deg)}}
.sbox{flex:1 1 auto;min-width:0;display:flex;align-items:center;gap:6px;height:42px;padding-inline:14px 4px;background:var(--card);border:1.5px solid var(--line);border-radius:99px}
.sbox:focus-within{border-color:var(--brand-2);box-shadow:0 0 0 4px color-mix(in srgb,var(--brand-2) 22%,transparent)}
.sbox svg{flex:none;color:var(--muted)}.sbox input{flex:1 1 auto;min-width:0;border:0;background:transparent;outline:0;font:inherit;color:inherit;height:100%}
.sbox button{flex:none;height:34px;padding-inline:16px;border:0;border-radius:99px;background:var(--btn);color:var(--brand-ink);font:600 .92rem "Readex Pro",sans-serif;cursor:pointer}
.bar nav{display:flex;gap:14px;align-items:center;font-size:.92rem;flex:none}
@media (max-width:640px){.brand span{display:none}.sbox button{display:none}.bar nav a:first-child{display:none}}
.crumbs{font-size:.88rem;color:var(--muted);margin:18px 0 6px}.crumbs a{color:var(--muted)}
.book{display:grid;grid-template-columns:240px 1fr;gap:28px;margin:12px 0 28px;align-items:start}
.cover{position:relative;aspect-ratio:2/3;border-radius:14px;overflow:hidden;box-shadow:0 22px 44px -22px rgba(26,72,140,.55);background:linear-gradient(165deg,hsl(var(--h) 85% 92%),hsl(var(--h) 75% 84%));color:hsl(var(--h) 50% 22%)}
.cv-fb{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:space-between;padding:18px 16px;text-align:center}
.cv-cat{font-size:.72rem;letter-spacing:.04em;opacity:.75}
.cv-title{font:700 1.2rem/1.35 "Noto Naskh Arabic","Source Serif 4",Georgia,serif;overflow:hidden;display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical}
.cv-auth{font-size:.82rem;opacity:.85}
.cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .2s}.cover img.ok{opacity:1}
h1{margin:0 0 6px;font-size:clamp(1.5rem,4vw,2.1rem);line-height:1.3}
.by{margin:0 0 14px;color:var(--muted);font-size:1.05rem}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
.tag{background:var(--soft);color:var(--brand);border-radius:999px;padding:3px 12px;font-size:.84rem;text-decoration:none}.tag:nth-child(2){background:var(--rose-soft);color:var(--rose)}
.nums{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin:0 0 18px;color:var(--muted)}
.num{display:inline-flex;align-items:center;gap:6px}
.like{display:inline-flex;align-items:center;gap:6px;background:var(--card);color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font:inherit;cursor:pointer}
.like.on{color:#E5484D;border-color:#E5484D}
.like:hover{border-color:var(--brand)}
.btns{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 20px}
.btn{display:inline-block;background:var(--btn);color:var(--brand-ink);padding:10px 22px;border-radius:99px;font-weight:600;text-decoration:none;box-shadow:0 8px 18px -10px rgba(26,111,223,.8);transition:transform .25s cubic-bezier(.34,1.56,.64,1)}
.btn:hover{transform:translateY(-2px)}
.btn.alt{background:var(--card);color:var(--brand);border:1.5px solid var(--line);font-weight:500;box-shadow:none}.btn.alt:hover{border-color:var(--brand-2)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;margin:0 0 8px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:14px 18px;box-shadow:var(--shadow)}
dt{color:var(--muted)}dd{margin:0}
.desc{color:var(--muted);margin:0 0 16px}
.about{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:18px 20px;margin:18px 0;box-shadow:var(--shadow)}.about h2{margin:0 0 6px;font-size:1.1rem}.about p{margin:0 0 6px}.about small{color:var(--muted)}
h2{font-size:1.15rem;margin:26px 0 10px}
ul.rel{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}
ul.rel li{background:var(--card);border:1px solid var(--line);border-radius:14px;transition:transform .25s cubic-bezier(.34,1.56,.64,1),border-color .2s}ul.rel li:hover{transform:translateY(-2px);border-color:var(--brand-2)}
ul.rel a{display:block;padding:10px 14px;text-decoration:none;color:var(--ink)}
ul.rel small{display:block;color:var(--muted)}
footer{position:relative;margin:34px 0 28px;color:var(--muted);font-size:.84rem;padding-top:22px}footer::before{content:"";position:absolute;inset-inline:0;top:0;height:14px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='14' viewBox='0 0 28 14'%3E%3Cpath d='M14 1.5l1.7 3.8 3.8 1.7-3.8 1.7L14 12.5l-1.7-3.8L8.5 7l3.8-1.7z' fill='%23FF8FB3' fill-opacity='.75'/%3E%3Ccircle cx='1' cy='7' r='1' fill='%235BC0FF'/%3E%3Ccircle cx='27' cy='7' r='1' fill='%235BC0FF'/%3E%3C/svg%3E") center/28px 14px repeat-x}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.05;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 .1 0 0 0 0 .12 0 0 0 0 .2 0 0 0 .6 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
html[lang="ar"] h1{font-family:"Reem Kufi","Readex Pro",sans-serif;letter-spacing:0}
@media (max-width:640px){.book{grid-template-columns:1fr;justify-items:center}.cover{width:200px}.book>div{width:100%}dl{grid-template-columns:1fr}}
"""

LIKE_JS = r'''<script>(function(){var b=document.getElementById('likeBtn');if(!b)return;var heart=function(f){return '<svg width="18" height="18" viewBox="0 0 24 24" fill="'+f+'" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-4.4-9.3-9A5.4 5.4 0 0 1 12 6.2 5.4 5.4 0 0 1 21.3 12C19 16.6 12 21 12 21z"/></svg>';};
b.addEventListener('click',function(){b.disabled=true;fetch('/api/like/'+b.dataset.id,{method:'POST'}).then(function(r){return r.json()}).then(function(j){if(typeof j.likes!=='number')return;b.classList.toggle('on',j.liked);b.setAttribute('aria-pressed',j.liked);document.getElementById('likeN').textContent=j.likes;document.getElementById('likeTxt').textContent=j.liked?b.dataset.liked:b.dataset.like;document.getElementById('likeIco').innerHTML=heart(j.liked?'currentColor':'none');}).catch(function(){}).then(function(){b.disabled=false;});});})();</script>'''

_cache = {}


def _cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    val = fn()
    _cache[key] = (time.time() + ttl, val)
    return val


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def is_arabic(s: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", s or ""))


def slugify(title: str) -> str:
    words = re.findall(r"\w+", norm(title), re.UNICODE)[:8]
    return ("-".join(words))[:70] or "book"


def default_ui(row) -> str:
    return "ar" if (row["lang"] == "ar" or row["origin"] == "a") and (row["title_ar"] or is_arabic(row["title"])) else "en"


def book_title(row, ui: str) -> str:
    return (row["title_ar"] or row["title"]) if ui == "ar" else row["title"]


def book_author(row, ui: str, authors: dict) -> str:
    a = authors.get(row["author_key"]) if row["author_key"] else None
    if a:
        return a["ar"] if ui == "ar" and a["ar"] else a["en"]
    return (row["author_ar"] if ui == "ar" and row["author_ar"] else row["author_en"]) or ""


def canonical_path(row) -> str:
    ui = default_ui(row)
    return "/book/%d/%s" % (row["id"], quote(slugify(book_title(row, ui))))


def site_base(request) -> str:
    """The public address used in canonical links, sitemaps and robots.txt: SITE_URL, else the domain
    Railway gives the service (always https), else what the request says."""
    env = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if env:
        return env
    railway = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip().strip("/")
    if railway:
        return "https://" + railway
    return str(request.base_url).rstrip("/")


def lang_name(code: str, ui: str) -> str:
    n = LANG_NAMES.get((code or "").lower())
    return (n[1] if ui == "ar" else n[0]) if n else (code or "").upper()


def read_links(row, ui: str):
    """Returns (main_url, is_direct_read, [(label, url), ...])."""
    t = T[ui]
    last = (row["author_en"] or "").split(" ")[-1] if row["author_en"] else ""
    q = quote((row["title"] + " " + last).strip())
    arch = ("https://archive.org/search?query=" + q, t["arch"])
    ol = ("https://openlibrary.org/search?mode=everything&has_fulltext=true&q=" + q, t["ol"])
    if row["gid"]:
        g = row["gid"]
        return ("https://www.gutenberg.org/cache/epub/%d/pg%d-images.html" % (g, g), True,
                [("https://www.gutenberg.org/ebooks/%d" % g, t["page_gut"]), arch])
    if row["htid"]:
        h = quote(row["htid"])
        return ("https://babel.hathitrust.org/cgi/pt?id=" + h, True,
                [("https://babel.hathitrust.org/cgi/ls?q1=%s&lmt=ft" % quote(row["title"]), t["page_ht"]), arch])
    if row["ws"]:
        return (ws_url(row["ws"]), True,
                [] if row["cat"] == "poe" else [("https://archive.org/search?query=" + quote(row["title_ar"] or row["title"]), t["arch"]), ol])
    if row["origin"] == "a":
        name = quote(row["title_ar"] or row["title"])
        return ("https://ar.wikisource.org/w/index.php?search=" + name, False,
                [("https://archive.org/search?query=" + name, t["arch"]), ol])
    return ("https://www.gutenberg.org/ebooks/search/?query=" + q, False, [arch, ol])


def ws_url(page: str) -> str:
    return "https://ar.wikisource.org/wiki/" + quote(page.replace(" ", "_"))


def source_name(row, ui: str) -> str:
    t = T[ui]
    if row["gid"]:
        return t["src_gut"]
    if row["htid"]:
        return t["src_ht"]
    return t["src_ws"] if row["ws"] or row["origin"] == "a" else t["src_idx"]


def cover_candidates(row):
    c = []
    if row["gid"]:
        c.append("https://www.gutenberg.org/cache/epub/%d/pg%d.cover.medium.jpg" % (row["gid"], row["gid"]))
    return c  # HathiTrust blocks its covers on other sites: the page asks /api/cover (Open Library) instead


def _authors(conn) -> dict:
    return _cached("authors", 600, lambda: {r["key"]: {"en": r["en"], "ar": r["ar"]} for r in conn.execute("SELECT key, en, ar FROM authors")})


def related(conn, row):
    """Similar books: same author first, then neighbours in the same category (same language preferred)."""
    out, seen = [], {row["id"]}
    if row["author_key"]:
        for r in conn.execute("SELECT * FROM books WHERE author_key=? AND id!=? ORDER BY ord LIMIT 8", (row["author_key"], row["id"])):
            out.append(r); seen.add(r["id"])
    if len(out) < 12:
        for r in conn.execute(
                "SELECT * FROM books WHERE id BETWEEN ? AND ? AND cat=? AND lang=? AND id!=? LIMIT 24",
                (row["id"] - 600, row["id"] + 600, row["cat"], row["lang"], row["id"])):
            if r["id"] not in seen and len(out) < 12:
                out.append(r); seen.add(r["id"])
    return "similar", out


LOGO_SVG = ('<svg viewBox="0 0 48 48" width="36" height="36" aria-hidden="true"><defs><linearGradient id="gL" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#5BC0FF"/><stop offset=".55" stop-color="#1A6FDF"/><stop offset="1" stop-color="#FF6B9A"/></linearGradient></defs>'
            '<rect x="1" y="1" width="46" height="46" rx="15" fill="url(#gL)"/>'
            '<path d="M24 35c-4.6-3-9.4-3.6-14-2.2V16.6c4.6-1.4 9.4-.8 14 2.4z" fill="#fff"/>'
            '<path d="M24 35c4.6-3 9.4-3.6 14-2.2V16.6c-4.6-1.4-9.4-.8-14 2.4z" fill="#fff" fill-opacity=".82"/>'
            '<path class="lg-q" d="M36.5 6.5c-6.2 1.4-10.6 6.4-11.6 13.6 2.6-4.8 6.4-9 11.6-13.6z" fill="#fff"/></svg>')
SEARCH_ICON = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">'
               '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')


def not_found_html(ui="en") -> str:
    t = T[ui]
    return ("<!doctype html><html lang=\"%s\" dir=\"%s\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex\"><title>%s</title><style>%s</style></head><body><div class=\"wrap\"><p style=\"margin:60px 0\">%s — <a href=\"/\">%s</a></p></div></body></html>"
            % (ui, t["dir"], esc(t["notfound"]), CSS, esc(t["notfound"]), esc(t["home"])))


WIKI_JS = """<script>(function(){var s=document.getElementById('aa');if(!s)return;
var cand=[[s.dataset.ui,s.dataset.name],[s.dataset.ui==='ar'?'en':'ar',s.dataset.alt],['en',s.dataset.alt||s.dataset.name]];var i=0;
function next(){if(i>=cand.length)return;var c=cand[i++];if(!c[1])return next();
fetch('https://'+c[0]+'.wikipedia.org/api/rest_v1/page/summary/'+encodeURIComponent(c[1].replace(/ /g,'_'))+'?redirect=true').then(function(r){return r.ok?r.json():null}).then(function(j){
if(!j||j.type!=='standard'||!j.extract||j.extract.length<60)return next();
document.getElementById('aaT').textContent=j.extract.length>600?j.extract.slice(0,600).replace(/\\s+\\S*$/,'')+'\u2026':j.extract;
var a=document.getElementById('aaL'),u=(j.content_urls&&j.content_urls.desktop&&j.content_urls.desktop.page)||'';a.href=/^https:\\/\\/[a-z-]+\\.wikipedia\\.org\\//.test(u)?u:'#';s.hidden=false;}).catch(next);}
next();})();</script>"""


def render_book(conn, row, base: str, ui: str = "", numbers=(0, 0), liked: bool = False, nonce: str = "") -> str:
    d_ui = default_ui(row)
    ui = ui if ui in T else d_ui
    t = T[ui]
    authors = _authors(conn)
    title = book_title(row, ui)
    author = book_author(row, ui, authors)
    cat = CATEGORIES.get(row["cat"], CATEGORIES["gen"])
    cat_name = cat[ui]
    lang = lang_name(row["lang"], ui)
    main_url, direct, extra = read_links(row, ui)
    canon = base + canonical_path(row)
    covers = cover_candidates(row)
    desc = t["desc"].format(t=title, a=(("— %s " % author) if author else ""), l=lang, c=cat_name)
    page_title = ("%s — %s | %s" % (title, author, BRAND[ui])) if author else ("%s | %s" % (title, BRAND[ui]))

    book = {"@type": "Book", "@id": canon + "#book", "name": title, "url": canon, "inLanguage": row["lang"] or "en",
            "isAccessibleForFree": True, "genre": cat_name, "sameAs": main_url,
            "potentialAction": {"@type": "ReadAction", "target": main_url}}
    if author:
        book["author"] = {"@type": "Person", "name": author}
    if covers:
        book["image"] = covers[0]
    crumbs = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": t["home"], "item": base + "/"},
        {"@type": "ListItem", "position": 2, "name": cat_name, "item": base + "/category/" + row["cat"]},
        {"@type": "ListItem", "position": 3, "name": title, "item": canon}]}
    ld = {"@context": "https://schema.org", "@graph": [book, crumbs]}
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")

    og_img = '<meta property="og:image" content="%s">' % esc(covers[0]) if covers else ""
    other_ui = "en" if ui == "ar" else "ar"

    btns = '<a class="btn" href="%s" target="_blank" rel="noopener">%s</a>' % (esc(main_url), esc(t["read" if direct else "find"]))
    btns += "".join('<a class="btn alt" href="%s" target="_blank" rel="noopener">%s</a>' % (esc(u), esc(n)) for u, n in extra)

    tags = '<a class="tag" href="/category/%s">%s</a>' % (esc(row["cat"]), esc(cat_name))
    tags += '<span class="tag">%s</span>' % esc(lang)
    views, likes = numbers
    heart = '<svg width="18" height="18" viewBox="0 0 24 24" fill="%s" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-4.4-9.3-9A5.4 5.4 0 0 1 12 6.2 5.4 5.4 0 0 1 21.3 12C19 16.6 12 21 12 21z"/></svg>'
    eye = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>'
    numbers_html = (
        '<div class="nums"><span class="num">%s<b>%d</b> %s</span>'
        '<button type="button" id="likeBtn" class="like%s" aria-pressed="%s" data-id="%d" data-like="%s" data-liked="%s">'
        '<span id="likeIco">%s</span><span id="likeTxt">%s</span> · <b id="likeN">%d</b></button></div>'
        % (eye, views, esc(t["views"]), " on" if liked else "", "true" if liked else "false", row["id"], esc(t["like"]), esc(t["liked"]),
           heart % ("currentColor" if liked else "none"), esc(t["liked"] if liked else t["like"]), likes))

    facts = ""
    if author:
        link = ('<a href="/author/%s">%s</a>' % (esc(quote(row["author_key"])), esc(author))) if row["author_key"] else esc(author)
        facts += "<dt>%s</dt><dd>%s</dd>" % (esc(t["by"]), link)
    facts += "<dt>%s</dt><dd>%s</dd><dt>%s</dt><dd>%s</dd><dt>%s</dt><dd>%s</dd>" % (
        esc(t["cat"]), esc(cat_name), esc(t["lang"]), esc(lang), esc(t["src"]), esc(source_name(row, ui)))

    key, rel_rows = related(conn, row)
    rel_html = ""
    if rel_rows:
        items = []
        for r in rel_rows:
            rt, ra = book_title(r, ui), book_author(r, ui, authors)
            items.append('<li><a href="/book/%d">%s%s</a></li>' % (r["id"], esc(rt), ("<small>%s</small>" % esc(ra)) if ra else ""))
        rel_html = "<h2>%s</h2><ul class=\"rel\">%s</ul>" % (esc(t[key]), "".join(items))

    about_html = '<section class="about"><h2>%s</h2><p>%s</p></section>' % (
        esc(t["about"]), esc(t["about_txt"].format(t=title, a=(t["about_by"].format(a=author) if author else ""), c=cat_name, l=lang)))
    if author:
        about_html += ('<section class="about" id="aa" hidden data-name="%s" data-alt="%s" data-ui="%s" data-src="%s"><h2>%s</h2><p id="aaT"></p>'
                       '<small><a id="aaL" href="#" target="_blank" rel="noopener">%s</a></small></section>'
                       % (esc(author), esc(row["author_en"] or ""), ui, esc(t["wiki"]), esc(t["about_author"]), esc(t["wiki"])))
    toggle = "?lang=" + other_ui
    cv_script = (
        "<script>(function(){var im=document.getElementById('cvimg');if(!im)return;var src=%s;var i=0;"
            "function done(ok){if(ok){im.classList.add('ok');}else next();}"
            "function next(){if(i<src.length){im.src=src[i++];}else{fetch('/api/cover/%d').then(function(r){return r.json()}).then(function(j){if(j&&j.url&&!im.dataset.ol){im.dataset.ol=1;im.src=j.url;}}).catch(function(){});}}"
            "im.addEventListener('load',function(){if(im.naturalWidth<40||im.naturalHeight<40){next();}else{done(true);}});"
            "im.addEventListener('error',function(){next();});next();})();</script>"
            % (json.dumps(covers), row["id"]))

    page = """<!doctype html>
<html lang="{ui}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="book">
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:site_name" content="{brand}">
{og_img}
<meta property="og:locale" content="{locale}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{page_title}">
<meta name="twitter:description" content="{desc}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@500;700&family=Readex+Pro:wght@400;500;600;700&family=Reem+Kufi:wght@700&family=Source+Serif+4:wght@600;700&display=swap">
<script type="application/ld+json">{ld}</script>
<style>{css}</style>
</head>
<body>
<header class="bar"><div class="wrap"><a class="brand" href="/">{logo}<span>{brand}</span></a>
<form class="sbox" action="/#browse" method="get" role="search">{search_icon}<input type="search" name="q" placeholder="{ph}" aria-label="{ph}"><button type="submit">{search}</button></form>
<nav><a href="/#browse">{all}</a><a href="{toggle}" hreflang="{other_ui}" rel="nofollow">{other_lang}</a></nav></div></header>
<main class="wrap">
<p class="crumbs"><a href="/">{home}</a> / <a href="/category/{catkey}">{cat_name}</a></p>
<article class="book">
<div class="cover" style="--h:{hue}"><span class="cv-fb"><span class="cv-cat">{cat_name}</span><span class="cv-title">{title}</span><span class="cv-auth">{author}</span></span><img id="cvimg" alt="{alt}" decoding="async" referrerpolicy="no-referrer"></div>
<div>
<h1>{title}</h1>
{by}
<div class="tags">{tags}</div>
{numbers_html}
<div class="btns">{btns}</div>
<p class="desc">{desc}</p>
<dl>{facts}</dl>
</div>
</article>
{about}
{rel}
<footer>{note}</footer>
</main>
{cv_script}
{like_js}
{wiki_js}
</body>
</html>
""".format(ui=ui, dir=t["dir"], page_title=esc(page_title), desc=esc(desc), canon=esc(canon), brand=esc(BRAND[ui]), og_img=og_img,
           ld=ld_json, css=CSS, all=esc(t["all"]), toggle=toggle, other_ui=other_ui, other_lang=esc(t["other_lang"]),
           home=esc(t["home"]), catkey=esc(row["cat"]), cat_name=esc(cat_name), hue=int(cat["hue"]), title=esc(title), author=esc(author),
           alt=esc(title), by=('<p class="by">%s</p>' % esc(author)) if author else "", tags=tags, numbers_html=numbers_html, btns=btns, facts=facts, rel=rel_html, about=about_html,
           note=esc(t["note"]), cv_script=cv_script, like_js=LIKE_JS, wiki_js=WIKI_JS,
           logo=LOGO_SVG, search_icon=SEARCH_ICON, ph=esc(t["ph"]), search=esc(t["search"]),
           locale="ar_AR" if ui == "ar" else "en_US")
    # the Content-Security-Policy of this response only lets scripts carrying its nonce run
    return page.replace("<script", '<script nonce="%s"' % esc(nonce)) if nonce else page


# ---------- sitemaps ----------

def _total(conn) -> int:
    return _cached("total", 300, lambda: conn.execute("SELECT COUNT(*) FROM books").fetchone()[0])


def sitemap_index(conn, base: str) -> str:
    n = max(1, math.ceil(_total(conn) / SITEMAP_PAGE))
    items = ["<sitemap><loc>%s/sitemap-main.xml</loc></sitemap>" % base]
    items += ["<sitemap><loc>%s/sitemap-books-%d.xml</loc></sitemap>" % (base, i) for i in range(1, n + 1)]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</sitemapindex>\n' % "\n".join(items)


def sitemap_main(base: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            "<url><loc>%s/</loc></url>\n</urlset>\n" % base)


def sitemap_books(conn, base: str, page: int):
    rows = conn.execute("SELECT id, title, title_ar, lang, origin FROM books ORDER BY id LIMIT ? OFFSET ?",
                        (SITEMAP_PAGE, (page - 1) * SITEMAP_PAGE)).fetchall()
    if not rows:
        return None
    out = []
    for r in rows:
        out.append("<url><loc>%s%s</loc></url>" % (base, html.escape(canonical_path(r))))
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % "\n".join(out)