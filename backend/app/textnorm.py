"""Text normalisation shared by the importer and the search endpoint."""
import re
import unicodedata

NORM_VERSION = "2"  # 2 = Persian look-alikes, Eastern digits and invisible marks; books.search follows (db.py)

_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)
# One table does every per-letter step in C: accents and harakat (Mn, left after NFD) and invisible marks (Cf:
# joiners, direction marks) are dropped, tatweel too, and letters that look alike or are typed either way become
# one: ٱ/ا, ى/ي, ة/ه, the Persian and Urdu forms of kaf, yeh and heh, ڤ/ف and friends, ٣/3 and ۳/3.
# (أ/إ/آ/ؤ/ئ lose their hamza in NFD. The lone ء stays: "شيء" would shrink to two letters, too short for the
# index, and a search without it ("شئ", "البيضا") still finds the title that has it.)
_TABLE = {cp: None for cp in range(0x10000) if unicodedata.category(chr(cp)) in ("Mn", "Cf")}
_TABLE.update({ord(k): v for k, v in {
    "ـ": None, "ٱ": "ا", "ى": "ي", "ة": "ه",
    "ک": "ك", "گ": "ك", "ی": "ي", "ے": "ي", "ھ": "ه", "ە": "ه", "ڤ": "ف", "پ": "ب", "چ": "ج", "ژ": "ز",
}.items()})
_TABLE.update({0x0660 + i: str(i) for i in range(10)})
_TABLE.update({0x06F0 + i: str(i) for i in range(10)})


def norm(text: str) -> str:
    """Lowercase, strip accents and Arabic diacritics, unify look-alike letters and digits, drop punctuation."""
    s = unicodedata.normalize("NFD", (text or "").lower()).translate(_TABLE)
    if not s.isascii() and max(s) > "\uffff":  # marks outside the table's range (rare scripts)
        s = "".join(ch for ch in s if unicodedata.category(ch) not in ("Mn", "Cf"))
    return _NON_WORD.sub(" ", s).strip()


_INVISIBLE = re.compile("[%s]" % "".join(chr(cp) for cp in range(0x10000) if unicodedata.category(chr(cp)) == "Cf"))


def has_invisible(text: str) -> bool:
    """Joiners, direction marks, soft hyphens: before NORM_VERSION 2 they split the word they sat in."""
    return bool(text) and bool(_INVISIBLE.search(text))
