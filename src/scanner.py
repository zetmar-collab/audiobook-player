"""Skanowanie katalogów i plików audio do obiektów Book (bez Qt, bez sieci)."""
import logging
import os
import re

import tags
from models import Book

log = logging.getLogger("audiobookplayer")

AUDIO_EXTS = {".mp3", ".m4a", ".m4b", ".aac", ".wma", ".wav", ".flac", ".ogg", ".opus"}


def is_audio(path):
    return os.path.splitext(path)[1].lower() in AUDIO_EXTS


def _natural_part(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def natural_path_key(path, root):
    """Klucz „naturalny" po całej ścieżce względnej: CD1/02 przed CD1/10, a CD2/01
    po wszystkich plikach z CD1 (sam basename mieszałby płyty)."""
    rel = os.path.relpath(path, root)
    return [_natural_part(part) for part in rel.split(os.sep)]


def list_audio_files(folder):
    """Rekurencyjnie zbiera pliki audio z katalogu w kolejności naturalnej."""
    files = []
    for root, _dirs, names in os.walk(folder):
        for n in names:
            if is_audio(n):
                files.append(os.path.join(root, n))
    files.sort(key=lambda p: natural_path_key(p, folder))
    return files


def has_direct_audio(folder):
    try:
        return any(is_audio(n) for n in os.listdir(folder)
                   if os.path.isfile(os.path.join(folder, n)))
    except OSError:
        return False


def has_any_audio(folder):
    for _root, _dirs, names in os.walk(folder):
        if any(is_audio(n) for n in names):
            return True
    return False


def guess_title_author(name):
    """Z nazwy katalogu/pliku wyciąga (tytuł, autor) dla wzorca „Autor - Tytuł"."""
    base = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", name)
    base = re.sub(r"[\[\(].*?[\]\)]", "", base)  # usuń [PL], (audiobook) itp.
    base = base.replace("_", " ").strip(" -.")
    parts = re.split(r"\s+-\s+", base, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip(), parts[0].strip()
    return base, ""


#: Nazwy podkatalogów typu płyta/część: ich zawartość to JEDNA książka (CD1, CD2…).
_DISC_RE = re.compile(r"^(cd|dvd|dysk|disc|disk|płyta|plyta|part|część|czesc|vol|volume|tom)"
                      r"[\s._-]*\d+$", re.I)


def _subfolders_with_audio(folder):
    try:
        names = sorted(os.listdir(folder), key=str.lower)
    except OSError:
        return []
    return [n for n in names
            if os.path.isdir(os.path.join(folder, n)) and has_any_audio(os.path.join(folder, n))]


def looks_like_disc_folders(folder):
    """Czy podkatalogi z audio to płyty jednej książki (CD1, CD2, Part 1…)?"""
    subs = _subfolders_with_audio(folder)
    return bool(subs) and all(_DISC_RE.match(n) for n in subs)


def expand_paths(paths, mode="auto"):
    """Zamienia listę ścieżek na zadania [(kind, path)] dla skanera.

    mode="single" — „Dodaj katalog": każdy katalog to jedna książka (rekurencyjnie),
                    plik audio to pojedyncza książka.
    mode="many"   — „Dodaj wiele katalogów": każdy podkatalog z audio to osobna
                    książka, luźne pliki audio w katalogu to pojedyncze książki.
    mode="auto"   — przeciąganie i argumenty wiersza poleceń:
        plik audio                              -> plik
        katalog z audio bezpośrednio            -> jedna książka
        katalog z podkatalogami CD1/CD2/Part 1  -> jedna książka
        pozostałe katalogi                      -> jak "many"
    """
    jobs = []
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isfile(p):
            if is_audio(p):
                jobs.append(("file", p))
            continue
        if not os.path.isdir(p):
            continue
        if mode == "single" or (mode == "auto" and (has_direct_audio(p)
                                                     or looks_like_disc_folders(p))):
            if has_any_audio(p):
                jobs.append(("folder", p))
            continue
        try:
            entries = sorted(os.listdir(p), key=str.lower)
        except OSError:
            continue
        for name in entries:
            full = os.path.join(p, name)
            if os.path.isdir(full) and has_any_audio(full):
                jobs.append(("folder", full))
            elif os.path.isfile(full) and is_audio(full):
                jobs.append(("file", full))
    return jobs


def build_book(kind, path, cover_saver=None, book_id=None):
    """Buduje Book: pliki, długości, tytuł/autor (nazwa katalogu lub tagi), rozdziały
    i osadzona okładka (`cover_saver(bytes, book_id) -> ścieżka` — opcjonalny)."""
    files = list_audio_files(path) if kind == "folder" else [path]
    if not files:
        return None
    name = os.path.basename(path.rstrip("\\/")) or path
    title, author = guess_title_author(name)
    book = Book.new(path, kind, files, title=title or name, author=author)
    if book_id:
        book["id"] = book_id

    book["durations"] = [tags.duration_ms(f) for f in files]

    # tytuł/autor z tagów — tylko gdy nazwa katalogu nie dała wzorca „Autor - Tytuł"
    t = tags.read_tags(files[0])
    if not author:
        if tags.useful(t["artist"]):
            book["author"] = t["artist"]
        album_or_title = t["album"] if kind == "folder" else (t["title"] or t["album"])
        if tags.useful(album_or_title):
            book["title"] = album_or_title

    chapters = []
    for i, f in enumerate(files):
        for ch in tags.read_chapters(f):
            chapters.append({"title": ch["title"], "file_index": i, "start_ms": ch["start_ms"]})
    book["chapters"] = chapters

    if cover_saver:
        for f in files[:3]:
            data = tags.extract_cover(f)
            if data:
                saved = cover_saver(data, book["id"])
                if saved:
                    book["cover"] = saved
                    break
    return book
