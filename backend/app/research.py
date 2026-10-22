"""Open-access research (medicine and engineering): real papers from OpenAlex shown on the site,
plus search links to the big open databases."""
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from urllib.parse import quote

from .security import safe_url
from .textnorm import norm

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
# the same topics in the site's other interface languages, in this order (a missing one shows its English name)
TOPIC_LANGS = ("zh", "fr", "es", "pt", "ja", "de")
TOPIC_NAMES = {
    "Anatomy": ("解剖学", "Anatomie", "Anatomía", "Anatomia", "解剖学", "Anatomie"),
    "Cardiology": ("心脏病学", "Cardiologie", "Cardiología", "Cardiologia", "循環器学", "Kardiologie"),
    "Oncology": ("肿瘤学", "Oncologie", "Oncología", "Oncologia", "腫瘍学", "Onkologie"),
    "Infectious diseases": ("传染病", "Maladies infectieuses", "Enfermedades infecciosas", "Doenças infecciosas", "感染症", "Infektionskrankheiten"),
    "Pharmacology": ("药理学", "Pharmacologie", "Farmacología", "Farmacologia", "薬理学", "Pharmakologie"),
    "Public health": ("公共卫生", "Santé publique", "Salud pública", "Saúde pública", "公衆衛生", "Öffentliche Gesundheit"),
    "Neuroscience": ("神经科学", "Neurosciences", "Neurociencia", "Neurociência", "神経科学", "Neurowissenschaften"),
    "Pediatrics": ("儿科学", "Pédiatrie", "Pediatría", "Pediatria", "小児科学", "Kinderheilkunde"),
    "Surgery": ("外科", "Chirurgie", "Cirugía", "Cirurgia", "外科", "Chirurgie"),
    "Nursing": ("护理", "Soins infirmiers", "Enfermería", "Enfermagem", "看護", "Pflege"),
    "Genetics": ("遗传学", "Génétique", "Genética", "Genética", "遺伝学", "Genetik"),
    "Nutrition": ("营养学", "Nutrition", "Nutrición", "Nutrição", "栄養学", "Ernährung"),
    "Diabetes": ("糖尿病", "Diabète", "Diabetes", "Diabetes", "糖尿病", "Diabetes"),
    "Radiology": ("放射学", "Radiologie", "Radiología", "Radiologia", "放射線医学", "Radiologie"),
    "Civil engineering": ("土木工程", "Génie civil", "Ingeniería civil", "Engenharia civil", "土木工学", "Bauingenieurwesen"),
    "Mechanical engineering": ("机械工程", "Génie mécanique", "Ingeniería mecánica", "Engenharia mecânica", "機械工学", "Maschinenbau"),
    "Electrical engineering": ("电气工程", "Génie électrique", "Ingeniería eléctrica", "Engenharia elétrica", "電気工学", "Elektrotechnik"),
    "Control systems": ("控制系统", "Systèmes de commande", "Sistemas de control", "Sistemas de controle", "制御システム", "Regelungstechnik"),
    "Signal processing": ("信号处理", "Traitement du signal", "Procesamiento de señales", "Processamento de sinais", "信号処理", "Signalverarbeitung"),
    "Computer architecture": ("计算机体系结构", "Architecture des ordinateurs", "Arquitectura de computadoras", "Arquitetura de computadores",
                              "コンピュータアーキテクチャ", "Rechnerarchitektur"),
    "Machine learning": ("机器学习", "Apprentissage automatique", "Aprendizaje automático", "Aprendizado de máquina", "機械学習", "Maschinelles Lernen"),
    "Robotics": ("机器人学", "Robotique", "Robótica", "Robótica", "ロボット工学", "Robotik"),
    "Renewable energy": ("可再生能源", "Énergies renouvelables", "Energías renovables", "Energia renovável", "再生可能エネルギー", "Erneuerbare Energien"),
    "Materials science": ("材料科学", "Science des matériaux", "Ciencia de materiales", "Ciência dos materiais", "材料科学", "Materialwissenschaft"),
    "Structural analysis": ("结构分析", "Analyse des structures", "Análisis estructural", "Análise estrutural", "構造解析", "Statik"),
    "Aerospace": ("航空航天", "Aérospatiale", "Aeroespacial", "Aeroespacial", "航空宇宙工学", "Luft- und Raumfahrt"),
    "Chemical engineering": ("化学工程", "Génie chimique", "Ingeniería química", "Engenharia química", "化学工学", "Verfahrenstechnik"),
    "Power systems": ("电力系统", "Réseaux électriques", "Sistemas de potencia", "Sistemas de potência", "電力システム", "Energiesysteme"),
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
        ("medRxiv", "أبحاث طبية قبل النشر تتاح مجاناً.", "Free preprints in the health sciences.",
         lambda q, raw: "https://www.medrxiv.org/search/" + q),
        ("DOAJ", _DOAJ_AR, _DOAJ_EN, _doaj),
        ("CORE", _CORE_AR, _CORE_EN, _core),
    ],
    "eng": [
        ("arXiv", "ملايين الأبحاث المجانية في الهندسة والحاسوب والفيزياء قبل النشر.",
         "Millions of free preprints in engineering, computing and physics.",
         lambda q, raw: "https://arxiv.org/search/?searchtype=all&query=" + q),
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


def to_english(domain: str, raw: str) -> str:
    """The databases are mostly English: a topic from our list in another language (Arabic, French...) is searched
    by its English name."""
    n = norm(raw)
    for en, ar in TOPICS[domain]["topics"]:
        if n and any(n == norm(name) for name in (ar,) + TOPIC_NAMES.get(en, ())):
            return en
    return raw


# ---------- papers from OpenAlex (free, no key; about 250 million works) ----------

OPENALEX = "https://api.openalex.org/works"
# OpenAlex research fields: medicine, nursing, health professions / engineering, computer science, materials, energy
FIELDS = {"med": "27|29|36", "eng": "22|17|25|21"}
PAPERS_TTL = 6 * 3600
_papers_cache = {}  # (domain, query) -> (expires, payload)
_papers_lock = threading.Lock()
_outbound = threading.BoundedSemaphore(4)  # at most 4 questions to OpenAlex at once, so they never hold every worker


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "AlWarraqLibrary/1.0 (open research desk)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


fetch_json = _http_json  # replaced in tests


# open repositories that never put a "checking your browser" wall in front of a reader
REPOSITORIES = ("ncbi.nlm.nih.gov", "europepmc.org", "arxiv.org", "zenodo.org", "hal.science", "scielo",
                "hdl.handle.net", "repository", "eprints", "dspace")
UNREACHABLE = ("osti.gov",)  # times out from parts of the Middle East


def _best_link(w: dict):
    """(url, is_pdf): a free copy in an open repository when there is one, else the publisher's open copy."""
    pmc = (w.get("ids") or {}).get("pmcid")
    if pmc:
        return pmc, False
    oa = [loc for loc in (w.get("locations") or []) if loc.get("is_oa")]
    best = w.get("best_oa_location") or {}
    candidates = []
    for loc in oa + [best]:
        for u, pdf in ((loc.get("pdf_url"), True), (loc.get("landing_page_url"), False)):
            if safe_url(u) and not any(h in u for h in UNREACHABLE):
                candidates.append((u, pdf))
    for u, pdf in candidates:
        if any(h in u for h in REPOSITORIES):
            return u, pdf
    if candidates:
        return next(((u, p) for u, p in candidates if (u, p) == (best.get("pdf_url"), True)), candidates[0])
    loc = w.get("primary_location") or {}
    for u in ((w.get("open_access") or {}).get("oa_url"), loc.get("landing_page_url"), (w.get("ids") or {}).get("doi")):
        if safe_url(u) and not any(h in u for h in UNREACHABLE):
            return u, False
    return w.get("id"), False  # the paper's page on OpenAlex


def _paper(w: dict) -> dict:
    loc = w.get("primary_location") or {}
    url, pdf = _best_link(w)
    url = safe_url(url)  # the link comes from another service: only http(s) may reach the page
    authors = [((a.get("author") or {}).get("display_name") or "") for a in (w.get("authorships") or [])]
    authors = [a for a in authors if a]
    return {
        "title": re.sub(r"<[^>]+>", "", w.get("display_name") or "").strip(),
        "year": w.get("publication_year"),
        "authors": ", ".join(authors[:3]) + (" …" if len(authors) > 3 else ""),
        "venue": ((loc.get("source") or {}).get("display_name") or ""),
        "url": url,
        "pdf": pdf,
        "cited": w.get("cited_by_count") or 0,
    }


def papers(domain: str, raw: str, limit: int = 8) -> dict:
    """Open-access papers on a topic, most relevant first (cached for 6 hours)."""
    raw = (raw or "").strip()[:120] or TOPICS[domain]["default"]
    query = to_english(domain, raw)
    key = (domain, query.lower())
    hit = _papers_cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    params = {
        "search": query,
        "filter": "is_oa:true,primary_topic.field.id:%s,from_publication_date:2005-01-01" % FIELDS[domain],
        "per_page": limit,
        "select": "id,ids,display_name,publication_year,authorships,primary_location,best_oa_location,locations,open_access,cited_by_count",
    }
    if not _outbound.acquire(timeout=3):
        raise RuntimeError("busy")
    try:
        data = fetch_json(OPENALEX + "?" + urllib.parse.urlencode(params, safe=":|,"))
    finally:
        _outbound.release()
    payload = {
        "query": query,
        "translated": query != raw,
        "total": (data.get("meta") or {}).get("count", 0),
        "items": [p for p in (_paper(w) for w in data.get("results") or []) if p["title"] and p["url"]],
    }
    with _papers_lock:
        if len(_papers_cache) > 500:
            _papers_cache.clear()
        _papers_cache[key] = (time.time() + PAPERS_TTL, payload)
    return payload


def build(domain: str, raw: str) -> dict:
    raw = (raw or "").strip()[:120] or TOPICS[domain]["default"]
    raw = to_english(domain, raw)
    q = quote(raw)
    return {
        "domain": domain,
        "query": raw,
        "default": TOPICS[domain]["default"],
        "topics": [dict(zip(TOPIC_LANGS, TOPIC_NAMES.get(en, ())), en=en, ar=ar) for en, ar in TOPICS[domain]["topics"]],
        "sources": [{"name": n, "ar": a, "en": e, "url": fn(q, raw)} for n, a, e, fn in SOURCES[domain]],
    }
