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
            legal2: 'حالة الملك العام تختلف من بلد لآخر (مشروع غوتنبرغ يتبع القانون الأمريكي). تحقق من قانون بلدك قبل إعادة النشر.'
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
            legal2: 'Public-domain status differs by country (Project Gutenberg follows US law). Check your local law before republishing.'
        }
    };

    const QUICK = [
        { q: 'المتنبي', ar: 'المتنبي', en: 'Al-Mutanabbi' },
        { q: 'جبران', ar: 'جبران', en: 'Gibran' },
        { q: 'ابن سينا', ar: 'ابن سينا', en: 'Avicenna' },
        { q: 'ألف ليلة', ar: 'ألف ليلة وليلة', en: 'Arabian Nights' },
        { q: 'shakespeare', ar: 'شكسبير', en: 'Shakespeare' },
        { q: 'dostoevsky', ar: 'دوستويفسكي', en: 'Dostoevsky' }
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
    const tr = (k, v) => { let s = (T[S.ui] && T[S.ui][k]) || k; if (v)
            for (const x in v) s = s.replace('{' + x + '}', v[x]); return s; };
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
    const catName = (c) => (S.cmap[c] ? S.cmap[c][S.ui] : c);

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
                S.poems = r.poems || 0; }
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
        document.querySelectorAll('[data-lhref]').forEach((e) => { e.href = e.dataset.lhref + (S.ui === 'en' ? '?lang=en' : ''); });
        $('#langBtn').textContent = S.ui === 'ar' ? 'EN' : 'ع';
        $('#langBtn').setAttribute('aria-label', S.ui === 'ar' ? 'English' : 'العربية');
        $('#filtBtn').textContent = tr('filters');
    }

    function renderHero() {
        $('#quick').innerHTML = '<span>' + esc(tr('quick')) + '</span>' + QUICK.map((c) => '<button class="qchip" type="button" data-q="' + esc(c.q) + '">' + esc(c[S.ui]) + '</button>').join('');
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
            '<a class="cc" href="/category/' + esc(c.key) + (S.ui === 'en' ? '?lang=en' : '') + '" data-cat="' + esc(c.key) + '" style="--h:' + num(c.hue) + ';--i:' + i + '"><span class="cci">' + ico(c.key, 26) + '</span><b>' + esc(c[S.ui]) + '</b><small>' + esc(c.count ? tr('n_books', { n: fmt(c.count) }) + (c.poems ? ' · ' + tr('n_poems', { n: fmt(c.poems) }) : '') : tr('n_poems', { n: fmt(c.poems) })) + '</small></a>').join('');
        renderFootCats();
    }

    function renderFootCats() {
        const el = $('#footCats');
        if (!el || !S.meta) return;
        el.innerHTML = S.meta.categories.map((c) => '<a href="/category/' + esc(c.key) + (S.ui === 'en' ? '?lang=en' : '') + '">' + esc(c[S.ui]) + '</a>').join('');
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
            S.meta.categories.map((c) => '<button class="catitem" type="button" data-cat="' + esc(c.key) + '" aria-pressed="' + (S.cat === c.key) + '"><i class="ci" style="--h:' + num(c.hue) + '">' + ico(c.key, 15) + '</i><span>' + esc(c[S.ui]) + '</span><small>' + fmt(c.count) + '</small></button>').join('');
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

    function renderResults(append) {
        const chips = [];
        if (S.au) chips.push('<button class="chip" type="button" data-clear="au">' + esc(S.au) + ' <span aria-hidden="true">×</span></button>');
        if (S.ak && S.amap[S.ak]) chips.push('<button class="chip" type="button" data-clear="ak">' + esc(S.ui === 'ar' ? S.amap[S.ak].ar : S.amap[S.ak].en) + ' <span aria-hidden="true">×</span></button>');
        if (S.q) chips.push('<button class="chip" type="button" data-clear="q">«' + esc(S.q) + '» <span aria-hidden="true">×</span></button>');
        if (S.cat && S.cmap[S.cat]) chips.push('<button class="chip" type="button" data-clear="cat">' + esc(catName(S.cat)) + ' <span aria-hidden="true">×</span></button>');
        $('#count').textContent = S.loading && !S.items.length ? tr('loading') : S.capped ? tr('results_more', { n: fmt(S.total) }) :
            S.poems >= S.total && S.total ? tr('n_poems', { n: fmt(S.total) }) :
            S.poems ? tr('results_mix', { b: fmt(S.total - S.poems), p: fmt(S.poems) }) : tr('results', { n: fmt(S.total) });
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
            rendered = S.items.length; } else if (S.items.length > rendered) { grid.insertAdjacentHTML('beforeend', S.items.slice(rendered).map(card).join(''));
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
            return '<a class="av" href="/author/' + enc(a.key) + (S.ui === 'en' ? '?lang=en' : '') + '" data-ak="' + esc(a.key) + '"><span class="mono" style="--h:' + num(hue(a.cat)) + '" aria-hidden="true">' + esc(ini) + '</span><b>' + esc(nm) + '</b><small>' + esc(tr('books_n', { n: fmt(a.count) })) + '</small></a>';
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
        $(d.topics).innerHTML = d.data.topics.map((t) => '<button class="topic" type="button" data-topic="' + esc(t.en) + '">' + esc(S.ui === 'ar' ? t.ar : t.en) + '</button>').join('');
        $(d.srcs).innerHTML = d.data.sources.map((s) => '<a class="src" href="' + esc(safeUrl(s.url)) + '" target="_blank" rel="noopener" title="' + esc(S.ui === 'ar' ? s.ar : s.en) + '"><b>' + esc(s.name) + '</b><em aria-hidden="true">' + tr('r_open') + '</em></a>').join('');
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

    $('#langBtn').addEventListener('click', () => {
        S.ui = S.ui === 'ar' ? 'en' : 'ar';
        lsSet('warraq.lang', S.ui);
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
    });
    $('#themeBtn').addEventListener('click', () => {
        const cur = document.documentElement.getAttribute('data-theme') || 'light'; // light by default, dark only on request
        const nx = cur === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', nx);
        lsSet('warraq.theme', nx);
    });
    const _t = lsGet('warraq.theme');
    if (_t === 'dark' || _t === 'light') document.documentElement.setAttribute('data-theme', _t);
    let _l = lsGet('warraq.lang');
    try { const ql = new URLSearchParams(location.search).get('lang'); if (ql === 'en' || ql === 'ar') _l = ql; } catch (e) {}
    // Arabic unless the visitor chose English (the EN button or ?lang=en): it is an Arabic library, and
    // search engines are told that "/" is the Arabic page
    S.ui = _l === 'en' ? 'en' : 'ar';

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