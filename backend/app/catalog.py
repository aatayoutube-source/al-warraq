"""Category definitions and Project Gutenberg metadata cleaning."""
import re

# key -> hue (used by the frontend to colour covers), English and Arabic labels
CATEGORIES = {
    "nov": {"hue": 14, "en": "Novels & Stories", "ar": "روايات وقصص"},
    "poe": {"hue": 330, "en": "Poetry", "ar": "شعر"},
    "dra": {"hue": 282, "en": "Drama", "ar": "مسرح"},
    "phi": {"hue": 215, "en": "Philosophy", "ar": "فلسفة"},
    "his": {"hue": 36, "en": "History", "ar": "تاريخ"},
    "sci": {"hue": 150, "en": "Natural Sciences", "ar": "علوم طبيعية"},
    "med": {"hue": 352, "en": "Medicine & Health", "ar": "طب وصحة"},
    "eng": {"hue": 194, "en": "Engineering & Technology", "ar": "هندسة وتقنية"},
    "mat": {"hue": 246, "en": "Mathematics & Astronomy", "ar": "رياضيات وفلك"},
    "rel": {"hue": 88, "en": "Religion & Mysticism", "ar": "دين وتصوف"},
    "pol": {"hue": 22, "en": "Politics & Economics", "ar": "سياسة واقتصاد"},
    "chi": {"hue": 48, "en": "Children's & Fairy Tales", "ar": "أدب الأطفال والحكايات"},
    "bio": {"hue": 170, "en": "Biography & Memoirs", "ar": "سير ومذكرات"},
    "tra": {"hue": 204, "en": "Travel & Geography", "ar": "رحلات وجغرافيا"},
    "psy": {"hue": 300, "en": "Psychology & Society", "ar": "نفس واجتماع"},
    "art": {"hue": 8, "en": "Arts & Architecture", "ar": "فنون وعمارة"},
    "gen": {"hue": 200, "en": "General & Other", "ar": "عام ومتنوع"},
}

# category -> keywords searched in Gutenberg Subjects + Bookshelves (first match wins)
RULES = [
    ("med", ["medicine", "medical", "anatomy", "surgery", "physiology", "disease", "hygiene", "nursing", "pharmac", "health", "psychiatr"]),
    ("eng", ["engineering", "technology", "machinery", "mechanic", "electric", "construction", "mining", "metallurgy", "railroad", "steam", "radio", "invention", "manufactur"]),
    ("mat", ["mathematic", "geometry", "algebra", "astronom", "arithmetic", "calculus", "trigonometry"]),
    ("sci", ["science", "biology", "chemistry", "physics", "botany", "zoology", "geology", "natural history", "evolution", "ornithology", "entomology", "nature"]),
    ("psy", ["psycholog", "sociolog", "anthropolog", "folklore", "social"]),
    ("pol", ["politic", "economic", "law", "government", "labor", "socialism", "war", "military", "finance", "business"]),
    ("rel", ["religion", "bible", "christian", "islam", "buddh", "hindu", "theology", "mysticism", "sermon", "quran", "koran", "sufi"]),
    ("phi", ["philosoph", "ethics", "logic", "metaphysic"]),
    ("tra", ["travel", "voyage", "geography", "description and travel", "exploration", "adventure"]),
    ("bio", ["biograph", "autobiograph", "memoir", "diaries", "correspondence", "letters"]),
    ("his", ["history", "histories", "antiquit", "archaeolog", "ancient"]),
    ("art", ["art", "architecture", "music", "painting", "sculpture", "design", "photograph", "cooking"]),
    ("chi", ["children", "juvenile", "fairy tale", "fables", "nursery"]),
    ("dra", ["drama", "plays", "theatre", "theater", "comedies", "tragedies"]),
    ("poe", ["poetry", "poems", "verse", "ballads", "sonnets", "epic poetry"]),
    ("nov", ["fiction", "novel", "stories", "short stories", "adventure stories", "romance", "detective", "mystery", "science fiction", "humor"]),
]

_COMPILED = [
    (code, [re.compile(r"\b" + re.escape(w) + (r"\b" if len(w) <= 4 else "")) for w in words])
    for code, words in RULES
]


def categorize(subjects: str, shelves: str, default: str = "nov") -> str:
    text = ((subjects or "") + " ; " + (shelves or "")).lower()
    if "science fiction" in text:
        return "nov"
    for code, patterns in _COMPILED:
        if any(p.search(text) for p in patterns):
            return code
    return default


def clean_author(raw: str) -> str:
    """'Austen, Jane, 1775-1817; Other, Name' -> 'Jane Austen'"""
    if not raw:
        return ""
    first = raw.split(";")[0].strip()
    first = re.sub(r",?\s*\d{3,4}\??\s*-\s*\d{0,4}\??\s*$", "", first)
    first = re.sub(r"\s*\[[^\]]*\]", "", first)
    first = re.sub(r"\s*\([^)]*\)", "", first)  # "Wells, H. G. (Herbert George)" -> "Wells, H. G."
    parts = [p.strip() for p in first.split(",") if p.strip()]
    if len(parts) >= 2:
        return (parts[1] + " " + parts[0]).strip()
    return parts[0] if parts else ""


def clean_title(raw: str) -> str:
    return re.sub(r"\s+", " ", raw or "").strip()[:140]
