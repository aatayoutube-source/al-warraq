"""Search-engine side of the site: crawlable category and author pages, the home page's head tags,
robots.txt, the main sitemap, and IndexNow (instant indexing on Bing, Yandex, Seznam...).

    python -m app.seo indexnow            # tell IndexNow about the home, category and author pages
    python -m app.seo indexnow --books    # ... and every book page as well (in batches of 10,000)

Settings (environment): SITE_URL (the public address, needed for absolute links), INDEXNOW_KEY,
GOOGLE_SITE_VERIFICATION, BING_SITE_VERIFICATION, YANDEX_VERIFICATION.
"""
import json
import math
import os
import re
import sys
import urllib.request
from urllib.parse import quote

from . import content, legal, modern
from .wikisource import WS_KIND
from .catalog import ARABIC_CAT, CATEGORIES
from .pages import (ARTICLES_NAME, BRAND, CSS, INFEED_AT, INFEED_MIN, LOGO_SVG, OG_LOCALE, SEARCH_ICON, T, UI_LANG_SHORT, UI_LANGS,
                    _authors, ad_head, ad_unit, analytics_head, book_author, book_title, canonical_path, esc, infeed_meta, infeed_unit,
                    lang_menu, lang_q, legal_links, native_unit, own_text, site_head)

PER_PAGE = 60
MAX_PAGES = 200  # category pages go this deep; the sitemaps list every single book anyway

S = {
    "ar": {
        "cat_h": "كتب {c} مجانية", "cat_d": "{n} في تصنيف «{c}»، مجانية سقط عنها حق النشر، تقرؤها كاملة من مصادرها المفتوحة.",
        "n_books": "{n} كتاباً", "n_poems": " و{p} قصيدة",
        "auth_h": "كتب {a}", "auth_d": "{n} من أعمال {a} مجانية في الملك العام، تقرؤها كاملة من مصادرها المفتوحة.",
        "cat_hm": "كتب {c}", "cat_dm": "{n} في تصنيف «{c}»: كتب سقط عنها حق النشر تقرؤها مجاناً، وكتب عربية حديثة نوصلك إلى صفحاتها لدى مصادرها القانونية.",
        "auth_dm": "{n} من أعمال {a} في مكتبة الوراق، نوصلك إليها في مصادرها المفتوحة والقانونية.",
        "cats": "التصنيفات", "authors": "مؤلفون مشهورون", "prev": "السابق", "next": "التالي", "page": "صفحة {p}",
        "open": "تصفّح في المكتبة", "home_t": "مكتبة الوراق | كتب مجانية وقصائد عربية في الملك العام",
        "intro_h": "ما هي مكتبة الوراق؟", "arts_h": "من مقالات المكتبة", "arts_all": "كل المقالات",
        "cat_about": "عن هذا التصنيف", "auth_about": "عن المؤلف",
        "arts_t": "مقالات مكتبة الوراق: أدلة القراءة والكتب والشعراء", "arts_d": "مقالات أصلية من مكتبة الوراق: أدلة لقراءة الكتب في الملك العام، ومداخل إلى الشعر العربي والروايات الكلاسيكية وتاريخ المكتبات.",
        "arts_lead": "مقالات نكتبها لتعينك على الاختيار والقراءة: أدلة عملية، ومداخل إلى كتّاب وأعمال، وصفحات من تاريخ الكتاب العربي.",
        "minutes": "{n} دقائق قراءة", "more_arts": "مقالات أخرى", "arts_lang": "",
    },
    "en": {
        "cat_h": "Free {c} books", "cat_d": "{n} in “{c}”, free and in the public domain, readable in full at their open sources.",
        "n_books": "{n} books", "n_poems": " and {p} poems",
        "auth_h": "Books by {a}", "auth_d": "{n} public-domain works by {a}, free to read at their open sources.",
        "cat_hm": "{c} books", "cat_dm": "{n} in “{c}”: public-domain books to read free, and modern Arabic books with links to their pages at legal sources.",
        "auth_dm": "{n} works by {a} at Al-Warraq Library, with links to their open and legal sources.",
        "cats": "Categories", "authors": "Famous authors", "prev": "Previous", "next": "Next", "page": "page {p}",
        "open": "Browse in the library", "home_t": "Al-Warraq Library | Free public-domain books and Arabic poetry",
        "intro_h": "What is Al-Warraq Library?", "arts_h": "From the library's articles", "arts_all": "All articles",
        "cat_about": "About this category", "auth_about": "About the author",
        "arts_t": "Al-Warraq Library articles: reading guides, books and poets", "arts_d": "Original articles from Al-Warraq Library (in Arabic): guides to public-domain books, Arabic poetry, classic novels and the history of libraries.",
        "arts_lead": "Articles we write to help you choose and read: practical guides, introductions to writers and works, and pages from the history of the Arabic book.",
        "minutes": "{n} min read", "more_arts": "More articles", "arts_lang": "The articles are written in Arabic.",
        "home_og": "Al-Warraq Library | مكتبة الوراق",
        "home_d": "Al-Warraq Library (مكتبة الوراق): over a million free public-domain books, Arabic poetry and modern Arabic "
                  "books, with covers and categories, linked to their legal sources.",
    },
    "zh": {
        "cat_h": "{c}：免费图书", "cat_d": "“{c}”类别中的{n}，均为免费的公有领域作品，可在开放来源阅读全文。",
        "n_books": "{n} 本图书", "n_poems": "和 {p} 首诗歌",
        "auth_h": "{a}的作品", "auth_d": "{a}的 {n} 部公有领域作品，可在开放来源免费阅读。",
        "cat_hm": "{c}：图书", "cat_dm": "“{c}”类别中的{n}：既有可免费阅读的公有领域图书，也有现代阿拉伯语图书，并附上它们在合法来源上的页面链接。",
        "auth_dm": "Al-Warraq 图书馆收录的{a}的 {n} 部作品，并附上它们在开放、合法来源上的链接。",
        "cats": "分类", "authors": "著名作者", "prev": "上一页", "next": "下一页", "page": "第 {p} 页",
        "open": "在图书馆中浏览", "home_t": "Al-Warraq 图书馆 | 免费的公有领域图书与阿拉伯语诗歌",
        "intro_h": "什么是 Al-Warraq 图书馆？", "arts_h": "图书馆文章精选", "arts_all": "全部文章",
        "cat_about": "关于这个分类", "auth_about": "关于作者",
        "arts_t": "Al-Warraq 图书馆文章：阅读指南、图书与诗人", "arts_d": "Al-Warraq 图书馆的原创文章（阿拉伯语）：公有领域图书阅读指南、阿拉伯诗歌、经典小说与图书馆的历史。",
        "arts_lead": "我们撰写这些文章，帮助你挑选和阅读：实用指南、作家与作品介绍，以及阿拉伯图书史上的篇章。",
        "minutes": "阅读约 {n} 分钟", "more_arts": "更多文章", "arts_lang": "这些文章以阿拉伯语撰写。",
        "home_og": "Al-Warraq 图书馆 | مكتبة الوراق",
        "home_d": "Al-Warraq 图书馆（مكتبة الوراق）：超过一百万本免费的公有领域图书、阿拉伯语诗歌和现代阿拉伯语图书，附封面和分类，并链接到它们的合法来源。",
    },
    "fr": {
        "cat_h": "{c} : livres gratuits", "cat_d": "{n} dans « {c} », gratuits et du domaine public, à lire en entier à leurs sources ouvertes.",
        "n_books": "{n} livres", "n_poems": " et {p} poèmes",
        "auth_h": "Livres de {a}", "auth_d": "{n} œuvres de {a} du domaine public, à lire gratuitement à leurs sources ouvertes.",
        "cat_hm": "{c} : livres", "cat_dm": "{n} dans « {c} » : des livres du domaine public à lire gratuitement, et des livres arabes modernes avec des liens vers leurs pages chez des sources légales.",
        "auth_dm": "{n} œuvres de {a} à la Bibliothèque Al-Warraq, avec des liens vers leurs sources ouvertes et légales.",
        "cats": "Catégories", "authors": "Auteurs célèbres", "prev": "Précédent", "next": "Suivant", "page": "page {p}",
        "open": "Parcourir dans la bibliothèque", "home_t": "Bibliothèque Al-Warraq | Livres gratuits du domaine public et poésie arabe",
        "intro_h": "Qu’est-ce que la Bibliothèque Al-Warraq ?", "arts_h": "Articles de la bibliothèque", "arts_all": "Tous les articles",
        "cat_about": "À propos de cette catégorie", "auth_about": "À propos de l’auteur",
        "arts_t": "Articles de la Bibliothèque Al-Warraq : guides de lecture, livres et poètes", "arts_d": "Articles originaux de la Bibliothèque Al-Warraq (en arabe) : guides des livres du domaine public, poésie arabe, romans classiques et histoire des bibliothèques.",
        "arts_lead": "Des articles que nous écrivons pour vous aider à choisir et à lire : guides pratiques, présentations d’auteurs et d’œuvres, et pages d’histoire du livre arabe.",
        "minutes": "{n} min de lecture", "more_arts": "Autres articles", "arts_lang": "Les articles sont rédigés en arabe.",
        "home_og": "Bibliothèque Al-Warraq | مكتبة الوراق",
        "home_d": "Bibliothèque Al-Warraq (مكتبة الوراق) : plus d’un million de livres gratuits du domaine public, de la poésie arabe et des "
                  "livres arabes modernes, avec couvertures et catégories, reliés à leurs sources légales.",
    },
    "es": {
        "cat_h": "{c}: libros gratis", "cat_d": "{n} en «{c}», gratis y de dominio público, para leer completos en sus fuentes abiertas.",
        "n_books": "{n} libros", "n_poems": " y {p} poemas",
        "auth_h": "Libros de {a}", "auth_d": "{n} obras de dominio público de {a}, para leer gratis en sus fuentes abiertas.",
        "cat_hm": "{c}: libros", "cat_dm": "{n} en «{c}»: libros de dominio público para leer gratis y libros árabes modernos con enlaces a sus páginas en fuentes legales.",
        "auth_dm": "{n} obras de {a} en la Biblioteca Al-Warraq, con enlaces a sus fuentes abiertas y legales.",
        "cats": "Categorías", "authors": "Autores célebres", "prev": "Anterior", "next": "Siguiente", "page": "página {p}",
        "open": "Explorar en la biblioteca", "home_t": "Biblioteca Al-Warraq | Libros gratis de dominio público y poesía árabe",
        "intro_h": "¿Qué es la Biblioteca Al-Warraq?", "arts_h": "Artículos de la biblioteca", "arts_all": "Todos los artículos",
        "cat_about": "Sobre esta categoría", "auth_about": "Sobre el autor",
        "arts_t": "Artículos de la Biblioteca Al-Warraq: guías de lectura, libros y poetas", "arts_d": "Artículos originales de la Biblioteca Al-Warraq (en árabe): guías de libros de dominio público, poesía árabe, novelas clásicas e historia de las bibliotecas.",
        "arts_lead": "Artículos que escribimos para ayudarte a elegir y a leer: guías prácticas, introducciones a autores y obras, y páginas de la historia del libro árabe.",
        "minutes": "{n} min de lectura", "more_arts": "Más artículos", "arts_lang": "Los artículos están escritos en árabe.",
        "home_og": "Biblioteca Al-Warraq | مكتبة الوراق",
        "home_d": "Biblioteca Al-Warraq (مكتبة الوراق): más de un millón de libros gratis de dominio público, poesía árabe y libros árabes "
                  "modernos, con portadas y categorías, enlazados a sus fuentes legales.",
    },
    "pt": {
        "cat_h": "{c}: livros grátis", "cat_d": "{n} em “{c}”, grátis e em domínio público, para ler na íntegra nas fontes abertas.",
        "n_books": "{n} livros", "n_poems": " e {p} poemas",
        "auth_h": "Livros de {a}", "auth_d": "{n} obras de {a} em domínio público, para ler de graça nas fontes abertas.",
        "cat_hm": "{c}: livros", "cat_dm": "{n} em “{c}”: livros em domínio público para ler de graça e livros árabes modernos com links para as páginas deles em fontes legais.",
        "auth_dm": "{n} obras de {a} na Biblioteca Al-Warraq, com links para as fontes abertas e legais.",
        "cats": "Categorias", "authors": "Autores famosos", "prev": "Anterior", "next": "Próxima", "page": "página {p}",
        "open": "Navegar na biblioteca", "home_t": "Biblioteca Al-Warraq | Livros grátis em domínio público e poesia árabe",
        "intro_h": "O que é a Biblioteca Al-Warraq?", "arts_h": "Artigos da biblioteca", "arts_all": "Todos os artigos",
        "cat_about": "Sobre esta categoria", "auth_about": "Sobre o autor",
        "arts_t": "Artigos da Biblioteca Al-Warraq: guias de leitura, livros e poetas", "arts_d": "Artigos originais da Biblioteca Al-Warraq (em árabe): guias de livros em domínio público, poesia árabe, romances clássicos e a história das bibliotecas.",
        "arts_lead": "Artigos que escrevemos para ajudar você a escolher e ler: guias práticos, apresentações de autores e obras e páginas da história do livro árabe.",
        "minutes": "{n} min de leitura", "more_arts": "Mais artigos", "arts_lang": "Os artigos são escritos em árabe.",
        "home_og": "Biblioteca Al-Warraq | مكتبة الوراق",
        "home_d": "Biblioteca Al-Warraq (مكتبة الوراق): mais de um milhão de livros grátis em domínio público, poesia árabe e livros árabes "
                  "modernos, com capas e categorias, ligados às fontes legais.",
    },
    "ja": {
        "cat_h": "{c}：無料の本", "cat_d": "「{c}」の{n}。いずれも無料のパブリックドメイン作品で、公開されている情報源で全文を読めます。",
        "n_books": "{n}冊の本", "n_poems": "と{p}篇の詩",
        "auth_h": "{a}の本", "auth_d": "{a}のパブリックドメイン作品{n}点。公開されている情報源で無料で読めます。",
        "cat_hm": "{c}の本", "cat_dm": "「{c}」の{n}：無料で読めるパブリックドメインの本と、合法的な情報源のページへのリンク付きの現代アラビア語の本。",
        "auth_dm": "アル・ワッラーク図書館にある{a}の作品{n}点。公開された合法的な情報源へのリンク付き。",
        "cats": "カテゴリー", "authors": "著名な著者", "prev": "前へ", "next": "次へ", "page": "{p}ページ",
        "open": "図書館で見る", "home_t": "アル・ワッラーク図書館 | 無料のパブリックドメインの本とアラビア語の詩",
        "intro_h": "アル・ワッラーク図書館とは？", "arts_h": "図書館の記事から", "arts_all": "すべての記事",
        "cat_about": "このカテゴリーについて", "auth_about": "著者について",
        "arts_t": "アル・ワッラーク図書館の記事：読書ガイド、本と詩人", "arts_d": "アル・ワッラーク図書館のオリジナル記事（アラビア語）：パブリックドメインの本のガイド、アラビア語の詩、古典小説、図書館の歴史。",
        "arts_lead": "本を選び、読むための記事です。実用的なガイド、作家と作品の紹介、そしてアラビア語の本の歴史をお届けします。",
        "minutes": "約{n}分で読めます", "more_arts": "ほかの記事", "arts_lang": "記事はアラビア語で書かれています。",
        "home_og": "アル・ワッラーク図書館 | مكتبة الوراق",
        "home_d": "アル・ワッラーク図書館（مكتبة الوراق）：100万冊以上の無料のパブリックドメインの本、アラビア語の詩、現代アラビア語の本を、"
                  "表紙とカテゴリー付きで紹介し、合法的な情報源へ案内します。",
    },
    "de": {
        "cat_h": "{c}: kostenlose Bücher", "cat_d": "{n} in „{c}“, kostenlos und gemeinfrei, vollständig an ihren offenen Quellen lesbar.",
        "n_books": "{n} Bücher", "n_poems": " und {p} Gedichte",
        "auth_h": "Bücher von {a}", "auth_d": "{n} gemeinfreie Werke von {a}, kostenlos an ihren offenen Quellen lesbar.",
        "cat_hm": "{c}: Bücher", "cat_dm": "{n} in „{c}“: gemeinfreie Bücher zum kostenlosen Lesen und moderne arabische Bücher mit Links zu ihren Seiten bei legalen Quellen.",
        "auth_dm": "{n} Werke von {a} in der Bibliothek Al-Warraq, mit Links zu ihren offenen und legalen Quellen.",
        "cats": "Kategorien", "authors": "Berühmte Autoren", "prev": "Zurück", "next": "Weiter", "page": "Seite {p}",
        "open": "In der Bibliothek stöbern", "home_t": "Bibliothek Al-Warraq | Kostenlose gemeinfreie Bücher und arabische Dichtung",
        "intro_h": "Was ist die Bibliothek Al-Warraq?", "arts_h": "Aus den Artikeln der Bibliothek", "arts_all": "Alle Artikel",
        "cat_about": "Über diese Kategorie", "auth_about": "Über den Autor",
        "arts_t": "Artikel der Bibliothek Al-Warraq: Leseführer, Bücher und Dichter", "arts_d": "Originalartikel der Bibliothek Al-Warraq (auf Arabisch): Leitfäden zu gemeinfreien Büchern, arabische Dichtung, klassische Romane und die Geschichte der Bibliotheken.",
        "arts_lead": "Artikel, die wir schreiben, um Ihnen bei Auswahl und Lektüre zu helfen: praktische Leitfäden, Einführungen in Autoren und Werke und Seiten aus der Geschichte des arabischen Buches.",
        "minutes": "{n} Min. Lesezeit", "more_arts": "Weitere Artikel", "arts_lang": "Die Artikel sind auf Arabisch verfasst.",
        "home_og": "Bibliothek Al-Warraq | مكتبة الوراق",
        "home_d": "Bibliothek Al-Warraq (مكتبة الوراق): über eine Million kostenlose gemeinfreie Bücher, arabische Dichtung und moderne "
                  "arabische Bücher, mit Umschlägen und Kategorien, verlinkt mit ihren legalen Quellen.",
    },
}
for _ui in UI_LANGS:  # a word a language lacks is shown in English
    S[_ui] = dict(S["en"], **S.get(_ui, {}))

EXTRA_CSS = """
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 4px}
.chips a{background:var(--card);border:1.5px solid var(--line);border-radius:12px;padding:5px 14px;text-decoration:none;color:var(--ink);font-size:.9rem}
.chips a:hover,.chips a[aria-current]{border-color:var(--brand-2);color:var(--brand)}
.pager{display:flex;justify-content:space-between;gap:12px;margin:22px 0}
.pager a{background:var(--card);border:1.5px solid var(--line);border-radius:12px;padding:8px 18px;text-decoration:none}
h1{margin-top:22px}
"""


def verification_meta() -> str:
    tags = []
    for env, name in (("GOOGLE_SITE_VERIFICATION", "google-site-verification"), ("BING_SITE_VERIFICATION", "msvalidate.01"),
                      ("YANDEX_VERIFICATION", "yandex-verification")):
        if os.environ.get(env):
            tags.append('<meta name="%s" content="%s">' % (name, esc(os.environ[env])))
    return "\n".join(tags)


def _ld(obj) -> str:
    return '<script type="application/ld+json">%s</script>' % json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _alternates(base: str, path: str, extra: str = "") -> str:
    """hreflang links: Arabic is the main language of the site (no ?lang=), every other one is ?lang=<code>."""
    def url(ui):
        q = lang_q(ui)
        return base + path + q + (("&" if q else "?") + extra if extra else "")
    return "\n".join(['<link rel="alternate" hreflang="%s" href="%s">' % (ui, esc(url(ui))) for ui in UI_LANGS]
                     + ['<link rel="alternate" hreflang="x-default" href="%s">' % esc(url("ar"))])


# ---------- the home page: the same file, with the tags only the server can know ----------

_home = {}  # ui -> (file times, index.html with that language's words in place)
# app.js keeps the interface strings (const T = {ar: {...}, en: {...}, zh: ...}): the server reads them there, one source
_STRING = re.compile(r"^ +(\w+): '((?:[^'\\]|\\.)*)',?$", re.M)
_DATA_I = re.compile(r'(<([a-z0-9]+)[^>]*? data-i="(\w+)"[^>]*>)([^<]*)(</\2>)')
_DATA_IPH = re.compile(r' data-iph="(\w+)"')
_DATA_IARL = re.compile(r' data-iarl="(\w+)"(?: aria-label="[^"]*")?')
_LHREF = re.compile(r' href="([^"]*)" data-lhref="([^"]*)"')


def ui_strings(frontend_dir: str) -> dict:
    """{"ar": {...}, "en": {...}, ...}: the interface strings of app.js, the very words its script puts in the page
    (a word or a language the script lacks is the English one, as the script itself does; Arabic keeps the page's
    own words instead)."""
    with open(os.path.join(frontend_dir, "app.js"), encoding="utf-8") as f:
        src = f.read()
    table = src[src.index("const T = {"):]
    out = {}
    for ui in UI_LANGS:
        start = table.find("\n        %s: {" % ui)
        if start < 0:
            continue
        end = table.index("\n        }", start)
        out[ui] = {k: v.replace("\\'", "'") for k, v in _STRING.findall(table[start:end])}
    return {ui: out.get(ui, {}) if ui == "ar" else dict(out.get("en", {}), **out.get(ui, {})) for ui in UI_LANGS}


def _home_template(frontend_dir: str, ui: str) -> str:
    """index.html with its words already in place for that language. A crawler reads the page before (or without)
    running the script: /?lang=en must be English in its very HTML (language, title, headings), not an empty shell
    with the Arabic title, or English searches have nothing to find."""
    paths = [os.path.join(frontend_dir, n) for n in ("index.html", "app.js")]
    key = tuple(os.path.getmtime(p) for p in paths if os.path.exists(p))
    hit = _home.get(ui)
    if hit and hit[0] == key:
        return hit[1]
    with open(paths[0], encoding="utf-8") as f:
        html = f.read()
    try:
        t = ui_strings(frontend_dir)[ui]
    except (OSError, ValueError):  # no script beside the page: the words are left to it
        t = {}
    if t:
        html = _DATA_I.sub(lambda m: m.group(1) + (esc(t[m.group(3)]) if m.group(3) in t else m.group(4)) + m.group(5), html)
        html = _DATA_IPH.sub(lambda m: m.group(0) + (' placeholder="%s" aria-label="%s"' % ((esc(t[m.group(1)]),) * 2)
                                                     if m.group(1) in t else ""), html)
        html = _DATA_IARL.sub(lambda m: ' data-iarl="%s" aria-label="%s"' % (m.group(1), esc(t.get(m.group(1), ""))), html)
        html = re.sub(r'(id="filtBtn"[^>]*>)(</button>)', lambda m: m.group(1) + esc(t.get("filters", "")) + m.group(2), html)
    if ui != "ar":
        s = S[ui]
        html = html.replace('<html lang="ar" dir="rtl">', '<html lang="%s" dir="%s">' % (ui, T[ui]["dir"]), 1)
        html = re.sub(r"<title>[^<]*</title>", lambda m: "<title>%s</title>" % esc(s["home_t"]), html, count=1)
        for attr, value in (('name="description"', s["home_d"]), ('property="og:description"', s["home_d"]),
                            ('property="og:title"', s["home_og"]), ('name="twitter:title"', s["home_og"])):
            html = re.sub(r'<meta %s content="[^"]*">' % attr, lambda m: '<meta %s content="%s">' % (attr, esc(value)), html, count=1)
        html = _LHREF.sub(lambda m: ' href="%s%s" data-lhref="%s"' % (m.group(2), lang_q(ui), m.group(2)), html)
    # the language menu shows which one this is
    html = html.replace(' data-ui="%s"' % ui, ' data-ui="%s" aria-current="true"' % ui, 1)
    html = re.sub(r'(<span id="langCur">)[^<]*(</span>)', lambda m: m.group(1) + esc(UI_LANG_SHORT[ui]) + m.group(2), html, count=1)
    _home[ui] = (key, html)
    return html


def with_nonce(page: str, nonce: str) -> str:
    """Every script of the page carries the response's nonce: the only scripts its Content-Security-Policy runs."""
    return page.replace("<script", '<script nonce="%s"' % esc(nonce)) if nonce else page


def _home_intro(ui: str) -> str:
    """What the library is (its own words) and its latest articles, for the home page."""
    s, q = S[ui], lang_q(ui)
    paras = content.home(ui)
    arts = content.articles()[:6]
    if not paras and not arts:
        return ""
    out = '<div class="intro" data-srv-lang="%s">' % ui
    if paras:
        out += "<h2>%s</h2>%s" % (esc(s["intro_h"]), own_text(paras, ui))
    if arts:
        out += '<div class="intro-arts"><h3>%s</h3><ul>%s</ul><a class="intro-all" href="/articles%s">%s</a></div>' % (
            esc(s["arts_h"]), "".join('<li><a href="/articles/%s" lang="ar">%s</a></li>' % (esc(a["slug"]), esc(a["title"])) for a in arts),
            q, esc(s["arts_all"]))
    return out + "</div>"


def home_html(frontend_dir: str, base: str, ui: str = "ar", nonce: str = "", search: bool = False) -> str:
    canon = base + "/" + lang_q(ui)
    head = "\n".join([
        '<link rel="canonical" href="%s">' % esc(canon),
        _alternates(base, "/"),
        '<meta property="og:url" content="%s">' % esc(canon),
        '<meta property="og:image" content="%s/og-image.png">' % esc(base),
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">',
        '<meta property="og:locale" content="%s">' % OG_LOCALE[ui],
        '<meta name="twitter:image" content="%s/og-image.png">' % esc(base),
        verification_meta(),
        analytics_head(),
        ad_head() if nonce else "",
        infeed_meta() if nonce else "",
        _ld({"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "@id": base + "/#site", "url": base + "/", "name": BRAND["ar"], "alternateName": BRAND["en"],
             "inLanguage": list(UI_LANGS), "publisher": {"@id": base + "/#org"},
             "potentialAction": {"@type": "SearchAction", "target": base + "/?q={search_term_string}",
                                 "query-input": "required name=search_term_string"}},
            {"@type": "Organization", "@id": base + "/#org", "name": BRAND["ar"], "alternateName": BRAND["en"], "url": base + "/",
             "logo": base + "/icon-512.png"},
        ]}),
    ])
    links = " ".join('<a href="/category/%s%s">%s</a>' % (k, lang_q(ui), esc(v[ui])) for k, v in CATEGORIES.items())
    ad = '<div class="wrap">%s</div>' % ad_unit(ui) if nonce and ad_unit(ui) else ""
    first = '<div class="wrap">%s</div>' % (ad_unit(ui) + native_unit(ui)) if nonce and (ad_unit(ui) or native_unit(ui)) else ""
    page = (_home_template(frontend_dir, ui).replace("<!--SEO:HEAD-->", head).replace("<!--SEO:CATS-->", links)
            .replace("<!--SEO:AD-->", first, 1).replace("<!--SEO:AD-->", ad).replace("<!--SEO:INTRO-->", _home_intro(ui)))
    if search:  # /?q=...: the same page showing search results, not a page of its own for search engines
        page = page.replace('<meta name="robots" content="index,follow">', '<meta name="robots" content="noindex,follow">', 1)
    return with_nonce(page, nonce)


# ---------- category and author pages (plain HTML: every crawler can read and follow them) ----------

def _shell(ui, base, path, title, desc, body, ld, page=1, extra_q="", extra_css="", nonce="", robots="", canonical="",
           alternates=True):
    t = T[ui]
    canon = base + path + "?" + "&".join(x for x in (lang_q(ui)[1:], ("page=%d" % page if page > 1 else "")) if x)
    canon = canonical or canon.rstrip("?")
    return """<!doctype html>
<html lang="{ui}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
{adsense}
{ad_head}
{robots}<link rel="canonical" href="{canon}">
{alts}
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:site_name" content="{brand}">
<meta property="og:image" content="{base}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Alexandria:wght@700;800&family=Amiri:wght@400;700&family=Fraunces:opsz,wght@9..144,700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap">
{ld}
<style>{css}{extra}</style>
</head>
<body>
<header class="bar"><div class="wrap"><a class="brand" href="/">{logo}<span>{brand}</span></a>
<form class="sbox" action="/#browse" method="get" role="search">{icon}<input type="search" name="q" placeholder="{ph}" aria-label="{ph}"><button type="submit">{search}</button></form>
<nav><a href="/#browse">{all}</a>{menu}</nav></div></header>
<main class="wrap">
{body}
<footer>{legal}<p>{note}</p></footer>
</main>
</body>
</html>
""".format(ui=ui, dir=t["dir"], title=esc(title), desc=esc(desc), canon=esc(canon), alts=_alternates(base, path) if alternates else "",
           robots=('<meta name="robots" content="%s">\n' % esc(robots)) if robots else "",
           brand=esc(BRAND[ui]), base=esc(base), ld=ld, css=CSS, extra=EXTRA_CSS + extra_css, logo=LOGO_SVG, icon=SEARCH_ICON,
           ph=esc(t["ph"]), search=esc(t["search"]), all=esc(t["all"]), menu=lang_menu(ui, lambda c: path + "?lang=" + c),
           # the native banner goes in the first ad place only (one per page)
           body=body.replace("<!--SEO:AD-->", ad_unit(ui) + native_unit(ui) if nonce else "", 1)
           .replace("<!--SEO:AD-->", ad_unit(ui) if nonce else "").replace("<!--SEO:FEED-->", infeed_unit(ui) if nonce else ""),
           note=esc(t["note"]), legal=legal_links(ui), adsense=site_head(), ad_head=ad_head() if nonce else "")


def _book_list(conn, rows, ui) -> str:
    authors = _authors(conn)
    items = []
    for r in rows:
        a = book_author(r, ui, authors)
        items.append('<li><a href="%s">%s%s</a></li>' % (esc(canonical_path(r)), esc(book_title(r, ui)), ("<small>%s</small>" % esc(a)) if a else ""))
    if len(items) >= INFEED_MIN:  # the in-feed ad's place, filled by _shell on pages that show ads
        items.insert(INFEED_AT, "<!--SEO:FEED-->")
    return '<ul class="rel">%s</ul>' % "".join(items)


def _pager(path, ui, page, pages) -> str:
    s, lang = S[ui], lang_q(ui, amp=True)
    prev = '<a rel="prev" href="%s?%spage=%d">%s</a>' % (path, lang, page - 1, s["prev"]) if page > 1 else "<span></span>"
    nxt = '<a rel="next" href="%s?%spage=%d">%s</a>' % (path, lang, page + 1, s["next"]) if page < pages else "<span></span>"
    return '<nav class="pager">%s%s</nav>' % (prev, nxt)


def _breadcrumbs(base, ui, name, path) -> dict:
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": T[ui]["home"], "item": base + "/"},
        {"@type": "ListItem", "position": 2, "name": name, "item": base + path}]}


def _has_modern(conn, cond: str, arg) -> bool:
    """Whether some of these books are modern ones under copyright (Safahat / Open Library)."""
    return bool(conn.execute("SELECT 1 FROM books WHERE " + cond + " AND curated IN (?, ?) LIMIT 1", (arg,) + modern.KINDS).fetchone())


def category_page(conn, key: str, base: str, ui: str = "ar", page: int = 1, nonce: str = ""):
    if key not in CATEGORIES:
        return None
    # the Arabic category is every book written in Arabic, not a topic
    cond, arg = ("lang=?", "ar") if key == ARABIC_CAT else ("cat=?", key)
    total = conn.execute("SELECT COUNT(*) FROM books WHERE " + cond, (arg,)).fetchone()[0]
    pages = max(1, min(MAX_PAGES, math.ceil(total / PER_PAGE)))
    if page < 1 or page > pages:
        return None
    rows = conn.execute("SELECT * FROM books WHERE " + cond + " ORDER BY ord LIMIT ? OFFSET ?", (arg, PER_PAGE, (page - 1) * PER_PAGE)).fetchall()
    s, name = S[ui], CATEGORIES[key][ui]
    path = "/category/" + key
    if _has_modern(conn, cond, arg):  # not every book here is free: say so
        s = dict(s, cat_h=s["cat_hm"], cat_d=s["cat_dm"])
    title = s["cat_h"].format(c=name) + ((" — " + s["page"].format(p=page)) if page > 1 else "") + " | " + BRAND[ui]
    # every poem is Arabic and in "poe": counted from the index alone
    poems = conn.execute("SELECT COUNT(*) FROM books WHERE curated=?", (WS_KIND,)).fetchone()[0] if key in (ARABIC_CAT, "poe") else 0
    n = s["n_books"].format(n="{:,}".format(total - poems)) + (s["n_poems"].format(p="{:,}".format(poems)) if poems else "")
    desc = s["cat_d"].format(n=n, c=name)
    chips = "".join('<a href="/category/%s%s"%s>%s</a>' % (k, lang_q(ui), ' aria-current="page"' if k == key else "", esc(v[ui]))
                    for k, v in CATEGORIES.items())
    body = ('<p class="crumbs"><a href="/">%s</a> / %s</p><h1>%s</h1><p class="desc">%s <a href="/?cat=%s#browse">%s</a></p>'
            '<nav class="chips" aria-label="%s">%s</nav>%s<!--SEO:AD-->%s%s'
            % (esc(T[ui]["home"]), esc(name), esc(s["cat_h"].format(c=name)), esc(desc), key, esc(s["open"]), esc(s["cats"]), chips,
               _text_section(s["cat_about"], content.category(key, ui), ui) if page == 1 else "",
               _book_list(conn, rows, ui), _pager(path, ui, page, pages)))
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": title, "description": desc, "url": base + path, "inLanguage": ui,
         "isPartOf": {"@id": base + "/#site"}},
        _breadcrumbs(base, ui, name, path)]})
    return with_nonce(_shell(ui, base, path, title, desc, body, ld, page, nonce=nonce), nonce)


def author_page(conn, key: str, base: str, ui: str = "ar", page: int = 1, nonce: str = ""):
    a = conn.execute("SELECT * FROM authors WHERE key=?", (key,)).fetchone()
    if not a:
        return None
    total = conn.execute("SELECT COUNT(*) FROM books WHERE author_key=?", (key,)).fetchone()[0]
    pages = max(1, min(MAX_PAGES, math.ceil(total / PER_PAGE)))
    if not total or page < 1 or page > pages:
        return None
    rows = conn.execute("SELECT * FROM books WHERE author_key=? ORDER BY ord LIMIT ? OFFSET ?", (key, PER_PAGE, (page - 1) * PER_PAGE)).fetchall()
    s, name = S[ui], (a["ar"] if ui == "ar" and a["ar"] else a["en"])
    if _has_modern(conn, "author_key=?", key):
        s = dict(s, auth_d=s["auth_dm"])
    path = "/author/" + quote(key)
    title = s["auth_h"].format(a=name) + ((" (%s)" % a["years"]) if a["years"] else "") + ((" — " + s["page"].format(p=page)) if page > 1 else "") + " | " + BRAND[ui]
    desc = s["auth_d"].format(n="{:,}".format(total), a=name)
    others = conn.execute("SELECT key, en, ar FROM authors ORDER BY ord LIMIT 40").fetchall()
    chips = "".join('<a href="/author/%s%s">%s</a>' % (quote(o["key"]), lang_q(ui), esc(o["ar"] if ui == "ar" else o["en"]))
                    for o in others if o["key"] != key)
    bio = content.author(key, ui)
    body = ('<p class="crumbs"><a href="/">%s</a> / %s</p><h1>%s</h1><p class="desc">%s <a href="/?ak=%s#browse">%s</a></p>%s<!--SEO:AD-->%s%s'
            '<h2>%s</h2><nav class="chips">%s</nav>'
            % (esc(T[ui]["home"]), esc(name), esc(s["auth_h"].format(a=name)), esc(desc), esc(quote(key)), esc(s["open"]),
               _text_section(s["auth_about"], bio, ui) if page == 1 else "",
               _book_list(conn, rows, ui), _pager(path, ui, page, pages), esc(s["authors"]), chips))
    person = {"@type": "Person", "name": a["en"], "alternateName": a["ar"]}
    if bio:
        person["description"] = _plain_text(bio[0])
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "ProfilePage", "name": title, "url": base + path, "inLanguage": ui, "mainEntity": person},
        _breadcrumbs(base, ui, name, path)]})
    robots = "" if author_indexable(conn, key, ui) else "noindex,follow"
    return with_nonce(_shell(ui, base, path, title, desc, body, ld, page, nonce=nonce if not robots else "", robots=robots), nonce)


def _text_section(heading: str, paras, ui: str) -> str:
    return '<section class="intro"><h2>%s</h2>%s</section>' % (esc(heading), own_text(paras, ui)) if paras else ""


def _plain_text(text: str) -> str:
    return " ".join(re.sub(r"\*\*([^*]+)\*\*", r"\1", re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)).split())


def author_indexable(conn, key: str, ui: str = "ar") -> bool:
    """An author page stands on its own with a biography, or with a first page of titles long enough to read
    (content.MIN_WORDS); otherwise THIN_NOINDEX keeps it out of search results, the sitemap and ads."""
    if not content.thin_noindex() or content.author(key, ui):
        return True
    rows = conn.execute("SELECT title, title_ar FROM books WHERE author_key=? ORDER BY ord LIMIT ?", (key, PER_PAGE)).fetchall()
    return content.words([book_title(r, ui) for r in rows]) >= content.MIN_WORDS


# ---------- articles (written in Arabic; the frame follows the visitor's language) ----------

ARTICLE_CSS = """
.post{max-width:760px}.post h1{margin:14px 0 6px;font:800 clamp(1.6rem,4vw,2.2rem)/1.5 "Alexandria","IBM Plex Sans Arabic",sans-serif}
.post .meta{color:var(--muted);font-size:.9rem;margin:0 0 10px}.post .lead{font-size:1.1rem;margin:0 0 16px}
.post h2{margin:30px 0 10px;font-size:1.35rem}.post h3{margin:22px 0 8px;font-size:1.12rem}
.post p,.post li{line-height:2}.post ul,.post ol{padding-inline-start:22px}.post li{margin:5px 0}
.post .verse{margin:16px 0;padding:14px 18px;border-inline-start:4px solid var(--brand-2);background:var(--card);border-radius:12px;font-family:"Amiri",serif;font-size:1.12rem}
.post .verse p{margin:4px 0;line-height:1.9}
.arts{list-style:none;margin:16px 0;padding:0;display:grid;gap:12px}
.arts li{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 18px}
.arts a{font-weight:700;font-size:1.08rem;text-decoration:none}.arts p{margin:6px 0 0;color:var(--muted)}.arts small{color:var(--muted)}
.intro{max-width:820px}.intro p+p{margin-top:.6em}
"""


def _minutes(words: int) -> int:
    return max(2, round(words / 200))


def articles_page(base: str, ui: str, nonce: str = "") -> str:
    s, q = S[ui], lang_q(ui)
    arts = content.articles()
    items = "".join(
        '<li><a href="/articles/%s%s" lang="ar">%s</a><p lang="ar">%s</p><small>%s · %s</small></li>'
        % (esc(a["slug"]), q, esc(a["title"]), esc(a.get("description", "")), esc(a.get("date", "")),
           esc(s["minutes"].format(n=_minutes(a["words"])))) for a in arts)
    name = ARTICLES_NAME[ui]
    body = ('<p class="crumbs"><a href="/%s">%s</a> / %s</p><h1>%s</h1><p class="desc">%s %s</p><ul class="arts">%s</ul><!--SEO:AD-->'
            % (q, esc(T[ui]["home"]), esc(name), esc(name), esc(s["arts_lead"]), esc(s["arts_lang"]), items))
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": s["arts_t"], "description": s["arts_d"], "url": base + "/articles", "inLanguage": "ar",
         "isPartOf": {"@id": base + "/#site"},
         "mainEntity": {"@type": "ItemList", "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "url": base + "/articles/" + a["slug"], "name": a["title"]} for i, a in enumerate(arts)]}},
        _breadcrumbs(base, ui, name, "/articles")]})
    return with_nonce(_shell(ui, base, "/articles", s["arts_t"] + " | " + BRAND[ui], s["arts_d"], body, ld, nonce=nonce,
                             extra_css=ARTICLE_CSS), nonce)


def article_page(slug: str, base: str, ui: str, nonce: str = ""):
    a = content.article(slug)
    if not a:
        return None
    s, q = S[ui], lang_q(ui)
    html_body = content.render(a["body"])
    # one ad after the second section, one at the end: well apart from the title, three at most on the page
    parts = html_body.split("<h2>")
    if len(parts) > 3:
        html_body = "<h2>".join(parts[:3]) + "<!--SEO:AD--><h2>" + "<h2>".join(parts[3:])
    others = [o for o in content.articles() if o["slug"] != slug][:5]
    more = ('<section class="intro"><h2>%s</h2><ul class="arts">%s</ul></section>' % (esc(s["more_arts"]), "".join(
        '<li><a href="/articles/%s%s" lang="ar">%s</a></li>' % (esc(o["slug"]), q, esc(o["title"])) for o in others))) if others else ""
    url = base + "/articles/" + slug
    body = ('<p class="crumbs"><a href="/%s">%s</a> / <a href="/articles%s">%s</a> / <span lang="ar">%s</span></p>'
            '<article class="post" lang="ar" dir="rtl"><h1>%s</h1><p class="meta">%s · %s</p><p class="lead">%s</p>%s</article><!--SEO:AD-->%s'
            % (q, esc(T[ui]["home"]), q, esc(ARTICLES_NAME[ui]), esc(a["title"]), esc(a["title"]), esc(a.get("date", "")),
               esc(S["ar"]["minutes"].format(n=_minutes(a["words"]))), esc(a.get("description", "")), html_body, more))
    org = {"@type": "Organization", "@id": base + "/#org", "name": BRAND["ar"], "url": base + "/",
           "logo": {"@type": "ImageObject", "url": base + "/icon-512.png"}}
    ld = _ld({"@context": "https://schema.org", "@graph": [
        {"@type": "Article", "@id": url + "#article", "headline": a["title"], "description": a.get("description", ""),
         "datePublished": a.get("date", ""), "dateModified": a.get("updated", a.get("date", "")), "inLanguage": "ar",
         "author": org, "publisher": org, "mainEntityOfPage": url, "image": base + "/og-image.png", "wordCount": a["words"]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": T["ar"]["home"], "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": ARTICLES_NAME["ar"], "item": base + "/articles"},
            {"@type": "ListItem", "position": 3, "name": a["title"], "item": url}]}]})
    # one text in Arabic: the Arabic address is the page search engines keep, whatever the frame's language
    return with_nonce(_shell(ui, base, "/articles/" + slug, a["title"] + " | " + BRAND["ar"], a.get("description", ""), body, ld,
                             nonce=nonce, extra_css=ARTICLE_CSS, canonical=url, alternates=False), nonce)


# ---------- robots.txt and the main sitemap ----------

def robots_txt(base: str) -> str:
    # the home page fills itself from /api/*: crawlers must be able to read it to see the books
    # AdSense's crawler gets its own group: nothing on the site is closed to it
    return ("User-agent: Mediapartners-Google\nAllow: /\n\n"
            "User-agent: *\nAllow: /\nDisallow: /api/hit\nDisallow: /api/like/\nDisallow: /api/track/\n"
            "Disallow: /admin/\nDisallow: /docs\nDisallow: /redoc\nSitemap: %s/sitemap.xml\n" % base)


def main_urls(conn, base: str):
    urls = [base + "/" + lang_q(ui) for ui in UI_LANGS]
    for p in legal.PAGES:
        if p not in legal.THIN_PAGES:  # the forms (contact, takedown) are not pages to find in a search engine
            urls += [base + "/" + p + lang_q(ui) for ui in UI_LANGS]
    urls.append(base + "/articles")
    urls += [base + "/articles/" + a["slug"] for a in content.articles()]
    for k in CATEGORIES:
        urls += [base + "/category/" + k + lang_q(ui) for ui in UI_LANGS]
    for r in conn.execute("SELECT key FROM authors a WHERE EXISTS (SELECT 1 FROM books WHERE author_key=a.key) ORDER BY ord"):
        # the other languages show the English page's texts and titles: what holds for English holds for them
        ok = {ui: author_indexable(conn, r["key"], ui) for ui in ("ar", "en")}
        urls += [base + "/author/" + quote(r["key"]) + lang_q(ui) for ui in UI_LANGS if ok[content.text_ui(ui)]]
    return urls


def sitemap_main(conn, base: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n'
            % "\n".join("<url><loc>%s</loc></url>" % esc(u) for u in main_urls(conn, base)))


# ---------- IndexNow: Bing, Yandex, Seznam, Naver... learn about new pages within minutes ----------

def indexnow(conn, base: str, key: str, with_books: bool = False, log=print) -> int:
    urls = main_urls(conn, base)
    if with_books:
        urls += [base + canonical_path(r) for r in conn.execute("SELECT id, title, title_ar, lang, origin FROM books ORDER BY id")]
    host = base.split("://", 1)[-1].split("/")[0]
    sent = 0
    for i in range(0, len(urls), 10000):
        body = json.dumps({"host": host, "key": key, "keyLocation": "%s/%s.txt" % (base, key), "urlList": urls[i:i + 10000]}).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=60) as r:
            log("IndexNow: %d URLs -> HTTP %d" % (len(urls[i:i + 10000]), r.status))
        sent += len(urls[i:i + 10000])
    return sent


def main() -> int:
    from . import db
    if len(sys.argv) < 2 or sys.argv[1] != "indexnow":
        print(__doc__)
        return 1
    base = os.environ.get("SITE_URL", "").strip().rstrip("/")
    key = os.environ.get("INDEXNOW_KEY", "").strip()
    if not base.startswith("https://") or not key:
        print("Set SITE_URL (https://...) and INDEXNOW_KEY first; the server must be live at SITE_URL.", file=sys.stderr)
        return 1
    conn = db.connect()
    print("sent", indexnow(conn, base, key, "--books" in sys.argv), "URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
