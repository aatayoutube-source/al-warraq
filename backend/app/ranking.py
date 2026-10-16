"""Search relevance: the book whose title is the search comes first, not wherever the catalogue order puts it.

The index finds every book holding the words; these helpers order them (exact title, the author's own books,
the title followed by more, the words inside a title, ...) and, when a search finds almost nothing, widen it to
spellings one slip away ("فرانكشتاين" finds "فرانكنشتاين") and to the word without its article.
"""
import re
import threading
import time
from array import array
from collections import OrderedDict
from functools import lru_cache

from .textnorm import norm

FEW = 10  # a search finding fewer books than this is widened (a word is widened only if it is that rare too)
MAX_WIDE = 3  # words widened in one search at most
MAX_WIDE_LEN = 15  # longer "words" are not words: widening them only costs time
RANK_MAX = 30_000  # rows ranked at most (a widened search can match many); beyond that the answer is "a lot"
CACHE_SIZE = 32  # ranked lists kept for the next pages of the same search
CACHE_TTL = 300
NEAR_BASE = 10  # widened matches come after every exact one (ranks 0-8)
POEM = 3  # wikisource.WS_KIND: a single poem is not "the author's book"

# the article and the one-letter words written joined to the next one (و ف ب ل ك)
ARTICLES = ("وال", "بال", "فال", "كال", "لل", "ال")
_CLITIC = "(?:[وفبلك]?(?:ال)?)"

_cache = OrderedDict()
_lock = threading.Lock()
_name = lru_cache(maxsize=65536)(norm)  # an author's name comes back on many rows


def variants(word: str) -> list:
    """LIKE patterns ('_' = any one letter) one slip away from word: a wrong, extra, missing or swapped letter,
    and the word without its article. Each keeps three letters in a row, so the trigram index can serve it.
    They only gather candidates: close_to() decides which books really have such a word."""
    out = {stem(word)}
    n = len(word)
    if n >= 5:
        for i in range(n):
            out.add(word[:i] + word[i + 1:])  # one extra letter typed (at an edge it also covers a wrong one)
            if 0 < i < n - 1:
                out.add(word[:i] + "_" + word[i + 1:])  # one wrong letter
            if i:
                out.add(word[:i] + "_" + word[i:])  # one letter left out
            if i + 1 < n and word[i] != word[i + 1]:
                out.add(word[:i] + word[i + 1] + word[i] + word[i + 2:])  # two letters swapped
    out.discard(word)
    return sorted(v for v in out if max(len(p) for p in v.split("_")) >= 3)


def stem(word: str) -> str:
    """The word without its article ("الخيميائي" -> "خيميائي"), if three letters stay."""
    for a in ARTICLES:
        if word.startswith(a) and len(word) - len(a) >= 3:
            return word[len(a):]
    return word


def _one_slip(a: str, b: str) -> bool:
    """a and b differ by at most one letter added, dropped or changed, or two neighbours swapped."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1 or min(la, lb) < 3:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1
                                  and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    if la > lb:
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def close_to(word: str, vocab) -> str:
    """The word of vocab that word is a slip of, or ""."""
    sw = stem(word)
    for v in vocab:
        if _one_slip(word, v) or _one_slip(sw, stem(v)):
            return v
    return ""


def _forms(text: str) -> set:
    """The words of text, also without a joined و/ف/ب/ل/ك and article: "والحب" counts as "الحب" and "حب"."""
    out = set()
    for w in text.split():
        out.add(w)
        if len(w) > 3 and w[0] in "وفبلك":
            out.add(w[1:])
        for a in ARTICLES:
            if w.startswith(a) and len(w) - len(a) >= 2:
                out.update((w[len(a):], "ال" + w[len(a):]))
                break
    return out


@lru_cache(maxsize=256)
def _phrase(query: str):
    return re.compile("(?:^| )" + _CLITIC + re.escape(query) + "(?: |$)")


def _tier(query: str, titles: list, authors: list, book: bool) -> int:
    """0 (the title is the search) to 8 (the search inside a longer word)."""
    if query in titles:
        return 0  # the title is the search
    if book and query in authors:
        return 1  # the author's own books, before the books about them ("طه حسين")
    if any(t.startswith(query + " ") for t in titles):
        return 2  # the title, followed by a subtitle or a volume
    if book and any(a.endswith(" " + query) for a in authors):
        return 3  # the author's surname ("دوستويفسكي")
    phrase = _phrase(query)
    if any(phrase.search(t) for t in titles):
        return 4  # the search, as whole words, inside the title
    words = query.split()
    # (one word: the phrase test above already looked at every word of the title, so 5 and 7 never apply)
    tw = _forms(" ".join(titles)) if len(words) > 1 else ()
    if tw and all(w in tw for w in words):
        return 5  # every word in the title, in any order
    if query in authors or any(phrase.search(a) for a in authors):
        return 6  # elsewhere in the author's name; single poems of a poet
    if tw:
        aw = _forms(" ".join(authors))
        if all(w in tw or w in aw for w in words):
            return 7  # title and author together ("طه حسين الأيام")
    return 8  # inside a longer word


def scorer(query: str, strict_words: list, wide_words=()):
    """A function giving each matching row its rank (lower is better), or None for a widened candidate that
    has no word one slip away from the search (the patterns are loose: "يكولا" is inside "نيكولاي")."""
    words = query.split()

    def rank(r):
        titles = [norm(t) for t in (r["title_ar"], r["title"]) if t]
        authors = [_name(a) for a in (r["author_ar"], r["author_en"]) if a]
        book = r["curated"] != POEM
        if all(w in r["search"] for w in strict_words):
            return _tier(query, titles, authors, book)
        # a near match: read the search the way this book spells it, then rank it like an exact one
        text = " ".join(titles + authors)
        vocab = _forms(text)
        tokens = text.split()
        vocab.update(a + b for a, b in zip(tokens, tokens[1:]))  # "فرانك شتاين" written apart
        fixed = []
        for w in words:
            if w in wide_words and w not in r["search"]:
                v = close_to(w, vocab)
                if not v:
                    return None
                w = v
            fixed.append(w)
        return NEAR_BASE + _tier(" ".join(fixed), titles, authors, book)
    return rank


def ranked(conn, key, clause: str, args: list, query: str, strict_words: list, wide_words=()):
    """(ids in rank order, poems among them, widened matches among them, capped) for one search, cached."""
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            _cache.move_to_end(key)
            return hit[1]
    # no ORDER BY: the rows are fetched through the matched ids (the index) and ordered here
    rows = conn.execute("SELECT id, title, title_ar, author_en, author_ar, curated, ord, search FROM books"
                        + clause + " LIMIT ?", args + [RANK_MAX + 1]).fetchall()
    capped = len(rows) > RANK_MAX
    rank = scorer(query, strict_words, frozenset(wide_words))
    scored = sorted(s for s in ((rank(r), r["ord"], r["id"], r["curated"] == POEM) for r in rows) if s[0] is not None)
    result = (array("q", (s[2] for s in scored)), sum(s[3] for s in scored), sum(s[0] >= NEAR_BASE for s in scored), capped)
    with _lock:
        _cache[key] = (now + CACHE_TTL, result)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return result


def clear_cache():
    with _lock:
        _cache.clear()
