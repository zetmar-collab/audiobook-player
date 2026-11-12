"""Pobieranie metadanych o książkach z serwisów polskich i zagranicznych.

Źródła polskie: lubimyczytac.pl, upolujebooka.pl
Źródła zagraniczne: Audible, Apple Books, Google Books, Open Library

Każde źródło zwraca listę słowników:
{source, title, author, description, cover_url, url}

`search_all` odpytuje źródła równolegle i zwraca `SearchOutcome`: wyniki oraz błędy
poszczególnych źródeł (żeby interfejs odróżnił „brak wyników" od „brak połączenia").
Moduł nie zależy od Qt.
"""
import difflib
import html as _html
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

import appinfo
from models import fold

log = logging.getLogger("audiobookplayer")

#: Uczciwy User-Agent z adresem projektu (serwisy akceptują go — sprawdzone) zamiast
#: podszywania się pod przeglądarkę.
HEADERS = {
    "User-Agent": appinfo.USER_AGENT,
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.5",
}
#: (connect, read) — krótki timeout połączenia, żeby niedostępne źródło
#: nie opóźniało równoległego wyszukiwania w pozostałych serwisach.
TIMEOUT = (5, 12)
SEARCH_DEADLINE = 25          # s — twardy limit całego wyszukiwania
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIN_INTERVAL = 0.25           # s między zapytaniami do tego samego hosta
CACHE_TTL = 600               # s

CONFIG = {"google_api_key": os.environ.get("GOOGLE_BOOKS_API_KEY", "")}


def configure(**kwargs):
    """Ustawienia z zewnątrz, np. configure(google_api_key="...")."""
    for k, v in kwargs.items():
        if k in CONFIG:
            CONFIG[k] = (v or "").strip()


# ---------------------------------------------------------------- HTTP

_throttle_lock = threading.Lock()
_last_call = {}


def _throttle(host):
    """Nie bombarduje jednego serwisu: min. MIN_INTERVAL między zapytaniami do hosta."""
    with _throttle_lock:
        now = time.monotonic()
        wait_for = _last_call.get(host, 0) + MIN_INTERVAL - now
        _last_call[host] = now + max(wait_for, 0)
    if wait_for > 0:
        time.sleep(wait_for)


def _get(url, **kw):
    _throttle(urlparse(url).netloc)
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


def error_code(exc):
    """Zamienia wyjątek sieciowy na (kod, szczegół) do przetłumaczenia w interfejsie."""
    if isinstance(exc, requests.HTTPError):
        status = getattr(exc.response, "status_code", 0)
        return ("rate_limit", status) if status == 429 else ("http", status)
    if isinstance(exc, requests.Timeout):
        return ("timeout", "")
    if isinstance(exc, requests.ConnectionError):
        return ("offline", "")
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return ("bad_response", "")
    return ("error", type(exc).__name__)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _strip_html(text):
    """Usuwa znaczniki HTML i dekoduje encje (opisy z Audible/Apple je zawierają)."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>|</p>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return _clean(_html.unescape(text))


# ---------------------------------------------------------------- lubimyczytac

def search_lubimyczytac(query, limit=6):
    results = []
    r = _get("https://lubimyczytac.pl/szukaj/ksiazki", params={"phrase": query})
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.select("div.book-card")[:limit]:
        a = card.select_one("a.book-card__title")
        if not a:
            continue
        author_el = card.select_one(".book-card__author")
        img = card.select_one("img.book-card__cover-image")
        cover = ""
        if img:
            cover = img.get("data-src") or img.get("src") or ""
        url = a.get("href") or ""
        if url.startswith("/"):
            url = "https://lubimyczytac.pl" + url
        results.append({
            "source": "lubimyczytac.pl",
            "title": _clean(a.get_text()),
            "author": _clean(author_el.get_text()) if author_el else "",
            "description": "",
            "cover_url": cover,
            "url": url,
        })
    return results


def details_lubimyczytac(url):
    """Dociąga opis (i lepszą okładkę) ze strony książki."""
    out = {}
    try:
        soup = BeautifulSoup(_get(url).text, "html.parser")
        desc = soup.select_one("div#book-description") or soup.select_one("div.collapse-content")
        if desc:
            out["description"] = _clean(desc.get_text(" "))
        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            out["cover_url"] = og["content"]
    except Exception as e:
        log.debug("details_lubimyczytac: %s", e)
    return out


# ---------------------------------------------------------------- upolujebooka

def search_upolujebooka(query, limit=6):
    results = []
    r = _get(f"https://upolujebooka.pl/szukaj,{quote(query)}.html")
    soup = BeautifulSoup(r.text, "html.parser")
    seen = set()
    # linki do ofert mają postać /oferta,<id>,<slug>.html; tytuł w atrybucie title
    for a in soup.select('a[href*="oferta,"][title]'):
        href = a.get("href") or ""
        title = _clean(a.get("title"))
        # zdejmij dopiski sklepowe z końca tytułu
        title = re.sub(r"[\s,–-]*(ebook|audiobook|pdf|mobi|epub|mp3)([\s,–-]*(pdf|mobi|epub|mp3))*\s*$",
                       "", title, flags=re.I).strip(" ,-–")
        if not title or href in seen:
            continue
        seen.add(href)
        if href.startswith("/"):
            href = "https://upolujebooka.pl" + href
        elif not href.startswith("http"):
            href = "https://upolujebooka.pl/" + href
        results.append({
            "source": "upolujebooka.pl",
            "title": title,
            "author": "",
            "description": "",
            "cover_url": "",
            "url": href,
        })
        if len(results) >= limit:
            break
    return results


def details_upolujebooka(url):
    """Czyta JSON-LD (schema.org/Book) ze strony oferty."""
    out = {}
    try:
        soup = BeautifulSoup(_get(url).text, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict) or item.get("@type") not in ("Book", "Product"):
                    continue
                if item.get("description") and "description" not in out:
                    out["description"] = _clean(_html.unescape(item["description"]))
                author = item.get("author")
                if author:
                    if isinstance(author, list):
                        author = author[0]
                    name = author.get("name") if isinstance(author, dict) else str(author)
                    if name:
                        out["author"] = _clean(_html.unescape(name))
                img = item.get("image")
                if img:
                    out["cover_url"] = img[0] if isinstance(img, list) else img
        if "author" not in out:
            # tytuł strony: "Tytuł - mp3 - Autor - UpolujEbooka.pl"
            title_tag = soup.find("title")
            if title_tag:
                parts = [p.strip() for p in title_tag.get_text().split(" - ")]
                if len(parts) >= 3 and "upolujebooka" in parts[-1].lower():
                    out["author"] = parts[-2]
    except Exception as e:
        log.debug("details_upolujebooka: %s", e)
    return out


# ---------------------------------------------------------------- Google Books

def search_google(query, limit=6):
    """Google Books. Bez klucza API obowiązuje dzienny limit anonimowy (HTTP 429) —
    klucz można podać w Ustawieniach lub zmienną GOOGLE_BOOKS_API_KEY. Bez
    ograniczenia języka: tytuły zagraniczne też mają być znajdowane."""
    params = {"q": query, "maxResults": limit, "printType": "books"}
    if CONFIG["google_api_key"]:
        params["key"] = CONFIG["google_api_key"]
    results = []
    r = _get("https://www.googleapis.com/books/v1/volumes", params=params)
    for item in r.json().get("items", [])[:limit]:
        v = item.get("volumeInfo", {})
        cover = (v.get("imageLinks") or {}).get("thumbnail", "").replace("http://", "https://")
        results.append({
            "source": "Google Books",
            "title": v.get("title", ""),
            "author": ", ".join(v.get("authors", [])),
            "description": _clean(v.get("description", "")),
            "cover_url": cover,
            "url": v.get("infoLink", ""),
        })
    return results


# -------------------------------------------------------------------- Audible

def search_audible(query, limit=6):
    """Publiczny katalog Audible — najlepsze źródło dla audiobooków zagranicznych."""
    results = []
    r = _get("https://api.audible.com/1.0/catalog/products", params={
        "keywords": query,
        "num_results": limit,
        "products_sort_by": "Relevance",
        "response_groups": "product_desc,media,contributors",
    })
    for p in r.json().get("products", [])[:limit]:
        authors = ", ".join(a.get("name", "") for a in (p.get("authors") or []) if a.get("name"))
        images = p.get("product_images") or {}
        cover = images.get("500") or (list(images.values())[0] if images else "")
        asin = p.get("asin") or ""
        results.append({
            "source": "Audible",
            "title": _clean(p.get("title")),
            "author": authors,
            "description": _strip_html(p.get("publisher_summary") or p.get("merchandising_summary")),
            "cover_url": cover,
            "url": f"https://www.audible.com/pd/{asin}" if asin else "",
        })
    return results


# ---------------------------------------------------------------- Apple Books

def search_apple_books(query, limit=6):
    """iTunes Search API — audiobooki i e-booki ze sklepu Apple Books."""
    results = []
    r = _get("https://itunes.apple.com/search", params={
        "term": query, "media": "audiobook", "limit": limit,
    })
    items = r.json().get("results", [])
    if not items:  # brak audiobooka — spróbuj e-booka
        r = _get("https://itunes.apple.com/search", params={
            "term": query, "media": "ebook", "limit": limit,
        })
        items = r.json().get("results", [])
    for d in items[:limit]:
        cover = (d.get("artworkUrl100") or "").replace("100x100bb", "600x600bb")
        results.append({
            "source": "Apple Books",
            "title": _clean(d.get("collectionName") or d.get("trackName")),
            "author": _clean(d.get("artistName")),
            "description": _strip_html(d.get("description")),
            "cover_url": cover,
            "url": d.get("collectionViewUrl") or d.get("trackViewUrl") or "",
        })
    return results


# --------------------------------------------------------------- Open Library

def search_openlibrary(query, limit=6):
    """Open Library (Internet Archive) — ogromny katalog książek, bez klucza."""
    results = []
    r = _get("https://openlibrary.org/search.json", params={
        "q": query, "limit": limit,
        "fields": "title,author_name,cover_i,key,first_publish_year",
    })
    for d in r.json().get("docs", [])[:limit]:
        cover_id = d.get("cover_i")
        key = d.get("key") or ""
        results.append({
            "source": "Open Library",
            "title": _clean(d.get("title")),
            "author": ", ".join(d.get("author_name") or []),
            "description": "",
            "cover_url": (f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                          if cover_id else ""),
            "url": f"https://openlibrary.org{key}" if key else "",
        })
    return results


def details_openlibrary(url):
    out = {}
    try:
        data = _get(url.rstrip("/") + ".json").json()
        desc = data.get("description")
        if isinstance(desc, dict):
            desc = desc.get("value")
        if desc:
            out["description"] = _clean(desc)
    except Exception as e:
        log.debug("details_openlibrary: %s", e)
    return out


# ---------------------------------------------------------------- API zbiorcze

_SOURCES = {
    "lubimyczytac.pl": search_lubimyczytac,
    "upolujebooka.pl": search_upolujebooka,
    "Audible": search_audible,
    "Apple Books": search_apple_books,
    "Google Books": search_google,
    "Open Library": search_openlibrary,
}
#: Kolejność źródeł zależna od języka interfejsu — najpierw te najbardziej trafne.
ORDER_PL = ["lubimyczytac.pl", "upolujebooka.pl", "Audible", "Apple Books",
            "Google Books", "Open Library"]
ORDER_EN = ["Audible", "Apple Books", "Google Books", "Open Library",
            "lubimyczytac.pl", "upolujebooka.pl"]


@dataclass
class SearchOutcome:
    results: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)   # źródło -> (kod, szczegół)


_cache = {}
_cache_lock = threading.Lock()


def clear_cache():
    with _cache_lock:
        _cache.clear()


def search_all(query, lang="pl", use_cache=True):
    """Odpytuje wszystkie źródła równolegle; martwe lub wolne źródło nie opóźnia reszty
    (twardy limit SEARCH_DEADLINE). Błędy źródeł trafiają do `errors`."""
    query = _clean(query)
    key = (fold(query), lang)
    if use_cache:
        with _cache_lock:
            hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_TTL:
            return SearchOutcome(list(hit[1]), {})

    order = ORDER_PL if lang == "pl" else ORDER_EN
    pool = ThreadPoolExecutor(max_workers=len(order))
    futures = {name: pool.submit(_SOURCES[name], query) for name in order}
    done, not_done = wait(futures.values(), timeout=SEARCH_DEADLINE)
    pool.shutdown(wait=False, cancel_futures=True)

    outcome = SearchOutcome()
    for name in order:                      # zachowaj kolejność źródeł
        fut = futures[name]
        if fut in not_done:
            outcome.errors[name] = ("timeout", "")
            continue
        try:
            outcome.results += fut.result()
        except Exception as e:
            outcome.errors[name] = error_code(e)
            log.info("źródło %s: %s", name, e)
    if not outcome.errors:                  # nie cache'uj częściowych awarii
        with _cache_lock:
            _cache[key] = (time.monotonic(), list(outcome.results))
    return outcome


def fetch_details(result):
    """Uzupełnia wybrany wynik o opis/okładkę ze strony szczegółów."""
    url = result.get("url")
    if not url:
        return result
    if result["source"] == "lubimyczytac.pl":
        result.update({k: v for k, v in details_lubimyczytac(url).items() if v})
    elif result["source"] == "upolujebooka.pl":
        result.update({k: v for k, v in details_upolujebooka(url).items() if v})
    elif result["source"] == "Open Library":
        result.update({k: v for k, v in details_openlibrary(url).items() if v})
    # Audible / Apple Books / Google Books zwracają pełny opis już przy wyszukiwaniu
    return result


def fill_missing_covers(results, max_workers=4):
    """Dociąga adres okładki dla wyników, które nie dostały go przy wyszukiwaniu
    (np. upolujebooka.pl — okładka jest tylko na stronie oferty). Mutuje słowniki
    w miejscu i zwraca tę samą listę."""
    need = [r for r in results if not r.get("cover_url") and r.get("url")]
    if not need:
        return results

    def fetch_one(r):
        try:
            if r["source"] == "upolujebooka.pl":
                d = details_upolujebooka(r["url"])
            elif r["source"] == "lubimyczytac.pl":
                d = details_lubimyczytac(r["url"])
            else:
                d = {}
            if d.get("cover_url"):
                r["cover_url"] = d["cover_url"]
        except Exception as e:
            log.debug("fill_missing_covers: %s", e)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(fetch_one, need))
    return results


def best_match(results, title, author="", threshold=0.62):
    """Najlepsze dopasowanie wyniku do (tytuł, autor) — do wsadowego uzupełniania.
    Zwraca (wynik, ocena) albo (None, 0.0), gdy nic nie przekracza progu."""
    t = fold(title)
    a = fold(author)
    best, best_score = None, 0.0
    for r in results:
        score = difflib.SequenceMatcher(None, t, fold(r.get("title", ""))).ratio()
        ra = fold(r.get("author", ""))
        if a and ra and (a in ra or ra in a):
            score += 0.15
        if r.get("cover_url"):
            score += 0.02          # remis rozstrzygnij na korzyść wyniku z okładką
        if score > best_score:
            best, best_score = r, score
    return (best, best_score) if best_score >= threshold else (None, 0.0)


# ---------------------------------------------------------------- obrazy

_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8", b"BM")


def looks_like_image(data):
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    return any(data.startswith(m) for m in _MAGIC)


def fetch_image_bytes(url, max_bytes=MAX_IMAGE_BYTES):
    """Pobiera obraz ze strumienia z limitem rozmiaru i sprawdzeniem sygnatury pliku
    (strona błędu z kodem 200 albo gigantyczna odpowiedź nie trafią na dysk).
    Zwraca bajty albo None."""
    candidates = [url]
    if url.startswith("http://"):
        candidates.insert(0, "https://" + url[len("http://"):])
    for u in candidates:
        try:
            _throttle(urlparse(u).netloc)
            with requests.get(u, headers=HEADERS, timeout=TIMEOUT, stream=True) as r:
                r.raise_for_status()
                length = int(r.headers.get("Content-Length") or 0)
                if length > max_bytes:
                    continue
                buf = bytearray()
                for chunk in r.iter_content(65536):
                    buf += chunk
                    if len(buf) > max_bytes:
                        buf = None
                        break
                if buf and looks_like_image(bytes(buf[:16])):
                    return bytes(buf)
        except Exception as e:
            log.debug("fetch_image_bytes %s: %s", u, e)
    return None
