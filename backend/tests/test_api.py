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
    assert len(m["categories"]) == 17
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
    assert client.get("/api/books", params={"q": "synthetic"}).json()["total"] > 70000

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
    assert res == again and res["poems"] == 1 and res["linked"] == 1  # Risalat al-Ghufran is a hand-picked book
    m._meta_cache.clear()

    hit = client.get("/api/books", params={"q": "البيداء"}).json()["items"]
    assert len(hit) == 1 and hit[0]["ws"] and hit[0]["ak"] == "mutanabbi" and hit[0]["c"] == "poe"
    meta = client.get("/api/meta").json()
    assert meta["poem_total"] == 1 and meta["poets"][0]["ar"] == "المتنبي"
    poets = client.get("/api/books", params={"au": meta["poets"][0]["ar"], "cat": "poe"}).json()
    assert hit[0]["id"] in [b["id"] for b in poets["items"]] and all(b["aa"] == "المتنبي" for b in poets["items"])
    page = client.get("/book/%d" % hit[0]["id"], follow_redirects=True).text
    assert "ar.wikisource.org/wiki/" in page
    ghufran = [b for b in client.get("/api/books", params={"q": "الغفران"}).json()["items"] if b["ws"]]
    assert ghufran and ghufran[0]["ak"] == "maarri"  # linked, not duplicated
    assert client.get("/api/cover/%d" % hit[0]["id"]).json()["url"] is None  # no Open Library lookup for poems


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
        assert client.get("/api/books", params={"q": q}).json()["total"] == expected, q
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
