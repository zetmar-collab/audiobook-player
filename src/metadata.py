"""Pobieranie metadanych o książkach z serwisów polskich i zagranicznych.

Źródła polskie: lubimyczytac.pl, upolujebooka.pl
Źródła zagraniczne: Audible, Apple Books, Google Books, Open Library

Każde źródło zwraca listę słowników:
{source, title, author, description, cover_url, url}
Wszystko best-effort — błędy sieci/parsowania dają pustą listę.
"""
import html as _html
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.5",
}
#: (connect, read) — krótki timeout połączenia, żeby niedostępne źródło
#: nie opóźniało równoległego wyszukiwania w pozostałych serwisach.
TIMEOUT = (5, 12)


def _get(url, **kw):
    return requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kw)


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
    try:
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
    except Exception:
        pass
    return results


def details_lubimyczytac(url):
    """Dociąga opis (i lepszą okładkę) ze strony książki."""
    out = {}
    try:
        r = _get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        desc = soup.select_one("div#book-description") or soup.select_one("div.collapse-content")
        if desc:
            out["description"] = _clean(desc.get_text(" "))
        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            out["cover_url"] = og["content"]
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- upolujebooka

def search_upolujebooka(query, limit=6):
    results = []
    try:
        from urllib.parse import quote
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
    except Exception:
        pass
    return results


def details_upolujebooka(url):
    """Czyta JSON-LD (schema.org/Book) ze strony oferty."""
    import html
    import json

    out = {}
    try:
        r = _get(url)
        soup = BeautifulSoup(r.text, "html.parser")
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
                    out["description"] = _clean(html.unescape(item["description"]))
                author = item.get("author")
                if author:
                    if isinstance(author, list):
                        author = author[0]
                    name = author.get("name") if isinstance(author, dict) else str(author)
                    if name:
                        out["author"] = _clean(html.unescape(name))
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
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- Google Books

def search_google(query, limit=6):
    results = []
    try:
        r = _get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": query, "maxResults": limit, "langRestrict": "pl", "printType": "books"},
        )
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
    except Exception:
        pass
    return results


# -------------------------------------------------------------------- Audible

def search_audible(query, limit=6):
    """Publiczny katalog Audible — najlepsze źródło dla audiobooków zagranicznych."""
    results = []
    try:
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
                "description": _strip_html(p.get("publisher_summary")
                                           or p.get("merchandising_summary")),
                "cover_url": cover,
                "url": f"https://www.audible.com/pd/{asin}" if asin else "",
            })
    except Exception:
        pass
    return results


# ---------------------------------------------------------------- Apple Books

def search_apple_books(query, limit=6):
    """iTunes Search API — audiobooki i e-booki ze sklepu Apple Books."""
    results = []
    try:
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
    except Exception:
        pass
    return results


# --------------------------------------------------------------- Open Library

def search_openlibrary(query, limit=6):
    """Open Library (Internet Archive) — ogromny katalog książek, bez klucza."""
    results = []
    try:
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
    except Exception:
        pass
    return results


def details_openlibrary(url):
    out = {}
    try:
        r = _get(url.rstrip("/") + ".json")
        data = r.json()
        desc = data.get("description")
        if isinstance(desc, dict):
            desc = desc.get("value")
        if desc:
            out["description"] = _clean(desc)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- API zbiorcze

#: Kolejność źródeł zależna od języka interfejsu — najpierw te najbardziej trafne.
SOURCES_PL = [search_lubimyczytac, search_upolujebooka, search_audible,
              search_apple_books, search_google, search_openlibrary]
SOURCES_EN = [search_audible, search_apple_books, search_google,
              search_openlibrary, search_lubimyczytac, search_upolujebooka]


def search_all(query, lang="pl"):
    """Odpytuje wszystkie źródła równolegle; martwe źródło nie opóźnia reszty."""
    sources = SOURCES_PL if lang == "pl" else SOURCES_EN
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = [pool.submit(fn, query) for fn in sources]
        results = []
        for f in futures:
            try:
                results += f.result()
            except Exception:
                pass
    return results


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


def download_cover(url, dest_path):
    try:
        r = _get(url)
        if r.ok and r.content:
            with open(dest_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False
