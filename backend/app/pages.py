"""Server-rendered page for every book (/book/<id>/<slug>) plus the sitemaps that list them.

Search engines get real HTML (title, description, JSON-LD, related books), and visitors get a
readable details page with the best reading links.
"""
import html
import json
import math
import os
import re
import time
from urllib.parse import quote

from . import content
from .catalog import CATEGORIES
from .textnorm import norm
from .modern import OL_KIND, SAFAHAT_KIND, ol_url, safahat_url
from .wikisource import WS_KIND

# ---------- the interface languages ----------
# Arabic is the site's own language (addresses without ?lang=); every other one is ?lang=<code>. A word missing
# from a language's table below is shown in English, never an error.
UI_LANGS = ("ar", "en", "zh", "fr", "es", "pt", "ja", "de")
UI_LANG_NAMES = {"ar": "العربية", "en": "English", "zh": "中文", "fr": "Français", "es": "Español", "pt": "Português",
                 "ja": "日本語", "de": "Deutsch"}  # each in its own language, as the language menu lists them
UI_LANG_SHORT = {"ar": "ع", "en": "EN", "zh": "中", "fr": "FR", "es": "ES", "pt": "PT", "ja": "日", "de": "DE"}
OG_LOCALE = {"ar": "ar_AR", "en": "en_US", "zh": "zh_CN", "fr": "fr_FR", "es": "es_ES", "pt": "pt_BR", "ja": "ja_JP", "de": "de_DE"}


def lang_q(ui: str, amp: bool = False) -> str:
    """The language part of an address: "" for Arabic, else "?lang=fr" (or "lang=fr&" to go before more parameters)."""
    if ui == "ar" or ui not in UI_LANGS:
        return ""
    return ("lang=%s&" if amp else "?lang=%s") % ui


def own_text(paras, ui: str) -> str:
    """The library's own paragraphs (a content.Text), marked with their language when English stands in for a
    translation this interface language does not have yet."""
    html_ = content.paragraphs(paras)
    lang = getattr(paras, "lang", "") or ui
    return html_ if not html_ or lang == ui else '<div lang="%s">%s</div>' % (lang, html_)


BRAND = {"ar": "مكتبة الوراق", "en": "Al-Warraq Library", "zh": "Al-Warraq 图书馆", "fr": "Bibliothèque Al-Warraq",
         "es": "Biblioteca Al-Warraq", "pt": "Biblioteca Al-Warraq", "ja": "アル・ワッラーク図書館", "de": "Bibliothek Al-Warraq"}
# the about / privacy / terms / contact pages (legal.py), linked from every footer
LEGAL = {"ar": (("about", "عن المكتبة"), ("privacy", "سياسة الخصوصية"), ("terms", "شروط الاستخدام"), ("contact", "اتصل بنا"),
                ("takedown", "طلب إزالة محتوى")),
         "en": (("about", "About us"), ("privacy", "Privacy policy"), ("terms", "Terms of use"), ("contact", "Contact us"),
                ("takedown", "Content removal")),
         "zh": (("about", "关于我们"), ("privacy", "隐私政策"), ("terms", "使用条款"), ("contact", "联系我们"),
                ("takedown", "内容移除申请")),
         "fr": (("about", "À propos"), ("privacy", "Politique de confidentialité"), ("terms", "Conditions d’utilisation"),
                ("contact", "Nous contacter"), ("takedown", "Demande de retrait")),
         "es": (("about", "Quiénes somos"), ("privacy", "Política de privacidad"), ("terms", "Términos de uso"),
                ("contact", "Contacto"), ("takedown", "Solicitud de retirada")),
         "pt": (("about", "Sobre nós"), ("privacy", "Política de privacidade"), ("terms", "Termos de uso"),
                ("contact", "Fale conosco"), ("takedown", "Pedido de remoção")),
         "ja": (("about", "私たちについて"), ("privacy", "プライバシーポリシー"), ("terms", "利用規約"), ("contact", "お問い合わせ"),
                ("takedown", "削除依頼")),
         "de": (("about", "Über uns"), ("privacy", "Datenschutzerklärung"), ("terms", "Nutzungsbedingungen"),
                ("contact", "Kontakt"), ("takedown", "Antrag auf Entfernung"))}
ARTICLES_NAME = {"ar": "مقالات", "en": "Articles", "zh": "文章", "fr": "Articles", "es": "Artículos", "pt": "Artigos",
                 "ja": "記事", "de": "Artikel"}
SITEMAP_PAGE = 40000  # URLs per sitemap file (Google allows 50,000)

# a book's language, named in each interface language (in this order)
_LANG_NAME_UIS = ("en", "ar", "zh", "fr", "es", "pt", "ja", "de")
LANG_NAMES = {
    "en": ("English", "الإنجليزية", "英语", "anglais", "inglés", "inglês", "英語", "Englisch"),
    "ar": ("Arabic", "العربية", "阿拉伯语", "arabe", "árabe", "árabe", "アラビア語", "Arabisch"),
    "fr": ("French", "الفرنسية", "法语", "français", "francés", "francês", "フランス語", "Französisch"),
    "de": ("German", "الألمانية", "德语", "allemand", "alemán", "alemão", "ドイツ語", "Deutsch"),
    "es": ("Spanish", "الإسبانية", "西班牙语", "espagnol", "español", "espanhol", "スペイン語", "Spanisch"),
    "it": ("Italian", "الإيطالية", "意大利语", "italien", "italiano", "italiano", "イタリア語", "Italienisch"),
    "pt": ("Portuguese", "البرتغالية", "葡萄牙语", "portugais", "portugués", "português", "ポルトガル語", "Portugiesisch"),
    "ru": ("Russian", "الروسية", "俄语", "russe", "ruso", "russo", "ロシア語", "Russisch"),
    "nl": ("Dutch", "الهولندية", "荷兰语", "néerlandais", "neerlandés", "neerlandês", "オランダ語", "Niederländisch"),
    "la": ("Latin", "اللاتينية", "拉丁语", "latin", "latín", "latim", "ラテン語", "Latein"),
    "fi": ("Finnish", "الفنلندية", "芬兰语", "finnois", "finés", "finlandês", "フィンランド語", "Finnisch"),
    "sv": ("Swedish", "السويدية", "瑞典语", "suédois", "sueco", "sueco", "スウェーデン語", "Schwedisch"),
    "da": ("Danish", "الدنماركية", "丹麦语", "danois", "danés", "dinamarquês", "デンマーク語", "Dänisch"),
    "no": ("Norwegian", "النرويجية", "挪威语", "norvégien", "noruego", "norueguês", "ノルウェー語", "Norwegisch"),
    "pl": ("Polish", "البولندية", "波兰语", "polonais", "polaco", "polonês", "ポーランド語", "Polnisch"),
    "hu": ("Hungarian", "المجرية", "匈牙利语", "hongrois", "húngaro", "húngaro", "ハンガリー語", "Ungarisch"),
    "cs": ("Czech", "التشيكية", "捷克语", "tchèque", "checo", "tcheco", "チェコ語", "Tschechisch"),
    "zh": ("Chinese", "الصينية", "中文", "chinois", "chino", "chinês", "中国語", "Chinesisch"),
    "ja": ("Japanese", "اليابانية", "日语", "japonais", "japonés", "japonês", "日本語", "Japanisch"),
    "tr": ("Turkish", "التركية", "土耳其语", "turc", "turco", "turco", "トルコ語", "Türkisch"),
    "el": ("Greek", "اليونانية", "希腊语", "grec", "griego", "grego", "ギリシャ語", "Griechisch"),
    "he": ("Hebrew", "العبرية", "希伯来语", "hébreu", "hebreo", "hebraico", "ヘブライ語", "Hebräisch"),
    "fa": ("Persian", "الفارسية", "波斯语", "persan", "persa", "persa", "ペルシア語", "Persisch"),
    "sa": ("Sanskrit", "السنسكريتية", "梵语", "sanskrit", "sánscrito", "sânscrito", "サンスクリット語", "Sanskrit"),
    "ko": ("Korean", "الكورية", "韩语", "coréen", "coreano", "coreano", "韓国語", "Koreanisch"),
    "ro": ("Romanian", "الرومانية", "罗马尼亚语", "roumain", "rumano", "romeno", "ルーマニア語", "Rumänisch"),
    "ca": ("Catalan", "الكتالانية", "加泰罗尼亚语", "catalan", "catalán", "catalão", "カタルーニャ語", "Katalanisch"),
}

T = {
    "ar": {
        "by": "المؤلف", "cat": "التصنيف", "lang": "اللغة", "src": "المصدر", "read": "اقرأ الكتاب",
        "find": "ابحث عن الكتاب", "more_author": "المزيد من كتب هذا المؤلف", "more_cat": "كتب أخرى من التصنيف نفسه",
        "ph": "ابحث بعنوان كتاب أو اسم مؤلف", "search": "بحث",
        "home": "الرئيسية", "all": "كل الكتب", "views": "مشاهدة", "likes": "إعجاب", "like": "أعجبني", "liked": "أعجبك", "similar": "كتب تشبه هذا الكتاب", "free": "كتاب مجاني ومسقط عنه حق النشر",
        "note": "الموقع فهرس يدلّك على المصادر المفتوحة والقانونية ولا يستضيف الكتب. كتب الملك العام هنا في الملكية العامة في الولايات المتحدة وقد يختلف وضعها في بلدك، أما الكتب العربية الحديثة فحقوقها لأصحابها ونعرض بيانات فهرستها فقط.",
        "page_gut": "صفحة الكتاب في Gutenberg", "page_ht": "HathiTrust", "arch": "Internet Archive", "ol": "Open Library",
        "menu_lang": "اللغة", "notfound": "الصفحة غير موجودة", "dir": "rtl",
        "nf_p": "ربما نُقلت الصفحة التي تبحث عنها أو كُتب الرابط بشكل خاطئ. ابحث في المكتبة أو عد إلى الصفحة الرئيسية.",
        "nf_home": "العودة إلى الرئيسية", "nf_try": "أو تصفّح أحد التصنيفات:",
        "share": "شارك:", "wa": "واتساب", "tg": "تيليجرام", "fb": "فيسبوك", "copy": "نسخ الرابط", "copied": "تم النسخ ✓",
        "share_txt": "اقرأ «{t}» مجاناً في مكتبة الوراق",
        "read_saf": "اقرأ على صفحات (هنداوي)", "view_ol": "اعرض الكتاب على Open Library",
        "src_saf": "صفحات (مؤسسة هنداوي)", "src_ol": "Open Library", "pub": "الناشر", "year": "سنة النشر", "pages": "عدد الصفحات",
        "note_saf": "هذا الكتاب متاح مجاناً على «صفحات» (مؤسسة هنداوي) بموجب اتفاق مع أصحاب حقوقه. نعرض هنا بيانات فهرسته فقط، والزر يوصلك إلى صفحته هناك.",
        "note_ol": "حقوق هذا الكتاب محفوظة لأصحابها. نعرض هنا بيانات فهرسته فقط، والزر يوصلك إلى صفحته في Open Library.",
        "desc_mod": "{t} {a}— ({l}، {c}). تعرّف على الكتاب وانتقل إلى صفحته في {s}.",
        "about_saf": "«{t}» كتاب {a}ضمن تصنيف «{c}»، مكتوب باللغة {l}. تقرؤه كاملاً ومجاناً على {s} بموجب اتفاق مع أصحاب حقوقه، عبر الزر أعلاه. وفي الأسفل كتب مشابهة قد تعجبك.",
        "about_ol": "«{t}» كتاب {a}ضمن تصنيف «{c}»، مكتوب باللغة {l}. حقوقه محفوظة لأصحابها، وتجد صفحته وطبعاته في {s} عبر الزر أعلاه. وفي الأسفل كتب مشابهة قد تعجبك.",
        "src_gut": "مشروع غوتنبرغ", "src_ht": "مكتبة HathiTrust", "src_ws": "ويكي مصدر", "src_idx": "فهرس الوراق",
        "about": "نبذة عن الكتاب", "about_author": "نبذة عن المؤلف", "wiki": "المصدر: ويكيبيديا",
        "about_txt": "«{t}» كتاب {a}ضمن تصنيف «{c}»، مكتوب باللغة {l}. هو من الكتب الموجودة في الملكية العامة، فيمكنك قراءته مجاناً من المصدر المفتوح عبر الأزرار أعلاه، وإن أعجبك فاضغط «أعجبني» لتساعد غيرك على اكتشافه. وفي الأسفل كتب مشابهة قد تعجبك.",
        "about_by": "للمؤلف {a} ",
        "facts_h": "معلومات الفهرسة", "context": "سياق الكتاب وأهميته", "bio_more": "كل كتب المؤلف",
        "legal_pd": "مكتبة الوراق لا تستضيف ملفات الكتب، بل توصلك إلى نسختها في مصدرها الأصلي. ووضع «الملك العام» يختلف من بلد إلى آخر، فتحقّق من قانون بلدك قبل تنزيل الكتاب أو إعادة نشره.",
        "takedown_q": "صاحب حق في هذا العمل؟", "takedown_a": "اطلب إزالته",
        "title_by": "{t} لـ{a}",
        "d_pd": "«{t}»{by}: {kind} في الملك العام{y}، ضمن تصنيف «{c}» باللغة {l}. اقرأه كاملاً ومجاناً من مصدره الأصلي على {s}.",
        "d_saf": "«{t}»{by}{y}، ضمن تصنيف «{c}» باللغة {l}. اقرأه كاملاً ومجاناً على {s} بإذن أصحاب حقوقه.",
        "d_ol": "«{t}»{by}{y}{p}، ضمن تصنيف «{c}» باللغة {l}. اطّلع على بيانات الكتاب وانتقل إلى صفحته في {s}.",
        "d_by": " لـ{a}", "d_y": "، صدر عام {y}", "d_p": " عن {p}", "k_book": "كتاب", "k_poem": "قصيدة",
        "desc": "{t} {a}— كتاب مجاني ({l}، {c}). اقرأه أو ابحث عن نسخه المجانية من المصادر المفتوحة.",
    },
    "en": {
        "by": "Author", "cat": "Category", "lang": "Language", "src": "Source", "read": "Read the book",
        "find": "Find the book", "more_author": "More books by this author", "more_cat": "More in this category",
        "ph": "Search a title or an author", "search": "Search",
        "home": "Home", "all": "All books", "views": "views", "likes": "likes", "like": "Like", "liked": "Liked", "similar": "Similar books", "free": "Free public-domain book",
        "note": "This site is an index that points to open and legal sources; it does not host the books. Public-domain books here are free in the United States and may be protected in your country; modern Arabic books belong to their rights holders, and we only show their catalogue records.",
        "page_gut": "Gutenberg book page", "page_ht": "HathiTrust", "arch": "Internet Archive", "ol": "Open Library",
        "menu_lang": "Language", "notfound": "Page not found", "dir": "ltr",
        "nf_p": "The page you are looking for may have moved, or the link is mistyped. Search the library or go back home.",
        "nf_home": "Back to home", "nf_try": "Or browse a category:",
        "share": "Share:", "wa": "WhatsApp", "tg": "Telegram", "fb": "Facebook", "copy": "Copy link", "copied": "Copied ✓",
        "share_txt": "Read \u201c{t}\u201d free at Al-Warraq Library",
        "read_saf": "Read on Safahat (Hindawi)", "view_ol": "View on Open Library",
        "src_saf": "Safahat (Hindawi Foundation)", "src_ol": "Open Library", "pub": "Publisher", "year": "Published", "pages": "Pages",
        "note_saf": "This book is free to read on Safahat (Hindawi Foundation) under an agreement with its rights holders. We only show its catalogue record; the button takes you to its page there.",
        "note_ol": "This book is under copyright. We only show its catalogue record; the button takes you to its page on Open Library.",
        "desc_mod": "{t} {a}— ({l}, {c}). About the book, with a link to its page on {s}.",
        "about_saf": "\u201c{t}\u201d is a book {a}in the \u201c{c}\u201d category, written in {l}. You can read it in full and for free on {s}, under an agreement with its rights holders, using the button above. Similar books are listed below.",
        "about_ol": "\u201c{t}\u201d is a book {a}in the \u201c{c}\u201d category, written in {l}. It is under copyright; its page and editions are on {s}, through the button above. Similar books are listed below.",
        "src_gut": "Project Gutenberg", "src_ht": "HathiTrust", "src_ws": "Wikisource", "src_idx": "Al-Warraq index",
        "about": "About this book", "about_author": "About the author", "wiki": "Source: Wikipedia",
        "about_txt": "\u201c{t}\u201d is a book {a}in the \u201c{c}\u201d category, written in {l}. It is in the public domain, so you can read it for free from the open source using the buttons above. If you enjoyed it, press Like to help others find it. Similar books are listed below.",
        "about_by": "by {a} ",
        "facts_h": "Catalogue details", "context": "Context and significance", "bio_more": "All books by this author",
        "legal_pd": "Al-Warraq Library does not host book files; it takes you to the copy at the original source. Public-domain status differs from country to country, so check the law where you live before downloading or republishing the book.",
        "takedown_q": "Do you hold rights in this work?", "takedown_a": "Request its removal",
        "title_by": "{t} by {a}",
        "d_pd": "\u201c{t}\u201d{by}: a public-domain {kind}{y} in \u201c{c}\u201d, written in {l}. Read it in full and free at its original source, {s}.",
        "d_saf": "\u201c{t}\u201d{by}{y}, in \u201c{c}\u201d, written in {l}. Read it in full and free on {s}, with its rights holders' permission.",
        "d_ol": "\u201c{t}\u201d{by}{y}{p}, in \u201c{c}\u201d, written in {l}. See its catalogue record and go to its page on {s}.",
        "d_by": " by {a}", "d_y": ", published {y}", "d_p": " by {p}", "k_book": "book", "k_poem": "poem",
        "desc": "{t} {a}— free public-domain book ({l}, {c}). Read it online or find free editions from open sources.",
    },
    "zh": {
        "by": "作者", "cat": "分类", "lang": "语言", "src": "来源", "read": "阅读本书", "find": "查找本书",
        "ph": "搜索书名或作者", "search": "搜索",
        "home": "首页", "all": "全部图书", "views": "次浏览", "like": "点赞", "liked": "已点赞", "similar": "相似图书",
        "note": "本站是一个指向开放、合法来源的索引，并不存放图书。这里的公有领域图书在美国属于公有领域，在你所在的国家可能仍受保护；现代阿拉伯语图书的版权归权利人所有，我们只展示其书目信息。",
        "page_gut": "古腾堡图书页面", "page_ht": "HathiTrust", "arch": "互联网档案馆", "ol": "Open Library",
        "menu_lang": "语言", "notfound": "页面不存在", "dir": "ltr",
        "nf_p": "你要找的页面可能已被移动，或者链接输入有误。请在图书馆中搜索，或返回首页。",
        "nf_home": "返回首页", "nf_try": "或者浏览一个分类：",
        "share": "分享：", "wa": "WhatsApp", "tg": "Telegram", "fb": "Facebook", "copy": "复制链接", "copied": "已复制 ✓",
        "share_txt": "在 Al-Warraq 图书馆免费阅读《{t}》",
        "read_saf": "在 Safahat（Hindawi）上阅读", "view_ol": "在 Open Library 上查看",
        "src_saf": "Safahat（Hindawi 基金会）", "src_ol": "Open Library", "pub": "出版者", "year": "出版年份", "pages": "页数",
        "note_saf": "本书经权利人同意，可在 Safahat（Hindawi 基金会）上免费阅读。我们这里只展示其书目信息，按钮会带你前往它在那里的页面。",
        "note_ol": "本书受版权保护。我们这里只展示其书目信息，按钮会带你前往它在 Open Library 上的页面。",
        "about_saf": "《{t}》是一部{a}作品，属于“{c}”类别，以{l}写成。根据与权利人的协议，你可以通过上方按钮在{s}上免费阅读全文。下方列出了相似的图书。",
        "about_ol": "《{t}》是一部{a}作品，属于“{c}”类别，以{l}写成。本书受版权保护，你可以通过上方按钮在{s}上找到它的页面和各个版本。下方列出了相似的图书。",
        "src_gut": "古腾堡计划", "src_ht": "HathiTrust", "src_ws": "维基文库", "src_idx": "Al-Warraq 索引",
        "about": "关于本书", "about_author": "关于作者", "wiki": "来源：维基百科",
        "about_txt": "《{t}》是一部{a}作品，属于“{c}”类别，以{l}写成。本书属于公有领域，你可以通过上方按钮从开放来源免费阅读。如果你喜欢这本书，请点击“点赞”，帮助更多人发现它。下方列出了相似的图书。",
        "about_by": "由{a}创作的",
        "facts_h": "书目信息", "context": "背景与意义", "bio_more": "该作者的全部图书",
        "legal_pd": "Al-Warraq 图书馆不存放图书文件，而是带你前往原始来源中的副本。公有领域的认定因国家而异，下载或转载本书前，请先了解你所在地的法律。",
        "takedown_q": "你是这部作品的权利人吗？", "takedown_a": "申请移除",
        "title_by": "{t}（{a} 著）",
        "d_pd": "《{t}》{by}{y}：公有领域{kind}，属于“{c}”类别，以{l}写成。可在原始来源{s}免费阅读全文。",
        "d_saf": "《{t}》{by}{y}，属于“{c}”类别，以{l}写成。经权利人许可，可在{s}上免费阅读全文。",
        "d_ol": "《{t}》{by}{y}{p}，属于“{c}”类别，以{l}写成。查看书目信息，并前往它在{s}上的页面。",
        "d_by": "，{a}著", "d_y": "（{y}年）", "d_p": "，{p}出版", "k_book": "图书", "k_poem": "诗歌",
    },
    "fr": {
        "by": "Auteur", "cat": "Catégorie", "lang": "Langue", "src": "Source", "read": "Lire le livre", "find": "Trouver le livre",
        "ph": "Rechercher un titre ou un auteur", "search": "Rechercher",
        "home": "Accueil", "all": "Tous les livres", "views": "vues", "like": "J’aime", "liked": "Aimé", "similar": "Livres similaires",
        "note": "Ce site est un index qui renvoie vers des sources ouvertes et légales ; il n’héberge pas les livres. Les livres du domaine public présentés ici sont libres aux États-Unis et peuvent être protégés dans votre pays ; les livres arabes modernes appartiennent à leurs ayants droit, et nous n’en montrons que la notice.",
        "page_gut": "Page du livre sur Gutenberg", "page_ht": "HathiTrust", "arch": "Internet Archive", "ol": "Open Library",
        "menu_lang": "Langue", "notfound": "Page introuvable", "dir": "ltr",
        "nf_p": "La page que vous cherchez a peut-être été déplacée, ou le lien est mal saisi. Cherchez dans la bibliothèque ou revenez à l’accueil.",
        "nf_home": "Retour à l’accueil", "nf_try": "Ou parcourez une catégorie :",
        "share": "Partager :", "wa": "WhatsApp", "tg": "Telegram", "fb": "Facebook", "copy": "Copier le lien", "copied": "Copié ✓",
        "share_txt": "Lisez « {t} » gratuitement sur la Bibliothèque Al-Warraq",
        "read_saf": "Lire sur Safahat (Hindawi)", "view_ol": "Voir sur Open Library",
        "src_saf": "Safahat (Fondation Hindawi)", "src_ol": "Open Library", "pub": "Éditeur", "year": "Publication", "pages": "Pages",
        "note_saf": "Ce livre se lit gratuitement sur Safahat (Fondation Hindawi), en vertu d’un accord avec ses ayants droit. Nous n’affichons que sa notice ; le bouton vous mène à sa page là-bas.",
        "note_ol": "Ce livre est protégé par le droit d’auteur. Nous n’affichons que sa notice ; le bouton vous mène à sa page sur Open Library.",
        "about_saf": "« {t} » est un livre {a}classé dans la catégorie « {c} » et écrit en {l}. Vous pouvez le lire en entier et gratuitement sur {s}, en vertu d’un accord avec ses ayants droit, grâce au bouton ci-dessus. Des livres similaires figurent plus bas.",
        "about_ol": "« {t} » est un livre {a}classé dans la catégorie « {c} » et écrit en {l}. Il est protégé par le droit d’auteur ; sa page et ses éditions se trouvent sur {s}, via le bouton ci-dessus. Des livres similaires figurent plus bas.",
        "src_gut": "Projet Gutenberg", "src_ht": "HathiTrust", "src_ws": "Wikisource", "src_idx": "Index d’Al-Warraq",
        "about": "À propos de ce livre", "about_author": "À propos de l’auteur", "wiki": "Source : Wikipédia",
        "about_txt": "« {t} » est un livre {a}classé dans la catégorie « {c} » et écrit en {l}. Il appartient au domaine public : vous pouvez le lire gratuitement à sa source ouverte grâce aux boutons ci-dessus. S’il vous a plu, cliquez sur « J’aime » pour aider d’autres lecteurs à le découvrir. Des livres similaires figurent plus bas.",
        "about_by": "de {a}, ",
        "facts_h": "Notice du catalogue", "context": "Contexte et portée", "bio_more": "Tous les livres de cet auteur",
        "legal_pd": "La Bibliothèque Al-Warraq n’héberge aucun fichier : elle vous conduit à l’exemplaire de la source d’origine. Le statut de domaine public varie d’un pays à l’autre ; vérifiez la loi de votre pays avant de télécharger ou de republier ce livre.",
        "takedown_q": "Vous détenez des droits sur cette œuvre ?", "takedown_a": "Demander son retrait",
        "title_by": "{t} de {a}",
        "d_pd": "« {t} »{by} : {kind} du domaine public{y}, dans la catégorie « {c} », écrit en {l}. Lisez-le en entier et gratuitement à sa source d’origine, {s}.",
        "d_saf": "« {t} »{by}{y}, dans la catégorie « {c} », écrit en {l}. Lisez-le en entier et gratuitement sur {s}, avec l’accord de ses ayants droit.",
        "d_ol": "« {t} »{by}{y}{p}, dans la catégorie « {c} », écrit en {l}. Consultez sa notice et rendez-vous sur sa page sur {s}.",
        "d_by": " de {a}", "d_y": ", publié en {y}", "d_p": " chez {p}", "k_book": "un livre", "k_poem": "un poème",
    },
    "es": {
        "by": "Autor", "cat": "Categoría", "lang": "Idioma", "src": "Fuente", "read": "Leer el libro", "find": "Buscar el libro",
        "ph": "Busca un título o un autor", "search": "Buscar",
        "home": "Inicio", "all": "Todos los libros", "views": "vistas", "like": "Me gusta", "liked": "Te gusta", "similar": "Libros similares",
        "note": "Este sitio es un índice que remite a fuentes abiertas y legales; no aloja los libros. Los libros de dominio público que aparecen aquí son libres en Estados Unidos y pueden estar protegidos en tu país; los libros árabes modernos pertenecen a sus titulares de derechos, y solo mostramos su ficha de catálogo.",
        "page_gut": "Página del libro en Gutenberg", "page_ht": "HathiTrust", "arch": "Internet Archive", "ol": "Open Library",
        "menu_lang": "Idioma", "notfound": "Página no encontrada", "dir": "ltr",
        "nf_p": "Puede que la página que buscas se haya movido o que el enlace esté mal escrito. Busca en la biblioteca o vuelve al inicio.",
        "nf_home": "Volver al inicio", "nf_try": "O explora una categoría:",
        "share": "Compartir:", "wa": "WhatsApp", "tg": "Telegram", "fb": "Facebook", "copy": "Copiar enlace", "copied": "Copiado ✓",
        "share_txt": "Lee «{t}» gratis en la Biblioteca Al-Warraq",
        "read_saf": "Leer en Safahat (Hindawi)", "view_ol": "Ver en Open Library",
        "src_saf": "Safahat (Fundación Hindawi)", "src_ol": "Open Library", "pub": "Editorial", "year": "Publicación", "pages": "Páginas",
        "note_saf": "Este libro se puede leer gratis en Safahat (Fundación Hindawi) gracias a un acuerdo con sus titulares de derechos. Aquí solo mostramos su ficha; el botón te lleva a su página allí.",
        "note_ol": "Este libro está protegido por derechos de autor. Aquí solo mostramos su ficha; el botón te lleva a su página en Open Library.",
        "about_saf": "«{t}» es un libro {a}de la categoría «{c}», escrito en {l}. Puedes leerlo completo y gratis en {s}, gracias a un acuerdo con sus titulares de derechos, con el botón de arriba. Más abajo hay libros similares.",
        "about_ol": "«{t}» es un libro {a}de la categoría «{c}», escrito en {l}. Está protegido por derechos de autor; su página y sus ediciones están en {s}, a través del botón de arriba. Más abajo hay libros similares.",
        "src_gut": "Proyecto Gutenberg", "src_ht": "HathiTrust", "src_ws": "Wikisource", "src_idx": "Índice de Al-Warraq",
        "about": "Sobre este libro", "about_author": "Sobre el autor", "wiki": "Fuente: Wikipedia",
        "about_txt": "«{t}» es un libro {a}de la categoría «{c}», escrito en {l}. Es de dominio público, así que puedes leerlo gratis en su fuente abierta con los botones de arriba. Si te gustó, pulsa «Me gusta» para ayudar a otros a descubrirlo. Más abajo hay libros similares.",
        "about_by": "de {a}, ",
        "facts_h": "Datos de catálogo", "context": "Contexto e importancia", "bio_more": "Todos los libros de este autor",
        "legal_pd": "La Biblioteca Al-Warraq no aloja archivos de libros: te lleva a la copia de la fuente original. La condición de dominio público cambia de un país a otro, así que consulta la ley de tu país antes de descargar o volver a publicar el libro.",
        "takedown_q": "¿Tienes derechos sobre esta obra?", "takedown_a": "Solicita su retirada",
        "title_by": "{t}, de {a}",
        "d_pd": "«{t}»{by}: {kind} de dominio público{y}, en la categoría «{c}», escrito en {l}. Léelo completo y gratis en su fuente original, {s}.",
        "d_saf": "«{t}»{by}{y}, en la categoría «{c}», escrito en {l}. Léelo completo y gratis en {s}, con permiso de sus titulares de derechos.",
        "d_ol": "«{t}»{by}{y}{p}, en la categoría «{c}», escrito en {l}. Consulta su ficha de catálogo y ve a su página en {s}.",
        "d_by": ", de {a}", "d_y": ", publicado en {y}", "d_p": ", editorial {p}", "k_book": "un libro", "k_poem": "un poema",
    },
    "pt": {
        "by": "Autor", "cat": "Categoria", "lang": "Idioma", "src": "Fonte", "read": "Ler o livro", "find": "Encontrar o livro",
        "ph": "Pesquise um título ou um autor", "search": "Pesquisar",
        "home": "Início", "all": "Todos os livros", "views": "visualizações", "like": "Curtir", "liked": "Curtido", "similar": "Livros semelhantes",
        "note": "Este site é um índice que aponta para fontes abertas e legais; ele não hospeda os livros. Os livros em domínio público aqui são livres nos Estados Unidos e podem estar protegidos no seu país; os livros árabes modernos pertencem aos detentores dos direitos, e mostramos apenas a ficha catalográfica.",
        "page_gut": "Página do livro no Gutenberg", "page_ht": "HathiTrust", "arch": "Internet Archive", "ol": "Open Library",
        "menu_lang": "Idioma", "notfound": "Página não encontrada", "dir": "ltr",
        "nf_p": "A página que você procura pode ter sido movida, ou o link foi digitado errado. Pesquise na biblioteca ou volte ao início.",
        "nf_home": "Voltar ao início", "nf_try": "Ou navegue por uma categoria:",
        "share": "Compartilhar:", "wa": "WhatsApp", "tg": "Telegram", "fb": "Facebook", "copy": "Copiar link", "copied": "Copiado ✓",
        "share_txt": "Leia “{t}” de graça na Biblioteca Al-Warraq",
        "read_saf": "Ler no Safahat (Hindawi)", "view_ol": "Ver no Open Library",
        "src_saf": "Safahat (Fundação Hindawi)", "src_ol": "Open Library", "pub": "Editora", "year": "Publicação", "pages": "Páginas",
        "note_saf": "Este livro pode ser lido de graça no Safahat (Fundação Hindawi), graças a um acordo com os detentores dos direitos. Aqui mostramos apenas a ficha catalográfica; o botão leva você à página dele lá.",
        "note_ol": "Este livro está protegido por direitos autorais. Aqui mostramos apenas a ficha catalográfica; o botão leva você à página dele no Open Library.",
        "about_saf": "“{t}” é um livro {a}da categoria “{c}”, escrito em {l}. Você pode lê-lo na íntegra e de graça em {s}, graças a um acordo com os detentores dos direitos, pelo botão acima. Abaixo há livros semelhantes.",
        "about_ol": "“{t}” é um livro {a}da categoria “{c}”, escrito em {l}. Ele está protegido por direitos autorais; a página e as edições dele estão em {s}, pelo botão acima. Abaixo há livros semelhantes.",
        "src_gut": "Projeto Gutenberg", "src_ht": "HathiTrust", "src_ws": "Wikisource", "src_idx": "Índice da Al-Warraq",
        "about": "Sobre este livro", "about_author": "Sobre o autor", "wiki": "Fonte: Wikipédia",
        "about_txt": "“{t}” é um livro {a}da categoria “{c}”, escrito em {l}. Ele está em domínio público, então você pode lê-lo de graça na fonte aberta pelos botões acima. Se gostou, toque em “Curtir” para ajudar outras pessoas a descobri-lo. Abaixo há livros semelhantes.",
        "about_by": "de {a}, ",
        "facts_h": "Dados de catálogo", "context": "Contexto e importância", "bio_more": "Todos os livros deste autor",
        "legal_pd": "A Biblioteca Al-Warraq não hospeda arquivos de livros: ela leva você ao exemplar na fonte original. A condição de domínio público varia de país para país, então confira a lei do seu país antes de baixar ou republicar o livro.",
        "takedown_q": "Você detém direitos sobre esta obra?", "takedown_a": "Peça a remoção",
        "title_by": "{t}, de {a}",
        "d_pd": "“{t}”{by}: {kind} em domínio público{y}, na categoria “{c}”, escrito em {l}. Leia na íntegra e de graça na fonte original, {s}.",
        "d_saf": "“{t}”{by}{y}, na categoria “{c}”, escrito em {l}. Leia na íntegra e de graça em {s}, com permissão dos detentores dos direitos.",
        "d_ol": "“{t}”{by}{y}{p}, na categoria “{c}”, escrito em {l}. Veja a ficha catalográfica e acesse a página dele em {s}.",
        "d_by": ", de {a}", "d_y": ", publicado em {y}", "d_p": ", editora {p}", "k_book": "um livro", "k_poem": "um poema",
    },
    "ja": {
        "by": "著者", "cat": "カテゴリー", "lang": "言語", "src": "出典", "read": "本を読む", "find": "本を探す",
        "ph": "書名や著者名で検索", "search": "検索",
        "home": "ホーム", "all": "すべての本", "views": "回閲覧", "like": "いいね", "liked": "いいね済み", "similar": "似ている本",
        "note": "このサイトはオープンで合法的な情報源へ案内する索引であり、本そのものは掲載していません。ここにあるパブリックドメインの本は米国で自由に利用できますが、お住まいの国では保護されている場合があります。現代アラビア語の本の権利は権利者に帰属し、当サイトでは書誌情報のみを表示しています。",
        "page_gut": "Gutenberg の書籍ページ", "page_ht": "HathiTrust", "arch": "インターネット・アーカイブ", "ol": "Open Library",
        "menu_lang": "言語", "notfound": "ページが見つかりません", "dir": "ltr",
        "nf_p": "お探しのページは移動したか、リンクが間違っている可能性があります。図書館内を検索するか、ホームに戻ってください。",
        "nf_home": "ホームに戻る", "nf_try": "またはカテゴリーから探す：",
        "share": "共有：", "wa": "WhatsApp", "tg": "Telegram", "fb": "Facebook", "copy": "リンクをコピー", "copied": "コピーしました ✓",
        "share_txt": "アル・ワッラーク図書館で『{t}』を無料で読む",
        "read_saf": "Safahat（Hindawi）で読む", "view_ol": "Open Library で見る",
        "src_saf": "Safahat（Hindawi 財団）", "src_ol": "Open Library", "pub": "出版社", "year": "刊行年", "pages": "ページ数",
        "note_saf": "この本は権利者との合意により Safahat（Hindawi 財団）で無料で読めます。ここでは書誌情報のみを表示しており、ボタンから同サイトのページへ移動できます。",
        "note_ol": "この本は著作権で保護されています。ここでは書誌情報のみを表示しており、ボタンから Open Library のページへ移動できます。",
        "about_saf": "『{t}』は{a}「{c}」カテゴリーの本で、{l}で書かれています。権利者との合意により、上のボタンから{s}で全文を無料で読めます。下に似ている本を紹介しています。",
        "about_ol": "『{t}』は{a}「{c}」カテゴリーの本で、{l}で書かれています。著作権で保護されているため、上のボタンから{s}でページと各版を確認できます。下に似ている本を紹介しています。",
        "src_gut": "プロジェクト・グーテンベルク", "src_ht": "HathiTrust", "src_ws": "ウィキソース", "src_idx": "アル・ワッラーク索引",
        "about": "この本について", "about_author": "著者について", "wiki": "出典：ウィキペディア",
        "about_txt": "『{t}』は{a}「{c}」カテゴリーの本で、{l}で書かれています。パブリックドメインの作品なので、上のボタンから公開されている情報源で無料で読めます。気に入ったら「いいね」を押して、ほかの人がこの本を見つけられるようにしてください。下に似ている本を紹介しています。",
        "about_by": "{a}による",
        "facts_h": "書誌情報", "context": "背景と意義", "bio_more": "この著者のすべての本",
        "legal_pd": "アル・ワッラーク図書館は本のファイルを掲載せず、元の情報源にある本へ案内します。パブリックドメインかどうかは国によって異なるため、本をダウンロードしたり再公開したりする前に、お住まいの国の法律を確認してください。",
        "takedown_q": "この作品の権利をお持ちですか？", "takedown_a": "削除を依頼する",
        "title_by": "{t}（{a}）",
        "d_pd": "『{t}』{by}{y}：パブリックドメインの{kind}。「{c}」カテゴリー、{l}の作品です。元の情報源である{s}で全文を無料で読めます。",
        "d_saf": "『{t}』{by}{y}：「{c}」カテゴリー、{l}の作品です。権利者の許可により、{s}で全文を無料で読めます。",
        "d_ol": "『{t}』{by}{y}{p}：「{c}」カテゴリー、{l}の作品です。書誌情報を確認し、{s}のページへ移動できます。",
        "d_by": "／{a}", "d_y": "（{y}年）", "d_p": "、{p}刊", "k_book": "本", "k_poem": "詩",
    },
    "de": {
        "by": "Autor", "cat": "Kategorie", "lang": "Sprache", "src": "Quelle", "read": "Buch lesen", "find": "Buch finden",
        "ph": "Titel oder Autor suchen", "search": "Suchen",
        "home": "Startseite", "all": "Alle Bücher", "views": "Aufrufe", "like": "Gefällt mir", "liked": "Gefällt Ihnen", "similar": "Ähnliche Bücher",
        "note": "Diese Website ist ein Verzeichnis, das auf offene und legale Quellen verweist; die Bücher selbst liegen nicht hier. Gemeinfreie Bücher sind in den USA frei und können in Ihrem Land noch geschützt sein; moderne arabische Bücher gehören ihren Rechteinhabern, und wir zeigen nur ihre Katalogdaten.",
        "page_gut": "Buchseite bei Gutenberg", "page_ht": "HathiTrust", "arch": "Internet Archive", "ol": "Open Library",
        "menu_lang": "Sprache", "notfound": "Seite nicht gefunden", "dir": "ltr",
        "nf_p": "Die gesuchte Seite wurde vielleicht verschoben, oder der Link ist falsch geschrieben. Durchsuchen Sie die Bibliothek oder kehren Sie zur Startseite zurück.",
        "nf_home": "Zur Startseite", "nf_try": "Oder stöbern Sie in einer Kategorie:",
        "share": "Teilen:", "wa": "WhatsApp", "tg": "Telegram", "fb": "Facebook", "copy": "Link kopieren", "copied": "Kopiert ✓",
        "share_txt": "Lesen Sie „{t}“ kostenlos in der Bibliothek Al-Warraq",
        "read_saf": "Bei Safahat (Hindawi) lesen", "view_ol": "Bei Open Library ansehen",
        "src_saf": "Safahat (Hindawi-Stiftung)", "src_ol": "Open Library", "pub": "Verlag", "year": "Erschienen", "pages": "Seiten",
        "note_saf": "Dieses Buch ist dank einer Vereinbarung mit den Rechteinhabern kostenlos bei Safahat (Hindawi-Stiftung) zu lesen. Wir zeigen hier nur die Katalogdaten; die Schaltfläche führt Sie zur Seite dort.",
        "note_ol": "Dieses Buch ist urheberrechtlich geschützt. Wir zeigen hier nur die Katalogdaten; die Schaltfläche führt Sie zur Seite bei Open Library.",
        "about_saf": "„{t}“ ist ein Buch {a}aus der Kategorie „{c}“, geschrieben auf {l}. Dank einer Vereinbarung mit den Rechteinhabern können Sie es über die Schaltfläche oben vollständig und kostenlos bei {s} lesen. Ähnliche Bücher finden Sie weiter unten.",
        "about_ol": "„{t}“ ist ein Buch {a}aus der Kategorie „{c}“, geschrieben auf {l}. Es ist urheberrechtlich geschützt; seine Seite und Ausgaben finden Sie über die Schaltfläche oben bei {s}. Ähnliche Bücher finden Sie weiter unten.",
        "src_gut": "Projekt Gutenberg", "src_ht": "HathiTrust", "src_ws": "Wikisource", "src_idx": "Verzeichnis von Al-Warraq",
        "about": "Über dieses Buch", "about_author": "Über den Autor", "wiki": "Quelle: Wikipedia",
        "about_txt": "„{t}“ ist ein Buch {a}aus der Kategorie „{c}“, geschrieben auf {l}. Es ist gemeinfrei, daher können Sie es über die Schaltflächen oben kostenlos an der offenen Quelle lesen. Wenn es Ihnen gefallen hat, klicken Sie auf „Gefällt mir“, damit andere es entdecken. Ähnliche Bücher finden Sie weiter unten.",
        "about_by": "von {a} ",
        "facts_h": "Katalogdaten", "context": "Hintergrund und Bedeutung", "bio_more": "Alle Bücher dieses Autors",
        "legal_pd": "Die Bibliothek Al-Warraq speichert keine Buchdateien, sondern führt Sie zum Exemplar an der Originalquelle. Ob ein Werk gemeinfrei ist, ist von Land zu Land verschieden; prüfen Sie daher das Recht Ihres Landes, bevor Sie das Buch herunterladen oder neu veröffentlichen.",
        "takedown_q": "Haben Sie Rechte an diesem Werk?", "takedown_a": "Entfernung beantragen",
        "title_by": "{t} von {a}",
        "d_pd": "„{t}“{by}: {kind}{y} in der Kategorie „{c}“, auf {l}. Vollständig und kostenlos an der Originalquelle lesbar: {s}.",
        "d_saf": "„{t}“{by}{y}, in der Kategorie „{c}“, auf {l}. Mit Erlaubnis der Rechteinhaber vollständig und kostenlos bei {s} lesbar.",
        "d_ol": "„{t}“{by}{y}{p}, in der Kategorie „{c}“, auf {l}. Katalogdaten ansehen und zur Seite bei {s} wechseln.",
        "d_by": " von {a}", "d_y": ", erschienen {y}", "d_p": ", Verlag {p}", "k_book": "ein gemeinfreies Buch", "k_poem": "ein gemeinfreies Gedicht",
    },
}
for _ui in UI_LANGS:  # a word a language lacks is shown in English
    T[_ui] = dict(T["en"], **T.get(_ui, {}))

CSS = """
:root{--bg:#F2F0EA;--card:#fff;--ink:#13201C;--muted:#5A6762;--line:#E1DCD0;--brand:#0E6B5A;--brand-2:#18A086;--brand-ink:#fff;--soft:#DDEEE8;--rose:#A35F08;--rose-soft:#FBEFD5;--btn:linear-gradient(140deg,#139477,#0B5546);--grad:linear-gradient(140deg,#18A086,#0E6B5A 58%,#0A4A3E);--shadow:0 1px 2px rgba(19,32,28,.05),0 14px 32px -18px rgba(10,74,62,.32)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 "IBM Plex Sans Arabic",system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif}
a{color:var(--brand)}
.wrap{max-width:980px;margin:0 auto;padding:0 16px}
.bar{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 80%,transparent);backdrop-filter:saturate(1.6) blur(14px);-webkit-backdrop-filter:saturate(1.6) blur(14px);border-bottom:1px solid var(--line)}
.bar .wrap{display:flex;align-items:center;gap:12px;min-height:62px}
.brand{display:flex;align-items:center;gap:9px;font:800 1.15rem/1.4 "Alexandria","IBM Plex Sans Arabic",sans-serif;color:var(--ink);text-decoration:none;flex:none}
.brand svg{filter:drop-shadow(0 6px 10px rgba(14,107,90,.28));transition:transform .4s cubic-bezier(.34,1.56,.64,1)}.brand:hover svg{transform:translateY(-2px)}
.brand .lg-sun{transform-box:fill-box;transform-origin:center;animation:sun 5s ease-in-out infinite}@keyframes sun{50%{transform:scale(1.16)}}
.sbox{flex:1 1 auto;min-width:0;display:flex;align-items:center;gap:6px;height:42px;padding-inline:14px 4px;background:var(--card);border:1.5px solid var(--line);border-radius:14px}
.sbox:focus-within{border-color:var(--brand-2);box-shadow:0 0 0 4px color-mix(in srgb,var(--brand-2) 22%,transparent)}
.sbox svg{flex:none;color:var(--muted)}.sbox input{flex:1 1 auto;min-width:0;border:0;background:transparent;outline:0;font:inherit;color:inherit;height:100%}
.sbox button{flex:none;height:34px;padding-inline:16px;border:0;border-radius:11px;background:var(--btn);color:var(--brand-ink);font:600 .92rem "IBM Plex Sans Arabic",sans-serif;cursor:pointer}
.bar nav{display:flex;gap:14px;align-items:center;font-size:.92rem;flex:none}
.lmenu{position:relative}.lmenu summary{display:inline-flex;align-items:center;gap:6px;height:38px;padding-inline:10px 12px;border:1.5px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink);font-weight:600;cursor:pointer;list-style:none}
.lmenu summary::-webkit-details-marker{display:none}.lmenu summary:hover,.lmenu[open] summary{border-color:var(--brand-2)}.lmenu summary svg{color:var(--brand)}
.lmenu-list{position:absolute;inset-inline-end:0;top:calc(100% + 6px);z-index:20;display:grid;min-width:170px;padding:6px;background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}
.lmenu-list a{padding:7px 12px;border-radius:9px;color:var(--ink);text-decoration:none}.lmenu-list a:hover{background:var(--soft);color:var(--brand)}.lmenu-list a[aria-current]{background:var(--soft);color:var(--brand);font-weight:600}
@media (max-width:640px){.brand span{display:none}.sbox button{display:none}.bar nav>a:first-child{display:none}}
.crumbs{font-size:.88rem;color:var(--muted);margin:18px 0 6px}.crumbs a{color:var(--muted)}
.book{display:grid;grid-template-columns:240px 1fr;gap:28px;margin:12px 0 28px;align-items:start}
.cover{position:relative;aspect-ratio:2/3;border-radius:14px;overflow:hidden;box-shadow:0 22px 44px -22px rgba(10,74,62,.5);background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='26' height='26' viewBox='0 0 26 26'%3E%3Cpath d='M13 1.5l3.2 8.3 8.3 3.2-8.3 3.2L13 24.5l-3.2-8.3L1.5 13l8.3-3.2z' fill='none' stroke='%23fff' stroke-opacity='.09'/%3E%3C/svg%3E"),linear-gradient(160deg,hsl(var(--h) 42% 27%),hsl(var(--h) 46% 17%));color:#F6F2E8}
.cv-fb{position:absolute;inset:10px;display:flex;flex-direction:column;justify-content:space-between;padding:18px 12px;text-align:center;border:1.5px solid rgb(242 181 68 / .75);border-radius:3px;box-shadow:inset 0 0 0 3px hsl(var(--h) 44% 21%),inset 0 0 0 4px rgb(242 181 68 / .35)}
.cv-cat{font-size:.72rem;letter-spacing:.04em;color:#F2B544}
.cv-title{font:700 1.2rem/1.45 "Amiri","Fraunces",Georgia,serif;overflow:hidden;display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical}
.cv-auth{font-size:.82rem;color:#F2B544}
.cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .2s}.cover img.ok{opacity:1}
h1{margin:0 0 6px;font:800 clamp(1.6rem,4vw,2.3rem)/1.35 "Alexandria","IBM Plex Sans Arabic",sans-serif;letter-spacing:-.01em}
.by{margin:0 0 14px;color:var(--muted);font-size:1.05rem}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
.tag{background:var(--soft);color:var(--brand);border-radius:10px;padding:3px 12px;font-size:.84rem;text-decoration:none}.tag:nth-child(2){background:var(--rose-soft);color:var(--rose)}
.nums{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin:0 0 18px;color:var(--muted)}
.num{display:inline-flex;align-items:center;gap:6px}
.like{display:inline-flex;align-items:center;gap:6px;background:var(--card);color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font:inherit;cursor:pointer}
.like.on{color:#E5484D;border-color:#E5484D}
.like:hover{border-color:var(--brand)}
.btns{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 20px}
.rights{margin:-8px 0 16px;padding:10px 14px;border-radius:12px;background:var(--rose-soft);color:var(--ink);font-size:.9rem;line-height:1.7}
.btn{display:inline-block;background:var(--btn);color:var(--brand-ink);padding:10px 22px;border-radius:14px;font-weight:600;text-decoration:none;box-shadow:0 8px 18px -10px rgba(14,107,90,.7);transition:transform .25s cubic-bezier(.34,1.56,.64,1)}
.btn:hover{transform:translateY(-2px)}
.btn.alt{background:var(--card);color:var(--brand);border:1.5px solid var(--line);font-weight:500;box-shadow:none}.btn.alt:hover{border-color:var(--brand-2)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;margin:0 0 8px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:14px 18px;box-shadow:var(--shadow)}
dt{color:var(--muted)}dd{margin:0}
.desc{color:var(--muted);margin:0 0 16px}
.about{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:18px 20px;margin:18px 0;box-shadow:var(--shadow)}.about h2{margin:0 0 6px;font-size:1.1rem}.about p{margin:0 0 6px}.about small{color:var(--muted)}
h2{font:700 1.2rem/1.4 "Alexandria","IBM Plex Sans Arabic",sans-serif;margin:26px 0 10px}
ul.rel{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}
ul.rel li{background:var(--card);border:1px solid var(--line);border-radius:14px;transition:transform .25s cubic-bezier(.34,1.56,.64,1),border-color .2s}ul.rel li:hover{transform:translateY(-2px);border-color:var(--brand-2)}
ul.rel a{display:block;padding:10px 14px;text-decoration:none;color:var(--ink)}
ul.rel small{display:block;color:var(--muted)}
footer{position:relative;margin:34px 0 28px;color:var(--muted);font-size:.84rem;padding-top:22px}footer::before{content:"";position:absolute;inset-inline:0;top:0;height:14px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='14' viewBox='0 0 16 14'%3E%3Cpath d='M3 14V8.5C3 5.5 5 3.5 8 1.5c3 2 5 4 5 7V14' fill='none' stroke='%230E6B5A' stroke-opacity='.35' stroke-width='1.2'/%3E%3C/svg%3E") center/16px 14px repeat-x}
html[lang="ar"] h1{letter-spacing:0}
.legal{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0 0 10px}.legal a{color:var(--ink);font-weight:600;text-decoration:none}.legal a:hover{color:var(--brand)}
footer p{margin:0}
.share{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:-6px 0 20px}.share>span{color:var(--muted);font-size:.9rem;margin-inline-end:2px}
.sh{display:inline-flex;align-items:center;gap:7px;padding:7px 14px;border-radius:12px;border:0;color:#fff;font:600 .9rem "IBM Plex Sans Arabic",sans-serif;text-decoration:none;cursor:pointer;transition:transform .25s cubic-bezier(.34,1.56,.64,1),box-shadow .25s}
.sh:hover{transform:translateY(-2px);box-shadow:0 8px 16px -10px rgba(0,0,0,.45)}.sh.wa{background:#168F4A}.sh.tg{background:#1F87C0}.sh.fb{background:#1877F2}
.sh.cp{background:var(--card);color:var(--ink);border:1.5px solid var(--line)}.sh.cp:hover{border-color:var(--brand-2)}
.nf{text-align:center;padding-top:36px;padding-bottom:10px}.nf .legal{justify-content:center}.bar .wrap>nav{margin-inline-start:auto}.nf h1{margin:6px 0 8px}.nf .desc{max-width:52ch;margin:0 auto 20px}
.nf-door{position:relative;width:170px;margin:0 auto 14px;isolation:isolate}
.nf-door::before{content:"";position:absolute;z-index:-1;width:64px;height:64px;border-radius:50%;top:-8px;inset-inline-end:-26px;background:radial-gradient(circle at 34% 32%,#FFD98A,#F2B544 58%,#E2951C);box-shadow:0 0 0 10px rgba(242,181,68,.16)}
.nf-arch{display:grid;place-items:center;aspect-ratio:40/46;padding-top:34px;background:var(--grad);color:#fff;font:800 3.1rem/1 "Alexandria",sans-serif;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 46' preserveAspectRatio='none'%3E%3Cpath d='M0 46V24C0 11.5 9 5 20 0c11 5 20 11.5 20 24v22z'/%3E%3C/svg%3E") center/100% 100% no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 46' preserveAspectRatio='none'%3E%3Cpath d='M0 46V24C0 11.5 9 5 20 0c11 5 20 11.5 20 24v22z'/%3E%3C/svg%3E") center/100% 100% no-repeat}
.nf .sbox{max-width:520px;margin:0 auto 18px;height:50px}.nf .sbox button{display:block}
.nf-try{color:var(--muted);margin:22px 0 10px}.nf-cats{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin:0 auto 10px;max-width:720px}
.nf-cats a{background:var(--card);border:1.5px solid var(--line);border-radius:12px;padding:5px 14px;text-decoration:none;color:var(--ink);font-size:.9rem}
.nf-cats a:hover{border-color:var(--brand-2);color:var(--brand)}
@media (max-width:640px){.book{grid-template-columns:1fr;justify-items:center}.cover{width:200px}.book>div{width:100%}dl{grid-template-columns:1fr}}
.book h2.facts-h{font-size:1rem;margin:18px 0 6px;color:var(--muted);font-weight:600}.rights.pd{background:var(--soft);color:var(--ink)}.rights a{font-weight:600}.crumbs span{color:var(--muted)}.about p+p{margin-top:.6em}.about small a{font-weight:600}
"""

LIKE_JS = r'''<script>(function(){var b=document.getElementById('likeBtn');if(!b)return;var heart=function(f){return '<svg width="18" height="18" viewBox="0 0 24 24" fill="'+f+'" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-4.4-9.3-9A5.4 5.4 0 0 1 12 6.2 5.4 5.4 0 0 1 21.3 12C19 16.6 12 21 12 21z"/></svg>';};
b.addEventListener('click',function(){b.disabled=true;fetch('/api/like/'+b.dataset.id,{method:'POST'}).then(function(r){return r.json()}).then(function(j){if(typeof j.likes!=='number')return;b.classList.toggle('on',j.liked);b.setAttribute('aria-pressed',j.liked);document.getElementById('likeN').textContent=j.likes;document.getElementById('likeTxt').textContent=j.liked?b.dataset.liked:b.dataset.like;document.getElementById('likeIco').innerHTML=heart(j.liked?'currentColor':'none');}).catch(function(){}).then(function(){b.disabled=false;});});})();</script>'''

_cache = {}


def _cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    val = fn()
    _cache[key] = (time.time() + ttl, val)
    return val


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def is_arabic(s: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", s or ""))


def slugify(title: str) -> str:
    words = re.findall(r"\w+", norm(title), re.UNICODE)[:8]
    return ("-".join(words))[:70] or "book"


def default_ui(row) -> str:
    return "ar" if (row["lang"] == "ar" or row["origin"] == "a") and (row["title_ar"] or is_arabic(row["title"])) else "en"


# ---------- the visitor's language ----------
LANG_COOKIE = "warraq_lang"  # the language button's choice (kept a year); the server reads it for every page
# Crawlers always get a page's own language: Googlebot sends no Accept-Language, and these are recognised too
# (Google's other fetchers, page-speed tools, headless browsers...)
_CRAWLER = re.compile(r"bot|crawl|spider|slurp|google|bing|yandex|baidu|lighthouse|pagespeed|preview|headless|"
                      r"facebookexternalhit|curl|wget|python|monitor|uptime", re.I)


def browser_ui(accept_language: str) -> str:
    """Whichever of the site's languages comes first in the browser's languages ("en-US,en;q=0.9,ar;q=0.8" -> en,
    "ku,ar;q=0.8" -> ar, "fr-CA" -> fr, "zh-TW" -> zh, "pt-BR" -> pt); English when it lists none of them (ru-RU);
    "" when the browser sends no list."""
    tags = []
    for i, part in enumerate((accept_language or "").split(",")):
        tag, _, params = part.strip().partition(";")
        q = 1.0
        for p in params.split(";"):
            k, _, v = p.strip().partition("=")
            if k.strip() == "q":
                try:
                    q = float(v)
                except ValueError:
                    q = 0.0
        tag = tag.strip().lower()
        if tag and tag != "*" and q > 0:
            tags.append((-q, i, tag))
    for _, _, tag in sorted(tags):
        base = re.split(r"[-_]", tag, 1)[0]  # zh-Hant-TW -> zh
        if base in UI_LANGS:
            return base
    return "en" if tags else ""


def visitor_ui(request, lang: str = "", default: str = "ar") -> str:
    """The language a page opens in: ?lang= when the address has it; else the visitor's saved choice; else their
    browser's language; else the page's own, which crawlers always get (search engines see every page as before)."""
    if lang in UI_LANGS:
        return lang
    saved = request.cookies.get(LANG_COOKIE, "")
    if saved in UI_LANGS:
        return saved
    if _CRAWLER.search(request.headers.get("user-agent", "") or ""):
        return default
    return browser_ui(request.headers.get("accept-language", "")) or default


def book_title(row, ui: str) -> str:
    return (row["title_ar"] or row["title"]) if ui == "ar" else row["title"]


def book_author(row, ui: str, authors: dict) -> str:
    a = authors.get(row["author_key"]) if row["author_key"] else None
    if a:
        return a["ar"] if ui == "ar" and a["ar"] else a["en"]
    return (row["author_ar"] if ui == "ar" and row["author_ar"] else row["author_en"]) or ""


def canonical_path(row) -> str:
    ui = default_ui(row)
    return "/book/%d/%s" % (row["id"], quote(slugify(book_title(row, ui))))


# Google Analytics 4 (the site's property). ANALYTICS=0 turns it off (a test copy); GA_ID replaces the property.
GA_ID = os.environ.get("GA_ID", "").strip() or "G-RB47QYRPE9"


def analytics_on() -> bool:
    return os.environ.get("ANALYTICS", "1").strip() != "0"


def analytics_head() -> str:
    """Google's loader, and the site's own /ga.js in place of Google's inline lines (no inline script: CSP)."""
    if not analytics_on():
        return ""
    return ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>\n'
            '<script src="/ga.js?v=1" data-id="%s"></script>' % (esc(GA_ID), esc(GA_ID)))


def site_head() -> str:
    """What every page carries in its head: Google Analytics."""
    return analytics_head()


def legal_links(ui: str) -> str:
    q = lang_q(ui)
    return '<nav class="legal" aria-label="%s"><a href="/articles%s">%s</a>%s</nav>' % (
        esc(BRAND[ui]), q, esc(ARTICLES_NAME[ui]), "".join('<a href="/%s%s">%s</a>' % (k, q, esc(n)) for k, n in LEGAL[ui]))


def site_base(request) -> str:
    """The public address used in canonical links, sitemaps and robots.txt: SITE_URL, else the domain
    Railway gives the service (always https), else what the request says."""
    env = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if env:
        return env
    railway = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip().strip("/")
    if railway:
        return "https://" + railway
    return str(request.base_url).rstrip("/")


def lang_name(code: str, ui: str) -> str:
    n = LANG_NAMES.get((code or "").lower())
    return n[_LANG_NAME_UIS.index(ui) if ui in _LANG_NAME_UIS else 0] if n else (code or "").upper()


def read_links(row, ui: str):
    """Returns (main_url, is_direct_read, [(label, url), ...])."""
    t = T[ui]
    if row["ext"] and row["curated"] == SAFAHAT_KIND:  # free to read there
        return safahat_url(row["ext"]), True, []
    if row["ext"] and row["curated"] == OL_KIND:  # a catalogue record: "view", not "read"
        return ol_url(row["ext"]), False, []
    last = (row["author_en"] or "").split(" ")[-1] if row["author_en"] else ""
    q = quote((row["title"] + " " + last).strip())
    arch = ("https://archive.org/search?query=" + q, t["arch"])
    ol = ("https://openlibrary.org/search?mode=everything&has_fulltext=true&q=" + q, t["ol"])
    if row["gid"]:
        g = row["gid"]
        return ("https://www.gutenberg.org/cache/epub/%d/pg%d-images.html" % (g, g), True,
                [("https://www.gutenberg.org/ebooks/%d" % g, t["page_gut"]), arch])
    if row["htid"]:
        h = quote(row["htid"])
        return ("https://babel.hathitrust.org/cgi/pt?id=" + h, True,
                [("https://babel.hathitrust.org/cgi/ls?q1=%s&lmt=ft" % quote(row["title"]), t["page_ht"]), arch])
    if row["ws"]:
        return (ws_url(row["ws"]), True,
                [] if row["cat"] == "poe" else [("https://archive.org/search?query=" + quote(row["title_ar"] or row["title"]), t["arch"]), ol])
    if row["origin"] == "a":
        name = quote(row["title_ar"] or row["title"])
        return ("https://ar.wikisource.org/w/index.php?search=" + name, False,
                [("https://archive.org/search?query=" + name, t["arch"]), ol])
    return ("https://www.gutenberg.org/ebooks/search/?query=" + q, False, [arch, ol])


def read_label(row, ui: str, direct: bool) -> str:
    t = T[ui]
    if row["ext"] and row["curated"] == SAFAHAT_KIND:
        return t["read_saf"]
    if row["ext"] and row["curated"] == OL_KIND:
        return t["view_ol"]
    return t["read" if direct else "find"]


def ws_url(page: str) -> str:
    return "https://ar.wikisource.org/wiki/" + quote(page.replace(" ", "_"))


def source_name(row, ui: str) -> str:
    t = T[ui]
    if row["ext"] and row["curated"] in (SAFAHAT_KIND, OL_KIND):
        return t["src_saf" if row["curated"] == SAFAHAT_KIND else "src_ol"]
    if row["gid"]:
        return t["src_gut"]
    if row["htid"]:
        return t["src_ht"]
    return t["src_ws"] if row["ws"] or row["origin"] == "a" else t["src_idx"]


def cover_candidates(row):
    c = []
    if row["gid"]:
        c.append("https://www.gutenberg.org/cache/epub/%d/pg%d.cover.medium.jpg" % (row["gid"], row["gid"]))
    return c  # HathiTrust blocks its covers on other sites: the page asks /api/cover (Open Library) instead


def _authors(conn) -> dict:
    return _cached("authors", 600, lambda: {r["key"]: {"en": r["en"], "ar": r["ar"]} for r in conn.execute("SELECT key, en, ar FROM authors")})


RELATED_MIN, RELATED_MAX = 5, 8


def related(conn, row):
    """5 to 8 similar books: the author's best known first, then neighbours in the same category (same language
    preferred), then the category's best known."""
    out, seen = [], {row["id"]}

    def add(rows):
        for r in rows:
            if r["id"] not in seen and len(out) < RELATED_MAX:
                out.append(r); seen.add(r["id"])
    if row["author_key"]:
        add(conn.execute("SELECT * FROM books WHERE author_key=? AND id!=? ORDER BY ord LIMIT 4", (row["author_key"], row["id"])))
    add(conn.execute("SELECT * FROM books WHERE id BETWEEN ? AND ? AND cat=? AND lang=? AND id!=? LIMIT 24",
                     (row["id"] - 600, row["id"] + 600, row["cat"], row["lang"], row["id"])))
    if len(out) < RELATED_MIN:
        add(conn.execute("SELECT * FROM books WHERE cat=? AND lang=? ORDER BY ord LIMIT 16", (row["cat"], row["lang"])))
    if len(out) < RELATED_MIN:
        add(conn.execute("SELECT * FROM books WHERE cat=? ORDER BY ord LIMIT 16", (row["cat"],)))
    return "similar", out


def book_indexable(row) -> bool:
    """In search results: a book page with a text of its own (in its default language). With
    THIN_NOINDEX off, every book page."""
    return not content.thin_noindex() or bool(content.book(row, default_ui(row)))


def _cut(text: str, n: int = 158) -> str:
    """At most n characters, ending on a whole word."""
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip("،,.؛:") + "…"


def _plain(text: str) -> str:
    """A paragraph without its Markdown: link texts and bold words only."""
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text))


LOGO_SVG = ('<svg viewBox="4 0 40 48" width="32" height="38" aria-hidden="true"><defs><linearGradient id="gL" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#18A086"/><stop offset=".6" stop-color="#0E6B5A"/><stop offset="1" stop-color="#0A4A3E"/></linearGradient></defs>'
            '<path d="M5 47V25C5 13 14 6.5 24 1c10 5.5 19 12 19 24v22z" fill="url(#gL)"/><circle class="lg-sun" cx="24" cy="14" r="4" fill="#F2B544"/>'
            '<path d="M25.08 25.17Q26.8 20.46 28.87 20.5Q30.42 20.54 31.65 22.53Q32.8 24.43 33.02 26.89Q33.24 29.32 32.23 33.38Q31.26 37.39 28.39 40.83Q25.52 44.27 23.58 44.44Q22 44.67 18.91 44Q17.41 43.7 16.24 43.36Q15.07 43.03 14.32 42.73Q13.84 42.5 13.97 41.98Q14.1 41.4 14.81 41.53Q17.45 41.93 21.11 41.09Q22.92 40.7 26.4 37.65Q28.17 36.11 29.25 34.9Q30.33 33.69 30.64 32.72Q30.59 32.49 30.48 32.16Q30.37 31.83 30.24 31.44Q28.39 33.82 25.79 32.63Q22.83 31.3 25.08 25.17ZM29.27 27.25Q27.99 25.17 26.54 27.07Q27.64 28.31 29.27 27.25Z" fill="#FBF8F1"/></svg>')
SEARCH_ICON = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">'
               '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')
GLOBE_ICON = ('<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">'
              '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.8 3 2.8 15 0 18M12 3c-2.8 3-2.8 15 0 18"/></svg>')


def lang_menu(ui: str, href, nofollow: bool = False) -> str:
    """The language menu of the server's pages: a plain link per language, so it needs no script. href(code) gives
    each one's address; Arabic's carries ?lang=ar too, so that it replaces a saved choice of another language."""
    links = "".join('<a href="%s" hreflang="%s" lang="%s"%s%s>%s</a>' % (
        esc(href(code)), code, code, ' rel="nofollow"' if nofollow else "", ' aria-current="true"' if code == ui else "",
        esc(UI_LANG_NAMES[code])) for code in UI_LANGS)
    return ('<details class="lmenu"><summary aria-label="%s">%s<span>%s</span></summary><div class="lmenu-list">%s</div></details>'
            % (esc(T[ui]["menu_lang"]), GLOBE_ICON, esc(UI_LANG_SHORT[ui]), links))


def not_found_html(ui="ar") -> str:
    """The 404 page: the site's header, a search box, a way home and the categories (never indexed)."""
    ui = ui if ui in T else "ar"
    t = T[ui]
    q = lang_q(ui)
    cats = "".join('<a href="/category/%s%s">%s</a>' % (k, q, esc(v[ui])) for k, v in CATEGORIES.items())
    return """<!doctype html>
<html lang="{ui}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
{site_head}
<title>{h} | {brand}</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Alexandria:wght@700;800&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap">
<style>{css}</style>
</head>
<body>
<header class="bar"><div class="wrap"><a class="brand" href="/{q}">{logo}<span>{brand}</span></a>
<nav><a href="/{q}#browse">{all}</a>{menu}</nav></div></header>
<main class="wrap nf">
<div class="nf-door" aria-hidden="true"><div class="nf-arch">404</div></div>
<h1>{h}</h1>
<p class="desc">{p}</p>
<form class="sbox" action="/#browse" method="get" role="search">{icon}<input type="search" name="q" placeholder="{ph}" aria-label="{ph}"><button type="submit">{search}</button></form>
<a class="btn" href="/{q}">{home}</a>
<p class="nf-try">{try_}</p>
<nav class="nf-cats" aria-label="{try_}">{cats}</nav>
<footer>{legal}<p>{note}</p></footer>
</main>
</body>
</html>
""".format(ui=ui, dir=t["dir"], h=esc(t["notfound"]), brand=esc(BRAND[ui]), css=CSS, q=q,
           logo=LOGO_SVG, all=esc(t["all"]), menu=lang_menu(ui, lambda c: "/?lang=" + c), p=esc(t["nf_p"]), icon=SEARCH_ICON,
           ph=esc(t["ph"]), search=esc(t["search"]), home=esc(t["nf_home"]), try_=esc(t["nf_try"]), cats=cats,
           legal=legal_links(ui), note=esc(t["note"]), site_head=site_head())


SHARE_ICONS = {"wa": '<svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" d="M12 3a9 9 0 0 0-7.7 13.6L3 21l4.5-1.2A9 9 0 1 0 12 3z"/><path fill="currentColor" d="M9.1 7.6c.3 0 .5 0 .7.5l.8 1.9c.1.3 0 .5-.1.7l-.6.7c-.1.2-.2.4 0 .6.9 1.5 2 2.6 3.5 3.4.2.1.4.1.6-.1l.8-.9c.2-.2.4-.3.7-.2l1.8.9c.3.1.5.3.5.5 0 .6-.3 1.4-.9 1.8-.7.5-1.6.6-2.5.3-3-.9-5.4-3.2-6.5-6.2-.3-.9-.2-1.9.4-2.6.2-.3.5-.5.8-.5z"/></svg>',
               "tg": '<svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M21.4 3.6 2.9 10.8c-1 .4-1 1.6 0 1.9l4.6 1.4 1.8 5.6c.2.7 1.1.9 1.6.4l2.6-2.4 4.7 3.5c.6.4 1.4.1 1.6-.6L22.9 5c.3-1.1-.6-1.9-1.5-1.4zM9.6 14l8.9-7.7-7.4 9.1-.3 2.8z"/></svg>',
               "fb": '<svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M13.6 21v-7.5h2.6l.4-3.1h-3V8.5c0-.9.3-1.5 1.6-1.5h1.6V4.2c-.3 0-1.2-.1-2.3-.1-2.3 0-3.9 1.4-3.9 4V10.4H8v3.1h2.6V21z"/></svg>',
               "link": '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/></svg>'}
# copy the page's link; browsers without the clipboard API get it in a prompt to copy by hand
SHARE_JS = """<script>(function(){var b=document.getElementById('copyBtn');if(!b)return;var l=b.querySelector('span'),o=l.textContent;
b.addEventListener('click',function(){var u=b.dataset.url;function ok(){l.textContent=b.dataset.done;setTimeout(function(){l.textContent=o},1800)}
if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(u).then(ok,function(){window.prompt('',u)})}else{window.prompt('',u)}});})();</script>"""

# the author's summary from Wikipedia in the page's language; the other interfaces fall back to English, not Arabic
WIKI_JS = """<script>(function(){var s=document.getElementById('aa');if(!s)return;var ui=s.dataset.ui;
var cand=ui==='ar'||ui==='en'?[[ui,s.dataset.name],[ui==='ar'?'en':'ar',s.dataset.alt],['en',s.dataset.alt||s.dataset.name]]:[[ui,s.dataset.name],['en',s.dataset.name]];var i=0;
function next(){if(i>=cand.length)return;var c=cand[i++];if(!c[1])return next();
fetch('https://'+c[0]+'.wikipedia.org/api/rest_v1/page/summary/'+encodeURIComponent(c[1].replace(/ /g,'_'))+'?redirect=true').then(function(r){return r.ok?r.json():null}).then(function(j){
if(!j||j.type!=='standard'||!j.extract||j.extract.length<60)return next();
var p=document.getElementById('aaT');p.lang=c[0];p.textContent=j.extract.length>600?j.extract.slice(0,600).replace(/\\s+\\S*$/,'')+'\u2026':j.extract;
var a=document.getElementById('aaL'),u=(j.content_urls&&j.content_urls.desktop&&j.content_urls.desktop.page)||'';a.href=/^https:\\/\\/[a-z-]+\\.wikipedia\\.org\\//.test(u)?u:'#';s.hidden=false;}).catch(next);}
next();})();</script>"""


def render_book(conn, row, base: str, ui: str = "", numbers=(0, 0), liked: bool = False, nonce: str = "") -> str:
    d_ui = default_ui(row)
    ui = ui if ui in T else d_ui
    t = T[ui]
    authors = _authors(conn)
    title = book_title(row, ui)
    author = book_author(row, ui, authors)
    cat = CATEGORIES.get(row["cat"], CATEGORIES["gen"])
    cat_name = cat[ui]
    lang = lang_name(row["lang"], ui)
    main_url, direct, extra = read_links(row, ui)
    canon = base + canonical_path(row)
    covers = cover_candidates(row)
    modern = row["curated"] in (SAFAHAT_KIND, OL_KIND) and bool(row["ext"])
    source = source_name(row, ui)
    facts_x = json.loads(row["info"]) if row["info"] else {}
    poem = row["cat"] == "poe" and row["curated"] == WS_KIND  # one poem from Wikisource, not a whole book
    note = content.book(row, ui)  # the library's own text about this book, when one is written
    indexable = book_indexable(row)
    if note.get("about"):
        desc = _cut(_plain(note["about"][0]))
    else:
        parts = dict(t=title, by=t["d_by"].format(a=author) if author else "", c=cat_name, l=lang, s=source,
                     y=t["d_y"].format(y=facts_x["year"]) if facts_x.get("year") else "",
                     p=t["d_p"].format(p=facts_x["pub"]) if facts_x.get("pub") else "",
                     kind=t["k_poem"] if poem else t["k_book"])
        form = t["d_saf" if modern and row["curated"] == SAFAHAT_KIND else "d_ol" if modern else "d_pd"]
        desc = form.format(**parts)
        if len(desc) > 158 and parts["p"]:  # too long to show whole: the publisher stays in the details below
            desc = form.format(**dict(parts, p=""))
        desc = _cut(desc)
    page_title = (t["title_by"].format(t=title, a=author) if author else title) + " | " + BRAND[ui]

    book = {"@type": "CreativeWork" if poem else "Book", "@id": canon + "#book", "name": title, "url": canon,
            "mainEntityOfPage": {"@id": canon}, "description": desc, "genre": cat_name, "isAccessibleForFree": True,
            "sameAs": main_url, "potentialAction": {"@type": "ReadAction", "target": {"@type": "EntryPoint", "urlTemplate": main_url}}}
    if not poem:
        book["bookFormat"] = "https://schema.org/EBook"
    if modern and row["curated"] == OL_KIND:  # under copyright, and the record cannot be read
        book["isAccessibleForFree"] = False
        book.pop("potentialAction")
        book.pop("bookFormat")
    if facts_x.get("year"):
        book["datePublished"] = str(facts_x["year"])
    if facts_x.get("pub"):
        book["publisher"] = {"@type": "Organization", "name": facts_x["pub"]}
    if facts_x.get("pages"):
        book["numberOfPages"] = facts_x["pages"]
    if row["lang"] and row["lang"] not in ("und", "mul", "zxx"):
        book["inLanguage"] = row["lang"]
    if title != row["title"]:
        book["alternateName"] = row["title"]
    if author:
        book["author"] = {"@type": "Person", "name": author}
        if row["author_key"]:
            book["author"]["url"] = base + "/author/" + quote(row["author_key"])
        if row["author_en"] and row["author_en"] != author:
            book["author"]["alternateName"] = row["author_en"]
    if covers:
        book["image"] = covers[0]
    if numbers[1]:
        book["interactionStatistic"] = {"@type": "InteractionCounter", "interactionType": "https://schema.org/LikeAction",
                                        "userInteractionCount": numbers[1]}
    crumbs = {"@type": "BreadcrumbList", "@id": canon + "#crumbs", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": t["home"], "item": base + "/"},
        {"@type": "ListItem", "position": 2, "name": cat_name, "item": base + "/category/" + row["cat"]},
        {"@type": "ListItem", "position": 3, "name": title, "item": canon}]}
    page_ld = {"@type": "ItemPage", "@id": canon, "url": canon, "name": page_title, "inLanguage": ui,
               "isPartOf": {"@type": "WebSite", "@id": base + "/#site", "url": base + "/", "name": BRAND[ui]},
               "mainEntity": {"@id": canon + "#book"}, "breadcrumb": {"@id": canon + "#crumbs"}}
    ld = {"@context": "https://schema.org", "@graph": [page_ld, book, crumbs]}
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")

    og_img = '<meta property="og:image" content="%s">' % esc(covers[0] if covers else base + "/og-image.png")

    btns = '<a class="btn" href="%s" target="_blank" rel="nofollow noopener">%s</a>' % (esc(main_url), esc(read_label(row, ui, direct)))
    btns += "".join('<a class="btn alt" href="%s" target="_blank" rel="nofollow noopener">%s</a>' % (esc(u), esc(n)) for u, n in extra)

    msg = t["share_txt"].format(t=title)
    share = ('<div class="share"><span>%s</span>'
             '<a class="sh wa" href="https://wa.me/?text=%s" target="_blank" rel="noopener nofollow">%s%s</a>'
             '<a class="sh tg" href="https://t.me/share/url?url=%s&amp;text=%s" target="_blank" rel="noopener nofollow">%s%s</a>'
             '<a class="sh fb" href="https://www.facebook.com/sharer/sharer.php?u=%s" target="_blank" rel="noopener nofollow">%s%s</a>'
             '<button type="button" class="sh cp" id="copyBtn" data-url="%s" data-done="%s">%s<span>%s</span></button></div>'
             % (esc(t["share"]), quote(msg + " " + canon, safe=""), SHARE_ICONS["wa"], esc(t["wa"]),
                quote(canon, safe=""), quote(msg, safe=""), SHARE_ICONS["tg"], esc(t["tg"]),
                quote(canon, safe=""), SHARE_ICONS["fb"], esc(t["fb"]),
                esc(canon), esc(t["copied"]), SHARE_ICONS["link"], esc(t["copy"])))
    takedown = '<a href="/takedown?%su=%s">%s</a>' % (esc(lang_q(ui, amp=True)), quote(canonical_path(row), safe=""), esc(t["takedown_a"]))
    if modern:  # whose book it is, and why there is no text here
        share = '<p class="rights">%s %s %s</p>' % (esc(t["note_saf" if row["curated"] == SAFAHAT_KIND else "note_ol"]), esc(t["takedown_q"]), takedown) + share
    else:  # no file here, and the public domain is not the same everywhere
        share = '<p class="rights pd">%s %s %s</p>' % (esc(t["legal_pd"]), esc(t["takedown_q"]), takedown) + share

    tags = '<a class="tag" href="/category/%s">%s</a>' % (esc(row["cat"]), esc(cat_name))
    tags += '<span class="tag">%s</span>' % esc(lang)
    views, likes = numbers
    heart = '<svg width="18" height="18" viewBox="0 0 24 24" fill="%s" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-4.4-9.3-9A5.4 5.4 0 0 1 12 6.2 5.4 5.4 0 0 1 21.3 12C19 16.6 12 21 12 21z"/></svg>'
    eye = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>'
    numbers_html = (
        '<div class="nums"><span class="num">%s<b>%d</b> %s</span>'
        '<button type="button" id="likeBtn" class="like%s" aria-pressed="%s" data-id="%d" data-like="%s" data-liked="%s">'
        '<span id="likeIco">%s</span><span id="likeTxt">%s</span> · <b id="likeN">%d</b></button></div>'
        % (eye, views, esc(t["views"]), " on" if liked else "", "true" if liked else "false", row["id"], esc(t["like"]), esc(t["liked"]),
           heart % ("currentColor" if liked else "none"), esc(t["liked"] if liked else t["like"]), likes))

    facts = ""
    if author:
        link = ('<a href="/author/%s">%s</a>' % (esc(quote(row["author_key"])), esc(author))) if row["author_key"] else esc(author)
        facts += "<dt>%s</dt><dd>%s</dd>" % (esc(t["by"]), link)
    facts += "<dt>%s</dt><dd>%s</dd><dt>%s</dt><dd>%s</dd><dt>%s</dt><dd>%s</dd>" % (
        esc(t["cat"]), esc(cat_name), esc(t["lang"]), esc(lang), esc(t["src"]), esc(source))
    for k in ("pub", "year", "pages"):
        if facts_x.get(k):
            facts += "<dt>%s</dt><dd>%s</dd>" % (esc(t[k]), esc(str(facts_x[k])))

    key, rel_rows = related(conn, row)
    rel_html = ""
    if rel_rows:
        items = []
        for r in rel_rows:
            rt, ra = book_title(r, ui), book_author(r, ui, authors)
            items.append('<li><a href="/book/%d">%s%s</a></li>' % (r["id"], esc(rt), ("<small>%s</small>" % esc(ra)) if ra else ""))
        rel_html = "<h2>%s</h2><ul class=\"rel\">%s</ul>" % (esc(t[key]), "".join(items))

    if note.get("about"):
        about_html = '<section class="about"><h2>%s</h2>%s</section>' % (esc(t["about"]), own_text(note["about"], ui))
        if note.get("context"):
            about_html += '<section class="about"><h2>%s</h2>%s</section>' % (esc(t["context"]), own_text(note["context"], ui))
    else:
        about_html = '<section class="about"><h2>%s</h2><p>%s</p></section>' % (
            esc(t["about"]), esc(t["about_saf" if modern and row["curated"] == SAFAHAT_KIND else "about_ol" if modern else "about_txt"].format(
                t=title, a=(t["about_by"].format(a=author) if author else ""), c=cat_name, l=lang, s=source)))
    bio = content.author(row["author_key"], ui)
    if bio:  # written for this site; Wikipedia's summary is only fetched for the others
        about_html += '<section class="about"><h2>%s</h2>%s<small><a href="/author/%s%s">%s</a></small></section>' % (
            esc(t["about_author"]), own_text(bio, ui), esc(quote(row["author_key"])), lang_q(ui), esc(t["bio_more"]))
    elif author:
        about_html += ('<section class="about" id="aa" hidden data-name="%s" data-alt="%s" data-ui="%s" data-src="%s"><h2>%s</h2><p id="aaT"></p>'
                       '<small><a id="aaL" href="#" target="_blank" rel="noopener">%s</a></small></section>'
                       % (esc(author), esc(row["author_en"] or ""), ui, esc(t["wiki"]), esc(t["about_author"]), esc(t["wiki"])))
    cv_script = (
        "<script>(function(){var im=document.getElementById('cvimg');if(!im)return;var src=%s;var i=0;"
            "function done(ok){if(ok){im.classList.add('ok');}else next();}"
            "function next(){if(i<src.length){im.src=src[i++];}else{fetch('/api/cover/%d').then(function(r){return r.json()}).then(function(j){if(j&&j.url&&!im.dataset.ol){im.dataset.ol=1;im.src=j.url;}}).catch(function(){});}}"
            "im.addEventListener('load',function(){if(im.naturalWidth<40||im.naturalHeight<40){next();}else{done(true);}});"
            "im.addEventListener('error',function(){next();});next();})();</script>"
            % (json.dumps(covers), row["id"]))

    page = """<!doctype html>
<html lang="{ui}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="book">
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:site_name" content="{brand}">
{og_img}
<meta property="og:locale" content="{locale}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{page_title}">
<meta name="twitter:description" content="{desc}">
<meta name="robots" content="{robots}">
{site_head}
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Alexandria:wght@700;800&family=Amiri:wght@400;700&family=Fraunces:opsz,wght@9..144,700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap">
<script type="application/ld+json">{ld}</script>
<style>{css}</style>
</head>
<body>
<header class="bar"><div class="wrap"><a class="brand" href="/">{logo}<span>{brand}</span></a>
<form class="sbox" action="/#browse" method="get" role="search">{search_icon}<input type="search" name="q" placeholder="{ph}" aria-label="{ph}"><button type="submit">{search}</button></form>
<nav><a href="/#browse">{all}</a>{menu}</nav></div></header>
<main class="wrap">
<p class="crumbs"><a href="/">{home}</a> / <a href="/category/{catkey}">{cat_name}</a> / <span>{title}</span></p>
<article class="book">
<div class="cover" style="--h:{hue}"><span class="cv-fb"><span class="cv-cat">{cat_name}</span><span class="cv-title">{title}</span><span class="cv-auth">{author}</span></span><img id="cvimg" alt="{alt}" decoding="async" referrerpolicy="no-referrer"></div>
<div>
<h1>{title}</h1>
{by}
<div class="tags">{tags}</div>
{numbers_html}
<div class="btns">{btns}</div>
{share}
<p class="desc">{desc}</p>
<h2 class="facts-h">{facts_h}</h2>
<dl>{facts}</dl>
</div>
</article>
{about}
{rel}
<footer>{legal}<p>{note}</p></footer>
</main>
{cv_script}
{like_js}
{wiki_js}
{share_js}
</body>
</html>
""".format(ui=ui, dir=t["dir"], page_title=esc(page_title), desc=esc(desc), canon=esc(canon), brand=esc(BRAND[ui]), og_img=og_img,
           ld=ld_json, css=CSS, all=esc(t["all"]), menu=lang_menu(ui, lambda c: "?lang=" + c, nofollow=True),
           home=esc(t["home"]), catkey=esc(row["cat"]), cat_name=esc(cat_name), hue=int(cat["hue"]), title=esc(title), author=esc(author),
           alt=esc(title), by=('<p class="by">%s</p>' % esc(author)) if author else "", tags=tags, numbers_html=numbers_html, btns=btns, share=share, share_js=SHARE_JS, facts=facts, rel=rel_html, about=about_html,
           note=esc(t["note"]), legal=legal_links(ui), cv_script=cv_script, like_js=LIKE_JS, wiki_js=WIKI_JS,
           logo=LOGO_SVG, search_icon=SEARCH_ICON, ph=esc(t["ph"]), search=esc(t["search"]),
           locale=OG_LOCALE[ui], site_head=site_head(),
           robots="index,follow,max-image-preview:large" if indexable else "noindex,follow", facts_h=esc(t["facts_h"]))
    # the Content-Security-Policy of this response only lets scripts carrying its nonce run
    return page.replace("<script", '<script nonce="%s"' % esc(nonce)) if nonce else page


# ---------- sitemaps ----------

def _total(conn) -> int:
    return _cached("total", 300, lambda: conn.execute("SELECT COUNT(*) FROM books").fetchone()[0])


def _sitemap_rows(conn):
    """With THIN_NOINDEX, the book pages that may be listed: those with a text of their own."""
    gids = sorted(content.described_gids())
    if not gids:
        return []
    rows = conn.execute("SELECT id, gid, curated, title, title_ar, lang, origin FROM books WHERE curated=1 AND gid IN (%s) ORDER BY id"
                        % ",".join("?" * len(gids)), gids).fetchall()
    return [r for r in rows if book_indexable(r)]


def sitemap_index(conn, base: str) -> str:
    n = 1 if content.thin_noindex() else max(1, math.ceil(_total(conn) / SITEMAP_PAGE))
    items = ["<sitemap><loc>%s/sitemap-main.xml</loc></sitemap>" % base]
    items += ["<sitemap><loc>%s/sitemap-books-%d.xml</loc></sitemap>" % (base, i) for i in range(1, n + 1)]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</sitemapindex>\n' % "\n".join(items)


def sitemap_main(base: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            "<url><loc>%s/</loc></url>\n</urlset>\n" % base)


def sitemap_books(conn, base: str, page: int):
    if content.thin_noindex():
        rows = _sitemap_rows(conn) if page == 1 else []
        if not rows:
            return None if page != 1 else '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n'
    else:
        rows = conn.execute("SELECT id, title, title_ar, lang, origin FROM books ORDER BY id LIMIT ? OFFSET ?",
                            (SITEMAP_PAGE, (page - 1) * SITEMAP_PAGE)).fetchall()
    if not rows:
        return None
    out = []
    for r in rows:
        out.append("<url><loc>%s%s</loc></url>" % (base, html.escape(canonical_path(r))))
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % "\n".join(out)