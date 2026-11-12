"""Parsery serwisów na próbkach odpowiedzi, błędy źródeł, cache i pobieranie obrazów."""
import time

import pytest
import requests

import metadata as meta

LUBIMY_HTML = """
<div class="book-card book-card--l"><div class="book-card__primary">
 <img class="book-card__cover-image" src="https://s.lubimyczytac.pl/upload/books/1/170x243.jpg">
 <a class="book-card__title" href="/ksiazka/138913/wiedzmin"> Wiedźmin </a>
 <div class="book-card__author"><a>Andrzej Sapkowski</a></div>
</div></div>
<div class="book-card"><a class="book-card__title" href="https://lubimyczytac.pl/ksiazka/2/x">Bez okładki</a></div>
<div class="book-card">bez tytułu</div>
"""

UPOLUJE_HTML = """
<a href="/oferta,67813,ostatnie_zyczenie_wiedzmin_-_audiobook.html"
   title="Ostatnie życzenie: Wiedźmin - audiobook mp3">x</a>
<a href="/oferta,67813,ostatnie_zyczenie_wiedzmin_-_audiobook.html"
   title="Ostatnie życzenie: Wiedźmin - audiobook mp3">duplikat</a>
<a href="/oferta,5,inna.html" title="Inna książka ebook pdf, mobi, epub">y</a>
"""

UPOLUJE_DETAIL = """<html><head><title>Tytuł - mp3 - Andrzej Sapkowski - UpolujEbooka.pl</title>
<script type="application/ld+json">{"@type": "Book", "name": "T",
 "description": "Opis z &oacute;smym znakiem", "image": ["https://img/x.jpg"]}</script>
</head></html>"""


class Resp:
    def __init__(self, text="", data=None, status=200):
        self.text, self._data, self.status_code = text, data, status

    def json(self):
        if self._data is None:
            raise ValueError("brak JSON")
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


@pytest.fixture(autouse=True)
def _no_sleep_no_cache(monkeypatch):
    monkeypatch.setattr(meta, "MIN_INTERVAL", 0)
    meta.clear_cache()
    yield
    meta.clear_cache()


# ---------------------------------------------------------------- parsery

def test_lubimyczytac_parses_cards(monkeypatch):
    monkeypatch.setattr(meta, "_get", lambda url, **kw: Resp(LUBIMY_HTML))
    r = meta.search_lubimyczytac("wiedzmin")
    assert [x["title"] for x in r] == ["Wiedźmin", "Bez okładki"]
    assert r[0]["author"] == "Andrzej Sapkowski"
    assert r[0]["cover_url"].endswith("170x243.jpg")
    assert r[0]["url"] == "https://lubimyczytac.pl/ksiazka/138913/wiedzmin"
    assert r[1]["cover_url"] == ""


def test_upolujebooka_dedupes_and_strips_shop_suffixes(monkeypatch):
    monkeypatch.setattr(meta, "_get", lambda url, **kw: Resp(UPOLUJE_HTML))
    r = meta.search_upolujebooka("wiedzmin")
    assert [x["title"] for x in r] == ["Ostatnie życzenie: Wiedźmin", "Inna książka"]
    assert r[0]["url"].startswith("https://upolujebooka.pl/oferta,67813")


def test_upolujebooka_details_json_ld_and_entities(monkeypatch):
    monkeypatch.setattr(meta, "_get", lambda url, **kw: Resp(UPOLUJE_DETAIL))
    d = meta.details_upolujebooka("https://upolujebooka.pl/oferta,1,x.html")
    assert d["description"] == "Opis z ósmym znakiem"
    assert d["cover_url"] == "https://img/x.jpg"
    assert d["author"] == "Andrzej Sapkowski"          # z tytułu strony


def test_google_has_no_language_restriction_and_uses_key(monkeypatch):
    seen = {}

    def fake(url, **kw):
        seen.update(kw["params"])
        seen["header"] = (kw.get("extra_headers") or {}).get("X-Goog-Api-Key")
        return Resp(data={"items": [{"volumeInfo": {
            "title": "Dune", "authors": ["Frank Herbert"],
            "imageLinks": {"thumbnail": "http://books.google/x.jpg"}}}]})
    monkeypatch.setattr(meta, "_get", fake)
    meta.configure(google_api_key="  SEKRET  ")
    try:
        r = meta.search_google("dune")
    finally:
        meta.configure(google_api_key="")
    assert "langRestrict" not in seen            # poprzednio: sztywno "pl"
    assert seen["header"] == "SEKRET"            # klucz w nagłówku...
    assert "key" not in seen                     # ...nie w URL (nie trafi do logów)
    assert r[0]["cover_url"] == "https://books.google/x.jpg"   # http -> https


def test_google_omits_key_when_not_configured(monkeypatch):
    seen = {}
    monkeypatch.setattr(meta, "_get",
                        lambda url, **kw: (seen.update(kw["params"]), Resp(data={}))[1])
    meta.configure(google_api_key="")
    assert meta.search_google("x") == [] and "key" not in seen


def test_apple_falls_back_to_ebooks_and_upgrades_artwork(monkeypatch):
    calls = []

    def fake(url, **kw):
        calls.append(kw["params"]["media"])
        if kw["params"]["media"] == "audiobook":
            return Resp(data={"results": []})
        return Resp(data={"results": [{"collectionName": "Książka", "artistName": "A",
                                       "artworkUrl100": "https://x/100x100bb.jpg",
                                       "description": "<b>Opis</b><br/>drugi"}]})
    monkeypatch.setattr(meta, "_get", fake)
    r = meta.search_apple_books("x")
    assert calls == ["audiobook", "ebook"]
    assert r[0]["cover_url"].endswith("600x600bb.jpg") and r[0]["description"] == "Opis drugi"


def test_audible_picks_largest_cover(monkeypatch):
    monkeypatch.setattr(meta, "_get", lambda url, **kw: Resp(data={"products": [{
        "title": " Dune ", "asin": "B1", "authors": [{"name": "Frank Herbert"}],
        "product_images": {"500": "https://img/500.jpg"}, "publisher_summary": "<p>Opis</p>"}]}))
    r = meta.search_audible("dune")
    assert r[0]["title"] == "Dune" and r[0]["cover_url"].endswith("500.jpg")
    assert r[0]["url"].endswith("/B1") and r[0]["description"] == "Opis"


# ---------------------------------------------------------------- search_all / błędy

def _fake_sources(monkeypatch, **behaviour):
    def make(name):
        def fn(q, limit=6):
            b = behaviour.get(name)
            if isinstance(b, Exception):
                raise b
            if callable(b):
                return b()
            return [{"source": name, "title": f"{q} {name}", "author": "", "description": "",
                     "cover_url": "u", "url": ""}]
        return fn
    monkeypatch.setattr(meta, "_SOURCES", {n: make(n) for n in meta._SOURCES})


def test_search_all_reports_per_source_errors_and_keeps_order(monkeypatch):
    err429 = requests.HTTPError("429")
    err429.response = Resp(status=429)
    _fake_sources(monkeypatch, **{"Google Books": err429,
                                  "Open Library": requests.ConnectTimeout("x"),
                                  "Audible": requests.ConnectionError("x"),
                                  "upolujebooka.pl": ValueError("zły json")})
    out = meta.search_all("dune", "pl")
    assert [r["source"] for r in out.results] == ["lubimyczytac.pl", "Apple Books"]
    assert out.errors == {"upolujebooka.pl": ("bad_response", ""),
                          "Audible": ("offline", ""),
                          "Google Books": ("rate_limit", 429),
                          "Open Library": ("timeout", "")}


def test_search_all_language_changes_order(monkeypatch):
    _fake_sources(monkeypatch)
    assert meta.search_all("x", "pl", use_cache=False).results[0]["source"] == "lubimyczytac.pl"
    assert meta.search_all("x", "en", use_cache=False).results[0]["source"] == "Audible"


def test_search_all_deadline_does_not_wait_for_hanging_source(monkeypatch):
    _fake_sources(monkeypatch, **{"Open Library": lambda: time.sleep(3) or []})
    monkeypatch.setattr(meta, "SEARCH_DEADLINE", 0.4)
    t0 = time.time()
    out = meta.search_all("x", "pl")
    assert time.time() - t0 < 2.0
    assert out.errors == {"Open Library": ("timeout", "")}
    assert len(out.results) == 5


def test_search_all_caches_only_complete_results(monkeypatch):
    calls = {"n": 0}

    def counting():
        calls["n"] += 1
        return []
    _fake_sources(monkeypatch, **{"Audible": counting})
    meta.search_all("Dune", "pl")
    meta.search_all("dune ", "pl")                  # ten sam klucz (fold) -> z cache
    assert calls["n"] == 1
    _fake_sources(monkeypatch, **{"Audible": requests.ConnectionError("x")})
    meta.clear_cache()
    meta.search_all("dune", "pl")
    meta.search_all("dune", "pl")                   # częściowa awaria nie jest cache'owana
    assert not meta._cache


def test_error_code_mapping():
    r429 = requests.HTTPError("x")
    r429.response = Resp(status=429)
    r503 = requests.HTTPError("x")
    r503.response = Resp(status=503)
    assert meta.error_code(r429) == ("rate_limit", 429)
    assert meta.error_code(r503) == ("http", 503)
    assert meta.error_code(requests.ReadTimeout()) == ("timeout", "")
    assert meta.error_code(requests.ConnectionError()) == ("offline", "")
    assert meta.error_code(KeyError("k")) == ("bad_response", "")
    assert meta.error_code(RuntimeError("x")) == ("error", "RuntimeError")


def test_get_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(meta.requests, "get", lambda *a, **k: Resp(status=429))
    with pytest.raises(requests.HTTPError):
        meta._get("https://example.com/x")


def test_throttle_spaces_requests_to_same_host(monkeypatch):
    monkeypatch.setattr(meta, "MIN_INTERVAL", 0.15)
    meta._last_call.clear()
    t0 = time.monotonic()
    meta._throttle("host-a")
    meta._throttle("host-a")
    meta._throttle("host-b")                        # inny host nie czeka
    elapsed = time.monotonic() - t0
    assert 0.14 <= elapsed < 0.6


def test_user_agent_is_honest():
    ua = meta.HEADERS["User-Agent"]
    assert ua.startswith("AudiobookPlayer/") and "github.com" in ua and "Chrome" not in ua


# ---------------------------------------------------------------- best_match / okładki

def test_best_match_prefers_title_and_author():
    results = [
        {"title": "Dune Messiah", "author": "Frank Herbert", "cover_url": "a"},
        {"title": "Dune", "author": "Frank Herbert", "cover_url": "b"},
        {"title": "Diuna", "author": "Inny", "cover_url": ""},
    ]
    best, score = meta.best_match(results, "Dune", "Frank Herbert")
    assert best["title"] == "Dune" and score > 0.9
    assert meta.best_match(results, "Zupełnie coś innego", "")[0] is None
    assert meta.best_match([], "x") == (None, 0.0)


def test_fill_missing_covers_only_touches_incomplete_results(monkeypatch):
    calls = []
    monkeypatch.setattr(meta, "details_upolujebooka",
                        lambda url: calls.append(url) or {"cover_url": "https://c/x.jpg"})
    rs = [{"source": "upolujebooka.pl", "url": "https://u/1", "cover_url": ""},
          {"source": "Audible", "url": "https://a/1", "cover_url": "https://have"},
          {"source": "Google Books", "url": "https://g/1", "cover_url": ""}]
    meta.fill_missing_covers(rs)
    assert calls == ["https://u/1"]
    assert rs[0]["cover_url"] == "https://c/x.jpg" and rs[2]["cover_url"] == ""


class FakeStream:
    def __init__(self, body, headers=None, status=200):
        self.body, self.headers, self.status_code = body, headers or {}, status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        Resp(status=self.status_code).raise_for_status()

    def iter_content(self, n):
        for i in range(0, len(self.body), n):
            yield self.body[i:i + n]


def test_fetch_image_accepts_real_image_rejects_html_and_oversized(monkeypatch):
    jpeg = b"\xff\xd8\xff\xe0" + b"x" * 100
    urls = []

    def fake_get(url, **kw):
        urls.append(url)
        if "html" in url:
            return FakeStream(b"<html>captive portal</html>")
        if "big" in url:
            return FakeStream(b"\xff\xd8\xff" + b"x" * 5000)
        if "claims-big" in url:
            return FakeStream(jpeg, {"Content-Length": "999999999"})
        return FakeStream(jpeg)
    monkeypatch.setattr(meta.requests, "get", fake_get)
    assert meta.fetch_image_bytes("https://x/ok.jpg") == jpeg
    assert meta.fetch_image_bytes("https://x/html.jpg") is None
    assert meta.fetch_image_bytes("https://x/big.jpg", max_bytes=1000) is None
    assert meta.fetch_image_bytes("https://x/claims-big.jpg", max_bytes=1000) is None


def test_fetch_image_prefers_https_then_falls_back(monkeypatch):
    jpeg = b"\xff\xd8\xff" + b"x" * 20
    urls = []

    def fake_get(url, **kw):
        urls.append(url)
        if url.startswith("https://"):
            raise requests.ConnectionError("brak https")
        return FakeStream(jpeg)
    monkeypatch.setattr(meta.requests, "get", fake_get)
    assert meta.fetch_image_bytes("http://stary.serwis/c.jpg") == jpeg
    assert urls == ["https://stary.serwis/c.jpg", "http://stary.serwis/c.jpg"]


def test_looks_like_image_signatures():
    assert meta.looks_like_image(b"\x89PNG\r\n\x1a\n....")
    assert meta.looks_like_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
    assert meta.looks_like_image(b"GIF89a")
    assert not meta.looks_like_image(b"<!DOCTYPE html>")
