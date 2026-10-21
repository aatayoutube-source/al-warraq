import csv
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

HEADER = ["Text#", "Type", "Issued", "Title", "Language", "Authors", "Subjects", "LoCC", "Bookshelves"]


def make_csv(path, extra=0):
    rows = [
        [1342, "Text", "1998", "Pride and Prejudice", "en", "Austen, Jane, 1775-1817", "Love stories", "PR", "Best Books Ever Listings"],
        [84, "Text", "1993", "Frankenstein; Or, The Modern Prometheus", "en", "Shelley, Mary Wollstonecraft, 1797-1851", "Science fiction", "PR", "Gothic Fiction"],
        [9999, "Text", "2010", "Gray's Anatomy\nof the Human Body", "en", "Gray, Henry, 1825-1861", "Anatomy -- Textbooks", "QM", "Medicine"],
        [7777, "Text", "2012", "رسالة الغفران الثانية", "ar", "المعري, أبو العلاء, 973-1057", "Arabic literature", "PJ", ""],
        [5555, "Audio", "2012", "Some Audiobook", "en", "Nobody, Nemo", "Music", "M", ""],
        [4444, "Text", "2005", "Steam Engine Handbook", "en", "Anonymous", "Steam-engines; Machinery", "TJ", "Engineering"],
        # false-positive guards: same title or same first name as a curated author, different person
        [6001, "Text", "2001", "Poems", "en", "Nobody, Jane", "Poetry", "PR", "Poetry"],
        [6002, "Text", "2001", "A Jack of All Trades", "en", "Smith, Jack", "Fiction", "PR", "Humor"],
        [6003, "Text", "2001", "The Time Machine", "en", "Wells, H. G. (Herbert George), 1866-1946", "Science fiction", "PR", "Science Fiction"],
        [6004, "Text", "2001", "Les Misérables", "fr", "Hugo, Victor, 1802-1885", "Fiction", "PQ", ""],
        [6005, "Text", "2001", "Le Roman", "fr", "Hugo, Jean", "Fiction", "PQ", ""],
    ]
    for i in range(extra):
        lang = ("en", "fr", "de")[i % 3]
        rows.append([20000 + i, "Text", "2001", "Synthetic Book %d" % i, lang, "Writer%d, Some" % i, "Fiction", "PS", "Short Stories"])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WARRAQ_DB", str(tmp_path / "t.db"))
    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c


def test_seed_and_meta(client):
    m = client.get("/api/meta").json()
    assert m["total"] == 386
    assert len(m["categories"]) == 21
    assert any(a["key"] == "gibran" and a["count"] == 6 for a in m["authors"])
    assert len(m["authors"]) == 146
    assert m["author_total"] == 145  # "Anonymous & Folk Tradition" is not counted as an author
    assert {l["code"] for l in m["languages"]} == {"ar", "en"}


def test_search_english_and_arabic(client):
    r = client.get("/api/books", params={"q": "dostoevsky crime"}).json()
    assert r["total"] == 1 and r["items"][0]["t"] == "Crime and Punishment"
    assert client.get("/api/books", params={"q": "الجريمه والعقاب"}).json()["total"] == 1  # taa-marbuta typed as haa
    assert client.get("/api/books", params={"q": "اوليفر"}).json()["total"] >= 1  # alef variants
    assert client.get("/api/books", params={"q": "miserables"}).json()["total"] == 1  # accents ignored


def test_filters_and_paging(client):
    r = client.get("/api/books", params={"cat": "med"}).json()
    assert r["total"] > 0 and all(i["c"] == "med" for i in r["items"])
    r = client.get("/api/books", params={"org": "a", "limit": 5}).json()
    assert len(r["items"]) == 5 and all(i["o"] == "a" for i in r["items"])
    p1 = client.get("/api/books", params={"limit": 10, "offset": 0}).json()["items"]
    p2 = client.get("/api/books", params={"limit": 10, "offset": 10}).json()["items"]
    assert not {b["id"] for b in p1} & {b["id"] for b in p2}
    assert client.get("/api/books", params={"ak": "plato"}).json()["total"] == 9
    assert client.get("/api/books", params={"bl": "ar"}).json()["total"] == client.get("/api/books", params={"org": "a"}).json()["total"]


def test_sort_and_validation(client):
    items = client.get("/api/books", params={"sort": "t", "ui": "en", "limit": 5}).json()["items"]
    titles = [i["t"].lower() for i in items]
    assert titles == sorted(titles)
    assert client.get("/api/books", params={"sort": "nope"}).status_code == 400
    assert client.get("/api/books", params={"limit": 9999}).status_code == 422


def test_shelf_and_research(client):
    items = client.get("/api/shelf").json()["items"]
    assert len(items) == 12 and len({i["id"] for i in items}) == 12
    r = client.get("/api/research", params={"domain": "med", "q": "heart failure"}).json()
    assert r["query"] == "heart failure" and len(r["sources"]) == 7  # BMC left: its search now redirects to a brand page
    assert any("pmc.ncbi.nlm.nih.gov" in s["url"] and "heart%20failure" in s["url"] for s in r["sources"])
    assert client.get("/api/research", params={"domain": "x"}).status_code == 400


def test_import_all(client, tmp_path):
    from app import db, importer
    csv_path = tmp_path / "pg.csv"
    make_csv(csv_path, extra=75000)
    conn = db.connect()
    t0 = time.time()
    res = importer.run(conn, limit=0, csv_path=str(csv_path))
    elapsed = time.time() - t0
    conn.close()
    assert elapsed < 60, "import of ~75k rows took %.1fs" % elapsed
    assert res["linked"] >= 4  # Pride, Frankenstein, Time Machine, Les Miserables, Risalat al-Ghufran

    from app import main as _m; _m._meta_cache.clear()
    m = client.get("/api/meta").json()
    assert m["total"] > 75000
    assert m["author_total"] >= 75000 + 145  # recounted after the import: every imported writer, not only famous ones
    assert {l["code"] for l in m["languages"]} >= {"en", "fr", "de", "ar"}

    # editions link to the curated book (same author + title prefix) and give it a Gutenberg id
    def one(q, **kw):
        return client.get("/api/books", params=dict(q=q, **kw)).json()["items"]
    assert [b["gid"] for b in one("pride prejudice")] == [1342]
    fr = one("frankenstein")
    assert len(fr) == 1 and fr[0]["gid"] == 84 and fr[0]["ak"] == "shelley"
    assert [b["gid"] for b in one("time machine") if b["ak"] == "wells"] == [6003]  # "H. G. Wells" matched
    assert [b["gid"] for b in one("الغفران")] == [7777]  # Arabic author + Arabic title prefix

    # false positives must NOT happen
    poems = [b for b in one("poems") if b["gid"] == 6001]
    assert poems and poems[0]["ak"] == ""            # "Nobody, Jane" is not Jane Austen / Emily Dickinson
    jack = [b for b in one("trades") if b["gid"] == 6002][0]
    assert jack["ak"] == ""                          # "Smith, Jack" is not Adam Smith / Jack London
    roman = [b for b in one("roman") if b["gid"] == 6005][0]
    assert roman["ak"] == ""                         # "Hugo, Jean" is not Victor Hugo

    gray = [b for b in one("human body anatomy") if b["gid"] == 9999][0]
    assert gray["c"] == "med" and gray["ak"] == "gray"
    assert client.get("/api/books", params={"q": "audiobook"}).json()["total"] == 0  # non-text skipped

    # language filter and paging deep into the list
    fr_only = client.get("/api/books", params={"bl": "fr", "limit": 5}).json()
    assert fr_only["total"] > 20000 and all(b["lg"] == "fr" for b in fr_only["items"])
    deep = client.get("/api/books", params={"offset": 70000, "limit": 3}).json()
    assert len(deep["items"]) == 3
    assert client.get("/api/books", params={"q": "synthetic", "offset": 60}).json()["total"] is None  # count only on first page
    common = client.get("/api/books", params={"q": "synthetic"}).json()  # 75,000 matches: shown as "more than 10,000"
    assert common["total"] == 10000 and common["capped"] and len(common["items"]) == 60

    # search stays fast on 75k rows
    t0 = time.time()
    r = client.get("/api/books", params={"q": "synthetic book 7"}).json()
    assert r["total"] > 1000 and time.time() - t0 < 1.5

    # re-import is idempotent
    conn = db.connect()
    importer.run(conn, limit=0, csv_path=str(csv_path))
    conn.close()
    _m._meta_cache.clear()
    assert client.get("/api/meta").json()["total"] == m["total"]


def test_import_limit_and_language(client, tmp_path):
    from app import db, importer
    csv_path = tmp_path / "pg.csv"
    make_csv(csv_path, extra=300)
    conn = db.connect()
    res = importer.run(conn, limit=50, langs=["fr"], csv_path=str(csv_path))
    conn.close()
    assert res["added"] + res["linked"] == 50
    assert client.get("/api/books", params={"bl": "de"}).json()["total"] == 0


def test_cover_cache(client, monkeypatch):
    from app import covers
    calls = []

    def fake(url):
        calls.append(url)
        if "Hamlet" in url:
            return {"docs": [{"title": "Hamlet"}, {"title": "Hamlet", "cover_i": 12345}]}
        return {"docs": []}

    monkeypatch.setattr(covers, "fetch_json", fake)
    monkeypatch.setattr(covers, "MIN_GAP", 0)
    hid = client.get("/api/books", params={"q": "hamlet"}).json()["items"][0]["id"]
    assert client.get("/api/cover/%d" % hid).json()["url"] == "https://covers.openlibrary.org/b/id/12345-M.jpg"
    assert client.get("/api/cover/%d" % hid).json()["url"].endswith("12345-M.jpg")
    assert len(calls) == 1  # second call came from the cache
    other = client.get("/api/books", params={"q": "macbeth"}).json()["items"][0]["id"]
    assert client.get("/api/cover/%d" % other).json()["url"] is None
    client.get("/api/cover/%d" % other)
    assert len(calls) == 2  # "no cover" is cached too
    assert client.get("/api/cover/99999999").json()["url"] is None

    def boom(url):
        raise OSError("offline")

    monkeypatch.setattr(covers, "fetch_json", boom)
    third = client.get("/api/books", params={"q": "othello"}).json()["items"][0]["id"]
    assert client.get("/api/cover/%d" % third).json()["url"] is None  # failure is not cached
    monkeypatch.setattr(covers, "fetch_json", lambda u: {"docs": [{"cover_i": 7}]})
    assert client.get("/api/cover/%d" % third).json()["url"].endswith("7-M.jpg")


def make_hathifile(path, bulk=520000):
    def row(htid, bib, title, lang, author, access="allow", rights="pd", fmt="BK"):
        f = [""] * 26
        f[0], f[1], f[2], f[3], f[11], f[18], f[19], f[25] = htid, access, rights, str(bib), title, lang, fmt, author
        return "\t".join(f)
    lines = [
        row("mdp.1", 1, "Pride and prejudice / by Jane Austen.", "eng", "Austen, Jane, 1775-1817."),  # duplicate of a Gutenberg book
        row("mdp.2", 2, "A history of the Ottoman Empire :", "eng", "Smith, Jack, 1850-1920."),
        row("mdp.3", 3, "تاريخ الطبري", "ara", "الطبري, محمد بن جرير, 839-923."),
        row("mdp.4", 4, "Locked book still in copyright", "eng", "Writer, Ann, 1950-.", access="deny", rights="ic"),
        row("mdp.5", 5, "Some journal", "eng", "", fmt="SE"),
        row("mdp.6", 6, "Hamlet, prince of Denmark", "eng", "Shakespeare, William, 1564-1616."),
        row("mdp.7", 6, "Hamlet, prince of Denmark", "eng", "Shakespeare, William, 1564-1616."),  # second volume, same bib
        row("mdp.8", 8, "Nothing about the author here", "fre", ""),
    ]
    for i in range(bulk):
        has_author = i % 26 != 0
        lines.append(row("uc1.b%d" % i, 100 + i, "Treatise number %d on the history of things" % i, ("eng", "fre", "ger")[i % 3],
                         ("Surname%d, Given" % i) if has_author else ""))
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines) + "\n")


def test_hathi_import_500k(client, tmp_path):
    import gzip, shutil
    from app import db, importer, hathi
    csv_path, raw, gz = tmp_path / "pg.csv", tmp_path / "hathi.txt", tmp_path / "hathi.txt.gz"
    make_csv(csv_path, extra=75000)
    make_hathifile(raw)
    with open(raw, "rb") as a, gzip.open(gz, "wb") as b:
        shutil.copyfileobj(a, b)
    conn = db.connect()
    importer.run(conn, limit=0, csv_path=str(csv_path))
    gut_total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    t0 = time.time()
    res = hathi.import_hathi(conn, str(gz), limit=450000, log=lambda *a: None)
    elapsed = time.time() - t0
    conn.close()
    assert elapsed < 240, "hathi import took %.0fs" % elapsed
    assert 449990 <= res["hathi_added"] <= 450000
    assert res["hathi_duplicates_skipped"] >= 1  # Pride and prejudice already present

    from app import main as m
    m._meta_cache.clear()
    meta = client.get("/api/meta").json()
    assert meta["total"] >= 500000, meta["total"]
    assert {l["code"] for l in meta["languages"]} >= {"en", "fr", "de", "ar"}
    assert any(c["key"] == "gen" for c in meta["categories"])

    def one(q, **kw):
        return client.get("/api/books", params=dict(q=q, **kw)).json()["items"]
    tab = [b for b in one("الطبري") if b["hid"]]
    assert tab and tab[0]["hid"] == "mdp.3" and tab[0]["ak"] == "tabari" and tab[0]["o"] == "a" and tab[0]["lg"] == "ar"
    assert [b["hid"] for b in one("ottoman")] == ["mdp.2"] and one("ottoman")[0]["c"] == "his"
    assert one("ottoman")[0]["ak"] == ""            # "Smith, Jack" is still not Adam Smith
    ham = [b for b in one("hamlet prince denmark") if b["hid"]]
    assert len(ham) == 1 and ham[0]["ak"] == "shakespeare" and ham[0]["t"] == "Hamlet, prince of Denmark"  # one volume per bib, subtitle cut
    assert not one("locked book copyright") and not one("some journal")  # not full view / not a book
    assert not [b for b in one("pride prejudice") if b["hid"]]

    # speed on ~525k rows
    t0 = time.time()
    r = client.get("/api/books", params={"q": "treatise number 4242"}).json()
    q1 = time.time() - t0
    t0 = time.time()
    client.get("/api/books", params={"q": "treatise", "offset": 90000, "limit": 60})  # the deepest page allowed is 100,000
    q2 = time.time() - t0
    t0 = time.time()
    client.get("/api/books", params={"cat": "his", "bl": "fr", "sort": "t"})
    q3 = time.time() - t0
    print("latency first=%.2fs deep=%.2fs filtered=%.2fs" % (q1, q2, q3))
    assert r["total"] >= 1 and q1 < 2 and q2 < 2 and q3 < 4

    # re-importing Gutenberg keeps the HathiTrust rows; re-importing HathiTrust is idempotent
    conn = db.connect()
    importer.run(conn, limit=0, csv_path=str(csv_path))
    kept = conn.execute("SELECT COUNT(*) FROM books WHERE curated=2").fetchone()[0]
    hathi.import_hathi(conn, str(gz), limit=450000, log=lambda *a: None)
    again = conn.execute("SELECT COUNT(*) FROM books WHERE curated=2").fetchone()[0]
    conn.close()
    assert kept == res["hathi_added"] and abs(again - kept) <= 2


def test_old_database_gets_htid_column(tmp_path):
    import sqlite3
    from app import db
    path = str(tmp_path / "old.db")
    c = sqlite3.connect(path)
    c.executescript("CREATE TABLE books(id INTEGER PRIMARY KEY AUTOINCREMENT, gid INTEGER, title TEXT NOT NULL, title_ar TEXT NOT NULL DEFAULT '', author_key TEXT NOT NULL DEFAULT '', author_en TEXT NOT NULL DEFAULT '', author_ar TEXT NOT NULL DEFAULT '', cat TEXT NOT NULL, origin TEXT NOT NULL, lang TEXT NOT NULL DEFAULT '', curated INTEGER NOT NULL DEFAULT 0, ord INTEGER NOT NULL, search TEXT NOT NULL);")
    c.close()
    conn = db.connect(path)
    db.init_db(conn)
    assert "htid" in {r[1] for r in conn.execute("PRAGMA table_info(books)")}
    assert "ws" in {r[1] for r in conn.execute("PRAGMA table_info(books)")}


def test_wikisource_import_offline(client):
    from app import db, wikisource
    from app import main as m
    poem = "http://www.wikidata.org/entity/Q5185279"
    lit = "http://www.wikidata.org/entity/Q7725634"
    rows = [
        {"item": "Q1", "page": "الخيل والليل والبيداء تعرفني", "label": "الخيلُ والليلُ والبيداءُ تعرفني", "type": lit, "form": poem, "aar": "المتنبي", "aen": "Al-Mutanabbi"},
        {"item": "Q2", "page": "رسالة الغفران", "label": "رسالة الغفران", "type": lit, "aar": "أبو العلاء المعري", "aen": "Abu al-Ala al-Ma'arri"},
        {"item": "Q3", "page": "تاريخ الرسل والملوك", "label": "", "type": lit, "aar": "", "aen": ""},
        {"item": "Q3", "page": "تاريخ الرسل والملوك", "label": "", "type": lit, "aar": "", "aen": ""},  # same item twice
        {"item": "Q4", "page": "كتاب/الفصل الأول", "label": "", "type": lit, "aar": "", "aen": ""},  # chapter page
        {"item": "Q5", "page": "دستور الكويت", "label": "دستور الكويت", "type": "http://www.wikidata.org/entity/Q7755", "aar": "", "aen": ""},
    ]
    recs = wikisource.parse(rows)
    assert {r["page"] for r in recs} == {"الخيل والليل والبيداء تعرفني", "رسالة الغفران", "تاريخ الرسل والملوك", "دستور الكويت"}
    cats = {r["page"]: r["cat"] for r in recs}
    assert cats["الخيل والليل والبيداء تعرفني"] == "poe" and cats["تاريخ الرسل والملوك"] == "his" and cats["دستور الكويت"] == "pol"
    assert wikisource.parse_tsv('?item\t?page\n<http://www.wikidata.org/entity/Q9>\t"قفا نبك"@ar\n') == [
        {"item": "http://www.wikidata.org/entity/Q9", "page": "قفا نبك"}]

    conn = db.connect()
    res = wikisource.import_records(conn, recs)
    again = wikisource.import_records(conn, recs)  # idempotent
    conn.close()
    assert res == again and res["poems"] == 1 and res["works"] == 0 and res["linked"] == 0  # poems only
    m._meta_cache.clear()

    found = client.get("/api/books", params={"q": "البيداء"}).json()
    hit = found["items"]  # the poem, then books one letter away (counted as "near")
    assert found["total"] - found["near"] == 1 and hit[0]["ws"] and hit[0]["ak"] == "mutanabbi" and hit[0]["c"] == "poe"
    meta = client.get("/api/meta").json()
    assert meta["poem_total"] == 1 and meta["poets"][0]["ar"] == "المتنبي"
    poets = client.get("/api/books", params={"au": meta["poets"][0]["ar"], "cat": "poe"}).json()
    assert hit[0]["id"] in [b["id"] for b in poets["items"]] and all(b["aa"] == "المتنبي" for b in poets["items"])
    page = client.get("/book/%d" % hit[0]["id"], follow_redirects=True).text
    assert "ar.wikisource.org/wiki/" in page
    assert not [b for b in client.get("/api/books", params={"q": "الغفران"}).json()["items"] if b["ws"]]  # no book from there
    assert client.get("/api/cover/%d" % hit[0]["id"]).json()["url"] is None  # no Open Library lookup for poems
    # a poem is counted as a poem, never as a book: the totals stay exact
    assert meta["total"] == 386  # the books only, as before the poem arrived
    poe = next(c for c in meta["categories"] if c["key"] == "poe")
    ara = next(c for c in meta["categories"] if c["key"] == "ara")
    assert poe["poems"] == 1 and ara["poems"] == 1 and ara["count"] + ara["poems"] == client.get(
        "/api/books", params={"cat": "ara"}).json()["total"]
    res = client.get("/api/books", params={"cat": "poe"}).json()
    assert res["poems"] == 1 and res["total"] == poe["count"] + 1


def test_names_categories_and_languages(client):
    from app.catalog import categorize_title, clean_author, fix_name_order
    assert clean_author("Elliot, H. M. Sir (Henry Miers), 1808-1853") == "Sir H. M. Elliot"
    assert clean_author("Little, Elbert L., Jr., 1907-2004") == "Elbert L. Little Jr."
    assert fix_name_order("John Lord") == "John Lord" and fix_name_order("Don Marquis") == "Don Marquis"
    assert categorize_title("Hearing before the Subcommittee on Forests") == "sci"
    assert categorize_title("Hearing before the Committee on Finance") == "pol"
    assert categorize_title("Histoire de la Révolution française") == "his"
    assert categorize_title("Installation housing management study guide") == "gen"
    meta = client.get("/api/meta").json()
    assert meta["lang_total"] == len(meta["languages"]) == 2


def test_fulltext_search_matches_like(client):
    from app import db
    conn = db.connect()
    assert db.fts_ready(conn)
    for q in ["hamlet", "اوليفر", "الجريمه والعقاب", "dostoevsky crime", "ab"]:
        from app.textnorm import norm
        words = norm(q).split()
        sql = "SELECT COUNT(*) FROM books WHERE " + " AND ".join("search LIKE ?" for _ in words)
        expected = conn.execute(sql, ["%" + w + "%" for w in words]).fetchone()[0]
        r = client.get("/api/books", params={"q": q}).json()
        assert r["total"] - (r.get("near") or 0) == expected, q  # near: extra books one letter away, never fewer
    conn.close()


def test_search_relevance_spelling_and_lookalikes(client):
    from app import db, ranking
    from app.textnorm import norm
    conn = db.connect()
    rows = [  # (title, author, ord): the exact title has the worst catalogue position
        ("رسائل الحب والحرب", "كاتب أول", 1), ("الحب في زمن آخر", "كاتب ثان", 2), ("والحب أيضا", "كاتب ثالث", 3),
        ("حبيبتي", "كاتب رابع", 4), ("الحب", "إبراهيم خليل", 900000),
        ("طه حسين والأدب", "ناقد", 5), ("الأيام", "طه حسين", 800000), ("دعاء الكروان", "طه حسين", 800001),
        ("رواية ١٩٨٤", "جورج أورويل", 6), ("زی‌کولا الثانية", "عمرو عبدالحميد", 7),
        ("النفوس الميتة", "نيكولاي غوغول", 8), ("مغامرات شرلوك هولمز", "آرثر كونان دويل", 9),
    ]
    for i, (t, a, o) in enumerate(rows):
        conn.execute("INSERT INTO books(title,title_ar,author_key,author_en,author_ar,cat,origin,lang,curated,ord,search,ext)"
                     " VALUES(?,?,'','',?,'nov','a','ar',4,?,?,?)", (t, t, a, o, norm(t + " " + a), "T%d" % i))
    conn.commit()
    ranking.clear_cache()

    def titles(q, **kw):
        return [b["ta"] for b in client.get("/api/books", params=dict(q=q, **kw)).json()["items"]]
    got = titles("الحب")
    assert got[0] == "الحب"  # exact title first, whatever its place in the catalogue
    assert got.index("الحب في زمن آخر") < got.index("رسائل الحب والحرب")  # then titles starting with it
    assert "والحب أيضا" in got and "حبيبتي" not in got  # "و" joined to the word still counts; a longer word does not
    assert titles("طه حسين") == ["الأيام", "دعاء الكروان", "طه حسين والأدب"]  # his own books, then the books about him
    assert titles("طه حسين الأيام")[0] == "الأيام"  # title and author together
    assert titles("1984") == ["رواية ١٩٨٤"] and titles("١٩٨٤") == ["رواية ١٩٨٤"]  # Eastern digits
    assert "زی‌کولا الثانية" in titles("زيكولا")  # Persian letters and an invisible joiner

    # a letter missing, extra or swapped: the closest books, after the exact ones and said so
    r = client.get("/api/books", params={"q": "فرانكشتاين"}).json()  # an ن left out
    assert r["near"] == r["total"] >= 1 and r["items"][0]["ta"] == "فرانكنشتاين"
    assert client.get("/api/books", params={"q": "فرانكنشتاين"}).json()["near"] == 0
    assert any(b["ta"] == "فرانكنشتاين" for b in client.get("/api/books", params={"q": "فرانكنشتياين"}).json()["items"])
    # every page of a ranked search: each book once
    seen = []
    for off in range(0, 40, 3):
        seen += [b["id"] for b in client.get("/api/books", params={"q": "الحب", "limit": 3, "offset": off}).json()["items"]]
    assert len(seen) == len(set(seen)) == client.get("/api/books", params={"q": "الحب"}).json()["total"]
    r = client.get("/api/books", params={"q": "شرلوك هولمس"}).json()  # the last letter wrong
    assert r["near"] == r["total"] >= 1 and "مغامرات شرلوك هولمز" in [b["ta"] for b in r["items"]]
    # loose patterns only gather candidates: "يكولا" is inside "نيكولاي", two letters away from "زيكولا"
    assert "النفوس الميتة" not in titles("زيكولاا") and "النفوس الميتة" not in titles("زيكولا")
    # the patterns stay usable by the index: three letters in a row
    for w in ("زيكولا", "الخيميائي", "abcde"):
        v = ranking.variants(w)
        assert v and all(max(len(p) for p in x.split("_")) >= 3 for x in v)
    assert "خيميائي" in ranking.variants("الخيميائي")  # the word without its article
    assert ranking.close_to("دستويفسكي", {"فيودور", "دوستويفسكي"}) == "دوستويفسكي" and not ranking.close_to("زيكولا", {"نيكولاي"})
    conn.close()


def test_old_search_text_is_renormalised(client):
    from app import db
    conn = db.connect()
    conn.execute("INSERT INTO books(title,title_ar,author_key,author_en,author_ar,cat,origin,lang,curated,ord,search,ext)"
                 " VALUES('کتاب الدر‌اسات ٣','','','','','gen','a','ar',4,5,?, 'X1')", ("کتاب الدر اسات ٣",))  # as norm() v1 made it
    conn.execute("DELETE FROM meta WHERE key='search_norm'")
    conn.commit()
    assert db.renorm_search(conn) == 1 and db.renorm_search(conn) == 0
    s = conn.execute("SELECT search FROM books WHERE ext='X1'").fetchone()[0]
    assert s.startswith("كتاب الدر اسات 3") and "الدراسات" in s
    assert conn.execute("SELECT COUNT(*) FROM books_fts WHERE search LIKE '%الدراسات%'").fetchone()[0] == 1
    conn.close()


def test_visitors_per_day_month_year(client):
    from app import main as m
    a, b = {"user-agent": "Mozilla/5.0 reader A"}, {"user-agent": "Mozilla/5.0 reader B"}
    client.post("/api/hit", headers=a)
    client.post("/api/hit", headers=a)  # same person again: counted once
    client.post("/api/hit", headers=b)
    client.post("/api/hit", headers={"user-agent": "Googlebot/2.1"})  # bots are not visitors
    m._meta_cache.clear()
    s = client.get("/api/stats").json()
    assert (s["visitors_today"], s["visitors_month"], s["visitors_year"]) == (2, 2, 2)


def test_research_papers(client, monkeypatch):
    from app import research
    research._papers_cache.clear()
    seen = []

    def fake(url):
        seen.append(url)
        return {"meta": {"count": 1234}, "results": [
            {"id": "https://openalex.org/W1", "display_name": "Heart <i>failure</i> today", "publication_year": 2020,
             "authorships": [{"author": {"display_name": n}} for n in ("A One", "B Two", "C Three", "D Four")],
             "primary_location": {"source": {"display_name": "Open Heart"}},
             "best_oa_location": {"pdf_url": "https://example.org/paper.pdf"}, "cited_by_count": 42},
            {"id": "https://openalex.org/W2", "display_name": "", "publication_year": 2019},  # no title: dropped
        ]}

    monkeypatch.setattr(research, "fetch_json", fake)
    r = client.get("/api/papers", params={"domain": "med", "q": "أمراض القلب"}).json()
    assert r["query"] == "Cardiology" and r["translated"] and r["total"] == 1234
    assert r["items"] == [{"title": "Heart failure today", "year": 2020, "authors": "A One, B Two, C Three …", "venue": "Open Heart",
                           "url": "https://example.org/paper.pdf", "pdf": True, "cited": 42}]
    assert "is_oa:true" in seen[0] and "search=Cardiology" in seen[0]
    client.get("/api/papers", params={"domain": "med", "q": "Cardiology"})
    assert len(seen) == 1  # cached

    def down(url):
        raise OSError("offline")

    monkeypatch.setattr(research, "fetch_json", down)
    assert client.get("/api/papers", params={"domain": "eng", "q": "robots"}).json()["error"] is True
    assert client.get("/api/papers", params={"domain": "x"}).status_code == 400
    links = client.get("/api/research", params={"domain": "eng", "q": "الروبوتات"}).json()
    assert links["query"] == "Robotics" and not any("osti.gov" in s["url"] for s in links["sources"])


def test_security_guards(client, monkeypatch):
    from app import research
    research._papers_cache.clear()
    # links from another service never reach the page unless they are plain web links
    monkeypatch.setattr(research, "fetch_json", lambda url: {"meta": {"count": 2}, "results": [
        {"id": "https://openalex.org/W1", "display_name": "Evil", "best_oa_location": {"pdf_url": "javascript:alert(1)"},
         "primary_location": {"landing_page_url": "javascript:alert(2)"}, "ids": {"doi": "javascript:alert(3)"}},
        {"id": "https://openalex.org/W2", "display_name": "Good", "best_oa_location": {"pdf_url": "https://example.org/a.pdf"}}]})
    items = client.get("/api/papers", params={"domain": "eng", "q": "xss"}).json()["items"]
    assert [i["url"] for i in items] == ["https://openalex.org/W1", "https://example.org/a.pdf"]

    # POSTs sent by another website are refused; the site's own are fine
    assert client.post("/api/hit", headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/hit", headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert client.post("/api/hit", headers={"origin": "http://testserver"}).status_code == 200

    # headers: CSP everywhere, and book pages only run scripts carrying this response's nonce
    home = client.get("/")
    assert "frame-ancestors 'none'" in home.headers["content-security-policy"] and home.headers["x-content-type-options"] == "nosniff"
    page = client.get("/book/1", follow_redirects=True)
    csp = page.headers["content-security-policy"]
    nonce = csp.split("'nonce-")[1].split("'")[0]
    assert page.text.count("<script") == page.text.count('<script nonce="%s"' % nonce) > 0

    # oversized or abusive inputs
    assert client.get("/api/books", params={"offset": 200000}).status_code == 422
    assert client.get("/api/books", params={"q": "x" * 500}).status_code == 422
    assert client.get("/sitemap-books-999999999.xml").status_code == 404


def test_counters_cannot_be_pumped(client):
    from app import main as m
    for _ in range(5):  # one person repeating a search or reloading a book page counts once
        client.post("/api/track/search", params={"q": "spam phrase"}, headers={"user-agent": "Mozilla/5.0 one"})
        client.get("/book/1", follow_redirects=True, headers={"user-agent": "Mozilla/5.0 one"})
    m._meta_cache.clear()
    s = client.get("/api/stats").json()
    assert "spam phrase" not in s["top_searches"] and s["views"] == 1
    for ua in ("Mozilla/5.0 two", "Mozilla/5.0 three"):  # three different people: now it is a real popular search
        client.post("/api/track/search", params={"q": "spam phrase"}, headers={"user-agent": ua})
    m._meta_cache.clear()
    assert "spam phrase" in client.get("/api/stats").json()["top_searches"]


def test_rate_limit(client):
    codes = [client.post("/api/hit").status_code for _ in range(25)]
    assert codes[:20] == [200] * 20 and codes[-1] == 429


def test_home_page_words_are_in_its_html(client):
    """A crawler reads the HTML before (or without) the script: /?lang=en must already be English there."""
    import re as _re
    en = client.get("/?lang=en").text
    assert '<html lang="en" dir="ltr">' in en and "<title>Al-Warraq Library | Free public-domain books" in en
    assert '<meta name="description" content="Al-Warraq Library' in en and '<h1 data-i="h1">Read what has left copyright</h1>' in en
    assert 'href="/about?lang=en"' in en and 'href="/category/nov?lang=en">Novels &amp; Stories</a>' in en
    ar = client.get("/").text
    assert '<html lang="ar" dir="rtl">' in ar and '<h1 data-i="h1">اقرأ ما سقط عنه حق النشر</h1>' in ar and "<title>مكتبة الوراق" in ar
    for page in (en, ar):  # every text the script would write is already there
        assert not _re.findall(r'data-i="\w+"[^>]*></', page)
        assert 'data-iph="ph" placeholder="' in page


def test_pages_open_in_the_visitors_language(client):
    from app.pages import browser_ui
    assert browser_ui("ar-IQ,ar;q=0.9,en-US;q=0.8") == "ar" and browser_ui("en-US,en;q=0.9,ar;q=0.8") == "en"
    assert browser_ui("ku-IQ,ar;q=0.8") == "ar" and browser_ui("fr-FR,fr;q=0.9") == "en" and browser_ui("") == ""
    chrome = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"

    def lang_of(url, **headers):
        r = client.get(url, headers=dict({"user-agent": chrome}, **headers), follow_redirects=True)
        return r.text.split('<html lang="')[1][:2]
    assert lang_of("/") == "ar"  # a browser that names no language: the page's own
    assert lang_of("/", **{"accept-language": "en-US,en;q=0.9"}) == "en"
    assert lang_of("/", **{"accept-language": "ar-IQ,ar;q=0.9,en;q=0.8"}) == "ar"
    assert lang_of("/category/nov", **{"accept-language": "en-GB"}) == "en" and lang_of("/about", **{"accept-language": "en"}) == "en"
    assert lang_of("/book/1", **{"accept-language": "ar"}) == "ar"  # Hamlet, an English book, with an Arabic interface
    # search engines keep seeing every page in its own language
    for bot in ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "Mediapartners-Google",
                "Mozilla/5.0 (compatible; bingbot/2.0)", "Mozilla/5.0 Chrome-Lighthouse"):
        assert lang_of("/", **{"accept-language": "en-US", "user-agent": bot}) == "ar", bot
    # the visitor's own choice wins over the browser; an address with ?lang= wins over both
    assert lang_of("/", **{"accept-language": "en", "cookie": "warraq_lang=ar"}) == "ar"
    assert lang_of("/", **{"cookie": "warraq_lang=en"}) == "en" and lang_of("/?lang=ar", **{"cookie": "warraq_lang=en"}) == "ar"
    # the language links inside the site keep the choice; arriving from elsewhere on ?lang= does not
    inside = client.get("/category/nov?lang=en", headers={"sec-fetch-site": "same-origin"})
    assert "warraq_lang=en" in inside.headers.get("set-cookie", "") and "Accept-Language" in inside.headers["vary"]
    assert "set-cookie" not in client.get("/?lang=en", headers={"sec-fetch-site": "cross-site"}).headers
    client.cookies.clear()  # the test client kept that choice, as a browser would: start again without one
    privacy = client.get("/privacy").text  # and the privacy policy says so, dated
    assert "warraq_lang" in privacy and "اختيارك للغة والمظهر" not in privacy and "آخر تحديث: 21 أكتوبر 2026" in privacy
    assert "<p>نعرض إعلانات من خلال Google AdSense" in privacy and "قد نعرض إعلانات" not in privacy
    assert "Our site sets the language cookie above" in client.get("/privacy?lang=en").text
    assert "آخر تحديث: 21 أكتوبر 2026" in client.get("/terms").text  # the terms changed with the takedown form


def test_seo_pages(client, monkeypatch):
    import json
    import re
    from app import main as m
    from fastapi.testclient import TestClient

    robots = client.get("/robots.txt").text
    assert "Disallow: /api/\n" not in robots and "Disallow: /api/like/" in robots and "Sitemap:" in robots  # the API stays readable
    assert client.get("/api/meta").headers["x-robots-tag"] == "noindex"

    def ld(html):  # every JSON-LD block must be valid JSON
        return [json.loads(x) for x in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)]

    home = client.get("/").text
    assert '<link rel="canonical" href="http://testserver/">' in home and 'hreflang="en"' in home and "og-image.png" in home
    assert ld(home)[0]["@graph"][0]["potentialAction"]["@type"] == "SearchAction"
    assert 'href="/category/his"' in home and "<!--SEO" not in home  # crawlable category links, markers replaced
    assert '<link rel="canonical" href="http://testserver/?lang=en">' in client.get("/", params={"lang": "en"}).text

    cat = client.get("/category/dra")
    assert cat.status_code == 200 and "<h1>كتب مسرح مجانية</h1>" in cat.text and 'href="/book/' in cat.text
    assert ld(cat.text)[0]["@graph"][1]["@type"] == "BreadcrumbList"
    assert "<h1>Free Drama books</h1>" in client.get("/category/dra", params={"lang": "en"}).text
    assert client.get("/category/nope").status_code == 404 and client.get("/category/dra", params={"page": 99}).status_code == 404
    auth = client.get("/author/shakespeare")
    assert auth.status_code == 200 and "شكسبير" in auth.text and "هاملت" in auth.text  # Arabic page: Arabic titles
    assert client.get("/author/nobody").status_code == 404

    sm = client.get("/sitemap-main.xml").text
    assert "/category/his</loc>" in sm and "/author/shakespeare</loc>" in sm and "?lang=en</loc>" in sm
    book = client.get("/book/1", follow_redirects=True).text
    assert 'href="/category/dra"' in book and 'href="/author/shakespeare"' in book
    graph = ld(book)[0]["@graph"]
    assert [g["@type"] for g in graph] == ["ItemPage", "Book", "BreadcrumbList"]
    work = graph[1]
    assert work["author"]["url"] == "http://testserver/author/shakespeare" and work["bookFormat"] == "https://schema.org/EBook"
    assert work["isAccessibleForFree"] is True and work["inLanguage"] == "en" and graph[0]["mainEntity"]["@id"] == work["@id"]
    assert client.get("/manifest.webmanifest").headers["content-type"].startswith("application/manifest+json")
    for f in ("/favicon.ico", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png", "/og-image.png"):
        assert client.get(f).status_code == 200, f

    # site verification tags and the IndexNow key file come from settings
    monkeypatch.setenv("GOOGLE_SITE_VERIFICATION", "g-123")
    monkeypatch.setenv("INDEXNOW_KEY", "0123456789abcdef")
    with TestClient(m.create_app()) as c2:
        assert '<meta name="google-site-verification" content="g-123">' in c2.get("/").text
        assert c2.get("/0123456789abcdef.txt").text == "0123456789abcdef"


def test_hathi_auto_download(client, tmp_path):
    """A fresh server fetches the newest full hathifile by itself, imports it, and removes the download."""
    import gzip, json, pathlib, shutil
    from app import db, hathi
    raw, gz = tmp_path / "src.txt", tmp_path / "hathi_full_20260101.txt.gz"
    make_hathifile(raw, bulk=300)
    with open(raw, "rb") as a, gzip.open(gz, "wb") as b:
        shutil.copyfileobj(a, b)
    listing = tmp_path / "list.json"
    listing.write_text(json.dumps([
        {"filename": "hathi_upd_20260102.txt.gz", "full": False, "url": "file:///nope"},
        {"filename": "hathi_full_20251201.txt.gz", "full": True, "url": "file:///old"},
        {"filename": gz.name, "full": True, "size": gz.stat().st_size, "url": pathlib.Path(gz).as_uri()},
    ]), encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    conn = db.connect()
    res = hathi.auto_import(conn, str(work), list_url=pathlib.Path(listing).as_uri(), log=lambda *a: None)
    n = conn.execute("SELECT COUNT(*) FROM books WHERE curated=2").fetchone()[0]
    conn.close()
    assert res["hathi_added"] == n >= 300 and list(work.iterdir()) == []  # imported, and the 1 GB file is not left behind


def test_stats_in_their_own_file(tmp_path, monkeypatch):
    """With STATS_DB the counters live in a small file of their own; the catalogue file has none of them."""
    import sqlite3
    from app.main import create_app
    from fastapi.testclient import TestClient
    monkeypatch.setenv("WARRAQ_DB", str(tmp_path / "books.db"))
    monkeypatch.setenv("STATS_DB", str(tmp_path / "keep" / "stats.db"))
    with TestClient(create_app()) as c:
        c.post("/api/hit", headers={"user-agent": "Mozilla/5.0 reader"})
        c.get("/book/1", follow_redirects=True, headers={"user-agent": "Mozilla/5.0 reader"})
        assert c.get("/api/stats").json()["visitors_today"] == 1
    books = sqlite3.connect(str(tmp_path / "books.db"))
    stats = sqlite3.connect(str(tmp_path / "keep" / "stats.db"))
    assert not books.execute("SELECT 1 FROM sqlite_master WHERE name='site_stats'").fetchone()
    assert stats.execute("SELECT n FROM site_stats WHERE key='visitors'").fetchone() == (1,)
    assert stats.execute("SELECT views FROM book_stats").fetchone() == (1,)


def test_download_ready_catalogue(tmp_path, monkeypatch):
    """DB_URL: the whole library arrives as one file instead of a long import."""
    import gzip, pathlib, shutil
    from app import db
    src = str(tmp_path / "src.db")
    conn = db.connect(src)
    db.init_db(conn)
    db.seed_curated(conn)
    conn.close()
    gz = tmp_path / "books.db.gz"
    with open(src, "rb") as a, gzip.open(gz, "wb") as b:
        shutil.copyfileobj(a, b)
    url, dest = pathlib.Path(gz).as_uri(), str(tmp_path / "live" / "warraq.db")
    assert db.needs_download(dest, url) and not db.needs_download(dest, "")
    db.download_books(url, dest, log=lambda *a: None)
    c = db.connect(dest)
    assert c.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 386
    c.close()
    assert not db.needs_download(dest, url) and db.needs_download(dest, url.replace("books.db", "books-v2.db"))  # a new release is fetched again
    bad = tmp_path / "bad.gz"
    with gzip.open(bad, "wb") as b:
        b.write(b"not a database")
    import pytest
    with pytest.raises(IOError):
        db.download_books(pathlib.Path(bad).as_uri(), str(tmp_path / "x" / "w.db"), log=lambda *a: None)


def test_unwritable_database_path_does_not_crash(tmp_path, monkeypatch, capsys):
    """A wrong WARRAQ_DB (a folder that cannot be created) falls back to the temp folder with a warning."""
    import os
    from app import db
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x")  # a file where a folder is expected: makedirs fails, like a read-only /app on a server
    monkeypatch.setenv("WARRAQ_DB", str(blocker / "data" / "warraq.db"))
    db._usable.clear()
    path = db.db_path()
    assert path != str(blocker / "data" / "warraq.db") and os.path.basename(path) == "warraq.db"
    assert "WARNING: cannot write the books database" in capsys.readouterr().err
    conn = db.connect()
    db.init_db(conn)
    db.seed_curated(conn)
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 386
    conn.close()
    db._usable.clear()


def test_links_use_the_public_https_address(client, monkeypatch):
    """Behind Railway's proxy the request looks like plain http: sitemaps and canonical links must still say https."""
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "warraq.up.railway.app")
    base = "https://warraq.up.railway.app"
    assert "Sitemap: %s/sitemap.xml" % base in client.get("/robots.txt").text
    assert "<loc>%s/sitemap-main.xml</loc>" % base in client.get("/sitemap.xml").text
    assert "<loc>%s/category/his</loc>" % base in client.get("/sitemap-main.xml").text
    monkeypatch.setenv("THIN_NOINDEX", "0")  # every book page indexed: all of them in the book sitemaps
    assert "<loc>%s/book/" % base in client.get("/sitemap-books-1.xml").text
    assert '<link rel="canonical" href="%s/">' % base in client.get("/").text
    monkeypatch.setenv("SITE_URL", "https://library.example.com/")  # an explicit address wins
    assert "Sitemap: https://library.example.com/sitemap.xml" in client.get("/robots.txt").text


def test_about_privacy_terms_contact(tmp_path, monkeypatch):
    monkeypatch.setenv("WARRAQ_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("RATE_LIMIT_SCALE", "0")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    from app import db, legal
    from app.main import create_app
    with TestClient(create_app()) as c:
        for p in legal.PAGES:
            for q in ("", "?lang=en"):
                r = c.get("/" + p + q)
                assert r.status_code == 200 and '<nav class="legal"' in r.text, (p, q)
        assert "Google AdSense" in c.get("/privacy").text and "aboutads.info" in c.get("/privacy?lang=en").text
        assert 'href="mailto:alwarraqibrary@gmail.com"' in c.get("/contact").text
        assert "386" in c.get("/about?lang=en").text  # the numbers come from the catalogue
        # every footer links to the four pages, and the sitemap lists them
        assert 'href="/terms"' in c.get("/").text and 'href="/privacy"' in c.get("/category/poe").text
        assert 'href="/contact' in c.get("/book/1").text  # an English book's page links to /contact?lang=en
        main_map = c.get("/sitemap-main.xml").text
        assert "/about?lang=en</loc>" in main_map and "/contact</loc>" not in main_map and "/takedown</loc>" not in main_map
        assert "Disallow: /admin/" in c.get("/robots.txt").text

        conn = db.connect()
        old = legal.form_token(conn, time.time() - 60)
        form = {"name": "Ali", "email": "ali@example.com", "topic": "suggest", "message": "Please add more books by al-Jahiz.", "t": old}
        r = c.post("/contact", data=form, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/contact?sent=1"
        assert "شكراً" in c.get("/contact?sent=1").text
        assert c.post("/contact?lang=en", data=form, follow_redirects=False).headers["location"] == "/contact?lang=en&sent=1"
        # a bot fills the hidden field: it is told "thank you" and nothing is kept
        assert c.post("/contact", data={**form, "website": "http://spam.example", "message": "buy pills now please"},
                      follow_redirects=False).status_code == 303
        # refused: sent too fast, forged token, bad email (what was typed comes back, escaped)
        fresh = legal.form_token(conn, time.time())  # made just now: a slow machine must not age it past the 3 s
        assert "انتهت صلاحية" in c.post("/contact", data={**form, "t": fresh}).text
        assert c.post("/contact", data={**form, "t": old[:-1] + ("1" if old[-1] == "0" else "0")}).status_code == 400
        r = c.post("/contact", data={**form, "email": "not-an-email", "message": "<script>alert(1)</script> hello"})
        assert r.status_code == 400 and "&lt;script&gt;" in r.text and "<script>alert" not in r.text
        # a message from another website is refused
        assert c.post("/contact", data=form, headers={"origin": "https://evil.example"}).status_code == 403
        # five messages a day per visitor
        for _ in range(3):
            assert c.post("/contact", data=form, follow_redirects=False).status_code == 303
        assert "كثيرة" in c.post("/contact", data=form).text
        conn.close()

        # the messages page exists only with a password, and asks for it
        assert c.get("/admin/messages").status_code == 404
        monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
        assert c.get("/admin/messages").status_code == 401
        assert c.get("/admin/messages", auth=("admin", "wrong")).status_code == 401
        r = c.get("/admin/messages", auth=("admin", "s3cret"))
        assert r.status_code == 200 and r.text.count("<article>") == 5 and "al-Jahiz" in r.text and "spam.example" not in r.text


def test_share_buttons_poems_and_404(client):
    import json as _json
    import re as _re
    from app import db, wikisource
    book = client.get("/book/1", follow_redirects=True).text
    for host in ("https://wa.me/?text=", "https://t.me/share/url?url=", "https://www.facebook.com/sharer/sharer.php?u="):
        assert host in book
    assert 'id="copyBtn"' in book and 'data-url="http://testserver/book/1/' in book
    # a poem from Wikisource is described as a creative work, not as a book
    conn = db.connect()
    pid = conn.execute("SELECT id FROM books WHERE cat='poe' LIMIT 1").fetchone()[0]
    conn.execute("UPDATE books SET curated=? WHERE id=?", (wikisource.WS_KIND, pid))
    conn.commit()
    conn.close()
    page = client.get("/book/%d" % pid, follow_redirects=True).text
    work = _json.loads(_re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, _re.S).group(1))["@graph"][1]
    assert work["@type"] == "CreativeWork" and "bookFormat" not in work
    # unknown addresses get the designed 404 page; the API keeps answering in JSON
    for url in ("/no/such/page", "/book/abc", "/book/999999999", "/category/nope"):
        r = client.get(url)
        assert r.status_code == 404 and r.headers["content-type"].startswith("text/html"), url
        assert 'name="robots" content="noindex"' in r.text and 'role="search"' in r.text and 'class="btn" href="/"' in r.text, url
    assert "Page not found" in client.get("/nothing-here?lang=en").text
    r = client.get("/api/nothing")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert client.get("/api/books", params={"limit": 0}).status_code == 422
    robots = client.get("/robots.txt").text
    assert robots.startswith("User-agent: Mediapartners-Google\nAllow: /\n")


def test_books_without_a_reading_link_are_removed(client, tmp_path):
    from app import db, importer
    conn = db.connect()
    assert db.prune_unreadable(conn) == 0  # nothing imported yet: hand-picked books are still waiting for their links
    make_csv(tmp_path / "pg.csv")
    importer.run(conn, limit=0, csv_path=str(tmp_path / "pg.csv"))
    linked = conn.execute("SELECT id FROM books WHERE curated=1 AND gid>0").fetchone()["id"]  # e.g. Pride and Prejudice
    lost = conn.execute("SELECT id, author_key FROM books WHERE curated=1 AND gid IS NULL AND author_key='gibran'").fetchone()
    removed = db.prune_unreadable(conn)
    assert removed > 0 and conn.execute("SELECT COUNT(*) FROM books WHERE " + db.UNREADABLE).fetchone()[0] == 0
    conn.close()
    assert client.get("/book/%d" % linked, follow_redirects=True).status_code == 200
    assert client.get("/book/%d" % lost["id"]).status_code == 404
    assert client.get("/author/gibran").status_code == 404  # no book left: no empty author page...
    assert "/author/gibran<" not in client.get("/sitemap-main.xml").text  # ...and not in the sitemap
    assert client.get("/api/books", params={"q": "gibran"}).json()["total"] == 0


def test_modern_arabic_books_from_safahat_and_open_library(client, tmp_path):
    import json as _json
    import re as _re
    from app import db, modern
    recs = [
        {"src": "safahat", "id": "61302419", "rank": 0, "title": "راغب عياد", "authors": ["بدر الدين أبو غازي"], "cats": ["arts", "biographies"]},
        {"src": "safahat", "id": "70959593", "rank": 1, "title": "فارس بلا وجود", "authors": ["إيتالو كالفينو"], "cats": ["novels"], "translated": True},
        {"src": "openlibrary", "id": "OL1W", "title": "أرض زيكولا", "authors": ["عمرو عبدالحميد", "Amr Abdelhamid"], "year": 2010,
         "publishers": ["دار عصير الكتب"], "subjects": ["Arabic fiction", "روايات"], "pages": 420, "cover": 12345, "want": 40, "ratings": 9},
        {"src": "openlibrary", "id": "OL2W", "title": "عقدك النفسية سجنك الأبدي", "authors": ["يوسف الحسيني"], "year": 2018, "subjects": []},
        {"src": "openlibrary", "id": "OL3W", "title": "راغب عياد", "authors": ["بدر الدين أبو غازي"], "year": 1972},  # already on Safahat
    ]
    path = tmp_path / "modern.jsonl"
    path.write_text("\n".join(_json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")
    conn = db.connect()
    res = modern.import_files(conn, [str(path)])
    assert res == {"safahat": 2, "openlibrary": 2, "skipped_duplicates": 1}
    ids = {r["ext"]: r["id"] for r in conn.execute("SELECT id, ext FROM books WHERE curated IN (4, 5)")}
    assert modern.import_files(conn, [str(path)]) == res  # importing again replaces, never doubles...
    assert {r["ext"]: r["id"] for r in conn.execute("SELECT id, ext FROM books WHERE curated IN (4, 5)")} == ids  # ...and keeps addresses
    rows = {r["title"]: r for r in conn.execute("SELECT * FROM books WHERE curated IN (4, 5)")}
    assert rows["عقدك النفسية سجنك الأبدي"]["cat"] == "dev" and rows["أرض زيكولا"]["cat"] == "nov"
    assert rows["فارس بلا وجود"]["origin"] == "w" and rows["راغب عياد"]["origin"] == "a"
    db.prune_unreadable(conn)  # they have a page to go to: never removed as unreadable
    assert conn.execute("SELECT COUNT(*) FROM books WHERE curated IN (4, 5)").fetchone()[0] == 4
    zik = rows["أرض زيكولا"]["id"]
    conn.close()

    found = client.get("/api/books", params={"q": "زيكولا"}).json()["items"]
    assert found and found[0]["x"] == "OL1W" and found[0]["k"] == 4
    assert client.get("/api/cover/%d" % zik).json()["url"] == "https://covers.openlibrary.org/b/id/12345-M.jpg"
    page = client.get("/book/%d" % zik, follow_redirects=True).text
    assert 'href="https://openlibrary.org/works/OL1W"' in page and "اعرض الكتاب على Open Library" in page
    assert "حقوق هذا الكتاب محفوظة" in page and "دار عصير الكتب" in page and "420" in page and "كتاب مجاني" not in page
    work = _json.loads(_re.search(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, _re.S).group(1))["@graph"][1]
    assert work["isAccessibleForFree"] is False and "potentialAction" not in work and work["datePublished"] == "2010"
    saf = client.get("/book/%d" % rows["راغب عياد"]["id"], follow_redirects=True).text
    assert 'href="https://www.safahat.org/books/61302419/"' in saf and "اقرأ على صفحات (هنداوي)" in saf
    m = client.get("/api/meta").json()
    assert any(c["key"] == "dev" and c["count"] == 1 for c in m["categories"])
    assert client.get("/category/dev").status_code == 200


def test_arabic_books_category(client):
    m = client.get("/api/meta").json()
    ara = next(c for c in m["categories"] if c["key"] == "ara")
    assert m["categories"][0]["key"] == "ara" and ara["ar"] == "الكتب العربية"  # first on the home page
    arabic = sum(l["count"] for l in m["languages"] if l["code"] == "ar")
    assert ara["count"] == arabic > 0
    r = client.get("/api/books", params={"cat": "ara", "limit": 200}).json()
    assert r["total"] == arabic and all(b["lg"] == "ar" for b in r["items"])
    # it still narrows down by words, and the books keep their own topic
    poets = client.get("/api/books", params={"cat": "ara", "q": "المتنبي"}).json()
    assert poets["total"] >= 1 and all(b["c"] != "ara" for b in poets["items"])
    page = client.get("/category/ara")
    assert page.status_code == 200 and "الكتب العربية" in page.text and 'href="/book/' in page.text


def test_modern_import_cleans_names_and_guesses_categories(client, tmp_path):
    import json as _json
    from app import db, modern
    recs = [
        {"src": "openlibrary", "id": "OL10W", "title": "خوف 2", "authors": ["مـسـلـم، أسـامـة"], "subjects": ["Arabic fiction"]},
        {"src": "openlibrary", "id": "OL11W", "title": "خوف", "authors": ["مسلم، أسامة"], "subjects": []},  # no subject: like his others
        {"src": "openlibrary", "id": "OL12W", "title": "رياض الصالحات", "authors": ["Badrān ʻAyyārī"], "subjects": ["Conduct of life", "Islam"]},
        {"src": "openlibrary", "id": "OL13W", "title": "گلستان", "authors": ["Saʻdī"], "subjects": []},  # Persian
        {"src": "openlibrary", "id": "OL14W", "title": "الروض العاطر", "authors": ["x"], "subjects": ["Erotic literature"]},
        {"src": "openlibrary", "id": "OL15W", "title": "المعتمد في علم الفرائض", "authors": ["y"], "subjects": ["Inheritance and succession"]},
    ]
    path = tmp_path / "ol.jsonl"
    path.write_text("\n".join(_json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")
    conn = db.connect()
    assert modern.import_files(conn, [str(path)])["openlibrary"] == 4  # the Persian and the erotic ones are left out
    got = {r["ext"]: r for r in conn.execute("SELECT * FROM books WHERE curated=4")}
    conn.close()
    assert got["OL11W"]["author_ar"] == "أسامة مسلم" and got["OL11W"]["cat"] == "hor"  # a horror writer's book
    assert got["OL12W"]["cat"] == "rel"  # manners in Islam: religion, not self-development
    assert got["OL15W"]["cat"] != "dev"  # "succession" is not "success"
    assert modern.fix_name("محفوظ، نجيب، 1911-2006") == "نجيب محفوظ"  # catalogue order and dates


def test_google_books_covers(client, monkeypatch, tmp_path):
    import json as _json
    from app import covers, db, modern
    calls = []

    def fake(url):
        calls.append(url)
        if "googleapis" in url:
            if "%D8%B2%D9%8A%D9%83%D9%88%D9%84%D8%A7" in url:  # زيكولا
                return {"items": [{"volumeInfo": {"title": "قصة أخرى", "imageLinks": {"thumbnail": "http://x/wrong"}}},
                                  {"volumeInfo": {"title": "أرض زيكولا", "imageLinks": {"thumbnail": "http://books.google.com/c?id=1&edge=curl"}}}]}
            return {"items": []}
        return {"docs": []}

    monkeypatch.setattr(covers, "fetch_json", fake)
    monkeypatch.setattr(covers, "MIN_GAP", 0)
    path = tmp_path / "ol.jsonl"
    path.write_text(_json.dumps({"src": "openlibrary", "id": "OL1W", "title": "أرض زيكولا", "authors": ["عمرو عبد الحميد"]},
                                ensure_ascii=False), encoding="utf-8")
    conn = db.connect()
    modern.import_files(conn, [str(path)])
    zik = conn.execute("SELECT id FROM books WHERE ext='OL1W'").fetchone()[0]
    conn.close()
    monkeypatch.delenv("GOOGLE_BOOKS_KEY", raising=False)
    assert client.get("/api/cover/%d" % zik).json()["url"] is None and calls == []  # no key: designed cover, no request
    monkeypatch.setenv("GOOGLE_BOOKS_KEY", "k")
    assert client.get("/api/cover/%d" % zik).json()["url"] == "https://books.google.com/c?id=1"  # the matching title only
    assert all("googleapis" in u for u in calls)  # Open Library is not asked again for its own book


def test_wikisource_books_are_dropped_poems_stay(client, tmp_path):
    from app import db, importer
    conn = db.connect()
    make_csv(tmp_path / "pg.csv")
    importer.run(conn, limit=0, csv_path=str(tmp_path / "pg.csv"))  # a catalogue that has been imported
    conn.execute("INSERT INTO books(ws,title,title_ar,cat,origin,lang,curated,ord,search) VALUES('ديوان','قصيدة','قصيدة','poe','a','ar',3,1,'قصيده')")
    conn.execute("INSERT INTO books(ws,title,title_ar,cat,origin,lang,curated,ord,search) VALUES('كتاب','كتاب فارغ','كتاب فارغ','his','a','ar',3,2,'كتاب فارغ')")
    linked = conn.execute("SELECT id FROM books WHERE curated=1 AND (gid IS NULL OR gid=0) LIMIT 1").fetchone()[0]
    conn.execute("UPDATE books SET ws='صفحة' WHERE id=?", (linked,))  # a hand-picked book only Wikisource had
    conn.commit()
    db.prune_unreadable(conn)
    kept = {r[0] for r in conn.execute("SELECT title FROM books WHERE curated=3")}
    assert kept == {"قصيدة"}
    assert not conn.execute("SELECT 1 FROM books WHERE id=?", (linked,)).fetchone()
    assert not conn.execute("SELECT 1 FROM books WHERE ws<>'' AND curated<>3").fetchone()
    conn.close()


def test_adsense_tag_on_every_page_and_ads_txt(client):
    tag = '<meta name="google-adsense-account" content="ca-pub-7058063023261152">'
    for url in ("/", "/?lang=en", "/book/1", "/category/poe", "/author/shakespeare", "/about", "/privacy", "/terms",
                "/contact", "/no/such/page"):
        r = client.get(url, follow_redirects=True)
        assert tag in r.text, url
        head = r.text.split("</head>")[0]
        assert tag in head, url  # inside <head>, where AdSense looks for it
    r = client.get("/ads.txt")
    assert r.status_code == 200 and r.text == "google.com, pub-7058063023261152, DIRECT, f08c47fec0942fa0\n"


def test_ad_units_on_content_pages_only(client, monkeypatch):
    monkeypatch.setenv("THIN_NOINDEX", "0")  # every book page shows its ad (the thin rule has its own test)
    unit = 'data-ad-slot="1844690351"'
    loader = "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7058063023261152"
    for url, n in (("/", 2), ("/?lang=en", 2), ("/category/poe", 1), ("/author/shakespeare", 1), ("/book/1", 1)):
        r = client.get(url, follow_redirects=True)
        csp = r.headers["content-security-policy"]
        nonce = csp.split("'nonce-")[1].split("'")[0]
        assert r.text.count(unit) == n and r.text.split("</head>")[0].count(loader) == 1, url
        assert "'strict-dynamic'" in csp and "frame-src https:" in csp and "frame-ancestors 'none'" in csp, url
        assert r.text.count("<script") == r.text.count('<script nonce="%s"' % nonce), url  # the only scripts that run
        assert r.headers["cross-origin-opener-policy"] == "same-origin-allow-popups"  # an ad's click may open its page
    book = client.get("/book/1", follow_redirects=True).text
    assert book.index('class="btns"') < book.index("</article>") < book.index('class="ad"')  # well below the read buttons
    # the in-feed unit: one item of a long book list, after the 8th book; the home page's script is told its name
    feed = 'data-ad-slot="6915772378"'
    cat = client.get("/category/nov").text
    items = cat.split('<ul class="rel">')[1].split("</ul>")[0].split("<li")[1:]
    assert cat.count(feed) == 1 and 'class="infeed"' in items[8] and len(items) >= 13
    assert '<meta name="warraq-infeed" content="ca-pub-7058063023261152|6915772378|-gg+g-1f-3w+ci">' in client.get("/").text
    for url in ("/about", "/privacy", "/terms", "/contact", "/no/such/page"):  # no ads beside thin or legal content
        r = client.get(url)
        assert unit not in r.text and loader not in r.text and "'strict-dynamic'" not in r.headers["content-security-policy"], url
    monkeypatch.setenv("ADS", "0")  # a test copy of the site: no ads, the strict policies as before
    r = client.get("/")
    assert unit not in r.text and loader not in r.text and "script-src 'self'" in r.headers["content-security-policy"]
    assert "warraq-infeed" not in r.text and "6915772378" not in client.get("/category/nov").text
    r = client.get("/book/1", follow_redirects=True)
    assert unit not in r.text and "'strict-dynamic'" not in r.headers["content-security-policy"]


def test_thin_pages_stay_out_of_search_sitemaps_and_ads(client, monkeypatch, tmp_path):
    """THIN_NOINDEX (on by default): a catalogue record with no words of its own is noindex, unlisted and ad-free;
    the library's own texts make a page whole: book texts, author biographies, category texts, articles."""
    import json as _json
    from app import content, db
    d = tmp_path / "content"
    (d / "articles").mkdir(parents=True)
    conn = db.connect()
    conn.execute("UPDATE books SET gid=1122 WHERE id=1")  # Hamlet, linked to its Gutenberg number as the import does
    # Seed test description directly into book_descriptions (DB takes precedence over books.json)
    _en_about = _json.dumps(["Hamlet, the prince of Denmark, returns home. " * 3])
    _en_ctx   = _json.dumps(["See also [Macbeth](/book/2?lang=en)."])
    _ar_about = _json.dumps(["هاملت أمير الدنمارك يعود إلى بلده."])
    _ar_ctx   = _json.dumps(["سياقها."])
    conn.execute("INSERT OR REPLACE INTO book_descriptions(gid,en,en_ctx,ar,ar_ctx) VALUES(1122,?,?,?,?)",
                 (_en_about, _en_ctx, _ar_about, _ar_ctx))
    # Make sure Macbeth (gid=1533) has no description so it stays thin
    conn.execute("DELETE FROM book_descriptions WHERE gid=1533")
    conn.commit()
    conn.close()
    (d / "books.json").write_text(_json.dumps({}), encoding="utf-8")  # DB is authoritative now
    (d / "authors.json").write_text(_json.dumps({"plato": {"ar": ["سيرة أفلاطون الفيلسوف اليوناني."], "en": ["Plato's life."]}}), encoding="utf-8")
    (d / "categories.json").write_text(_json.dumps({"nov": {"ar": ["نص تصنيف الروايات."], "en": ["The novels text."]}}), encoding="utf-8")
    (d / "home.json").write_text(_json.dumps({"ar": ["المكتبة بكلماتها."], "en": ["The library in its words."]}), encoding="utf-8")
    (d / "articles" / "01-test.md").write_text(
        "---\nslug: test-article\ntitle: مقال تجريبي\ndescription: وصف المقال\ndate: 2026-10-21\n---\nمقدمة.\n\n## أول\n\n"
        "فقرة فيها [رابط](/book/1) و**كلمة بارزة**.\n\n## ثان\n\n- بند\n- بند آخر\n\n## ثالث\n\n> شطر ... شطر\n\n## رابع\n\n"
        "خاتمة <script>alert(1)</script> [سيئ](javascript:alert(1)).", encoding="utf-8")
    monkeypatch.setattr(content, "DIR", str(d))
    content._cache.clear()
    unit = 'data-ad-slot="1844690351"'

    # a book with a text of its own: indexed, with its ad, its text, and a description taken from it
    hamlet = client.get("/book/1", follow_redirects=True).text
    assert 'name="robots" content="index,follow' in hamlet and unit in hamlet
    assert "Context and significance" in hamlet and '<meta name="description" content="Hamlet, the prince of Denmark' in hamlet
    assert '<a href="/book/2?lang=en">Macbeth</a>' in hamlet and "<title>Hamlet by William Shakespeare | Al-Warraq Library</title>" in hamlet
    # a catalogue record alone: out of search results and ads, under the strict policy
    macbeth = client.get("/book/2", follow_redirects=True)
    assert 'name="robots" content="noindex,follow"' in macbeth.text and unit not in macbeth.text
    assert "'strict-dynamic'" not in macbeth.headers["content-security-policy"] and "Catalogue details" in macbeth.text
    books_map = client.get("/sitemap-books-1.xml").text
    assert "/book/1/" in books_map and "/book/2/" not in books_map and client.get("/sitemap-books-2.xml").status_code == 404
    # authors: a biography makes the page whole; a short list of titles does not
    plato = client.get("/author/plato").text
    assert "سيرة أفلاطون" in plato and 'name="robots"' not in plato and unit in plato
    kafka = client.get("/author/kafka").text
    assert 'name="robots" content="noindex,follow"' in kafka and unit not in kafka
    main_map = client.get("/sitemap-main.xml").text
    assert "/author/plato</loc>" in main_map and "/author/kafka</loc>" not in main_map and "/articles/test-article</loc>" in main_map
    # a category's own text, the home page's own words and articles; a search result page is not indexed
    assert "نص تصنيف الروايات" in client.get("/category/nov").text and "The novels text" in client.get("/category/nov?lang=en").text
    home = client.get("/").text
    assert "المكتبة بكلماتها" in home and 'href="/articles/test-article"' in home and 'name="robots" content="index,follow"' in home
    assert 'name="robots" content="noindex,follow"' in client.get("/?q=hamlet").text
    # the articles: written in Arabic, Article data, two ads, nothing unsafe passes from the text
    page = client.get("/articles/test-article")
    a = page.text
    assert page.status_code == 200 and "<h1>مقال تجريبي</h1>" in a and '"Article"' in a and a.count(unit) == 2
    assert '<a href="/book/1">رابط</a>' in a and "<strong>كلمة بارزة</strong>" in a and "<li>بند آخر</li>" in a and 'class="verse"' in a
    assert "<script>alert" not in a and 'href="javascript' not in a
    assert '<link rel="canonical" href="http://testserver/articles/test-article">' in client.get("/articles/test-article?lang=en").text
    assert client.get("/articles/nope").status_code == 404 and 'href="/articles/test-article"' in client.get("/articles").text
    # THIN_NOINDEX off: every book page indexed and with ads, as before
    monkeypatch.setenv("THIN_NOINDEX", "0")
    assert unit in client.get("/book/2", follow_redirects=True).text


def test_takedown_requests(client):
    from app import db, legal
    r = client.get("/takedown?u=/book/1")
    assert r.status_code == 200 and 'name="robots" content="noindex,follow"' in r.text and 'value="http://testserver/book/1"' in r.text
    assert 'href="/takedown' in client.get("/book/1", follow_redirects=True).text  # every book page links to it
    assert 'href="/takedown"' in client.get("/terms").text and 'href="/articles"' in client.get("/about").text  # and the footer
    conn = db.connect()
    form = {"name": "Rights Holder", "email": "owner@example.com", "url": "http://testserver/book/1",
            "reason": "I hold the translation rights to this edition.", "t": legal.form_token(conn, time.time() - 60)}
    r = client.post("/takedown", data=form, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/takedown?sent=1"
    row = conn.execute("SELECT * FROM contact_messages ORDER BY id DESC LIMIT 1").fetchone()
    assert row["topic"] == "takedown" and "http://testserver/book/1" in row["message"] and "translation rights" in row["message"]
    bad = client.post("/takedown", data={**form, "reason": "short", "url": "<b>x</b>"})
    assert bad.status_code == 400 and "20" in bad.text and "&lt;b&gt;x&lt;/b&gt;" in bad.text
    conn.close()
    privacy = client.get("/privacy").text
    assert "warraq_lang" in privacy and 'href="https://www.google.com/settings/ads"' in privacy and 'href="mailto:alwarraqibrary@gmail.com"' in privacy


def test_static_files_are_cached(client):
    assert client.get("/style.css?v=21").headers["cache-control"] == "public, max-age=31536000, immutable"
    assert client.get("/logo.svg").headers["cache-control"] == "public, max-age=604800"
    assert client.get("/").headers["cache-control"] == "no-cache" and client.get("/about").headers["cache-control"] == "no-cache"


def test_google_analytics_on_every_page(client, monkeypatch):
    loader = '<script async src="https://www.googletagmanager.com/gtag/js?id=G-RB47QYRPE9"></script>'
    setup = 'src="/ga.js?v=1" data-id="G-RB47QYRPE9"></script>'
    for url in ("/", "/?lang=en", "/category/nov", "/author/shakespeare", "/book/1", "/about", "/privacy", "/terms",
                "/contact", "/no/such/page"):
        r = client.get(url, follow_redirects=True)
        head = r.text.split("</head>")[0]
        csp = r.headers["content-security-policy"]
        assert head.count("googletagmanager.com/gtag/js") == 1 and setup in head, url  # once, in the head
        if "'nonce-" in csp:  # the pages with ads: both scripts carry the nonce
            nonce = csp.split("'nonce-")[1].split("'")[0]
            assert r.text.count("<script") == r.text.count('<script nonce="%s"' % nonce), url
        else:  # the strict policy lets Google's loader in and its reports out, and nothing inline
            assert loader in head and "script-src 'self' https://www.googletagmanager.com;" in csp, url
            assert "https://*.google-analytics.com" in csp and "'unsafe-inline' https://fonts" in csp and "script-src 'self' 'unsafe" not in csp
    ga = client.get("/ga.js")
    assert ga.status_code == 200 and "gtag('config', id)" in ga.text and "analytics_storage: 'denied'" in ga.text
    privacy = client.get("/privacy").text  # the privacy policy names it, its cookies and how to opt out
    assert "Google Analytics" in privacy and "_ga" in privacy and "tools.google.com/dlpage/gaoptout" in privacy
    assert "single cookie" not in client.get("/privacy?lang=en").text
    monkeypatch.setenv("ANALYTICS", "0")  # a test copy of the site measures nothing
    assert "googletagmanager" not in client.get("/").text and "ga.js" not in client.get("/about").text


def test_api_docs_are_hidden_unless_asked(tmp_path, monkeypatch):
    monkeypatch.setenv("WARRAQ_DB", str(tmp_path / "t.db"))
    monkeypatch.delenv("API_DOCS", raising=False)
    from app.main import create_app
    with TestClient(create_app()) as c:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert c.get(path).status_code == 404, path
        assert c.get("/api/health").json() == {"ok": True}
    monkeypatch.setenv("API_DOCS", "1")
    with TestClient(create_app()) as c:
        assert c.get("/openapi.json").status_code == 200 and c.get("/docs").status_code == 200


def test_horror_and_mystery(client, tmp_path):
    from app import catalog, db, importer, modern
    assert catalog.categorize("Horror tales; Science fiction", "") == "hor"
    assert catalog.categorize("Detective and mystery stories", "Crime Fiction") == "mys"
    assert catalog.categorize("Love stories", "") == "nov"
    assert modern.safahat_category("علامة الأربعة", ["detective.fiction"]) == "mys"
    assert modern.safahat_category("القضية الغريبة للدكتور جيكل ومستر هايد", ["novels"]) == "hor"
    assert modern.safahat_category("تحوُّل", ["science.fiction"], ["ماري شيلي"]) == "hor"
    assert modern.safahat_category("لويزيتو: قصة حب", ["novels"]) == "nov"
    assert modern.ol_category("قصص رعب من الريف", []) == "hor"
    assert modern.ol_category("دور سلاح الرعب في سياسة المغول", ["Politics and government"]) != "hor"
    assert modern.known_author_category("حسن الجندي") == "hor"
    # Gutenberg books move into the new category without being imported again: same ids
    make_csv(tmp_path / "pg.csv", extra=3)
    conn = db.connect()
    importer.run(conn, limit=0, csv_path=str(tmp_path / "pg.csv"))
    before = conn.execute("SELECT id, cat FROM books WHERE gid=20000").fetchone()  # an ordinary imported novel
    assert before["cat"] == "nov"
    lines = open(tmp_path / "pg.csv", encoding="utf-8").read().splitlines(keepends=True)
    (tmp_path / "pg2.csv").write_text("".join(l.replace("Fiction", "Ghost stories") if l.startswith("20000,") else l for l in lines),
                                      encoding="utf-8")
    assert importer.recategorize(conn, str(tmp_path / "pg2.csv")) >= 1
    assert conn.execute("SELECT id, cat FROM books WHERE gid=20000").fetchone()[:] == (before["id"], "hor")
    conn.close()


def test_horror_ranked_by_downloads_and_hathi_titles(client, tmp_path):
    from app import db, importer
    make_csv(tmp_path / "pg.csv", extra=3)
    conn = db.connect()
    importer.run(conn, limit=0, csv_path=str(tmp_path / "pg.csv"))
    rows = conn.execute("SELECT id, gid FROM books WHERE gid IN (20000, 20001, 20002)").fetchall()
    conn.executemany("UPDATE books SET cat='hor' WHERE id=?", [(r["id"],) for r in rows])
    conn.commit()
    pages = {"horror": [{"id": 20001, "download_count": 900}, {"id": 20002, "download_count": 50}, {"id": 999999, "download_count": 5000}]}

    def fake(url):  # Gutendex: one page per topic, the most downloaded first
        topic = url.split("topic=")[1].replace("+", " ")
        return {"results": pages.get(topic, []), "next": None}

    assert importer.rank_horror(conn, fetch_json=fake, pause=0) == 2  # a book we do not have is skipped
    order = [r["gid"] for r in conn.execute("SELECT gid FROM books WHERE cat='hor' ORDER BY ord")]
    assert order[:2] == [20001, 20002] and order[-1] == 20000
    # HathiTrust titles that say so outright
    for i, title in enumerate(["Ghost stories of an antiquary", "The vampire bat in Brazil", "The adventures of Sherlock Holmes",
                               "A history of Rome"]):
        conn.execute("INSERT INTO books(htid,title,cat,origin,lang,curated,ord,search) VALUES(?,?,'gen','w','en',2,?,?)",
                     ("h.%d" % i, title, 2000000 + i, title.lower()))
    conn.commit()
    assert importer.recategorize_hathi_titles(conn) == {"hor": 1, "mys": 1}
    cats = {r["title"]: r["cat"] for r in conn.execute("SELECT title, cat FROM books WHERE curated=2")}
    assert cats["Ghost stories of an antiquary"] == "hor" and cats["The vampire bat in Brazil"] == "gen"
    assert cats["The adventures of Sherlock Holmes"] == "mys" and cats["A history of Rome"] == "gen"
    conn.close()
