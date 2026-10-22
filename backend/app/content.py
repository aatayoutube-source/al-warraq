"""The library's own writing: its articles, and the texts that give pages substance (the home page, the
categories, the best-known books and authors). They live as files in app/data/content, written and reviewed
apart from the code:

    home.json        {"ar": [paragraph, ...], "en": [...]}
    categories.json  {"nov": {"ar": [...], "en": [...]}, ...}
    books.json       {"gid:1122": {"ar": {"about": [...], "context": [...]}, "en": {...}}, ...}   (hand-picked books)
    authors.json     {"shakespeare": {"ar": [...], "en": [...]}, ...}
    articles/*.md    a front matter (slug, title, description, date) and a light Markdown body

Beside "ar" and "en", each text may be written in the other interface languages ("zh", "fr", "es", "pt", "ja", "de",
as is the book descriptions file app/data/book_descriptions.json); a language it lacks shows the English text.
Paragraphs may hold **bold** and [links](/path) (site paths and https addresses only); everything else is text.

A page whose own words are too few to stand on their own (a catalogue record) is "thin": with THIN_NOINDEX on
(the default) it stays out of search results and the sitemap until it gets a text of its own here.
"""
import json
import os
import re
from html import escape

DIR = os.path.join(os.path.dirname(__file__), "data", "content")
MIN_WORDS = 150  # a page with fewer words of its own is thin
_cache = {}  # file name -> (mtime, parsed)


def thin_noindex() -> bool:
    return os.environ.get("THIN_NOINDEX", "1").strip() != "0"


def text_ui(ui: str) -> str:
    """The language the legal pages (legal.py) are read in: they are written in Arabic and English, and every other
    interface language (French, Chinese...) shows the English one."""
    return ui if ui in ("ar", "en") else "en"


class Text(list):
    """Paragraphs, and the language they are written in (English stands in for a language not translated yet)."""
    def __init__(self, items=(), lang=""):
        super().__init__(items or ())
        self.lang = lang


def _pick(entry: dict, ui: str):
    """(text, its language) from {"ar": ..., "en": ..., "fr": ...}: this language's, else the English one (Arabic,
    the site's own, never falls back)."""
    if entry.get(ui):
        return entry[ui], ui
    if ui != "ar" and entry.get("en"):
        return entry["en"], "en"
    return None, ui


def _load(name: str, default):
    path = os.path.join(DIR, name)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return default
    hit = _cache.get(name)
    if hit and hit[0] == mtime:
        return hit[1]
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _cache[name] = (mtime, data)
    return data


def home(ui: str) -> Text:
    return Text(*_pick(_load("home.json", {}), ui))


def category(key: str, ui: str) -> Text:
    return Text(*_pick(_load("categories.json", {}).get(key, {}), ui))


def author(key: str, ui: str) -> Text:
    return Text(*_pick(_load("authors.json", {}).get(key, {}), ui)) if key else Text()


def book(row, ui: str) -> dict:
    """{"about": Text, "context": Text} for a book in that language.
    Reads from DB book_descriptions (keyed by gid), falls back to books.json."""
    if not row["gid"]:
        return {}
    try:
        from . import db as _db
        conn = _db.connect()
        dr = conn.execute(
            "SELECT ar, ar_ctx, en, en_ctx, i18n FROM book_descriptions WHERE gid=?",
            (row["gid"],)
        ).fetchone()
        conn.close()
        if dr:
            texts = {"ar": {"about": json.loads(dr["ar"]), "context": json.loads(dr["ar_ctx"])},
                     "en": {"about": json.loads(dr["en"]), "context": json.loads(dr["en_ctx"])}}
            texts.update(json.loads(dr["i18n"] or "{}"))
            note, lang = _pick({k: v for k, v in texts.items() if v.get("about")}, ui)
            if note:
                return {"about": Text(note["about"], lang), "context": Text(note.get("context"), lang)}
    except Exception:
        pass
    # Legacy books.json fallback
    if row["curated"] != 1:
        return {}
    note, lang = _pick(_load("books.json", {}).get("gid:%d" % row["gid"], {}), ui)
    return {k: Text(v, lang) for k, v in note.items()} if note else {}


def described_gids(ui: str = "") -> set:
    """Gutenberg numbers of books that have a description (DB or books.json)."""
    out = set()
    try:
        from . import db as _db
        conn = _db.connect()
        col = "ar" if ui == "ar" else "en"
        if ui:
            rows = conn.execute(
                f"SELECT gid FROM book_descriptions WHERE {col}!='[]' AND {col}!=''"
            ).fetchall()
        else:
            rows = conn.execute("SELECT gid FROM book_descriptions").fetchall()
        conn.close()
        for r in rows:
            if r["gid"]:
                out.add(r["gid"])
    except Exception:
        pass
    # Legacy books.json
    for k, v in _load("books.json", {}).items():
        if k.startswith("gid:") and (not ui or v.get(ui)):
            out.add(int(k[4:]))
    return out


def words(*texts) -> int:
    n = 0
    for t in texts:
        if isinstance(t, (list, tuple)):
            n += words(*t)
        elif t:
            n += len(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", str(t)).split())
    return n


# ---------- a light Markdown: headings, paragraphs, lists, verses, bold, links ----------

_LINK = re.compile(r"\[([^\]\n]+)\]\(((?:/|https://)[^)\s]*)\)")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")


def inline(text: str) -> str:
    """Escaped text with **bold** and [links](...); a link outside the site opens apart and passes no rank."""
    s = escape(text, quote=False)

    def link(m):
        href = m.group(2).replace('"', "%22")
        if href.startswith("/"):
            return '<a href="%s">%s</a>' % (href, m.group(1))
        return '<a href="%s" target="_blank" rel="noopener nofollow">%s</a>' % (href, m.group(1))
    return _BOLD.sub(r"<strong>\1</strong>", _LINK.sub(link, s))


def paragraphs(items) -> str:
    return "".join("<p>%s</p>" % inline(p) for p in items)


def render(md: str) -> str:
    """Blocks separated by blank lines: "## " and "### " headings, "- " and "1. " lists, "> " verses, paragraphs."""
    out = []
    for block in re.split(r"\n\s*\n", md.strip()):
        lines = [l.rstrip() for l in block.strip().split("\n") if l.strip()]
        if not lines:
            continue
        first = lines[0]
        if first.startswith("### "):
            out.append("<h3>%s</h3>" % inline(first[4:].strip()))
            lines = lines[1:]
        elif first.startswith("## "):
            out.append("<h2>%s</h2>" % inline(first[3:].strip()))
            lines = lines[1:]
        if not lines:
            continue
        if all(l.lstrip().startswith("- ") for l in lines):
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % inline(l.lstrip()[2:].strip()) for l in lines))
        elif all(re.match(r"\s*\d+\.\s", l) for l in lines):
            out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % inline(re.sub(r"^\s*\d+\.\s", "", l)) for l in lines))
        elif all(l.lstrip().startswith(">") for l in lines):
            out.append('<blockquote class="verse">%s</blockquote>' % "".join(
                "<p>%s</p>" % inline(l.lstrip()[1:].strip()) for l in lines))
        else:
            out.append("<p>%s</p>" % inline(" ".join(l.strip() for l in lines)))
    return "\n".join(out)


# ---------- articles ----------

def articles() -> list:
    """Every article, newest first: dicts with slug, title, description, date, body (Markdown), words."""
    folder = os.path.join(DIR, "articles")
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".md"))
    except OSError:
        return []
    stamp = tuple((n, os.path.getmtime(os.path.join(folder, n))) for n in names)
    hit = _cache.get("articles")
    if hit and hit[0] == stamp:
        return hit[1]
    out = []
    for n in names:
        with open(os.path.join(folder, n), encoding="utf-8") as f:
            src = f.read().replace("\r\n", "\n")
        meta, body = {}, src
        if src.startswith("---\n"):
            head, _, body = src[4:].partition("\n---\n")
            for line in head.split("\n"):
                k, _, v = line.partition(":")
                if k.strip():
                    meta[k.strip()] = v.strip()
        if not meta.get("slug") or not meta.get("title"):
            continue
        meta["body"] = body.strip()
        meta["words"] = words(re.sub(r"[#>*-]", " ", body))
        out.append(meta)
    out.sort(key=lambda a: a.get("date", ""), reverse=True)  # newest first; one day's in their files' order (01-, 02-...)
    _cache["articles"] = (stamp, out)
    return out


def article(slug: str):
    return next((a for a in articles() if a["slug"] == slug), None)
