"""Open-access research sources (medicine and engineering) with server-built search links."""
import json
from urllib.parse import quote

TOPICS = {
    "med": {
        "default": "cardiology",
        "topics": [
            ("Anatomy", "التشريح"), ("Cardiology", "أمراض القلب"), ("Oncology", "الأورام"),
            ("Infectious diseases", "الأمراض المعدية"), ("Pharmacology", "علم الأدوية"),
            ("Public health", "الصحة العامة"), ("Neuroscience", "علم الأعصاب"), ("Pediatrics", "طب الأطفال"),
            ("Surgery", "الجراحة"), ("Nursing", "التمريض"), ("Genetics", "علم الوراثة"),
            ("Nutrition", "التغذية"), ("Diabetes", "السكري"), ("Radiology", "الأشعة"),
        ],
    },
    "eng": {
        "default": "control systems",
        "topics": [
            ("Civil engineering", "الهندسة المدنية"), ("Mechanical engineering", "الهندسة الميكانيكية"),
            ("Electrical engineering", "الهندسة الكهربائية"), ("Control systems", "أنظمة التحكم"),
            ("Signal processing", "معالجة الإشارات"), ("Computer architecture", "معمارية الحاسوب"),
            ("Machine learning", "تعلم الآلة"), ("Robotics", "الروبوتات"),
            ("Renewable energy", "الطاقة المتجددة"), ("Materials science", "علم المواد"),
            ("Structural analysis", "التحليل الإنشائي"), ("Aerospace", "هندسة الطيران"),
            ("Chemical engineering", "الهندسة الكيميائية"), ("Power systems", "نظم القدرة"),
        ],
    },
}

_DOAJ_AR = "دليل المجلات المفتوحة المحكّمة، بحث في مقالاتها."
_DOAJ_EN = "Directory of peer-reviewed open-access journals, searched by article."
_CORE_AR = "أكبر مجمّع للأبحاث المفتوحة من المستودعات الجامعية."
_CORE_EN = "The largest aggregator of open research from university repositories."


def _doaj(q, raw):
    return "https://doaj.org/search/articles?source=" + quote(json.dumps({"query": {"query_string": {"query": raw}}}))


def _core(q, raw):
    return "https://core.ac.uk/search?q=" + q


SOURCES = {
    "med": [
        ("PubMed Central (PMC)", "نص كامل مجاني لملايين الأبحاث الطبية الحيوية من المعاهد الصحية الأمريكية.",
         "Free full text of millions of biomedical papers from the US National Institutes of Health.",
         lambda q, raw: "https://pmc.ncbi.nlm.nih.gov/search/?term=" + q),
        ("Europe PMC", "أبحاث الوصول المفتوح في علوم الحياة، مع تصفية على الأبحاث المجانية.",
         "Open-access life-science literature, filtered to freely readable papers.",
         lambda q, raw: "https://europepmc.org/search?query=" + quote(raw + " OPEN_ACCESS:y")),
        ("NCBI Bookshelf", "كتب ومراجع طبية مجانية، منها مراجع ودلائل سريرية.",
         "Free medical textbooks, references and clinical guidelines.",
         lambda q, raw: "https://www.ncbi.nlm.nih.gov/books/?term=" + q),
        ("PLOS", "مجلات مفتوحة بالكامل في الطب والأحياء.", "Fully open journals in medicine and biology.",
         lambda q, raw: "https://journals.plos.org/plosone/search?q=" + q),
        ("BMC (BioMed Central)", "مئات المجلات الطبية المفتوحة.", "Hundreds of open-access medical journals.",
         lambda q, raw: "https://www.biomedcentral.com/search?query=" + q),
        ("medRxiv", "أبحاث طبية قبل النشر تتاح مجاناً.", "Free preprints in the health sciences.",
         lambda q, raw: "https://www.medrxiv.org/search/" + q),
        ("DOAJ", _DOAJ_AR, _DOAJ_EN, _doaj),
        ("CORE", _CORE_AR, _CORE_EN, _core),
    ],
    "eng": [
        ("arXiv", "ملايين الأبحاث المجانية في الهندسة والحاسوب والفيزياء قبل النشر.",
         "Millions of free preprints in engineering, computing and physics.",
         lambda q, raw: "https://arxiv.org/search/?searchtype=all&query=" + q),
        ("OSTI.gov", "تقارير تقنية مجانية من وزارة الطاقة الأمريكية.",
         "Free technical reports from the US Department of Energy.",
         lambda q, raw: "https://www.osti.gov/search/semantic:" + q),
        ("NASA Technical Reports", "تقارير وأبحاث ناسا الهندسية والفضائية المفتوحة.",
         "NASA open engineering and aerospace reports.",
         lambda q, raw: "https://ntrs.nasa.gov/search?q=" + q),
        ("MIT OpenCourseWare", "مقررات هندسية كاملة من معهد ماساتشوستس بمحاضراتها ومراجعها.",
         "Full engineering courses from MIT with lectures and readings.",
         lambda q, raw: "https://ocw.mit.edu/search/?q=" + q),
        ("OAPEN", "كتب أكاديمية مفتوحة الوصول للتحميل.", "Open-access academic books free to download.",
         lambda q, raw: "https://library.oapen.org/discover?query=" + q),
        ("DOAB", "دليل الكتب المفتوحة الأكاديمية.", "Directory of open-access academic books.",
         lambda q, raw: "https://directory.doabooks.org/discover?query=" + q),
        ("Zenodo", "مستودع مفتوح للأبحاث والبيانات والبرمجيات.", "Open repository for research, data and software.",
         lambda q, raw: "https://zenodo.org/search?q=" + q),
        ("DOAJ", _DOAJ_AR, _DOAJ_EN, _doaj),
        ("CORE", _CORE_AR, _CORE_EN, _core),
    ],
}


def build(domain: str, raw: str) -> dict:
    raw = (raw or "").strip()[:120] or TOPICS[domain]["default"]
    q = quote(raw)
    return {
        "domain": domain,
        "query": raw,
        "default": TOPICS[domain]["default"],
        "topics": [{"en": en, "ar": ar} for en, ar in TOPICS[domain]["topics"]],
        "sources": [{"name": n, "ar": a, "en": e, "url": fn(q, raw)} for n, a, e, fn in SOURCES[domain]],
    }
