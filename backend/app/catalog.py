"""Category definitions and Project Gutenberg metadata cleaning."""
import re

# "ara" is not a topic: it gathers every book written in Arabic, which also keeps its own topic below
ARABIC_CAT = "ara"
# key -> hue (used by the frontend to colour covers) and the label in every interface language (pages.UI_LANGS)
CATEGORIES = {
    "ara": {"hue": 158, "en": "Arabic Books", "ar": "الكتب العربية", "zh": "阿拉伯语图书", "fr": "Livres arabes",
            "es": "Libros árabes", "pt": "Livros árabes", "ja": "アラビア語の本", "de": "Arabische Bücher"},
    "nov": {"hue": 14, "en": "Novels & Stories", "ar": "روايات وقصص", "zh": "小说与故事", "fr": "Romans et nouvelles",
            "es": "Novelas y cuentos", "pt": "Romances e contos", "ja": "小説・物語", "de": "Romane und Erzählungen"},
    "hor": {"hue": 262, "en": "Horror", "ar": "رعب", "zh": "恐怖", "fr": "Horreur", "es": "Terror", "pt": "Terror",
            "ja": "ホラー", "de": "Horror"},
    "mys": {"hue": 228, "en": "Crime & Mystery", "ar": "جريمة وغموض", "zh": "犯罪与悬疑", "fr": "Policier et mystère",
            "es": "Crimen y misterio", "pt": "Crime e mistério", "ja": "ミステリー・犯罪", "de": "Krimi und Mystery"},
    "dev": {"hue": 120, "en": "Self-Development", "ar": "تنمية بشرية", "zh": "自我提升", "fr": "Développement personnel",
            "es": "Desarrollo personal", "pt": "Desenvolvimento pessoal", "ja": "自己啓発", "de": "Persönlichkeitsentwicklung"},
    "poe": {"hue": 330, "en": "Poetry", "ar": "شعر", "zh": "诗歌", "fr": "Poésie", "es": "Poesía", "pt": "Poesia",
            "ja": "詩", "de": "Lyrik"},
    "dra": {"hue": 282, "en": "Drama", "ar": "مسرح", "zh": "戏剧", "fr": "Théâtre", "es": "Teatro", "pt": "Teatro",
            "ja": "戯曲", "de": "Drama"},
    "phi": {"hue": 215, "en": "Philosophy", "ar": "فلسفة", "zh": "哲学", "fr": "Philosophie", "es": "Filosofía",
            "pt": "Filosofia", "ja": "哲学", "de": "Philosophie"},
    "his": {"hue": 36, "en": "History", "ar": "تاريخ", "zh": "历史", "fr": "Histoire", "es": "Historia", "pt": "História",
            "ja": "歴史", "de": "Geschichte"},
    "sci": {"hue": 150, "en": "Natural Sciences", "ar": "علوم طبيعية", "zh": "自然科学", "fr": "Sciences naturelles",
            "es": "Ciencias naturales", "pt": "Ciências naturais", "ja": "自然科学", "de": "Naturwissenschaften"},
    "med": {"hue": 352, "en": "Medicine & Health", "ar": "طب وصحة", "zh": "医学与健康", "fr": "Médecine et santé",
            "es": "Medicina y salud", "pt": "Medicina e saúde", "ja": "医学・健康", "de": "Medizin und Gesundheit"},
    "eng": {"hue": 194, "en": "Engineering & Technology", "ar": "هندسة وتقنية", "zh": "工程与技术", "fr": "Ingénierie et technologie",
            "es": "Ingeniería y tecnología", "pt": "Engenharia e tecnologia", "ja": "工学・技術", "de": "Technik und Ingenieurwesen"},
    "mat": {"hue": 246, "en": "Mathematics & Astronomy", "ar": "رياضيات وفلك", "zh": "数学与天文", "fr": "Mathématiques et astronomie",
            "es": "Matemáticas y astronomía", "pt": "Matemática e astronomia", "ja": "数学・天文学", "de": "Mathematik und Astronomie"},
    "rel": {"hue": 88, "en": "Religion & Mysticism", "ar": "دين وتصوف", "zh": "宗教与神秘主义", "fr": "Religion et mystique",
            "es": "Religión y mística", "pt": "Religião e misticismo", "ja": "宗教・神秘思想", "de": "Religion und Mystik"},
    "pol": {"hue": 22, "en": "Politics & Economics", "ar": "سياسة واقتصاد", "zh": "政治与经济", "fr": "Politique et économie",
            "es": "Política y economía", "pt": "Política e economia", "ja": "政治・経済", "de": "Politik und Wirtschaft"},
    "chi": {"hue": 48, "en": "Children's & Fairy Tales", "ar": "أدب الأطفال والحكايات", "zh": "儿童文学与童话", "fr": "Jeunesse et contes",
            "es": "Literatura infantil y cuentos de hadas", "pt": "Literatura infantil e contos de fadas", "ja": "児童文学・童話",
            "de": "Kinderbücher und Märchen"},
    "bio": {"hue": 170, "en": "Biography & Memoirs", "ar": "سير ومذكرات", "zh": "传记与回忆录", "fr": "Biographies et mémoires",
            "es": "Biografías y memorias", "pt": "Biografias e memórias", "ja": "伝記・回想録", "de": "Biografien und Memoiren"},
    "tra": {"hue": 204, "en": "Travel & Geography", "ar": "رحلات وجغرافيا", "zh": "旅行与地理", "fr": "Voyages et géographie",
            "es": "Viajes y geografía", "pt": "Viagens e geografia", "ja": "旅行・地理", "de": "Reisen und Geografie"},
    "psy": {"hue": 300, "en": "Psychology & Society", "ar": "نفس واجتماع", "zh": "心理与社会", "fr": "Psychologie et société",
            "es": "Psicología y sociedad", "pt": "Psicologia e sociedade", "ja": "心理・社会", "de": "Psychologie und Gesellschaft"},
    "art": {"hue": 8, "en": "Arts & Architecture", "ar": "فنون وعمارة", "zh": "艺术与建筑", "fr": "Arts et architecture",
            "es": "Arte y arquitectura", "pt": "Artes e arquitetura", "ja": "芸術・建築", "de": "Kunst und Architektur"},
    "gen": {"hue": 200, "en": "General & Other", "ar": "عام ومتنوع", "zh": "综合与其他", "fr": "Généralités et divers",
            "es": "General y otros", "pt": "Geral e outros", "ja": "総記・その他", "de": "Allgemeines und Sonstiges"},
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
