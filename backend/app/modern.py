"""Modern Arabic books that are not in the public domain, listed with a link to the page that shows them.

Two sources, both legal to list:
  * Safahat (formerly the Hindawi Foundation library): every book there is free to read, published under an
    agreement with its rights holders. Its robots.txt allows /books/.
  * Open Library: its catalogue data is public domain (CC0). Most modern Arabic records only describe the book;
    the button says "view", never "read".
The site keeps catalogue facts only (title, author, publisher, year, subjects, page count): never a description
or any of the text. Only titles written in Arabic script are taken from Open Library (most of its Arabic
records are romanized, which Arabic readers can neither read nor search).

    python -m app.modern safahat FILE.jsonl      # collect the Safahat catalogue (~3,400 books, about an hour)
    python -m app.modern openlibrary FILE.jsonl  # collect Arabic-script Open Library works (about 45 minutes)
    python -m app.modern import FILE.jsonl ...   # add them to the database (replaces earlier rows of the same source)

Collecting is polite: one request at a time, a pause between requests, an identifying User-Agent, and it
resumes where it stopped.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from .catalog import CATEGORIES
from .textnorm import norm

OL_KIND = 4       # books.curated value for Open Library rows (0 Gutenberg, 1 hand-picked, 2 HathiTrust, 3 Wikisource)
SAFAHAT_KIND = 5  # books.curated value for Safahat (Hindawi) rows
KINDS = (OL_KIND, SAFAHAT_KIND)
SAFAHAT_ORD_BASE = 50_000      # free to read: right after the hand-picked books
OL_POPULAR_ORD_BASE = 95_000   # Open Library books people want to read: before the big public-domain imports
ARABIC_HORROR_ORD_BASE = 60_000  # Arabic horror from Open Library (a few dozen): right after Safahat's
OL_POPULAR_MAX = 4_999
OL_ORD_BASE = 2_000_000        # the rest: after HathiTrust, before single poems
UA = "AlWarraqLibrary/2.0 (+https://warraq-fullstack-production.up.railway.app; alwarraqibrary@gmail.com)"
SAFAHAT = "https://www.safahat.org"
OL_SEARCH = "https://openlibrary.org/search.json"
OL_FIELDS = ("key,title,subtitle,author_name,first_publish_year,publisher,subject,number_of_pages_median,"
             "ebook_access,cover_i,want_to_read_count,ratings_count,edition_count")

ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-zÀ-ɏḀ-ỿ]")


# ---------- helpers ----------

def _get(url: str, tries: int = 4, timeout: int = 120) -> bytes:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ar,en"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1) * (3 if e.code == 429 else 1))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1))
    return b""


def arabic_part(text: str) -> str:
    """The Arabic-script part of a title or name written in two scripts ("أرض زيكولا Ard Zikola" -> "أرض زيكولا")."""
    text = html.unescape(text or "").strip()
    if not ARABIC.search(text):
        return ""
    words = text.split()
    keep = [w for w in words if not LATIN.search(w)]
    out = " ".join(keep).strip(" -–—:/|،,.()[]")
    return out if ARABIC.search(out) else ""


def is_arabic_title(text: str) -> bool:
    letters = [c for c in text or "" if c.isalpha()]
    return bool(letters) and sum(1 for c in letters if ARABIC.match(c)) >= 0.6 * len(letters)


# ---------- categories ----------

SAFAHAT_CATS = {
    "detective.fiction": "mys", "novels": "nov", "science.fiction": "nov", "literature": "nov", "literary.criticism": "gen",
    "poetry": "poe", "plays": "dra", "children.stories": "chi", "travel.literature": "tra", "geography": "tra",
    "religions": "rel", "history": "his", "biographies": "bio", "philosophy": "phi", "psychology": "psy",
    "social.sciences": "psy", "politics": "pol", "economics": "pol", "business": "pol", "health": "med",
    "science": "sci", "environmental.sciences": "sci", "technology": "eng", "arts": "art", "linguistics": "gen",
}
# Open Library subjects (English or Arabic), first match wins; English words match whole words only
# (so "succession" in inheritance law is not "success"). Literary forms come first ("Religion -- Fiction" is a
# novel, "Conduct of life -- Juvenile fiction" a children's book), then religion ("Conduct of life" on an Islamic
# book of manners is religion, not self-development).
SUBJECT_RULES = [
    ("hor", ["horror", "horror tales", "horror fiction", "ghost stories", "occult fiction", "vampires", "paranormal fiction",
             "haunted houses", "قصص الرعب", "روايات الرعب"]),
    ("mys", ["detective and mystery stories", "mystery fiction", "detective fiction", "crime fiction", "الروايات البوليسية",
             "القصص البوليسية"]),
    ("chi", ["juvenile", "juvenile fiction", "juvenile literature", "children's stories", "أطفال"]),
    ("nov", ["fiction", "novel", "novels", "short stories", "روايات", "رواية", "قصص"]),
    ("poe", ["poetry", "poems", "شعر"]),
    ("dra", ["drama", "plays", "theater", "مسرح"]),
    ("rel", ["islam", "islamic", "koran", "qur'an", "quran", "hadith", "hadiths", "sunnah", "sunna", "fiqh", "prophet",
             "religion", "religious", "theology", "sufism", "muslims", "إسلام", "فقه", "الحديث النبوي", "الحديث الشريف"]),
    ("dev", ["self-actualization", "self-help", "self-help techniques", "self-realization", "success", "conduct of life",
             "motivation", "personal development", "self-esteem", "happiness", "emotional intelligence",
             "time management", "تطوير الذات", "تنمية بشرية", "التنمية البشرية", "النجاح"]),
    ("psy", ["psychology", "sociology", "social", "family", "women", "marriage", "علم النفس", "اجتماع"]),
    ("med", ["medicine", "health", "diseases", "nutrition", "طب", "صحة"]),
    ("pol", ["politic", "politics", "economic", "economics", "business", "management", "law", "finance", "سياسة", "اقتصاد", "قانون"]),
    ("bio", ["biography", "memoir", "memoirs", "سيرة", "مذكرات"]),
    ("his", ["history", "تاريخ"]),
    ("phi", ["philosophy", "ethics", "فلسفة"]),
    ("tra", ["travel", "description and travel", "geography", "رحلات"]),
    ("eng", ["engineering", "technology", "computer", "computers", "تقنية", "هندسة"]),
    ("mat", ["mathematics", "astronomy", "رياضيات"]),
    ("sci", ["science", "biology", "chemistry", "physics", "علوم"]),
    ("art", ["art", "arts", "music", "architecture", "cooking", "فنون", "موسيقى"]),
]
# modern books usually reach Open Library without subjects: authors known for one kind of book give it away
# Arab horror writers: their books are horror even when they arrive without a subject
HORROR_WRITERS = ["حسن الجندي", "أسامة المسلم", "أسامة مسلم", "تامر إبراهيم", "عمرو المنوفي", "محمد عصمت", "شريف عبد الهادي",
                  "منال عبد الحميد", "أحمد يونس",
                  # the classics of world horror, as their translators spell them
                  "ماري شيلي", "برام ستوكر", "هوارد فيليبس لافكرافت", "إتش بي لافكرافت", "شيريدان لو فانو", "ألجرنون بلاكوود",
                  "آرثر ماكين", "أمبروز بيرس", "ويليام هوب هودجسون", "إم آر جيمس"]
NOVELISTS = ["عمرو عبد الحميد", "أحمد مراد", "أحمد خالد توفيق", "خولة حمدي",
             "محمد صادق", "أحلام مستغانمي", "يوسف زيدان", "رضوى عاشور", "سعود السنعوسي", "علاء الأسواني", "الطيب صالح",
             "غسان كنفاني", "عبد الرحمن منيف", "نجيب محفوظ", "إحسان عبد القدوس", "يوسف السباعي", "محمد المنسي قنديل",
             "بهاء طاهر", "أحمد سعداوي", "إبراهيم نصر الله", "واسيني الأعرج", "حنان الشيخ", "ربيع جابر", "جبرا إبراهيم جبرا",
             "حنا مينه", "محمد شكري", "الطاهر وطار", "عبده خال", "رجاء عالم", "يوسف إدريس", "صنع الله إبراهيم",
             "إبراهيم الكوني", "جمال الغيطاني", "خيري شلبي", "محمد عبد الحليم عبد الله", "منى المرشود", "حمور زيادة",
             "شكري المبخوت", "أثير عبد الله النشمي", "إبراهيم عيسى", "أحمد آل حمدان", "منذر القباني", "تامر إبراهيم"]
SELF_HELP = ["إبراهيم الفقي", "محمد طه", "أحمد الشقيري", "كريم الشاذلي", "صلاح الراشد", "ياسر حارب", "أحمد عمارة",
             "يوسف الحسيني", "فهد عامر الأحمدي"]  # not preachers who also write self-help: their books are mostly religion
_KNOWN = {norm(n).replace(" ", ""): cat for cat, names in (("nov", NOVELISTS), ("dev", SELF_HELP), ("hor", HORROR_WRITERS))
          for n in names}
LITERARY = ("nov", "poe", "dra", "chi", "hor", "mys")  # forms an author keeps from book to book
# horror in an Arabic title (series and words that never mean anything else)
HORROR_TITLE = ["ما وراء الطبيعه", "قصص رعب", "قصه رعب", "حكايه رعب", "روايه رعب", "قصص الرعب", "بيت الاشباح", "مصاص دماء",
                "دراكولا", "الدراكولا", "فرانكنشتاين", "فرانكنستين", "جيكل", "مستر هايد",
                "مصاصي الدماء", "مصاصه دماء", "البيت المسكون", "المنزل المسكون"]


def known_author_category(name: str) -> str:
    return _KNOWN.get(norm(name).replace(" ", ""), "")


# self-development titles ("how to win friends", "the power of the subconscious"...), checked on the normalized title
DEV_TITLE = ["تطوير الذات", "تنميه بشريه", "التنميه البشريه", "الثقه بالنفس", "التفكير الايجابي", "العقل الباطن",
             "الذكاء العاطفي", "قوه العقل", "قوه التفكير", "كيف تكسب", "كيف تصبح", "كيف تنجح", "اسرار النجاح", "سر النجاح",
             "طريق النجاح", "فن النجاح", "العادات السبع", "عادات الناجحين", "اداره الوقت", "فن التعامل", "فن الحياه",
             "استمتع بحياتك", "لا تحزن", "طريق السعاده", "صناعه السعاده", "تحفيز الذات", "قوه الارداه", "قوه الاراده", "غير حياتك", "عقدك النفسيه"]


def _dev_title(title: str) -> bool:
    t = " " + norm(title) + " "
    return any(" " + norm(k) + " " in t or t.startswith(" " + norm(k)) for k in DEV_TITLE)


_SUBJECT_COMPILED = [(cat, re.compile("|".join(
    (r"(?<![a-z])" + re.escape(k) + r"(?![a-z])") if LATIN.search(k) else re.escape(k) for k in keys)))
    for cat, keys in SUBJECT_RULES]


def ol_category(title: str, subjects, fallback: bool = True) -> str:
    """Category from the title and the subjects; "" when neither says anything and fallback is off."""
    if _dev_title(title):
        return "dev"
    if _horror_title(title) and not re.search(r"islam|koran|qur|hadith|religio|politic", " ".join(subjects or []), re.I):
        return "hor"  # "the jinn" in Islamic studies or "terror" in politics are not horror
    if any(k in norm(title) for k in ("رسول الله", "صلي الله عليه وسلم", "سيره النبي", "السيره النبويه")):
        return "rel"
    text = " | ".join(subjects or []).lower()
    serious = re.search(r"islam|koran|qur|hadith|religio|theolog|miracle|politic|histor|military|folklore", text)  # not horror
    for cat, pattern in _SUBJECT_COMPILED:
        if pattern.search(text) and not (cat == "hor" and serious):
            return cat
    from .wikisource import ar_category
    cat = ar_category(title)
    return cat if fallback or cat != "gen" else ""


def _horror_title(title: str) -> bool:
    t = " " + norm(title) + " "
    return any(" " + norm(k) + " " in t for k in HORROR_TITLE)


def safahat_category(title: str, slugs, authors=None) -> str:
    if _dev_title(title):
        return "dev"
    fiction = set(slugs or []) & {"novels", "literature", "science.fiction", "detective.fiction"}
    if fiction and (_horror_title(title) or known_author_category(" ".join(authors or [])) == "hor"):
        return "hor"  # tales of horror, and the classic horror writers in translation
    if "detective.fiction" in (slugs or []):
        return "mys"  # crime and mystery novels
    for s in slugs or []:
        if s in SAFAHAT_CATS:
            return SAFAHAT_CATS[s]
    from .wikisource import ar_category
    return ar_category(title)


# ---------- collecting: Safahat ----------

def _done_keys(path: str, field: str):
    keys = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    keys.add(json.loads(line)[field])
                except (ValueError, KeyError):
                    pass
    return keys


def parse_safahat_list(page: str):
    """[(id, title)] from one listing page."""
    out = []
    for m in re.finditer(r"href='/books/(\d{6,})/'.*?alt=\"(?:كتاب بعنوان )?([^\"]*)\"", page, re.S):
        out.append((m.group(1), html.unescape(m.group(2)).strip()))
    return out


def parse_safahat_book(page: str) -> dict:
    art = re.search(r'<article class="book">(.*?)</article>', page, re.S)
    body = art.group(1) if art else page
    title = re.search(r"<h2>\s*(.*?)\s*</h2>", body, re.S)
    author_div = re.search(r'<div class="author">(.*?)</div>', body, re.S)
    people = re.findall(r'href="/contributors/\d+/">\s*([^<]+?)\s*<', author_div.group(1)) if author_div else []
    tags = re.search(r'<ul class="tags">(.*?)</ul>', body, re.S)
    slugs = re.findall(r'href="/books/categories/([a-z.]+)/"', tags.group(1)) if tags else []
    translated = bool(author_div and re.search(r"ترجم", author_div.group(1)))
    return {"title": html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else "",
            "authors": [html.unescape(p) for p in people], "cats": slugs, "translated": translated}


def harvest_safahat(out_path: str, pause: float = 1.0, log=print) -> int:
    done = _done_keys(out_path, "id")
    listed = []
    n = 1
    while True:
        try:
            items = parse_safahat_list(_get("%s/books/%d/" % (SAFAHAT, n)).decode("utf-8", "replace"))
        except urllib.error.HTTPError:
            if n == 1:
                raise
            items = []  # past the last page the site answers with a server error, not an empty page
        if not items:
            break
        listed += items
        n += 1
        time.sleep(pause)
    log("Safahat: %d books listed on %d pages, %d already collected" % (len(listed), n - 1, len(done)))
    added = 0
    with open(out_path, "a", encoding="utf-8") as f:
        for i, (bid, list_title) in enumerate(listed):
            if bid in done:
                continue
            try:
                rec = parse_safahat_book(_get("%s/books/%s/" % (SAFAHAT, bid)).decode("utf-8", "replace"))
            except urllib.error.HTTPError as e:
                log("  skip %s (HTTP %d)" % (bid, e.code))
                continue
            rec.update({"src": "safahat", "id": bid, "rank": i, "title": rec["title"] or list_title})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            added += 1
            if added % 200 == 0:
                log("  %d books collected" % added)
            time.sleep(pause)
    return added


# ---------- collecting: Open Library ----------

def _ol_partitions():
    yield "first_publish_year:[* TO 1899]"
    for y in range(1900, time.gmtime().tm_year + 2):
        yield "first_publish_year:%d" % y
    yield "-first_publish_year:[* TO *]"


def harvest_openlibrary(out_path: str, pause: float = 1.0, log=print) -> int:
    """Every Arabic Open Library work (one year at a time, so paging stays shallow), keeping Arabic-script titles."""
    state = out_path + ".done"
    finished = set(open(state, encoding="utf-8").read().split("\n")) if os.path.exists(state) else set()
    kept = 0
    with open(out_path, "a", encoding="utf-8") as f, open(state, "a", encoding="utf-8") as st:
        for part in _ol_partitions():
            if part in finished:
                continue
            page, seen = 1, 0
            while True:
                q = urllib.parse.urlencode({"q": "language:ara AND " + part, "fields": OL_FIELDS, "limit": 1000, "page": page})
                data = json.loads(_get(OL_SEARCH + "?" + q))
                docs = data.get("docs", [])
                for d in docs:
                    title = arabic_part(d.get("title", ""))
                    if not title or not is_arabic_title(d.get("title", "")) and len(title) < 4:
                        continue
                    rec = {"src": "openlibrary", "id": d["key"].rsplit("/", 1)[-1], "title": title,
                           "subtitle": arabic_part(d.get("subtitle", "")), "authors": d.get("author_name", [])[:3],
                           "year": d.get("first_publish_year"), "publishers": (d.get("publisher") or [])[:2],
                           "subjects": (d.get("subject") or [])[:15], "pages": d.get("number_of_pages_median"),
                           "access": d.get("ebook_access"), "cover": d.get("cover_i"),
                           "want": d.get("want_to_read_count", 0), "ratings": d.get("ratings_count", 0),
                           "editions": d.get("edition_count", 0)}
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    kept += 1
                seen += len(docs)
                f.flush()
                if len(docs) < 1000 or seen >= data.get("numFound", 0):
                    break
                page += 1
                time.sleep(pause)
            st.write(part + "\n")
            st.flush()
            log("Open Library %s: %d works, %d Arabic-script titles kept so far" % (part, seen, kept))
            time.sleep(pause)
    return kept


# ---------- adding to the database ----------

def _records(paths):
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


PERSIAN = re.compile("[گپچژکی]")  # letters Arabic does not use: a Persian or Urdu title
ADULT = re.compile(r"(?<![a-z])(sex|sexual|erotic|erotica)(?![a-z])|جنس", re.I)  # kept off a family library (and AdSense)


def fix_name(name: str) -> str:
    """'مسلم، أسامة' (library catalogue order) -> 'أسامة مسلم'; no tatweel, no trailing dates."""
    n = html.unescape(name or "").replace("ـ", "").strip()
    n = re.sub(r"[\s,،]*\d{3,4}\s*-\s*(\d{3,4})?\.?$", "", n).strip()
    if ARABIC.search(n):
        parts = [p.strip() for p in re.split(r"[،,]", n) if p.strip()]
        if len(parts) == 2:
            n = parts[1] + " " + parts[0]
    return n.strip(" .")


def _names(authors):
    """(Arabic name, Latin name) from a list of author names in either script."""
    ar = next((fix_name(arabic_part(a)) for a in authors if arabic_part(a)), "")
    en = next((a.strip(" .") for a in authors if a and not ARABIC.search(a)), "")
    return ar, en


def _wanted(rec) -> bool:
    return not PERSIAN.search(rec["title"]) and not ADULT.search(" | ".join(rec.get("subjects") or []))


def safahat_url(book_id: str) -> str:
    return "%s/books/%s/" % (SAFAHAT, book_id)


def ol_url(work_id: str) -> str:
    return "https://openlibrary.org/works/" + work_id


def import_files(conn, paths) -> dict:
    from .wikisource import _author_keys
    records = list(_records(paths))
    saf = [r for r in records if r.get("src") == "safahat" and r.get("title")]
    ol = [r for r in records if r.get("src") == "openlibrary" and r.get("title") and _wanted(r)]
    kinds = ([SAFAHAT_KIND] if saf else []) + ([OL_KIND] if ol else [])
    # a book keeps its id (and so its address, likes and views) when its source is imported again
    old_ids = {(r["curated"], r["ext"]): r["id"] for r in conn.execute(
        "SELECT id, curated, ext FROM books WHERE curated IN (%s)" % ",".join("?" * len(KINDS)), KINDS)}
    for k in kinds:  # a source is replaced as a whole
        conn.execute("DELETE FROM cover_cache WHERE book_id IN (SELECT id FROM books WHERE curated=?)", (k,))
        conn.execute("DELETE FROM books WHERE curated=?", (k,))
    keys = _author_keys(conn)
    info = {r["key"]: (r["en"], r["ar"]) for r in conn.execute("SELECT key, en, ar FROM authors")}
    # what the library already has in Arabic (titles alone, and title + author)
    have = set()
    for r in conn.execute("SELECT title, title_ar, author_en, author_ar FROM books WHERE lang='ar'"):
        t = norm(r["title_ar"] or r["title"])
        have.add(t + "|" + norm(r["author_ar"] or r["author_en"]))
    if not saf:  # Open Library alone: still never list a Safahat book twice
        for r in conn.execute("SELECT title, author_ar, author_en FROM books WHERE curated=?", (SAFAHAT_KIND,)):
            have.add(norm(r["title"]) + "|" + norm(r["author_ar"] or r["author_en"]))

    rows, covers, seen = [], [], set()

    def add(rec, kind, ord_, cat, cover, extra):
        a_ar, a_en = _names(rec.get("authors") or [])
        key = keys.get(norm(a_ar)) or keys.get(norm(a_en)) or ""
        if key:
            a_en, a_ar = info[key][0] or a_en, info[key][1] or a_ar
        dup = norm(rec["title"]) + "|" + norm(a_ar or a_en)
        if dup in have or dup in seen:
            return
        seen.add(dup)
        origin = "w" if rec.get("translated") or (a_en and not a_ar) else "a"
        rows.append((old_ids.get((kind, rec["id"])), rec["id"], rec["title"], rec["title"], key, a_en or a_ar, a_ar, cat, origin, kind, ord_,
                     norm(" ".join([rec["title"], a_en, a_ar])), json.dumps(extra, ensure_ascii=False) if extra else None))
        if cover:
            covers.append((rec["id"], kind, cover))

    for rec in sorted(saf, key=lambda r: r.get("rank", 0)):
        add(rec, SAFAHAT_KIND, SAFAHAT_ORD_BASE + rec.get("rank", 0), safahat_category(rec["title"], rec.get("cats"), rec.get("authors")),
            "https://downloads.hindawi.org/covers/304x406/%s.jpg" % rec["id"], None)
    # most modern novels come without subjects: they take the category of the author's other books
    def who(rec):
        a_ar, a_en = _names(rec.get("authors") or [])
        return norm(a_ar or a_en)

    first = {r["id"]: ol_category(r["title"], r.get("subjects"), fallback=False) for r in ol}
    votes = {}  # author -> {category: books}
    for rec, cat in [(r, safahat_category(r["title"], r.get("cats"), r.get("authors"))) for r in saf] + [(r, first[r["id"]]) for r in ol]:
        if cat not in ("", "gen") and who(rec):
            v = votes.setdefault(who(rec), {})
            v[cat] = v.get(cat, 0) + 1

    def category(rec):
        if first[rec["id"]]:
            return first[rec["id"]]
        known = known_author_category(who(rec))
        if known:
            return known
        v = votes.get(who(rec))
        if v:  # the author's other books: only for literary forms, which an author keeps
            cat, n = max(v.items(), key=lambda kv: kv[1])
            if cat in LITERARY and n >= 0.6 * sum(v.values()):
                return cat
        return ol_category(rec["title"], rec.get("subjects"))

    popular = sorted(ol, key=lambda r: (-(r.get("want") or 0), -(r.get("ratings") or 0), -(r.get("editions") or 0),
                                         -(r.get("year") or 0), r["title"]))
    for i, rec in enumerate(popular):
        cat = category(rec)
        wanted = (rec.get("want") or 0) + (rec.get("ratings") or 0) > 0 or (rec.get("editions") or 0) >= 3
        if cat == "hor":  # the rare Arabic horror books: first in their category, before the world classics
            ord_ = ARABIC_HORROR_ORD_BASE + i
        else:
            ord_ = OL_POPULAR_ORD_BASE + i if wanted and i <= OL_POPULAR_MAX else OL_ORD_BASE + i
        title = rec["title"] + ((": " + rec["subtitle"]) if rec.get("subtitle") else "")
        extra = {k: v for k, v in (("year", rec.get("year")), ("pub", (rec.get("publishers") or [""])[0]),
                                   ("pages", rec.get("pages")), ("subjects", [s for s in (rec.get("subjects") or []) if ARABIC.search(s)][:6]))
                 if v}
        add(dict(rec, title=title), OL_KIND, ord_, cat,
            "https://covers.openlibrary.org/b/id/%d-M.jpg" % int(rec["cover"]) if rec.get("cover") else "", extra)

    conn.executemany(
        "INSERT INTO books(id,gid,htid,ws,ext,title,title_ar,author_key,author_en,author_ar,cat,origin,lang,curated,ord,search,info)"
        " VALUES(?,NULL,NULL,NULL,?,?,?,?,?,?,?,?,'ar',?,?,?,?)", rows)
    ids = {(r["ext"], r["curated"]): r["id"] for r in
           conn.execute("SELECT id, ext, curated FROM books WHERE curated IN (%s)" % ",".join("?" * len(KINDS)), KINDS)}
    conn.executemany("INSERT OR REPLACE INTO cover_cache(book_id,url) VALUES(?,?)",
                     [(ids[(e, k)], u) for e, k, u in covers if (e, k) in ids])
    conn.commit()
    return {"safahat": sum(1 for r in rows if r[9] == SAFAHAT_KIND), "openlibrary": sum(1 for r in rows if r[9] == OL_KIND),
            "skipped_duplicates": len(saf) + len(ol) - len(rows)}


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in ("safahat", "openlibrary", "import"):
        print(__doc__)
        return 1
    if sys.argv[1] == "safahat":
        print("collected", harvest_safahat(sys.argv[2]))
    elif sys.argv[1] == "openlibrary":
        print("collected", harvest_openlibrary(sys.argv[2]))
    else:
        from . import db
        conn = db.connect()
        db.init_db(conn)
        print(import_files(conn, sys.argv[2:]))
        print("Books in database: %d" % conn.execute("SELECT COUNT(*) FROM books").fetchone()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
