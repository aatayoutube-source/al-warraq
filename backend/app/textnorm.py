"""Text normalisation shared by the importer and the search endpoint."""
import re
import unicodedata

_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)
_TATWEEL = "ـ"


def norm(text: str) -> str:
    """Lowercase, strip accents and Arabic diacritics, unify alef/yaa/taa-marbuta, drop punctuation."""
    s = unicodedata.normalize("NFD", (text or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # accents, harakat, hamza marks
    s = s.replace(_TATWEEL, "")
    s = s.replace("ٱ", "ا").replace("ى", "ي").replace("ة", "ه")
    s = _NON_WORD.sub(" ", s)
    return s.strip()
