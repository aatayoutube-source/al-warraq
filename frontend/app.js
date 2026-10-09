/* Al-Warraq frontend: talks to the FastAPI backend (/api/*). No build step. */
(() => {
    'use strict';

    const PAGE = 60;

    const T = {
        ar: {
            brand: 'مكتبة الوراق',
            theme: 'تبديل المظهر',
            nav_browse: 'الكتب',
            nav_authors: 'المؤلفون',
            nav_research: 'البحوث',
            ph: 'ابحث بعنوان كتاب أو اسم مؤلف',
            search: 'بحث',
            eyebrow: 'كتب في الملك العام',
            h1: 'اقرأ ما سقط عنه حق النشر',
            lede: 'فهرس مفتوح لمئات الآلاف من الكتب، بأغلفتها وتصنيفاتها، يوصلك إلى روابط قراءة وتنزيل قانونية من المصادر الأصلية.',
            quick: 'ابدأ من هنا:',
            st_books: 'كتاب',
            st_auth: 'مؤلف مشهور',
            st_lang: 'لغة',
            f_cat: 'التصنيف',
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
            loading: 'جارٍ التحميل…',
            more: 'عرض المزيد',
            none: 'لا توجد نتائج في الفهرس. جرّب المصادر الكاملة أعلاه.',
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
            authors_h: 'المؤلفون والشخصيات المشهورة',
            authors_p: 'اضغط على اسم لعرض أعماله.',
            show_all: 'عرض كل المؤلفين ({n})',
            show_less: 'عرض أقل',
            books_n: '{n} كتاب',
            research_h: 'مكتب البحوث المفتوحة',
            research_p: 'اكتب موضوعك واختر المصدر. كل الروابط تفتح قواعد بيانات مجانية وقانونية للبحوث والكتب.',
            med_h: 'البحوث الطبية',
            med_p: 'أبحاث وكتب طبية وحيوية بنص كامل مجاني.',
            eng_h: 'البحوث الهندسية',
            eng_p: 'أبحاث وتقارير ومقررات هندسية وتقنية مفتوحة.',
            r_open: '↗',
            legal1: 'جميع الروابط تقود إلى مواقع خارجية. المكتبة لا تستضيف ملفات، وتعرض الأعمال المصنفة في الملك العام وفق مصادرها.',
            legal2: 'حالة الملك العام تختلف من بلد لآخر (مشروع غوتنبرغ يتبع القانون الأمريكي). تحقق من قانون بلدك قبل إعادة النشر.'
        },
        en: {
            brand: 'Al-Warraq Library',
            theme: 'Toggle theme',
            nav_browse: 'Books',
            nav_authors: 'Authors',
            nav_research: 'Research',
            ph: 'Search a title or an author',
            search: 'Search',
            eyebrow: 'Public-domain books',
            h1: 'Read what has left copyright',
            lede: 'An open index of hundreds of thousands of books with covers and categories, linking to legal reading and download pages at the original sources.',
            quick: 'Start with:',
            st_books: 'books',
            st_auth: 'famous authors',
            st_lang: 'languages',
            f_cat: 'Category',
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
            loading: 'Loading…',
            more: 'Show more',
            none: 'No matches in the index. Try the full sources above.',
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
            authors_h: 'Famous authors & figures',
            authors_p: 'Select a name to see their works.',
            show_all: 'Show all authors ({n})',
            show_less: 'Show fewer',
            books_n: '{n} books',
            research_h: 'Open research desk',
            research_p: 'Type a topic and pick a source. Every link opens a free, legal database of papers and books.',
            med_h: 'Medical research',
            med_p: 'Biomedical papers and books with free full text.',
            eng_h: 'Engineering research',
            eng_p: 'Open engineering and technology papers, reports and courses.',
            r_open: '↗',
            legal1: 'All links lead to external sites. This library hosts no files and lists works that are public domain at their sources.',
            legal2: 'Public-domain status differs by country (Project Gutenberg follows US law). Check your local law before republishing.'
        }
    };

    const QUICK = [
        { q: 'shakespeare', ar: 'شكسبير', en: 'Shakespeare' },
        { q: 'dostoevsky', ar: 'دوستويفسكي', en: 'Dostoevsky' },
        { q: 'ابن سينا', ar: 'ابن سينا', en: 'Avicenna' },
        { q: 'جبران', ar: 'جبران', en: 'Gibran' },
        { q: 'sherlock holmes', ar: 'شرلوك هولمز', en: 'Sherlock Holmes' },
        { q: 'ألف ليلة', ar: 'ألف ليلة وليلة', en: 'Arabian Nights' }
    ];

    const S = {
        ui: 'ar',
        cat: '',
        org: '',
        ak: '',
        bl: '',
        sort: 'def',
        q: '',
        items: [],
        total: 0,
        meta: null,
        cmap: {},
        amap: {},
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
    const htCover = (hid) => 'https://babel.hathitrust.org/cgi/imgsrv/cover?id=' + enc(hid);
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

    function setImg(el, url) { const img = el.querySelector('.cvimg'); if (img && img.getAttribute('src') !== url) img.src = url; }

    function startCover(el) {
        el.dataset.started = '1';
        const gid = +el.dataset.gid,
            hid = el.dataset.hid;
        if (gid) { el.dataset.stage = '1';
            setImg(el, gutUrl(gid)); } else if (hid) { el.dataset.stage = '1';
            setImg(el, htCover(hid)); } else { el.dataset.stage = '2';
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
        return '<a class="cover' + (title.length > 36 ? ' cv-long' : '') + '" style="--h:' + h + '" href="' + esc(links(b).main) + '" target="_blank" rel="noopener"' +
            ' data-id="' + b.id + '" data-gid="' + (b.gid || '') + '" data-hid="' + esc(b.hid || '') + '" aria-label="' + esc(title + (au ? ' — ' + au : '')) + '">' +
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
            if (r.total != null) S.total = r.total;
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
        S.total = 0; };

    /* ---------- links ---------- */
    function links(b) {
        const a = b.ak && S.amap[b.ak];
        const last = a ? a.en.split(' ').slice(-1)[0] : (b.a || '').split(' ').slice(-1)[0];
        const qs = enc((b.t + ' ' + last).trim());
        const arch = 'https://archive.org/search?query=' + qs;
        const ol = 'https://openlibrary.org/search?mode=everything&has_fulltext=true&q=' + qs;
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
        $('#langBtn').textContent = S.ui === 'ar' ? 'EN' : 'ع';
        $('#langBtn').setAttribute('aria-label', S.ui === 'ar' ? 'English' : 'العربية');
        $('#filtBtn').textContent = tr('filters');
    }

    function renderHero() {
        $('#quick').innerHTML = '<span>' + esc(tr('quick')) + '</span>' + QUICK.map((c) => '<button class="qchip" type="button" data-q="' + esc(c.q) + '">' + esc(c[S.ui]) + '</button>').join('');
        if (!S.meta) { $('#stats').innerHTML = ''; return; }
        $('#stats').innerHTML = [
                [S.meta.total, 'st_books'],
                [S.meta.authors.length, 'st_auth'],
                [S.meta.languages.length, 'st_lang']
            ]
            .map((x) => '<div class="stat"><b>' + fmt(x[0]) + '</b><span>' + esc(tr(x[1])) + '</span></div>').join('');
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
            '<button class="catitem" type="button" data-cat="" aria-pressed="' + (S.cat === '') + '"><i style="--h:215"></i><span>' + esc(tr('all_cats')) + '</span><small>' + fmt(total) + '</small></button>' +
            S.meta.categories.map((c) => '<button class="catitem" type="button" data-cat="' + c.key + '" aria-pressed="' + (S.cat === c.key) + '"><i style="--h:' + c.hue + '"></i><span>' + esc(c[S.ui]) + '</span><small>' + fmt(c.count) + '</small></button>').join('');
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
            '<div class="meta"><h3 class="ttl">' + esc(title) + '</h3>' + (au ? '<p class="by">' + esc(au) + '</p>' : '') +
            '<div class="row"><a class="btn" href="' + esc(L.main) + '" target="_blank" rel="noopener">' + esc(tr(L.read ? 'read' : 'find')) + '</a>' +
            L.list.map((x) => '<a class="lnk" href="' + esc(x[1]) + '" target="_blank" rel="noopener">' + esc(x[0]) + '</a>').join('') + '</div></div></article>';
    }
    let rendered = 0;

    function renderResults(append) {
        const chips = [];
        if (S.ak && S.amap[S.ak]) chips.push('<button class="chip" type="button" data-clear="ak">' + esc(S.ui === 'ar' ? S.amap[S.ak].ar : S.amap[S.ak].en) + ' <span aria-hidden="true">×</span></button>');
        if (S.q) chips.push('<button class="chip" type="button" data-clear="q">«' + esc(S.q) + '» <span aria-hidden="true">×</span></button>');
        if (S.cat && S.cmap[S.cat]) chips.push('<button class="chip" type="button" data-clear="cat">' + esc(catName(S.cat)) + ' <span aria-hidden="true">×</span></button>');
        $('#count').textContent = S.loading && !S.items.length ? tr('loading') : tr('results', { n: fmt(S.total) });
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
        else if (S.loading) msg = '<p class="state">' + esc(tr('loading')) + '</p>';
        else if (!S.items.length) msg = '<p class="state">' + esc(tr('none')) + '</p>';
        $('#state').innerHTML = msg;
        const mb = $('#moreBtn');
        mb.hidden = S.loading || S.err || S.items.length >= S.total;
        mb.textContent = tr('more') + ' (' + fmt(Math.max(S.total - S.items.length, 0)) + ')';
    }

    function renderAuthors() {
        if (!S.meta) return;
        const keys = S.meta.authors,
            list = S.authAll ? keys : keys.slice(0, 16);
        const av = $('#avs');
        av.classList.toggle('all', S.authAll);
        av.innerHTML = list.map((a) => {
            const nm = S.ui === 'ar' ? a.ar : a.en,
                ini = Array.from(nm.replace(/[^\p{L}]/gu, '') || '?')[0];
            return '<button class="av" type="button" data-ak="' + a.key + '"><span class="mono" style="--h:' + hue(a.cat) + '" aria-hidden="true">' + esc(ini) + '</span><b>' + esc(nm) + '</b><small>' + esc(tr('books_n', { n: fmt(a.count) })) + '</small></button>';
        }).join('');
        const m = $('#authMore');
        m.hidden = keys.length <= 16;
        m.textContent = S.authAll ? tr('show_less') : tr('show_all', { n: keys.length });
    }

    /* ---------- research ---------- */
    const DESKS = [
        { domain: 'med', input: '#rqMed', topics: '#topicsMed', srcs: '#srcsMed', def: 'cardiology', data: null, req: 0, timer: 0 },
        { domain: 'eng', input: '#rqEng', topics: '#topicsEng', srcs: '#srcsEng', def: 'control systems', data: null, req: 0, timer: 0 }
    ];

    function renderDesk(d) {
        if (!d.data) { $(d.topics).innerHTML = '';
            $(d.srcs).innerHTML = ''; return; }
        $(d.topics).innerHTML = d.data.topics.map((t) => '<button class="topic" type="button" data-topic="' + esc(t.en) + '">' + esc(S.ui === 'ar' ? t.ar : t.en) + '</button>').join('');
        $(d.srcs).innerHTML = d.data.sources.map((s) => '<a class="src" href="' + esc(s.url) + '" target="_blank" rel="noopener"><div><b>' + esc(s.name) + '</b><span>' + esc(S.ui === 'ar' ? s.ar : s.en) + '</span></div><em aria-hidden="true">' + tr('r_open') + '</em></a>').join('');
    }

    function loadDesk(d) {
        const id = ++d.req;
        api('/api/research', { domain: d.domain, q: $(d.input).value.trim() }).then((r) => { if (id === d.req) { d.data = r;
                renderDesk(d); } }).catch(() => {});
    }

    /* ---------- events ---------- */
    function applyFilters() { resetPaging();
        renderSide();
        loadBooks(false); }

    function toBrowse() {
        const rm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
        $('#browse').scrollIntoView({ behavior: rm ? 'auto' : 'smooth', block: 'start' });
    }

    function setQuery(q) { S.q = q;
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
        DESKS.forEach(renderDesk);
        const grid = $('#grid');
        grid.innerHTML = '';
        if (S.sort !== 'def') loadBooks(false);
        else renderResults(false);
    });
    $('#themeBtn').addEventListener('click', () => {
        const cur = document.documentElement.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        const nx = cur === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', nx);
        lsSet('warraq.theme', nx);
    });
    const _t = lsGet('warraq.theme');
    if (_t === 'dark' || _t === 'light') document.documentElement.setAttribute('data-theme', _t);
    const _l = lsGet('warraq.lang');
    if (_l === 'en' || _l === 'ar') S.ui = _l;
    else {
        // first visit: follow the browser language (Arabic -> Arabic, anything else -> English)
        let _b = '';
        try { _b = ((navigator.languages && navigator.languages[0]) || navigator.language || '').toLowerCase(); } catch (e) {}
        S.ui = (!_b || _b.indexOf('ar') === 0) ? 'ar' : 'en';
    }

    $('#q').addEventListener('input', (e) => { S.q = e.target.value;
        resetPaging();
        reloadSoon(); });
    $('#searchForm').addEventListener('submit', (e) => { e.preventDefault();
        S.q = $('#q').value;
        applyFilters();
        toBrowse(); });
    $('#quick').addEventListener('click', (e) => { const b = e.target.closest('.qchip'); if (b) setQuery(b.dataset.q); });
    $('#catList').addEventListener('click', (e) => { const b = e.target.closest('.catitem'); if (!b) return;
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
    $('#state').addEventListener('click', (e) => { if (e.target.id === 'retryBtn') { if (S.meta) loadBooks(S.items.length > 0);
            else init(); } });
    $('#avs').addEventListener('click', (e) => {
        const b = e.target.closest('.av');
        if (!b) return;
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
            if (es[0].isIntersecting && S.meta && !S.loading && !S.err && S.items.length && S.items.length < S.total) loadBooks(true);
        }, { rootMargin: '700px' }).observe($('#sentinel'));
    }

    /* ---------- start ---------- */
    function init() {
        S.err = false;
        applyStatic();
        renderHero();
        renderResults(false);
        loadMeta().then(() => {
            applyStatic();
            renderHero();
            renderSide();
            renderAuthors();
            loadBooks(false);
            DESKS.forEach(loadDesk);
            api('/api/shelf', { count: 5 }).then((r) => renderFan(r.items)).catch(() => {});
        }).catch(() => { S.loading = false;
            S.err = true;
            renderResults(false); });
    }
    init();
})();