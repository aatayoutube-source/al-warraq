/* Al-Warraq frontend: talks to the FastAPI backend (/api/*). No build step. */
(() => {
    'use strict';

    document.documentElement.classList.add('js'); // enables the scroll-in animations (CSS shows everything without JS)
    const PAGE = 60;
    const AUTO_MAX = PAGE * 3; // scrolling loads up to 180 books by itself; after that the "more" button does, so the footer stays reachable

    const T = {
        ar: {
            brand: 'مكتبة الوراق',
            brand_sub: 'كتب وقصائد في الملك العام',
            theme: 'تبديل المظهر',
            nav_browse: 'الكتب',
            nav_poetry: 'الشعر',
            nav_authors: 'المؤلفون',
            nav_research: 'البحوث',
            ph: 'ابحث بعنوان كتاب أو اسم مؤلف',
            search: 'بحث',
            eyebrow: 'كتب في الملك العام',
            h1: 'اقرأ ما سقط عنه حق النشر',
            lede: 'فهرس مفتوح لأكثر من مليون كتاب وعشرات آلاف القصائد العربية، وآلاف الكتب العربية الحديثة، بأغلفتها وتصنيفاتها، يوصلك إلى صفحاتها في مصادرها الأصلية القانونية.',
            quick: 'ابدأ من هنا:',
            st_books: 'كتاب',
            st_auth: 'مؤلف',
            st_lang: 'لغة',
            f_cat: 'التصنيف',
            cats_h: 'تصفّح حسب التصنيف',
            cats_p: 'اختر تصنيفاً لتصل إلى كتبه مباشرة.',
            poems_tag: 'جديد من ويكي مصدر',
            poems_h: 'ديوان العرب',
            poems_lead: '{n} قصيدة لكبار شعراء العربية، من الجاهلية إلى العصر الحديث، تقرؤها كاملة في ويكي مصدر. اختر شاعراً لتتصفح قصائده.',
            poems_n: '{n} قصيدة',
            browse_h: 'كل الكتب',
            browse_p: 'ابحث وصفِّ حسب التصنيف واللغة، ثم افتح الكتاب من مصدره مباشرة.',
            foot_about: 'فهرس عربي مفتوح للكتب والقصائد التي سقط عنها حق النشر، وللكتب العربية الحديثة. لا نستضيف الملفات، بل نوصلك إلى مصادرها الأصلية.',
            foot_src: 'المصادر',
            foot_cats: 'تصفّح التصنيفات',
            foot_pages: 'صفحات المكتبة',
            pg_about: 'عن المكتبة',
            pg_privacy: 'سياسة الخصوصية',
            pg_terms: 'شروط الاستخدام',
            pg_contact: 'اتصل بنا',
            pg_articles: 'مقالات',
            pg_takedown: 'طلب إزالة محتوى',
            ws_name: 'ويكي مصدر',
            pop_h: 'الأكثر مشاهدة',
            pop_s: 'الأكثر بحثاً',
            v_h: 'زوار الموقع',
            v_today: 'زائر اليوم',
            v_month: 'زائر هذا الشهر',
            v_year: 'زائر هذه السنة',
            n_books: '{n} كتاب',
            n_poems: '{n} قصيدة',
            results_mix: '{b} كتاب و{p} قصيدة',
            f_lang: 'لغة الكتاب',
            f_org: 'الأصل',
            f_sort: 'الترتيب',
            all: 'الكل',
            all_cats: 'كل التصنيفات',
            org_a: 'تراث عربي وإسلامي',
            org_w: 'أدب وعلم عالمي',
            sort_def: 'الافتراضي',
            sort_t: 'العنوان',
            sort_a: 'المؤلف',
            clear: 'مسح الفلاتر',
            filters: 'تصفية',
            results: '{n} كتاب',
            results_more: 'أكثر من {n} كتاب',
            ad: 'إعلانات', // the labels Google permits: "Advertisements" or "Sponsored links"
            near_all: 'لا يوجد تطابق تام لـ«{q}»، وهذه {n} نتيجة قريبة منه',
            near_some: 'منها {n} بتهجئة قريبة',
            loading: 'جارٍ التحميل…',
            more: 'عرض المزيد',
            none: 'لا توجد نتائج في الفهرس. جرّب المصادر الكاملة أعلاه.',
            none_f: 'لا توجد كتب تجمع كل الفلاتر المختارة.',
            clear_f: 'امسح الفلاتر واعرض كل الكتب',
            err: 'تعذّر الاتصال بالخادم.',
            retry: 'إعادة المحاولة',
            beyond: 'ابحث عن «{q}» في المصادر الكاملة',
            l_gut: 'غوتنبرغ',
            l_arch: 'أرشيف الإنترنت',
            l_ol: 'المكتبة المفتوحة',
            l_ws: 'ويكي مصدر',
            l_page: 'صفحة الكتاب',
            l_ht: 'نسخ أخرى',
            read: 'اقرأ',
            find: 'ابحث عن الكتاب',
            view: 'اعرض',
            src_saf: 'صفحات (هنداوي)',
            authors_h: 'المؤلفون والشخصيات المشهورة',
            authors_p: 'اضغط على اسم لعرض أعماله.',
            show_all: 'عرض الكل ({n})',
            show_less: 'عرض أقل',
            books_n: '{n} كتاب',
            research_h: 'مكتب البحوث المفتوحة',
            research_p: 'اكتب موضوعك واختر المصدر. كل الروابط تفتح قواعد بيانات مجانية وقانونية للبحوث والكتب.',
            med_h: 'البحوث الطبية',
            med_p: 'أبحاث وكتب طبية وحيوية بنص كامل مجاني.',
            eng_h: 'البحوث الهندسية',
            eng_p: 'أبحاث وتقارير ومقررات هندسية وتقنية مفتوحة.',
            r_ph: 'اكتب موضوعاً (بالإنجليزية أفضل) أو اختر من القائمة',
            also_src: 'ابحث أيضاً في قواعد البيانات المفتوحة:',
            p_loading: 'جارٍ جلب الأبحاث…',
            p_found: '{n} بحث مفتوح عن «{q}»، وهذه أهمها:',
            p_none: 'لا توجد أبحاث بهذا الموضوع. جرّب كلمة إنجليزية أو اختر موضوعاً من القائمة.',
            p_err: 'تعذّر جلب الأبحاث الآن. جرّب قواعد البيانات بالأسفل.',
            p_read: 'اقرأ البحث',
            p_pdf: 'PDF مجاني',
            p_cited: '{n} استشهاد',
            r_open: '↗',
            legal1: 'جميع الروابط تقود إلى مواقع خارجية. المكتبة لا تستضيف ملفات، وتعرض أعمال الملك العام، أما الكتب الحديثة فنعرض بيانات فهرستها فقط ونوصلك إلى مصادرها القانونية.',
            legal2: 'حالة الملك العام تختلف من بلد لآخر (مشروع غوتنبرغ يتبع القانون الأمريكي). تحقق من قانون بلدك قبل إعادة النشر.',
            lang_menu: 'اللغة'
        },
        en: {
            brand: 'Al-Warraq Library',
            brand_sub: 'Public-domain books & poetry',
            theme: 'Toggle theme',
            nav_browse: 'Books',
            nav_poetry: 'Poetry',
            nav_authors: 'Authors',
            nav_research: 'Research',
            ph: 'Search a title or an author',
            search: 'Search',
            eyebrow: 'Public-domain books',
            h1: 'Read what has left copyright',
            lede: 'An open index of over a million books, tens of thousands of Arabic poems and thousands of modern Arabic books, with covers and categories, linking to their pages at legal original sources.',
            quick: 'Start with:',
            st_books: 'books',
            st_auth: 'authors',
            st_lang: 'languages',
            f_cat: 'Category',
            cats_h: 'Browse by category',
            cats_p: 'Pick a category to jump straight to its books.',
            poems_tag: 'New from Wikisource',
            poems_h: 'The Arabic poetry collection',
            poems_lead: '{n} poems by the great Arabic poets, from pre-Islamic times to the modern era, each readable in full on Wikisource. Pick a poet to browse their poems.',
            poems_n: '{n} poems',
            browse_h: 'All books',
            browse_p: 'Search, filter by category and language, then open the book at its source.',
            foot_about: 'An open Arabic index of public-domain books and poems, and of modern Arabic books. We host no files; every link leads to the original source.',
            foot_src: 'Sources',
            foot_cats: 'Browse categories',
            foot_pages: 'Library pages',
            pg_about: 'About us',
            pg_privacy: 'Privacy policy',
            pg_terms: 'Terms of use',
            pg_contact: 'Contact us',
            pg_articles: 'Articles',
            pg_takedown: 'Content removal',
            ws_name: 'Wikisource (Arabic)',
            pop_h: 'Most viewed',
            pop_s: 'Popular searches',
            v_h: 'Site visitors',
            v_today: 'visitors today',
            v_month: 'visitors this month',
            v_year: 'visitors this year',
            n_books: '{n} books',
            n_poems: '{n} poems',
            results_mix: '{b} books and {p} poems',
            f_lang: 'Book language',
            f_org: 'Origin',
            f_sort: 'Sort by',
            all: 'All',
            all_cats: 'All categories',
            org_a: 'Arabic & Islamic heritage',
            org_w: 'World literature & science',
            sort_def: 'Default',
            sort_t: 'Title',
            sort_a: 'Author',
            clear: 'Clear filters',
            filters: 'Filters',
            results: '{n} books',
            results_more: 'More than {n} books',
            ad: 'Advertisements',
            near_all: 'No exact match for “{q}”: {n} close results',
            near_some: '{n} of them spelled a little differently',
            loading: 'Loading…',
            more: 'Show more',
            none: 'No matches in the index. Try the full sources above.',
            none_f: 'No books match all the selected filters together.',
            clear_f: 'Clear the filters and show every book',
            err: 'Could not reach the server.',
            retry: 'Try again',
            beyond: 'Search the full sources for “{q}”',
            l_gut: 'Gutenberg',
            l_arch: 'Internet Archive',
            l_ol: 'Open Library',
            l_ws: 'Wikisource',
            l_page: 'Book page',
            l_ht: 'Other copies',
            read: 'Read',
            find: 'Find the book',
            view: 'View',
            src_saf: 'Safahat (Hindawi)',
            authors_h: 'Famous authors & figures',
            authors_p: 'Select a name to see their works.',
            show_all: 'Show all ({n})',
            show_less: 'Show fewer',
            books_n: '{n} books',
            research_h: 'Open research desk',
            research_p: 'Type a topic and pick a source. Every link opens a free, legal database of papers and books.',
            med_h: 'Medical research',
            med_p: 'Biomedical papers and books with free full text.',
            eng_h: 'Engineering research',
            eng_p: 'Open engineering and technology papers, reports and courses.',
            r_ph: 'Type a topic or pick one below',
            also_src: 'Search the open databases too:',
            p_loading: 'Finding papers…',
            p_found: '{n} open papers on “{q}”. The most relevant:',
            p_none: 'No papers on this topic. Try other words or pick a topic below.',
            p_err: 'Papers could not be loaded right now. Try the databases below.',
            p_read: 'Read the paper',
            p_pdf: 'Free PDF',
            p_cited: '{n} citations',
            r_open: '↗',
            legal1: 'All links lead to external sites. This library hosts no files; it lists public-domain works, and for modern books only their catalogue record with a link to a legal source.',
            legal2: 'Public-domain status differs by country (Project Gutenberg follows US law). Check your local law before republishing.',
            lang_menu: 'Language'
        },
        zh: {
            brand: 'Al-Warraq 图书馆',
            brand_sub: '公有领域图书与诗歌',
            theme: '切换主题',
            nav_browse: '图书',
            nav_poetry: '诗歌',
            nav_authors: '作者',
            nav_research: '研究',
            ph: '搜索书名或作者',
            search: '搜索',
            eyebrow: '公有领域图书',
            h1: '阅读已脱离版权的作品',
            lede: '一个开放的索引，收录超过一百万本图书、数万首阿拉伯语诗歌和数千本现代阿拉伯语图书，附封面和分类，并链接到它们在合法原始来源上的页面。',
            quick: '从这里开始：',
            st_books: '本图书',
            st_auth: '位作者',
            st_lang: '种语言',
            f_cat: '分类',
            cats_h: '按分类浏览',
            cats_p: '选择一个分类，直接查看其中的图书。',
            poems_tag: '维基文库新增',
            poems_h: '阿拉伯诗歌集',
            poems_lead: '{n} 首阿拉伯伟大诗人的诗作，从前伊斯兰时期到现代，均可在维基文库阅读全文。选择一位诗人，浏览其诗作。',
            poems_n: '{n} 首诗',
            browse_h: '全部图书',
            browse_p: '搜索并按分类和语言筛选，然后直接在来源处打开图书。',
            foot_about: '一个开放的阿拉伯语索引，收录公有领域的图书和诗歌，以及现代阿拉伯语图书。我们不存放文件，每个链接都通向原始来源。',
            foot_src: '来源',
            foot_cats: '浏览分类',
            foot_pages: '图书馆页面',
            pg_about: '关于我们',
            pg_privacy: '隐私政策',
            pg_terms: '使用条款',
            pg_contact: '联系我们',
            pg_articles: '文章',
            pg_takedown: '内容移除申请',
            ws_name: '维基文库（阿拉伯语）',
            pop_h: '最多浏览',
            pop_s: '热门搜索',
            v_h: '网站访客',
            v_today: '今日访客',
            v_month: '本月访客',
            v_year: '今年访客',
            n_books: '{n} 本图书',
            n_poems: '{n} 首诗',
            results_mix: '{b} 本图书和 {p} 首诗',
            f_lang: '图书语言',
            f_org: '起源',
            f_sort: '排序',
            all: '全部',
            all_cats: '全部分类',
            org_a: '阿拉伯与伊斯兰遗产',
            org_w: '世界文学与科学',
            sort_def: '默认',
            sort_t: '书名',
            sort_a: '作者',
            clear: '清除筛选',
            filters: '筛选',
            results: '{n} 本图书',
            results_more: '超过 {n} 本图书',
            ad: '广告',
            near_all: '没有与“{q}”完全匹配的结果：{n} 个相近结果',
            near_some: '其中 {n} 个拼写略有不同',
            loading: '加载中…',
            more: '显示更多',
            none: '索引中没有匹配结果。请试试上方的完整来源。',
            none_f: '没有同时符合所有所选筛选条件的图书。',
            clear_f: '清除筛选并显示所有图书',
            err: '无法连接到服务器。',
            retry: '重试',
            beyond: '在完整来源中搜索“{q}”',
            l_gut: '古腾堡',
            l_arch: '互联网档案馆',
            l_ol: 'Open Library',
            l_ws: '维基文库',
            l_page: '图书页面',
            l_ht: '其他副本',
            read: '阅读',
            find: '查找本书',
            view: '查看',
            src_saf: 'Safahat（Hindawi）',
            authors_h: '著名作者与人物',
            authors_p: '选择一个名字，查看其作品。',
            show_all: '显示全部（{n}）',
            show_less: '收起',
            books_n: '{n} 本图书',
            research_h: '开放研究台',
            research_p: '输入主题并选择来源。每个链接都会打开一个免费、合法的论文和图书数据库。',
            med_h: '医学研究',
            med_p: '可免费阅读全文的生物医学论文和图书。',
            eng_h: '工程研究',
            eng_p: '开放的工程与技术论文、报告和课程。',
            r_ph: '输入主题（英文效果最好），或从下方选择',
            also_src: '也可以在开放数据库中搜索：',
            p_loading: '正在查找论文…',
            p_found: '关于“{q}”的开放论文共 {n} 篇，最相关的是：',
            p_none: '没有关于这个主题的论文。请换个词，或从下方选择一个主题。',
            p_err: '暂时无法加载论文。请试试下方的数据库。',
            p_read: '阅读论文',
            p_pdf: '免费 PDF',
            p_cited: '{n} 次引用',
            r_open: '↗',
            legal1: '所有链接都通向外部网站。本图书馆不存放任何文件；它列出公有领域作品，对于现代图书，只提供书目信息和指向合法来源的链接。',
            legal2: '公有领域的认定因国家而异（古腾堡计划遵循美国法律）。转载前请先了解你所在地的法律。',
            lang_menu: '语言'
        },
        fr: {
            brand: 'Bibliothèque Al-Warraq',
            brand_sub: 'Livres et poésie du domaine public',
            theme: 'Changer de thème',
            nav_browse: 'Livres',
            nav_poetry: 'Poésie',
            nav_authors: 'Auteurs',
            nav_research: 'Recherche',
            ph: 'Rechercher un titre ou un auteur',
            search: 'Rechercher',
            eyebrow: 'Livres du domaine public',
            h1: 'Lisez ce qui est libre de droits',
            lede: 'Un index ouvert de plus d’un million de livres, de dizaines de milliers de poèmes arabes et de milliers de livres arabes modernes, avec couvertures et catégories, qui renvoie vers leurs pages aux sources d’origine légales.',
            quick: 'Pour commencer :',
            st_books: 'livres',
            st_auth: 'auteurs',
            st_lang: 'langues',
            f_cat: 'Catégorie',
            cats_h: 'Parcourir par catégorie',
            cats_p: 'Choisissez une catégorie pour accéder directement à ses livres.',
            poems_tag: 'Nouveau sur Wikisource',
            poems_h: 'La poésie arabe',
            poems_lead: '{n} poèmes des grands poètes arabes, de l’époque préislamique à nos jours, à lire en entier sur Wikisource. Choisissez un poète pour parcourir ses poèmes.',
            poems_n: '{n} poèmes',
            browse_h: 'Tous les livres',
            browse_p: 'Cherchez, filtrez par catégorie et par langue, puis ouvrez le livre à sa source.',
            foot_about: 'Un index arabe ouvert des livres et poèmes du domaine public, et des livres arabes modernes. Nous n’hébergeons aucun fichier : chaque lien mène à la source d’origine.',
            foot_src: 'Sources',
            foot_cats: 'Parcourir les catégories',
            foot_pages: 'Pages de la bibliothèque',
            pg_about: 'À propos',
            pg_privacy: 'Politique de confidentialité',
            pg_terms: 'Conditions d’utilisation',
            pg_contact: 'Nous contacter',
            pg_articles: 'Articles',
            pg_takedown: 'Demande de retrait',
            ws_name: 'Wikisource (arabe)',
            pop_h: 'Les plus consultés',
            pop_s: 'Recherches populaires',
            v_h: 'Visiteurs du site',
            v_today: 'visiteurs aujourd’hui',
            v_month: 'visiteurs ce mois-ci',
            v_year: 'visiteurs cette année',
            n_books: '{n} livres',
            n_poems: '{n} poèmes',
            results_mix: '{b} livres et {p} poèmes',
            f_lang: 'Langue du livre',
            f_org: 'Origine',
            f_sort: 'Trier par',
            all: 'Tout',
            all_cats: 'Toutes les catégories',
            org_a: 'Patrimoine arabe et islamique',
            org_w: 'Littérature et science du monde',
            sort_def: 'Par défaut',
            sort_t: 'Titre',
            sort_a: 'Auteur',
            clear: 'Effacer les filtres',
            filters: 'Filtres',
            results: '{n} livres',
            results_more: 'Plus de {n} livres',
            ad: 'Publicités',
            near_all: 'Aucun résultat exact pour « {q} » : {n} résultats proches',
            near_some: 'dont {n} avec une orthographe un peu différente',
            loading: 'Chargement…',
            more: 'Afficher plus',
            none: 'Aucun résultat dans l’index. Essayez les sources complètes ci-dessus.',
            none_f: 'Aucun livre ne correspond à tous les filtres choisis.',
            clear_f: 'Effacer les filtres et afficher tous les livres',
            err: 'Impossible de joindre le serveur.',
            retry: 'Réessayer',
            beyond: 'Chercher « {q} » dans les sources complètes',
            l_gut: 'Gutenberg',
            l_arch: 'Internet Archive',
            l_ol: 'Open Library',
            l_ws: 'Wikisource',
            l_page: 'Page du livre',
            l_ht: 'Autres exemplaires',
            read: 'Lire',
            find: 'Trouver le livre',
            view: 'Voir',
            src_saf: 'Safahat (Hindawi)',
            authors_h: 'Auteurs et figures célèbres',
            authors_p: 'Choisissez un nom pour voir ses œuvres.',
            show_all: 'Tout afficher ({n})',
            show_less: 'Afficher moins',
            books_n: '{n} livres',
            research_h: 'Bureau de la recherche ouverte',
            research_p: 'Tapez un sujet et choisissez une source. Chaque lien ouvre une base gratuite et légale d’articles et de livres.',
            med_h: 'Recherche médicale',
            med_p: 'Articles et livres biomédicaux en texte intégral gratuit.',
            eng_h: 'Recherche en ingénierie',
            eng_p: 'Articles, rapports et cours ouverts en ingénierie et technologie.',
            r_ph: 'Tapez un sujet (de préférence en anglais) ou choisissez-en un ci-dessous',
            also_src: 'Cherchez aussi dans les bases ouvertes :',
            p_loading: 'Recherche d’articles…',
            p_found: '{n} articles ouverts sur « {q} ». Les plus pertinents :',
            p_none: 'Aucun article sur ce sujet. Essayez d’autres mots ou choisissez un sujet ci-dessous.',
            p_err: 'Impossible de charger les articles pour le moment. Essayez les bases ci-dessous.',
            p_read: 'Lire l’article',
            p_pdf: 'PDF gratuit',
            p_cited: '{n} citations',
            r_open: '↗',
            legal1: 'Tous les liens mènent à des sites externes. Cette bibliothèque n’héberge aucun fichier ; elle répertorie des œuvres du domaine public et, pour les livres modernes, seulement leur notice avec un lien vers une source légale.',
            legal2: 'Le statut de domaine public varie selon les pays (le Projet Gutenberg suit le droit américain). Vérifiez la loi de votre pays avant toute republication.',
            lang_menu: 'Langue'
        },
        es: {
            brand: 'Biblioteca Al-Warraq',
            brand_sub: 'Libros y poesía de dominio público',
            theme: 'Cambiar tema',
            nav_browse: 'Libros',
            nav_poetry: 'Poesía',
            nav_authors: 'Autores',
            nav_research: 'Investigación',
            ph: 'Busca un título o un autor',
            search: 'Buscar',
            eyebrow: 'Libros de dominio público',
            h1: 'Lee lo que ya no tiene derechos de autor',
            lede: 'Un índice abierto de más de un millón de libros, decenas de miles de poemas árabes y miles de libros árabes modernos, con portadas y categorías, que enlaza a sus páginas en fuentes originales legales.',
            quick: 'Empieza por aquí:',
            st_books: 'libros',
            st_auth: 'autores',
            st_lang: 'idiomas',
            f_cat: 'Categoría',
            cats_h: 'Explora por categoría',
            cats_p: 'Elige una categoría para ir directamente a sus libros.',
            poems_tag: 'Novedad de Wikisource',
            poems_h: 'La poesía árabe',
            poems_lead: '{n} poemas de los grandes poetas árabes, desde la época preislámica hasta la actualidad, para leer completos en Wikisource. Elige un poeta para ver sus poemas.',
            poems_n: '{n} poemas',
            browse_h: 'Todos los libros',
            browse_p: 'Busca, filtra por categoría e idioma, y abre el libro en su fuente.',
            foot_about: 'Un índice árabe abierto de libros y poemas de dominio público, y de libros árabes modernos. No alojamos archivos: cada enlace lleva a la fuente original.',
            foot_src: 'Fuentes',
            foot_cats: 'Explorar categorías',
            foot_pages: 'Páginas de la biblioteca',
            pg_about: 'Quiénes somos',
            pg_privacy: 'Política de privacidad',
            pg_terms: 'Términos de uso',
            pg_contact: 'Contacto',
            pg_articles: 'Artículos',
            pg_takedown: 'Solicitud de retirada',
            ws_name: 'Wikisource (árabe)',
            pop_h: 'Lo más visto',
            pop_s: 'Búsquedas populares',
            v_h: 'Visitantes del sitio',
            v_today: 'visitantes hoy',
            v_month: 'visitantes este mes',
            v_year: 'visitantes este año',
            n_books: '{n} libros',
            n_poems: '{n} poemas',
            results_mix: '{b} libros y {p} poemas',
            f_lang: 'Idioma del libro',
            f_org: 'Origen',
            f_sort: 'Ordenar por',
            all: 'Todos',
            all_cats: 'Todas las categorías',
            org_a: 'Patrimonio árabe e islámico',
            org_w: 'Literatura y ciencia universales',
            sort_def: 'Predeterminado',
            sort_t: 'Título',
            sort_a: 'Autor',
            clear: 'Borrar filtros',
            filters: 'Filtros',
            results: '{n} libros',
            results_more: 'Más de {n} libros',
            ad: 'Anuncios',
            near_all: 'No hay coincidencias exactas para «{q}»: {n} resultados parecidos',
            near_some: '{n} de ellos con una ortografía algo distinta',
            loading: 'Cargando…',
            more: 'Mostrar más',
            none: 'No hay resultados en el índice. Prueba las fuentes completas de arriba.',
            none_f: 'Ningún libro cumple todos los filtros elegidos a la vez.',
            clear_f: 'Borra los filtros y muestra todos los libros',
            err: 'No se pudo conectar con el servidor.',
            retry: 'Reintentar',
            beyond: 'Busca «{q}» en las fuentes completas',
            l_gut: 'Gutenberg',
            l_arch: 'Internet Archive',
            l_ol: 'Open Library',
            l_ws: 'Wikisource',
            l_page: 'Página del libro',
            l_ht: 'Otras copias',
            read: 'Leer',
            find: 'Buscar el libro',
            view: 'Ver',
            src_saf: 'Safahat (Hindawi)',
            authors_h: 'Autores y figuras célebres',
            authors_p: 'Elige un nombre para ver sus obras.',
            show_all: 'Mostrar todos ({n})',
            show_less: 'Mostrar menos',
            books_n: '{n} libros',
            research_h: 'Mesa de investigación abierta',
            research_p: 'Escribe un tema y elige una fuente. Cada enlace abre una base de datos gratuita y legal de artículos y libros.',
            med_h: 'Investigación médica',
            med_p: 'Artículos y libros biomédicos con texto completo gratuito.',
            eng_h: 'Investigación en ingeniería',
            eng_p: 'Artículos, informes y cursos abiertos de ingeniería y tecnología.',
            r_ph: 'Escribe un tema (mejor en inglés) o elige uno abajo',
            also_src: 'Busca también en las bases de datos abiertas:',
            p_loading: 'Buscando artículos…',
            p_found: '{n} artículos abiertos sobre «{q}». Los más relevantes:',
            p_none: 'No hay artículos sobre este tema. Prueba otras palabras o elige un tema abajo.',
            p_err: 'No se pudieron cargar los artículos ahora. Prueba las bases de datos de abajo.',
            p_read: 'Leer el artículo',
            p_pdf: 'PDF gratis',
            p_cited: '{n} citas',
            r_open: '↗',
            legal1: 'Todos los enlaces llevan a sitios externos. Esta biblioteca no aloja archivos; recoge obras de dominio público y, de los libros modernos, solo su ficha de catálogo con un enlace a una fuente legal.',
            legal2: 'La condición de dominio público cambia según el país (el Proyecto Gutenberg sigue la ley de EE. UU.). Consulta la ley de tu país antes de volver a publicar.',
            lang_menu: 'Idioma'
        },
        pt: {
            brand: 'Biblioteca Al-Warraq',
            brand_sub: 'Livros e poesia em domínio público',
            theme: 'Mudar tema',
            nav_browse: 'Livros',
            nav_poetry: 'Poesia',
            nav_authors: 'Autores',
            nav_research: 'Pesquisa',
            ph: 'Pesquise um título ou um autor',
            search: 'Pesquisar',
            eyebrow: 'Livros em domínio público',
            h1: 'Leia o que já saiu dos direitos autorais',
            lede: 'Um índice aberto de mais de um milhão de livros, dezenas de milhares de poemas árabes e milhares de livros árabes modernos, com capas e categorias, que leva às páginas deles em fontes originais legais.',
            quick: 'Comece por aqui:',
            st_books: 'livros',
            st_auth: 'autores',
            st_lang: 'idiomas',
            f_cat: 'Categoria',
            cats_h: 'Navegue por categoria',
            cats_p: 'Escolha uma categoria para ir direto aos livros dela.',
            poems_tag: 'Novo no Wikisource',
            poems_h: 'A poesia árabe',
            poems_lead: '{n} poemas dos grandes poetas árabes, da era pré-islâmica aos dias de hoje, para ler na íntegra no Wikisource. Escolha um poeta para ver os poemas dele.',
            poems_n: '{n} poemas',
            browse_h: 'Todos os livros',
            browse_p: 'Pesquise, filtre por categoria e idioma e abra o livro na fonte.',
            foot_about: 'Um índice árabe aberto de livros e poemas em domínio público e de livros árabes modernos. Não hospedamos arquivos: cada link leva à fonte original.',
            foot_src: 'Fontes',
            foot_cats: 'Navegar pelas categorias',
            foot_pages: 'Páginas da biblioteca',
            pg_about: 'Sobre nós',
            pg_privacy: 'Política de privacidade',
            pg_terms: 'Termos de uso',
            pg_contact: 'Fale conosco',
            pg_articles: 'Artigos',
            pg_takedown: 'Pedido de remoção',
            ws_name: 'Wikisource (árabe)',
            pop_h: 'Mais vistos',
            pop_s: 'Pesquisas populares',
            v_h: 'Visitantes do site',
            v_today: 'visitantes hoje',
            v_month: 'visitantes este mês',
            v_year: 'visitantes este ano',
            n_books: '{n} livros',
            n_poems: '{n} poemas',
            results_mix: '{b} livros e {p} poemas',
            f_lang: 'Idioma do livro',
            f_org: 'Origem',
            f_sort: 'Ordenar por',
            all: 'Todos',
            all_cats: 'Todas as categorias',
            org_a: 'Patrimônio árabe e islâmico',
            org_w: 'Literatura e ciência mundiais',
            sort_def: 'Padrão',
            sort_t: 'Título',
            sort_a: 'Autor',
            clear: 'Limpar filtros',
            filters: 'Filtros',
            results: '{n} livros',
            results_more: 'Mais de {n} livros',
            ad: 'Anúncios',
            near_all: 'Nenhum resultado exato para “{q}”: {n} resultados parecidos',
            near_some: '{n} deles com grafia um pouco diferente',
            loading: 'Carregando…',
            more: 'Mostrar mais',
            none: 'Nenhum resultado no índice. Tente as fontes completas acima.',
            none_f: 'Nenhum livro atende a todos os filtros escolhidos ao mesmo tempo.',
            clear_f: 'Limpe os filtros e mostre todos os livros',
            err: 'Não foi possível conectar ao servidor.',
            retry: 'Tentar de novo',
            beyond: 'Pesquise “{q}” nas fontes completas',
            l_gut: 'Gutenberg',
            l_arch: 'Internet Archive',
            l_ol: 'Open Library',
            l_ws: 'Wikisource',
            l_page: 'Página do livro',
            l_ht: 'Outras cópias',
            read: 'Ler',
            find: 'Encontrar o livro',
            view: 'Ver',
            src_saf: 'Safahat (Hindawi)',
            authors_h: 'Autores e figuras famosas',
            authors_p: 'Escolha um nome para ver as obras.',
            show_all: 'Mostrar todos ({n})',
            show_less: 'Mostrar menos',
            books_n: '{n} livros',
            research_h: 'Central de pesquisa aberta',
            research_p: 'Digite um tema e escolha uma fonte. Cada link abre uma base de dados gratuita e legal de artigos e livros.',
            med_h: 'Pesquisa médica',
            med_p: 'Artigos e livros biomédicos com texto completo gratuito.',
            eng_h: 'Pesquisa em engenharia',
            eng_p: 'Artigos, relatórios e cursos abertos de engenharia e tecnologia.',
            r_ph: 'Digite um tema (de preferência em inglês) ou escolha um abaixo',
            also_src: 'Pesquise também nas bases de dados abertas:',
            p_loading: 'Buscando artigos…',
            p_found: '{n} artigos abertos sobre “{q}”. Os mais relevantes:',
            p_none: 'Nenhum artigo sobre este tema. Tente outras palavras ou escolha um tema abaixo.',
            p_err: 'Não foi possível carregar os artigos agora. Tente as bases de dados abaixo.',
            p_read: 'Ler o artigo',
            p_pdf: 'PDF grátis',
            p_cited: '{n} citações',
            r_open: '↗',
            legal1: 'Todos os links levam a sites externos. Esta biblioteca não hospeda arquivos; ela lista obras em domínio público e, dos livros modernos, apenas a ficha catalográfica com um link para uma fonte legal.',
            legal2: 'A condição de domínio público varia de país para país (o Projeto Gutenberg segue a lei dos EUA). Confira a lei do seu país antes de republicar.',
            lang_menu: 'Idioma'
        },
        ja: {
            brand: 'アル・ワッラーク図書館',
            brand_sub: 'パブリックドメインの本と詩',
            theme: 'テーマを切り替える',
            nav_browse: '本',
            nav_poetry: '詩',
            nav_authors: '著者',
            nav_research: '研究',
            ph: '書名や著者名で検索',
            search: '検索',
            eyebrow: 'パブリックドメインの本',
            h1: '著作権の切れた名作を読もう',
            lede: '100万冊以上の本、数万篇のアラビア語の詩、数千冊の現代アラビア語の本を、表紙とカテゴリー付きで収めたオープンな索引です。合法的な元の情報源にあるページへ案内します。',
            quick: 'ここから始める：',
            st_books: '冊の本',
            st_auth: '人の著者',
            st_lang: '言語',
            f_cat: 'カテゴリー',
            cats_h: 'カテゴリーから探す',
            cats_p: 'カテゴリーを選ぶと、その本が一覧で表示されます。',
            poems_tag: 'ウィキソースから新着',
            poems_h: 'アラビア語詩集',
            poems_lead: 'イスラーム以前から現代まで、アラビアの偉大な詩人による{n}篇の詩を、ウィキソースで全文読めます。詩人を選んで作品を見てみましょう。',
            poems_n: '{n}篇の詩',
            browse_h: 'すべての本',
            browse_p: '検索し、カテゴリーや言語で絞り込んで、元の情報源で本を開きましょう。',
            foot_about: 'パブリックドメインの本と詩、そして現代アラビア語の本のためのオープンなアラビア語索引です。ファイルは掲載せず、すべてのリンクが元の情報源へつながります。',
            foot_src: '情報源',
            foot_cats: 'カテゴリー一覧',
            foot_pages: '図書館のページ',
            pg_about: '私たちについて',
            pg_privacy: 'プライバシーポリシー',
            pg_terms: '利用規約',
            pg_contact: 'お問い合わせ',
            pg_articles: '記事',
            pg_takedown: '削除依頼',
            ws_name: 'ウィキソース（アラビア語）',
            pop_h: 'よく見られている本',
            pop_s: '人気の検索',
            v_h: 'サイトの訪問者',
            v_today: '今日の訪問者',
            v_month: '今月の訪問者',
            v_year: '今年の訪問者',
            n_books: '{n}冊',
            n_poems: '{n}篇の詩',
            results_mix: '{b}冊の本と{p}篇の詩',
            f_lang: '本の言語',
            f_org: '由来',
            f_sort: '並べ替え',
            all: 'すべて',
            all_cats: 'すべてのカテゴリー',
            org_a: 'アラブ・イスラームの遺産',
            org_w: '世界の文学と科学',
            sort_def: '標準',
            sort_t: '書名',
            sort_a: '著者',
            clear: '絞り込みを解除',
            filters: '絞り込み',
            results: '{n}冊',
            results_more: '{n}冊以上',
            ad: '広告',
            near_all: '「{q}」に完全一致する結果はありません：近い結果 {n}件',
            near_some: 'うち{n}件は表記が少し異なります',
            loading: '読み込み中…',
            more: 'もっと見る',
            none: '索引に該当する本がありません。上の完全な情報源をお試しください。',
            none_f: '選択したすべての条件に合う本はありません。',
            clear_f: '絞り込みを解除してすべての本を表示',
            err: 'サーバーに接続できませんでした。',
            retry: '再試行',
            beyond: '「{q}」を完全な情報源で検索',
            l_gut: 'Gutenberg',
            l_arch: 'インターネット・アーカイブ',
            l_ol: 'Open Library',
            l_ws: 'ウィキソース',
            l_page: '本のページ',
            l_ht: 'ほかの版',
            read: '読む',
            find: '本を探す',
            view: '見る',
            src_saf: 'Safahat（Hindawi）',
            authors_h: '著名な著者と人物',
            authors_p: '名前を選ぶと作品が表示されます。',
            show_all: 'すべて表示（{n}）',
            show_less: '表示を減らす',
            books_n: '{n}冊',
            research_h: 'オープン研究デスク',
            research_p: 'テーマを入力して情報源を選んでください。すべてのリンクは無料で合法的な論文・書籍データベースにつながります。',
            med_h: '医学研究',
            med_p: '全文を無料で読める生物医学の論文と本。',
            eng_h: '工学研究',
            eng_p: '工学・技術分野のオープンな論文、報告書、講義。',
            r_ph: 'テーマを入力（英語がおすすめ）するか、下から選択',
            also_src: 'オープンデータベースでも検索：',
            p_loading: '論文を検索中…',
            p_found: '「{q}」に関するオープンな論文 {n}件。関連性の高いもの：',
            p_none: 'このテーマの論文はありません。別の言葉を試すか、下からテーマを選んでください。',
            p_err: '現在、論文を読み込めません。下のデータベースをお試しください。',
            p_read: '論文を読む',
            p_pdf: '無料PDF',
            p_cited: '被引用 {n}件',
            r_open: '↗',
            legal1: 'すべてのリンクは外部サイトにつながります。当図書館はファイルを掲載せず、パブリックドメインの作品を紹介し、現代の本については書誌情報と合法的な情報源へのリンクのみを表示します。',
            legal2: 'パブリックドメインかどうかは国によって異なります（プロジェクト・グーテンベルクは米国法に従います）。再公開する前に、お住まいの国の法律を確認してください。',
            lang_menu: '言語'
        },
        de: {
            brand: 'Bibliothek Al-Warraq',
            brand_sub: 'Gemeinfreie Bücher und Lyrik',
            theme: 'Design wechseln',
            nav_browse: 'Bücher',
            nav_poetry: 'Lyrik',
            nav_authors: 'Autoren',
            nav_research: 'Forschung',
            ph: 'Titel oder Autor suchen',
            search: 'Suchen',
            eyebrow: 'Gemeinfreie Bücher',
            h1: 'Lesen Sie, was gemeinfrei ist',
            lede: 'Ein offenes Verzeichnis von über einer Million Büchern, Zehntausenden arabischen Gedichten und Tausenden modernen arabischen Büchern, mit Umschlägen und Kategorien, das zu ihren Seiten an legalen Originalquellen führt.',
            quick: 'Fangen Sie hier an:',
            st_books: 'Bücher',
            st_auth: 'Autoren',
            st_lang: 'Sprachen',
            f_cat: 'Kategorie',
            cats_h: 'Nach Kategorie stöbern',
            cats_p: 'Wählen Sie eine Kategorie, um direkt zu ihren Büchern zu gelangen.',
            poems_tag: 'Neu aus Wikisource',
            poems_h: 'Arabische Dichtung',
            poems_lead: '{n} Gedichte der großen arabischen Dichter, von der vorislamischen Zeit bis in die Moderne, vollständig auf Wikisource lesbar. Wählen Sie einen Dichter, um seine Gedichte zu durchsuchen.',
            poems_n: '{n} Gedichte',
            browse_h: 'Alle Bücher',
            browse_p: 'Suchen, nach Kategorie und Sprache filtern und das Buch direkt an der Quelle öffnen.',
            foot_about: 'Ein offenes arabisches Verzeichnis gemeinfreier Bücher und Gedichte sowie moderner arabischer Bücher. Wir speichern keine Dateien; jeder Link führt zur Originalquelle.',
            foot_src: 'Quellen',
            foot_cats: 'Kategorien durchsuchen',
            foot_pages: 'Seiten der Bibliothek',
            pg_about: 'Über uns',
            pg_privacy: 'Datenschutzerklärung',
            pg_terms: 'Nutzungsbedingungen',
            pg_contact: 'Kontakt',
            pg_articles: 'Artikel',
            pg_takedown: 'Antrag auf Entfernung',
            ws_name: 'Wikisource (Arabisch)',
            pop_h: 'Meistgesehen',
            pop_s: 'Beliebte Suchen',
            v_h: 'Besucher der Website',
            v_today: 'Besucher heute',
            v_month: 'Besucher diesen Monat',
            v_year: 'Besucher dieses Jahr',
            n_books: '{n} Bücher',
            n_poems: '{n} Gedichte',
            results_mix: '{b} Bücher und {p} Gedichte',
            f_lang: 'Sprache des Buches',
            f_org: 'Herkunft',
            f_sort: 'Sortieren nach',
            all: 'Alle',
            all_cats: 'Alle Kategorien',
            org_a: 'Arabisches und islamisches Erbe',
            org_w: 'Weltliteratur und Wissenschaft',
            sort_def: 'Standard',
            sort_t: 'Titel',
            sort_a: 'Autor',
            clear: 'Filter zurücksetzen',
            filters: 'Filter',
            results: '{n} Bücher',
            results_more: 'Mehr als {n} Bücher',
            ad: 'Anzeigen',
            near_all: 'Kein genauer Treffer für „{q}“: {n} ähnliche Ergebnisse',
            near_some: 'davon {n} mit etwas anderer Schreibweise',
            loading: 'Wird geladen…',
            more: 'Mehr anzeigen',
            none: 'Keine Treffer im Verzeichnis. Versuchen Sie die vollständigen Quellen oben.',
            none_f: 'Kein Buch erfüllt alle gewählten Filter zugleich.',
            clear_f: 'Filter zurücksetzen und alle Bücher zeigen',
            err: 'Der Server ist nicht erreichbar.',
            retry: 'Erneut versuchen',
            beyond: '„{q}“ in den vollständigen Quellen suchen',
            l_gut: 'Gutenberg',
            l_arch: 'Internet Archive',
            l_ol: 'Open Library',
            l_ws: 'Wikisource',
            l_page: 'Buchseite',
            l_ht: 'Weitere Exemplare',
            read: 'Lesen',
            find: 'Buch finden',
            view: 'Ansehen',
            src_saf: 'Safahat (Hindawi)',
            authors_h: 'Berühmte Autoren und Persönlichkeiten',
            authors_p: 'Wählen Sie einen Namen, um die Werke zu sehen.',
            show_all: 'Alle zeigen ({n})',
            show_less: 'Weniger zeigen',
            books_n: '{n} Bücher',
            research_h: 'Offener Forschungstisch',
            research_p: 'Geben Sie ein Thema ein und wählen Sie eine Quelle. Jeder Link öffnet eine kostenlose, legale Datenbank für Fachartikel und Bücher.',
            med_h: 'Medizinische Forschung',
            med_p: 'Biomedizinische Artikel und Bücher mit kostenlosem Volltext.',
            eng_h: 'Ingenieurwissenschaftliche Forschung',
            eng_p: 'Offene Artikel, Berichte und Kurse aus Technik und Ingenieurwesen.',
            r_ph: 'Thema eingeben (am besten auf Englisch) oder unten wählen',
            also_src: 'Suchen Sie auch in den offenen Datenbanken:',
            p_loading: 'Fachartikel werden gesucht…',
            p_found: '{n} offene Fachartikel zu „{q}“. Die wichtigsten:',
            p_none: 'Keine Fachartikel zu diesem Thema. Versuchen Sie andere Wörter oder wählen Sie unten ein Thema.',
            p_err: 'Die Fachartikel können gerade nicht geladen werden. Versuchen Sie die Datenbanken unten.',
            p_read: 'Artikel lesen',
            p_pdf: 'Kostenloses PDF',
            p_cited: '{n} Zitierungen',
            r_open: '↗',
            legal1: 'Alle Links führen zu externen Websites. Diese Bibliothek speichert keine Dateien; sie verzeichnet gemeinfreie Werke und zeigt bei modernen Büchern nur die Katalogdaten mit einem Link zu einer legalen Quelle.',
            legal2: 'Ob ein Werk gemeinfrei ist, hängt vom Land ab (Projekt Gutenberg folgt US-Recht). Prüfen Sie das Recht Ihres Landes, bevor Sie etwas neu veröffentlichen.',
            lang_menu: 'Sprache'
        }
    };
    // the interface languages, as the server has them (pages.UI_LANGS); Arabic is the site's own (no ?lang=)
    const LANGS = ['ar', 'en', 'zh', 'fr', 'es', 'pt', 'ja', 'de'];
    const LANG_SHORT = { ar: 'ع', en: 'EN', zh: '中', fr: 'FR', es: 'ES', pt: 'PT', ja: '日', de: 'DE' };

    const QUICK = [
        { q: 'المتنبي', ar: 'المتنبي', en: 'Al-Mutanabbi', zh: '穆太奈比', ja: 'ムタナッビー' },
        { q: 'جبران', ar: 'جبران', en: 'Gibran', zh: '纪伯伦', ja: 'ジブラーン' },
        { q: 'ابن سينا', ar: 'ابن سينا', en: 'Avicenna', zh: '伊本·西那', fr: 'Avicenne', es: 'Avicena', pt: 'Avicena', ja: 'イブン・シーナー' },
        { q: 'ألف ليلة', ar: 'ألف ليلة وليلة', en: 'Arabian Nights', zh: '一千零一夜', fr: 'Les Mille et Une Nuits', es: 'Las mil y una noches', pt: 'As Mil e Uma Noites', ja: '千夜一夜物語', de: 'Tausendundeine Nacht' },
        { q: 'shakespeare', ar: 'شكسبير', en: 'Shakespeare', zh: '莎士比亚', ja: 'シェイクスピア' },
        { q: 'dostoevsky', ar: 'دوستويفسكي', en: 'Dostoevsky', zh: '陀思妥耶夫斯基', fr: 'Dostoïevski', es: 'Dostoyevski', pt: 'Dostoiévski', ja: 'ドストエフスキー', de: 'Dostojewski' }
    ];

    // famous public-domain verses shown in the poetry section
    const VERSES = [
        ['الخيلُ والليلُ والبيداءُ تعرفني', 'والسيفُ والرمحُ والقرطاسُ والقلمُ', 'المتنبي'],
        ['وإني وإن كنتُ الأخيرَ زمانُهُ', 'لآتٍ بما لم تستطعْهُ الأوائلُ', 'أبو العلاء المعري'],
        ['أراكَ عصيَّ الدمعِ شيمتُكَ الصبرُ', 'أما للهوى نهيٌ عليكَ ولا أمرُ', 'أبو فراس الحمداني'],
        ['وما نيلُ المطالبِ بالتمنّي', 'ولكنْ تُؤخذُ الدنيا غِلابا', 'أحمد شوقي'],
        ['قِفا نبكِ من ذِكرى حبيبٍ ومنزلِ', 'بسِقطِ اللِّوى بينَ الدَّخولِ فحَوْمَلِ', 'امرؤ القيس']
    ];

    const ICONS = {
        nov: 'M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z M8 7h7 M8 11h5',
        poe: 'M20.2 3.8C13 4 8 9 8 15v2h2c6 0 10.5-5 10.2-13.2z M4 21l6-6',
        dra: 'M3 4h18 M5 4v16 M19 4v16 M5 8c4 0 5 4 7 4s3-4 7-4',
        phi: 'M9 18h6 M10 21h4 M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z',
        his: 'M5 21h14 M6 21V9 M10 21V9 M14 21V9 M18 21V9 M3 9l9-6 9 6z',
        sci: 'M9 3h6 M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3 M8 15h8',
        med: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 8v8 M8 12h8',
        eng: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M19 5l-2 2 M7 17l-2 2',
        mat: 'M4 7h16 M8 7v12 M16 7v10a2 2 0 0 0 2 2',
        rel: 'M12 3l2.5 6 6.5.5-5 4.3 1.6 6.4-5.6-3.5-5.6 3.5L8 13.8 3 9.5l6.5-.5z',
        pol: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M3 12h18 M12 3c3 3 3 15 0 18 M12 3c-3 3-3 15 0 18',
        chi: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M8 14s1.5 2 4 2 4-2 4-2 M9 9h.01 M15 9h.01',
        bio: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21a8 8 0 0 1 16 0',
        tra: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M15.5 8.5l-2 5-5 2 2-5z',
        psy: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M2 20a7 7 0 0 1 14 0 M17 4.5a3.5 3.5 0 0 1 0 6 M19 20a7 7 0 0 0-3-5.7',
        art: 'M12 3a9 9 0 1 0 0 18c1.5 0 2-1 1.5-2s0-2 1.5-2h2a3 3 0 0 0 3-3 9 9 0 0 0-8-11z M7.5 11h.01 M10 7h.01 M14.5 7h.01',
        dev: 'M3 20h18 M6 16l4-4 3 3 6-7 M15 8h4v4',
        hor: 'M12 3a7 7 0 0 0-7 7v10l2.3-1.6L9.7 20l2.3-1.6 2.3 1.6 2.4-1.6L19 20V10a7 7 0 0 0-7-7z M9.5 10.5h.01 M14.5 10.5h.01',
        mys: 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z M21 21l-5.6-5.6 M8 10.5h5',
        ara: 'M5 21V11a7 7 0 0 1 14 0v10z M9.5 21v-5a2.5 2.5 0 0 1 5 0v5 M12 4V2',
        gen: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
        eye: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
        cite: 'M6 17h3l2-4V7H5v6h3z M14 17h3l2-4V7h-6v6h3z',
        cal: 'M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z M4 10h16 M8 3v4 M16 3v4 M8 14h.01 M12 14h.01 M16 14h.01',
        year: 'M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z M4 10h16 M8 3v4 M16 3v4 M12 12.5l1.2 2.4 2.6.4-1.9 1.8.5 2.6-2.4-1.3-2.4 1.3.5-2.6-1.9-1.8 2.6-.4z'
    };
    const ico = (k, size) => '<svg class="ic ic-' + (ICONS[k] ? k : 'gen') + '" width="' + (size || 18) + '" height="' + (size || 18) + '" viewBox="0 0 24 24" aria-hidden="true"><path pathLength="1" d="' + (ICONS[k] || ICONS.gen) + '"/></svg>';
    ICONS.book = ICONS.nov;
    ICONS.users = ICONS.psy;
    ICONS.globe = ICONS.pol;

    const S = {
        ui: 'ar',
        cat: '',
        org: '',
        ak: '',
        au: '',
        bl: '',
        sort: 'def',
        q: '',
        items: [],
        total: 0,
        capped: false, // the server stopped counting at 10,000
        near: 0, // results found with a letter forgiven
        end: false, // the last page came back short: nothing more to load
        meta: null,
        cmap: {},
        amap: {},
        live: null,
        authAll: false,
        req: 0,
        loading: true,
        err: false
    };

    /* ---------- helpers ---------- */
    const $ = (s) => document.querySelector(s);
    const enc = encodeURIComponent;
    const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const fmt = (n) => Number(n).toLocaleString('en-US');
    const hash = (s) => { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h; };
    const lsGet = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
    const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
    // the visitor's language choice, read by the server for every page (pages.visitor_ui)
    const saveLang = (ui) => {
        document.cookie = 'warraq_lang=' + ui + '; path=/; max-age=31536000; samesite=lax' + (location.protocol === 'https:' ? '; secure' : '');
        try { localStorage.removeItem('warraq.lang'); } catch (e) {}
    };
    const tr = (k, v) => { let s = (T[S.ui] && T[S.ui][k]) || T.en[k] || k; if (v)
            for (const x in v) s = s.replace('{' + x + '}', v[x]); return s; };
    // a name kept in several languages ({ar, en, fr...}): the interface's, else the English one
    const inUi = (o) => (o && (o[S.ui] || o.en)) || '';
    const langQ = () => (S.ui === 'ar' ? '' : '?lang=' + S.ui);
    const isArabic = (s) => /[؀-ۿ]/.test(s || '');
    // links and images that come from other services: plain web addresses only (never javascript: or data:)
    const safeUrl = (u) => (/^https?:\/\//i.test(String(u || '')) ? String(u) : '#');
    const num = (n) => Number(n) || 0;

    function api(path, params) {
        const qs = new URLSearchParams();
        Object.keys(params || {}).forEach((k) => { if (params[k] !== '' && params[k] != null) qs.set(k, params[k]); });
        const url = path + (qs.toString() ? '?' + qs.toString() : '');
        return fetch(url, { headers: { Accept: 'application/json' } }).then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); });
    }
    const hue = (c) => (S.cmap[c] ? S.cmap[c].hue : 210);
    const catName = (c) => (S.cmap[c] ? inUi(S.cmap[c]) : c);

    function authName(b) {
        const a = b.ak && S.amap[b.ak];
        if (a) return S.ui === 'ar' ? a.ar : a.en;
        return S.ui === 'ar' && b.aa ? b.aa : (b.a || '');
    }
    const bookTitle = (b) => (S.ui === 'ar' ? (b.ta || b.t) : b.t);

    function langName(code) {
        try { return new Intl.DisplayNames([S.ui], { type: 'language' }).of(code) || code; } catch (e) { return code; }
    }

    /* ---------- covers: real image first, designed fallback underneath ---------- */
    const gutUrl = (gid) => 'https://www.gutenberg.org/cache/epub/' + gid + '/pg' + gid + '.cover.medium.jpg';
    const covCache = new Map();
    const covQueue = [];
    let covActive = 0;

    function pumpCov() {
        while (covActive < 3 && covQueue.length) {
            const job = covQueue.shift();
            covActive++;
            job().then(() => { covActive--;
                pumpCov(); });
        }
    }

    function openLibraryCover(el) {
        const id = +el.dataset.id;
        if (covCache.has(id)) { const u = covCache.get(id); if (u) setImg(el, u); return; }
        covQueue.push(() => {
            if (!el.isConnected) return Promise.resolve();
            return api('/api/cover/' + id).then((r) => {
                if (r.url) covCache.set(id, r.url);
                if (r.url && el.isConnected) setImg(el, r.url);
            }).catch(() => {});
        });
        pumpCov();
    }

    function setImg(el, url) { url = safeUrl(url); if (url === '#') return;
        const img = el.querySelector('.cvimg'); if (img && img.getAttribute('src') !== url) img.src = url; }

    function startCover(el) {
        el.dataset.started = '1';
        if (el.dataset.ws) return; // poems and Wikisource texts: the designed cover is the cover
        const gid = +el.dataset.gid;
        // HathiTrust refuses to serve its cover images to other sites, so those books go straight to Open Library
        if (gid) { el.dataset.stage = '1';
            setImg(el, gutUrl(gid)); } else { el.dataset.stage = '2';
            openLibraryCover(el); }
    }

    function coverFailed(el) {
        if (el.dataset.stage === '1') { el.dataset.stage = '2';
            openLibraryCover(el); }
    }
    const io = 'IntersectionObserver' in window ? new IntersectionObserver((entries) => {
        entries.forEach((e) => { if (e.isIntersecting) { io.unobserve(e.target);
                startCover(e.target); } });
    }, { rootMargin: '400px' }) : null;

    function watchCovers(root) {
        root.querySelectorAll('.cover[data-id]:not([data-started])').forEach((el) => { if (io) io.observe(el);
            else startCover(el); });
    }
    // img load/error do not bubble: listen in the capture phase
    document.addEventListener('load', (e) => {
        const img = e.target;
        if (!img.classList || !img.classList.contains('cvimg')) return;
        if (img.naturalWidth < 40 || img.naturalHeight < 40) { coverFailed(img.parentElement); return; } // placeholder pixel
        img.classList.add('ok');
    }, true);
    document.addEventListener('error', (e) => {
        const img = e.target;
        if (img.classList && img.classList.contains('cvimg')) coverFailed(img.parentElement);
    }, true);

    function coverHTML(b, extra) {
        const title = bookTitle(b),
            au = authName(b),
            h = hue(b.c);
        const ar = isArabic(title);
        return '<a class="cover' + (title.length > 36 ? ' cv-long' : '') + '" style="--h:' + num(h) + '" data-v="' + (num(b.id) % 3) + '" href="/book/' + num(b.id) + '"' +
            ' data-id="' + num(b.id) + '" data-gid="' + (num(b.gid) || '') + '" data-hid="' + esc(b.hid || '') + '"' + (b.ws && !b.gid && !b.hid ? ' data-ws="1"' : '') + ' aria-label="' + esc(title + (au ? ' — ' + au : '')) + '">' +
            '<span class="cv-fb"><span class="cv-deco"></span><span class="cv-cat">' + esc(catName(b.c)) + '</span>' +
            '<span class="cv-title' + (ar ? ' ar' : '') + '">' + esc(title) + '</span><span class="cv-auth">' + esc(au || ' ') + '</span></span>' +
            '<img class="cvimg" alt="" decoding="async" referrerpolicy="no-referrer"></a>';
    }

    /* ---------- data ---------- */
    function loadMeta() {
        return api('/api/meta').then((m) => {
            S.meta = m;
            S.cmap = {};
            S.amap = {};
            m.categories.forEach((c) => { S.cmap[c.key] = c; });
            m.authors.forEach((a) => { S.amap[a.key] = a; });
        });
    }
    const params = (append) => ({
        q: S.q.trim(),
        cat: S.cat,
        org: S.org,
        ak: S.ak,
        au: S.au,
        bl: S.bl,
        sort: S.sort,
        ui: S.ui,
        offset: append ? S.items.length : 0,
        limit: PAGE
    });

    function loadBooks(append) {
        const id = ++S.req;
        S.loading = true;
        S.err = false;
        renderResults(append);
        return api('/api/books', params(append)).then((r) => {
            if (id !== S.req) return;
            S.items = append ? S.items.concat(r.items) : r.items;
            if (r.total != null) { S.total = r.total;
                S.capped = !!r.capped;
                S.poems = r.poems || 0;
                S.near = r.near || 0; }
            S.end = r.items.length < PAGE;
            S.loading = false;
            renderResults(append);
        }).catch(() => {
            if (id !== S.req) return;
            S.loading = false;
            S.err = true;
            renderResults(append);
        });
    }
    let debounceT;
    const reloadSoon = () => { clearTimeout(debounceT);
        debounceT = setTimeout(() => loadBooks(false), 250); };
    const resetPaging = () => { S.items = [];
        S.total = 0;
        S.capped = false;
        S.poems = 0;
        S.near = 0;
        S.end = false; };

    /* ---------- links ---------- */
    function links(b) {
        const a = b.ak && S.amap[b.ak];
        const last = a ? a.en.split(' ').slice(-1)[0] : (b.a || '').split(' ').slice(-1)[0];
        const qs = enc((b.t + ' ' + last).trim());
        const arch = 'https://archive.org/search?query=' + qs;
        const ol = 'https://openlibrary.org/search?mode=everything&has_fulltext=true&q=' + qs;
        // modern Arabic books: free to read on Safahat (Hindawi), or a catalogue record on Open Library
        if (b.x && b.k === 5) { const u = 'https://www.safahat.org/books/' + enc(b.x) + '/'; return { main: u, read: true, list: [[tr('src_saf'), u]] }; }
        if (b.x && b.k === 4) { const u = 'https://openlibrary.org/works/' + enc(b.x); return { main: u, read: false, label: tr('view'), list: [['Open Library', u]] }; }
        if (b.gid) {
            const read = 'https://www.gutenberg.org/cache/epub/' + b.gid + '/pg' + b.gid + '-images.html';
            return { main: read, read: true, list: [
                    [tr('l_page'), 'https://www.gutenberg.org/ebooks/' + b.gid],
                    [tr('l_arch'), arch]
                ] };
        }
        if (b.hid) {
            const read = 'https://babel.hathitrust.org/cgi/pt?id=' + enc(b.hid);
            return { main: read, read: true, list: [
                    [tr('l_ht'), 'https://babel.hathitrust.org/cgi/ls?q1=' + enc(b.t) + '&lmt=ft'],
                    [tr('l_arch'), arch]
                ] };
        }
        if (b.ws) {
            const page = 'https://ar.wikisource.org/wiki/' + enc(b.ws.replace(/ /g, '_'));
            return { main: page, read: true, list: b.c === 'poe' ? [] : [
                    [tr('l_arch'), 'https://archive.org/search?query=' + enc(b.ta || b.t)]
                ] };
        }
        if (b.o === 'a') {
            const ws = 'https://ar.wikisource.org/w/index.php?search=' + enc(b.ta || b.t);
            return { main: ws, list: [
                    [tr('l_arch'), 'https://archive.org/search?query=' + enc(b.ta || b.t)],
                    [tr('l_ol'), ol]
                ] };
        }
        const gut = 'https://www.gutenberg.org/ebooks/search/?query=' + qs;
        return { main: gut, list: [
                [tr('l_arch'), arch],
                [tr('l_ol'), ol]
            ] };
    }

    /* ---------- render ---------- */
    function applyStatic() {
        document.documentElement.lang = S.ui;
        document.documentElement.dir = S.ui === 'ar' ? 'rtl' : 'ltr';
        document.querySelectorAll('[data-i]').forEach((e) => { e.textContent = tr(e.dataset.i); });
        document.querySelectorAll('[data-iph]').forEach((e) => { e.placeholder = tr(e.dataset.iph);
            e.setAttribute('aria-label', tr(e.dataset.iph)); });
        document.querySelectorAll('[data-iarl]').forEach((e) => { e.setAttribute('aria-label', tr(e.dataset.iarl)); });
        document.querySelectorAll('[data-lhref]').forEach((e) => { e.href = e.dataset.lhref + langQ(); });
        $('#langCur').textContent = LANG_SHORT[S.ui];
        document.querySelectorAll('#langList [data-ui]').forEach((e) => { if (e.dataset.ui === S.ui) e.setAttribute('aria-current', 'true');
            else e.removeAttribute('aria-current'); });
        $('#filtBtn').textContent = tr('filters');
        document.querySelectorAll('[data-srv-lang]').forEach((e) => { e.hidden = e.dataset.srvLang !== S.ui; });
    }

    function renderHero() {
        $('#quick').innerHTML = '<span>' + esc(tr('quick')) + '</span>' + QUICK.map((c) => '<button class="qchip" type="button" data-q="' + esc(c.q) + '">' + esc(inUi(c)) + '</button>').join('');
        if (!S.meta) { $('#stats').innerHTML = ''; return; }
        $('#stats').innerHTML = [
                [S.meta.total, 'st_books', 'book'],
                [S.meta.author_total, 'st_auth', 'bio'],
                [S.meta.lang_total || S.meta.languages.length, 'st_lang', 'globe']
            ]
            .map((x) => '<div class="stat"><span class="st-ic">' + ico(x[2], 22) + '</span><span><b data-n="' + num(x[0]) + '">' + fmt(num(x[0])) + '</b><span>' + esc(tr(x[1])) + '</span></span></div>').join('');
        countUp($('#stats'));
    }

    // numbers roll up from zero the first time they appear
    function countUp(root) {
        if (root.dataset.counted) return;
        root.dataset.counted = '1';
        const els = root.querySelectorAll('b[data-n]'),
            t0 = performance.now(),
            dur = 1400;
        if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) {
            els.forEach((el) => { el.textContent = fmt(+el.dataset.n); });
            return;
        }
        const step = (t) => {
            const k = Math.min(1, (t - t0) / dur),
                e = 1 - Math.pow(1 - k, 3);
            els.forEach((el) => { el.textContent = fmt(Math.round(+el.dataset.n * e)); });
            if (k < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    }

    // visitor numbers at the bottom of the page: today, this month, this year
    const visitsIO = 'IntersectionObserver' in window ? new IntersectionObserver((es) => {
        es.forEach((e) => { if (e.isIntersecting && e.target.querySelector('b[data-n]')) { visitsIO.unobserve(e.target);
                countUp(e.target); } });
    }) : null;

    function renderLive() {
        const el = $('#visits');
        if (!el) return;
        const l = S.live;
        el.hidden = !l;
        if (!l) return;
        const items = [
            [l.visitors_today, 'v_today', 'eye'],
            [l.visitors_month, 'v_month', 'cal'],
            [l.visitors_year, 'v_year', 'year']
        ];
        el.innerHTML = '<h3>' + esc(tr('v_h')) + '</h3><div class="fv-row">' + items.map((x) =>
            '<div class="fv"><span class="fv-ic">' + ico(x[2], 22) + '</span><span><b data-n="' + num(x[0]) + '">' + fmt(el.dataset.counted ? num(x[0]) : 0) + '</b><small>' + esc(tr(x[1])) + '</small></span></div>').join('') + '</div>';
        if (el.dataset.counted) return;
        if (visitsIO) visitsIO.observe(el);
        else countUp(el);
    }

    function renderCats() {
        const el = $('#catGrid');
        if (!el || !S.meta) return;
        el.innerHTML = S.meta.categories.filter((c) => c.count + (c.poems || 0) > 0).map((c, i) =>
            '<a class="cc" href="/category/' + esc(c.key) + langQ() + '" data-cat="' + esc(c.key) + '" style="--h:' + num(c.hue) + ';--i:' + i + '"><span class="cci">' + ico(c.key, 26) + '</span><b>' + esc(inUi(c)) + '</b><small>' + esc(c.count ? tr('n_books', { n: fmt(c.count) }) + (c.poems ? ' · ' + tr('n_poems', { n: fmt(c.poems) }) : '') : tr('n_poems', { n: fmt(c.poems) })) + '</small></a>').join('');
        renderFootCats();
    }

    function renderFootCats() {
        const el = $('#footCats');
        if (!el || !S.meta) return;
        el.innerHTML = S.meta.categories.map((c) => '<a href="/category/' + esc(c.key) + langQ() + '">' + esc(inUi(c)) + '</a>').join('');
    }

    function renderPopular() {
        const sec = $('#popular');
        if (!sec) return;
        const l = S.live,
            books = (l && l.top_books) || [],
            qs = (l && l.top_searches) || [];
        sec.hidden = !(books.length || qs.length);
        $('#popBooks').innerHTML = books.length ? '<h3>' + esc(tr('pop_h')) + '</h3><div class="shelfrow">' + books.map((b) =>
            '<div class="sh">' + coverHTML(b) + '<a class="sh-t" href="/book/' + num(b.id) + '">' + esc(bookTitle(b)) + '</a><span class="sh-v">' + ico('eye', 14) + ' ' + fmt(b.views) + '</span></div>').join('') + '</div>' : '';
        $('#popSearch').innerHTML = qs.length ? '<h3>' + esc(tr('pop_s')) + '</h3><div class="qrow">' + qs.map((q) => '<button class="qchip" type="button" data-q="' + esc(q) + '">' + esc(q) + '</button>').join('') + '</div>' : '';
        watchCovers(sec);
    }

    function renderPoets() {
        const sec = $('#poetry');
        const m = S.meta;
        if (!sec || !m || !m.poets || !m.poets.length) return;
        sec.hidden = false;
        $('#poemsLead').textContent = tr('poems_lead', { n: fmt(m.poem_total) });
        $('#poets').innerHTML = m.poets.slice(0, 12).map((p, i) => {
            const nm = S.ui === 'ar' ? p.ar : (p.en || p.ar),
                last = p.ar.trim().split(/\s+/).pop().replace(/^ال/, ''), // the name people know: المعري، الرومي، البحتري
                ini = Array.from(last.replace(/[^\p{L}]/gu, '') || '?')[0];
            return '<button class="poet" type="button" data-au="' + esc(p.ar) + '" style="--i:' + i + '"><i class="pm" aria-hidden="true">' + esc(ini) + '</i><span><b>' + esc(nm) + '</b><small>' + esc(tr('poems_n', { n: fmt(p.count) })) + '</small></span></button>';
        }).join('');
    }

    let verseI = 0;

    function showVerse() {
        const el = $('#verse');
        if (!el) return;
        const v = VERSES[verseI % VERSES.length];
        el.classList.add('out');
        setTimeout(() => {
            el.innerHTML = '<span>' + esc(v[0]) + '</span><span>' + esc(v[1]) + '</span><cite>— ' + esc(v[2]) + '</cite>';
            el.classList.remove('out');
        }, el.textContent ? 450 : 0);
        verseI++;
    }

    function loadLive() {
        return api('/api/stats').then((r) => { S.live = r;
            renderLive();
            renderPopular(); }).catch(() => {});
    }

    function renderFan(items) {
        const el = $('#fan');
        el.innerHTML = items.slice(0, 5).map((b) => coverHTML(b)).join('');
        watchCovers(el);
    }

    function renderSide() {
        if (!S.meta) return;
        const total = S.meta.total;
        $('#catList').innerHTML =
            '<button class="catitem" type="button" data-cat="" aria-pressed="' + (S.cat === '') + '"><i class="ci" style="--h:215">' + ico('gen', 15) + '</i><span>' + esc(tr('all_cats')) + '</span><small>' + fmt(total) + '</small></button>' +
            S.meta.categories.map((c) => '<button class="catitem" type="button" data-cat="' + esc(c.key) + '" aria-pressed="' + (S.cat === c.key) + '"><i class="ci" style="--h:' + num(c.hue) + '">' + ico(c.key, 15) + '</i><span>' + esc(inUi(c)) + '</span><small>' + fmt(c.count) + '</small></button>').join('');
        $('#fLang').innerHTML = '<option value="">' + esc(tr('all')) + '</option>' + S.meta.languages.map((l) => '<option value="' + esc(l.code) + '">' + esc(langName(l.code)) + ' (' + fmt(l.count) + ')</option>').join('');
        $('#fLang').value = S.bl;
        $('#fOrg').innerHTML = '<option value="">' + esc(tr('all')) + '</option><option value="a">' + esc(tr('org_a')) + '</option><option value="w">' + esc(tr('org_w')) + '</option>';
        $('#fOrg').value = S.org;
        $('#fSort').innerHTML = '<option value="def">' + esc(tr('sort_def')) + '</option><option value="t">' + esc(tr('sort_t')) + '</option><option value="a">' + esc(tr('sort_a')) + '</option>';
        $('#fSort').value = S.sort;
    }

    function card(b) {
        const L = links(b),
            title = bookTitle(b),
            au = authName(b);
        return '<article class="book">' + coverHTML(b) +
            '<div class="meta"><h3 class="ttl"><a class="ttl-a" href="/book/' + num(b.id) + '">' + esc(title) + '</a></h3>' + (au ? '<p class="by">' + esc(au) + '</p>' : '') +
            '<div class="row"><a class="btn" href="' + esc(safeUrl(L.main)) + '" target="_blank" rel="noopener">' + esc(L.label || tr(L.read ? 'read' : 'find')) + '</a>' +
            L.list.map((x) => '<a class="lnk" href="' + esc(safeUrl(x[1])) + '" target="_blank" rel="noopener">' + esc(x[0]) + '</a>').join('') + '</div></div></article>';
    }
    let rendered = 0;

    // The AdSense in-feed unit among the results (the server names it in a meta tag, only where ads are shown):
    // one per search, made once and put back in place when the same list is drawn again, so that switching the
    // language never reloads an ad on its own.
    const FEED = (() => { const m = document.querySelector('meta[name="warraq-infeed"]');
        const p = m ? (m.getAttribute('content') || '').split('|') : [];
        return p.length === 3 && p[0] && p[1] ? { client: p[0], slot: p[1], layout: p[2] } : null; })();
    const FEED_AT = 8; // after the 8th book, in a list of 12 or more
    let feedAd = null,
        feedKey = '';

    function placeFeedAd(grid) {
        if (!FEED || S.loading || S.err || S.items.length < FEED_AT + 4) return;
        const at = grid.children[FEED_AT - 1];
        if (!at) return;
        const key = [S.q.trim(), S.cat, S.org, S.ak, S.au, S.bl, S.sort].join('\u0001');
        const fresh = !feedAd || key !== feedKey;
        if (fresh) {
            feedAd = document.createElement('div');
            feedAd.className = 'infeed';
            feedKey = key;
        }
        feedAd.setAttribute('aria-label', tr('ad'));
        if (fresh) feedAd.innerHTML = '<span class="ad-l">' + esc(tr('ad')) + '</span><ins class="adsbygoogle" style="display:block" data-ad-format="fluid" data-ad-layout-key="' + esc(FEED.layout) + '" data-ad-client="' + esc(FEED.client) + '" data-ad-slot="' + esc(FEED.slot) + '"></ins>';
        else feedAd.querySelector('.ad-l').textContent = tr('ad');
        at.after(feedAd);
        if (fresh) try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) {}
    }

    function renderResults(append) {
        const chips = [];
        if (S.au) chips.push('<button class="chip" type="button" data-clear="au">' + esc(S.au) + ' <span aria-hidden="true">×</span></button>');
        if (S.ak && S.amap[S.ak]) chips.push('<button class="chip" type="button" data-clear="ak">' + esc(S.ui === 'ar' ? S.amap[S.ak].ar : S.amap[S.ak].en) + ' <span aria-hidden="true">×</span></button>');
        if (S.q) chips.push('<button class="chip" type="button" data-clear="q">«' + esc(S.q) + '» <span aria-hidden="true">×</span></button>');
        if (S.cat && S.cmap[S.cat]) chips.push('<button class="chip" type="button" data-clear="cat">' + esc(catName(S.cat)) + ' <span aria-hidden="true">×</span></button>');
        // near: books found by forgiving a letter (the search found almost nothing as typed)
        $('#count').textContent = S.loading && !S.items.length ? tr('loading') : S.capped ? tr('results_more', { n: fmt(S.total) }) :
            S.near && S.near >= S.total ? tr('near_all', { q: S.q.trim(), n: fmt(S.total) }) :
            (S.poems >= S.total && S.total ? tr('n_poems', { n: fmt(S.total) }) :
            S.poems ? tr('results_mix', { b: fmt(S.total - S.poems), p: fmt(S.poems) }) : tr('results', { n: fmt(S.total) })) +
            (S.near ? ' · ' + tr('near_some', { n: fmt(S.near) }) : '');
        $('#chips').innerHTML = chips.join('');

        const bq = $('#beyond');
        if (S.q.trim()) {
            const e = enc(S.q.trim());
            const ls = [
                ['Project Gutenberg', 'https://www.gutenberg.org/ebooks/search/?query=' + e],
                ['Internet Archive', 'https://archive.org/search?query=' + e],
                ['Open Library', 'https://openlibrary.org/search?mode=everything&has_fulltext=true&q=' + e],
                ['Wikisource (ar)', 'https://ar.wikisource.org/w/index.php?search=' + e],
                ['Wikisource (en)', 'https://en.wikisource.org/w/index.php?search=' + e]
            ];
            bq.innerHTML = '<div class="beyond"><p>' + esc(tr('beyond', { q: S.q.trim() })) + '</p><div>' + ls.map((x) => '<a href="' + esc(x[1]) + '" target="_blank" rel="noopener">' + esc(x[0]) + '</a>').join('') + '</div></div>';
        } else bq.innerHTML = '';

        const grid = $('#grid');
        if (!append) { grid.innerHTML = S.items.map(card).join('');
            rendered = S.items.length;
            placeFeedAd(grid); } else if (S.items.length > rendered) { grid.insertAdjacentHTML('beforeend', S.items.slice(rendered).map(card).join(''));
            rendered = S.items.length; }
        watchCovers(grid);

        let msg = '';
        if (S.err) msg = '<div class="err" role="alert">' + esc(tr('err')) + '<button id="retryBtn" type="button">' + esc(tr('retry')) + '</button></div>';
        else if (S.loading) msg = '<p class="state loading">' + esc(tr('loading')) + '</p>';
        else if (!S.items.length && [S.q.trim(), S.cat, S.ak, S.au, S.bl, S.org].filter(Boolean).length >= 2) msg = '<div class="state empty"><p>' + esc(tr('none_f')) + '</p><button class="more" id="clearFBtn" type="button">' + esc(tr('clear_f')) + '</button></div>';
        else if (!S.items.length) msg = '<p class="state">' + esc(tr('none')) + '</p>';
        $('#state').innerHTML = msg;
        const mb = $('#moreBtn');
        mb.hidden = S.loading || S.err || !hasMore();
        mb.textContent = S.capped ? tr('more') : tr('more') + ' (' + fmt(Math.max(S.total - S.items.length, 0)) + ')';
    }

    function hasMore() { return !S.end && (S.capped || S.items.length < S.total); }

    function renderAuthors() {
        if (!S.meta) return;
        const keys = S.meta.authors,
            list = S.authAll ? keys : keys.slice(0, 16);
        const av = $('#avs');
        av.classList.toggle('all', S.authAll);
        av.innerHTML = list.map((a) => {
            const nm = S.ui === 'ar' ? a.ar : a.en,
                ini = Array.from(nm.replace(/[^\p{L}]/gu, '') || '?')[0];
            return '<a class="av" href="/author/' + enc(a.key) + langQ() + '" data-ak="' + esc(a.key) + '"><span class="mono" style="--h:' + num(hue(a.cat)) + '" aria-hidden="true">' + esc(ini) + '</span><b>' + esc(nm) + '</b><small>' + esc(tr('books_n', { n: fmt(a.count) })) + '</small></a>';
        }).join('');
        const m = $('#authMore');
        m.hidden = keys.length <= 16;
        m.textContent = S.authAll ? tr('show_less') : tr('show_all', { n: keys.length });
    }

    /* ---------- research ---------- */
    const DESKS = [
        { domain: 'med', input: '#rqMed', topics: '#topicsMed', srcs: '#srcsMed', list: '#papersMed', def: 'cardiology', data: null, papers: null, req: 0, timer: 0 },
        { domain: 'eng', input: '#rqEng', topics: '#topicsEng', srcs: '#srcsEng', list: '#papersEng', def: 'control systems', data: null, papers: null, req: 0, timer: 0 }
    ];

    function renderDesk(d) {
        if (!d.data) { $(d.topics).innerHTML = '';
            $(d.srcs).innerHTML = ''; return; }
        $(d.topics).innerHTML = d.data.topics.map((t) => '<button class="topic" type="button" data-topic="' + esc(t.en) + '">' + esc(inUi(t)) + '</button>').join('');
        $(d.srcs).innerHTML = d.data.sources.map((s) => '<a class="src" href="' + esc(safeUrl(s.url)) + '" target="_blank" rel="noopener" title="' + esc(inUi(s)) + '"><b>' + esc(s.name) + '</b><em aria-hidden="true">' + tr('r_open') + '</em></a>').join('');
        renderPapers(d);
    }

    // real open-access papers on the topic, straight from OpenAlex through our server
    function renderPapers(d) {
        const el = $(d.list);
        if (!el) return;
        const p = d.papers;
        if (!p) {
            el.innerHTML = '<p class="p-msg loading">' + esc(tr('p_loading')) + '</p>' + '<div class="p-skel"></div>'.repeat(3);
            return;
        }
        if (p.error) { el.innerHTML = '<p class="p-msg">' + esc(tr('p_err')) + '</p>'; return; }
        if (!p.items.length) { el.innerHTML = '<p class="p-msg">' + esc(tr('p_none')) + '</p>'; return; }
        el.innerHTML = '<p class="p-head">' + esc(tr('p_found', { n: fmt(p.total), q: p.query })) + '</p>' + p.items.map((x, i) =>
            '<article class="paper" style="--i:' + i + '"><a class="p-t" dir="auto" href="' + esc(safeUrl(x.url)) + '" target="_blank" rel="noopener noreferrer">' + esc(x.title) + '</a>' +
            '<p class="p-m" dir="auto">' + [x.authors, x.venue, x.year].filter(Boolean).map(esc).join(' · ') + '</p>' +
            '<div class="p-f"><a class="btn" href="' + esc(safeUrl(x.url)) + '" target="_blank" rel="noopener noreferrer">' + esc(tr(x.pdf ? 'p_pdf' : 'p_read')) + '</a>' +
            (x.cited ? '<span class="p-c">' + ico('cite', 14) + esc(tr('p_cited', { n: fmt(x.cited) })) + '</span>' : '') + '</div></article>').join('');
    }

    function loadDesk(d) {
        const id = ++d.req,
            q = $(d.input).value.trim();
        d.papers = null;
        renderPapers(d);
        api('/api/research', { domain: d.domain, q: q }).then((r) => { if (id === d.req) { d.data = r;
                renderDesk(d); } }).catch(() => {});
        api('/api/papers', { domain: d.domain, q: q }).then((r) => { if (id === d.req) { d.papers = r;
                renderPapers(d); } }).catch(() => { if (id === d.req) { d.papers = { items: [], error: true };
                renderPapers(d); } });
    }

    /* ---------- events ---------- */
    function applyFilters() { resetPaging();
        renderSide();
        loadBooks(false); }

    function toBrowse() {
        const rm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
        $('#browse').scrollIntoView({ behavior: rm ? 'auto' : 'smooth', block: 'start' });
    }
    let lastLogged = '',
        logT = 0;

    function logSearch(q) {
        q = (q || '').trim();
        if (q.length < 2 || q === lastLogged) return;
        lastLogged = q;
        fetch('/api/track/search?q=' + enc(q), { method: 'POST' }).catch(() => {});
    }

    function setQuery(q) { logSearch(q);
        freshStart(true);
        S.q = q;
        $('#q').value = q;
        applyFilters();
        toBrowse(); }

    // the language menu: a plain click switches the page in place (its links work without the script too)
    const langMenu = $('#langMenu');
    $('#langList').addEventListener('click', (e) => {
        const a = e.target.closest('[data-ui]');
        if (!a || !inPage(e)) return;
        e.preventDefault();
        langMenu.open = false;
        setLang(a.dataset.ui);
    });
    document.addEventListener('click', (e) => { if (langMenu.open && !langMenu.contains(e.target)) langMenu.open = false; });
    langMenu.addEventListener('keydown', (e) => { if (e.key === 'Escape' && langMenu.open) { langMenu.open = false;
            $('#langBtn').focus(); } });

    function setLang(ui) {
        if (ui === S.ui || LANGS.indexOf(ui) < 0) return;
        S.ui = ui;
        saveLang(S.ui);
        try { // an address that names a language goes on naming the one shown, so a reload keeps it
            const u = new URL(location.href);
            if (u.searchParams.has('lang')) {
                if (ui === 'ar') u.searchParams.delete('lang');
                else u.searchParams.set('lang', ui);
                history.replaceState(history.state, '', u.pathname + u.search + u.hash);
            }
        } catch (e) {}
        applyStatic();
        renderHero();
        renderSide();
        renderAuthors();
        renderLive();
        renderCats();
        renderPoets();
        renderPopular();
        DESKS.forEach(renderDesk);
        const grid = $('#grid');
        grid.innerHTML = '';
        if (S.sort !== 'def') loadBooks(false);
        else renderResults(false);
    }
    $('#themeBtn').addEventListener('click', () => {
        const cur = document.documentElement.getAttribute('data-theme') || 'light'; // light by default, dark only on request
        const nx = cur === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', nx);
        lsSet('warraq.theme', nx);
    });
    const _t = lsGet('warraq.theme');
    if (_t === 'dark' || _t === 'light') document.documentElement.setAttribute('data-theme', _t);
    // The language: ?lang= when the address has it, otherwise the one the server wrote in <html lang>: the
    // visitor's saved choice (a cookie, set by the language button), else their browser's language. Crawlers
    // always get Arabic on "/", so search engines see the Arabic page there as before.
    let _l = '';
    try { const ql = new URLSearchParams(location.search).get('lang'); if (LANGS.indexOf(ql) >= 0) _l = ql; } catch (e) {}
    const _old = lsGet('warraq.lang'); // where the choice used to be kept: carried over to the cookie once
    if ((_old === 'en' || _old === 'ar') && !/(?:^|;\s*)warraq_lang=/.test(document.cookie)) {
        saveLang(_old);
        if (!_l) _l = _old;
    }
    _l = _l || document.documentElement.lang;
    S.ui = LANGS.indexOf(_l) >= 0 ? _l : 'ar';

    // a fresh choice (category card, quick search, new search) starts from the whole library
    function freshStart(keepQuery) {
        S.ak = '';
        S.au = '';
        S.bl = '';
        S.org = '';
        S.cat = '';
        if (!keepQuery) { S.q = '';
            $('#q').value = ''; }
    }

    $('#q').addEventListener('input', (e) => {
        if (!S.q.trim() && e.target.value.trim()) { freshStart(true); // a new search looks in every category
            renderSide(); }
        S.q = e.target.value;
        resetPaging();
        reloadSoon();
        clearTimeout(logT);
        logT = setTimeout(() => logSearch(S.q), 1600); });
    $('#searchForm').addEventListener('submit', (e) => { e.preventDefault();
        S.q = $('#q').value;
        logSearch(S.q);
        applyFilters();
        toBrowse(); });
    $('#quick').addEventListener('click', (e) => { const b = e.target.closest('.qchip'); if (b) setQuery(b.dataset.q); });
    // a plain click filters in place; ctrl/cmd/middle click still opens the category's own page
    const inPage = (e) => !(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button > 0);
    $('#catGrid').addEventListener('click', (e) => { const b = e.target.closest('.cc'); if (!b || !inPage(e)) return;
        e.preventDefault();
        freshStart(false);
        S.cat = b.dataset.cat;
        applyFilters();
        toBrowse(); });
    $('#popSearch').addEventListener('click', (e) => { const b = e.target.closest('.qchip'); if (b) setQuery(b.dataset.q); });
    $('#catList').addEventListener('click', (e) => { const b = e.target.closest('.catitem'); if (!b) return;
        S.ak = ''; // the sidebar narrows the current search, but a category is not a single person's shelf
        S.au = '';
        S.cat = b.dataset.cat;
        applyFilters(); });
    $('#fLang').addEventListener('change', (e) => { S.bl = e.target.value;
        applyFilters(); });
    $('#fOrg').addEventListener('change', (e) => { S.org = e.target.value;
        applyFilters(); });
    $('#fSort').addEventListener('change', (e) => { S.sort = e.target.value;
        applyFilters(); });
    $('#clearBtn').addEventListener('click', () => { S.cat = '';
        S.org = '';
        S.ak = '';
        S.au = '';
        S.bl = '';
        S.q = '';
        S.sort = 'def';
        $('#q').value = '';
        applyFilters(); });
    $('#chips').addEventListener('click', (e) => {
        const b = e.target.closest('[data-clear]');
        if (!b) return;
        const k = b.dataset.clear;
        if (k === 'q') { S.q = '';
            $('#q').value = ''; } else S[k] = '';
        applyFilters();
    });
    $('#filtBtn').addEventListener('click', () => { const s = $('#side'); const open = s.classList.toggle('open');
        $('#filtBtn').setAttribute('aria-expanded', String(open)); });
    $('#moreBtn').addEventListener('click', () => loadBooks(true));
    $('#state').addEventListener('click', (e) => {
        if (e.target.id === 'retryBtn') { if (S.meta) loadBooks(S.items.length > 0);
            else init(); }
        if (e.target.id === 'clearFBtn') { freshStart(false);
            applyFilters(); }
    });
    $('#poets').addEventListener('click', (e) => {
        const b = e.target.closest('.poet');
        if (!b) return;
        S.au = b.dataset.au;
        S.ak = '';
        S.cat = 'poe';
        S.q = '';
        $('#q').value = '';
        applyFilters();
        toBrowse();
    });
    $('#avs').addEventListener('click', (e) => {
        const b = e.target.closest('.av');
        if (!b || !inPage(e)) return;
        e.preventDefault();
        S.au = '';
        S.ak = b.dataset.ak;
        S.cat = '';
        S.q = '';
        $('#q').value = '';
        applyFilters();
        toBrowse();
    });
    $('#authMore').addEventListener('click', () => { S.authAll = !S.authAll;
        renderAuthors(); });
    DESKS.forEach((d) => {
        $(d.input).addEventListener('input', () => { clearTimeout(d.timer);
            d.timer = setTimeout(() => loadDesk(d), 300); });
        $(d.topics).addEventListener('click', (e) => { const b = e.target.closest('.topic'); if (!b) return;
            $(d.input).value = b.dataset.topic;
            loadDesk(d); });
    });
    if ('IntersectionObserver' in window) {
        new IntersectionObserver((es) => {
            if (es[0].isIntersecting && S.meta && !S.loading && !S.err && S.items.length && S.items.length < AUTO_MAX && hasMore()) loadBooks(true);
        }, { rootMargin: '700px' }).observe($('#sentinel'));
    }

    /* ---------- scroll-in animations ---------- */
    const revealIO = 'IntersectionObserver' in window ? new IntersectionObserver((es) => {
        es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in');
                revealIO.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -12% 0px' }) : null;
    document.querySelectorAll('.reveal').forEach((el) => { if (revealIO) revealIO.observe(el);
        else el.classList.add('in'); });

    /* ---------- start ---------- */
    function init() {
        try { // links from book pages: /?cat=nov  /?ak=jane-austen  /?q=...
            const sp = new URLSearchParams(location.search);
            if (sp.get('q')) { S.q = sp.get('q');
                $('#q').value = S.q; }
            if (sp.get('cat')) S.cat = sp.get('cat');
            if (sp.get('ak')) S.ak = sp.get('ak');
        } catch (e) {}
        S.err = false;
        applyStatic();
        renderHero();
        renderResults(false);
        fetch('/api/hit', { method: 'POST' }).catch(() => {}).then(loadLive); // counts the visit, then shows live numbers
        loadMeta().then(() => {
            applyStatic();
            renderHero();
            renderSide();
            renderAuthors();
            renderCats();
            renderPoets();
            showVerse();
            setInterval(showVerse, 7000);
            loadBooks(false);
            DESKS.forEach(loadDesk);
            api('/api/shelf', { count: 5 }).then((r) => renderFan(r.items)).catch(() => {});
        }).catch(() => { S.loading = false;
            S.err = true;
            renderResults(false); });
    }
    init();
})();