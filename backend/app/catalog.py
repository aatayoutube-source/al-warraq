"""Category definitions and Project Gutenberg metadata cleaning."""
import re

# "ara" is not a topic: it gathers every book written in Arabic, which also keeps its own topic below
ARABIC_CAT = "ara"
# key -> hue (used by the frontend to colour covers), English and Arabic labels
CATEGORIES = {
    "ara": {"hue": 158, "en": "Arabic Books", "ar": "الكتب العربية"},
    "nov": {"hue": 14, "en": "Novels & Stories", "ar": "روايات وقصص"},
    "hor": {"hue": 262, "en": "Horror", "ar": "رعب"},
    "mys": {"hue": 228, "en": "Crime & Mystery", "ar": "جريمة وغموض"},
    "dev": {"hue": 120, "en": "Self-Development", "ar": "تنمية بشرية"},
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

# one alternation per category (short words must match whole, longer ones may be prefixes: "philosoph")
_COMPILED = [
    (code, re.compile("|".join(r"\b" + re.escape(w) + (r"\b" if len(w) <= 4 else "") for w in words)))
    for code, words in RULES
]


# horror, then crime and mystery, come before everything: "Horror tales; Science fiction" is horror
HORROR = re.compile(r"horror|ghost stor|ghosts|supernatural|vampire|werewol|haunted|gothic fiction|occult fiction")
MYSTERY = re.compile(r"detective and mystery|mystery and detective|detective fiction|mystery fiction|crime fiction|"
                     r"detective stories|mystery stories|private investigators")


def categorize(subjects: str, shelves: str, default: str = "nov") -> str:
    text = ((subjects or "") + " ; " + (shelves or "")).lower()
    if HORROR.search(text):
        return "hor"
    if MYSTERY.search(text):
        return "mys"
    if "science fiction" in text:
        return "nov"
    for code, pattern in _COMPILED:
        if pattern.search(text):
            return code
    return default


# Extra words for books that only have a title (HathiTrust): English title words, the main European
# languages and transliterated Arabic. Tried after RULES; first match wins, so the generic
# government-document words come last.
TITLE_RULES = [
    ("med", ["hospital", "hospitals", "nurse", "nurses", "drugs", "cancer", "mental health", "dental", "veterinary", "medecine", "medizin", "medicina", "tibb"]),
    ("eng", ["energy", "transportation", "highway", "highways", "aviation", "aircraft", "nuclear", "engine", "engines", "railway", "railways", "bridges",
             "telegraph", "automobile", "computer", "computers", "petroleum", "industrial", "technical", "technik", "technique"]),
    ("sci", ["agriculture", "agricultural", "farm", "farms", "farming", "forest", "forests", "forestry", "soil", "soils", "crops", "fisheries",
             "wildlife", "geological", "climate", "weather", "plants", "animals", "birds", "insects", "environmental", "chimie", "chemie", "physik",
             "physique", "botanique", "botanik", "zoologie", "naturgeschichte"]),
    ("mat", ["statistics", "statistical", "mathematiques", "mathematik", "matematica", "census"]),
    ("rel", ["church", "churches", "god", "christ", "jesus", "gospel", "prayer", "prayers", "catholic", "methodist", "baptist", "presbyterian",
             "missionary", "missions", "saints", "spiritual", "theologie", "kirche", "eglise", "predigten", "tafsir", "hadith", "fiqh", "quran"]),
    ("psy", ["education", "educational", "school", "schools", "teaching", "teachers", "students", "pedagogy", "erziehung"]),
    ("bio", ["life of", "life and", "recollections", "reminiscences", "diary", "letters of", "lettres", "briefe", "cartas",
             "memoires", "leben", "vie de", "vida de", "sirah"]),
    ("his", ["historical", "civil war", "revolution", "colonial", "genealogy", "genealogical", "centennial", "histoire", "geschichte", "historia",
             "storia", "tarikh"]),
    ("tra", ["guide book", "guidebook", "tourist", "tour", "travels", "journey", "atlas", "maps", "voyage", "reise", "viaje", "viaggio", "rihlah"]),
    ("poe", ["songs", "rhymes", "verses", "poesies", "poemes", "gedichte", "poesie", "poesias", "carmina", "diwan"]),
    ("dra", ["theatre", "comedie", "tragedie", "lustspiel", "schauspiel", "commedia", "tragedia"]),
    ("nov", ["tale", "tales", "a story", "a romance", "a novel", "roman", "romanzo", "novela", "erzahlungen", "contes", "novelle"]),
    ("phi", ["philosophie", "filosofia"]),
    ("pol", ["hearing", "hearings", "committee", "subcommittee", "congress", "congressional", "senate", "representatives", "appropriation",
             "appropriations", "legislation", "legislative", "oversight", "budget", "fiscal", "regulation", "regulations", "statute", "statutes",
             "acts", "court", "courts", "judiciary", "constitution", "constitutional", "policy", "policies", "administration", "commission",
             "tariff", "tax", "taxation", "treaty", "election", "elections", "parliament", "parliamentary", "municipal", "laws", "legal", "bill",
             "report", "reports", "droit", "recht", "gesetz", "derecho", "diritto", "politique", "politik", "economie"]),
]
_TITLE_COMPILED = [(code, re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b")) for code, words in TITLE_RULES]


def categorize_title(title: str, default: str = "gen") -> str:
    """Category for a book known only by its title."""
    code = categorize(title, "", default="")
    if code:
        return code
    from .textnorm import norm  # local: textnorm is tiny, keeps catalog importable on its own
    text = norm(title)
    for code, pattern in _TITLE_COMPILED:
        if pattern.search(text):
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
        extra = " ".join(p for p in parts[2:] if p.rstrip(".") in ("Sir", "Mrs", "Jr", "Sr"))
        return fix_name_order((parts[1] + " " + extra + " " + parts[0]).replace("  ", " ").strip())
    return parts[0] if parts else ""


_PREFIX = re.compile(r"^(.+?) (Sir|Mrs\.?) (\S+)$")
_SUFFIX = re.compile(r"^(.+?) (Jr\.?|Sr\.?) (\S+)$")


def fix_name_order(name: str) -> str:
    """'H. M. Sir Elliot' -> 'Sir H. M. Elliot', 'Elbert L. Jr. Little' -> 'Elbert L. Little Jr.'"""
    m = _PREFIX.match(name)
    if m:
        return "%s %s %s" % (m.group(2), m.group(1), m.group(3))
    m = _SUFFIX.match(name)
    if m:
        return "%s %s %s" % (m.group(1), m.group(3), m.group(2))
    return name


def clean_title(raw: str) -> str:
    return re.sub(r"\s+", " ", raw or "").strip()[:140]
