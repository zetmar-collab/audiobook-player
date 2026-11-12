"""Wątki robocze (QThread): sieć i dysk poza wątkiem GUI.

Zasady, które rozwiązują błędy z audytu:
- wątek nigdy nie dotyka widgetów — zwraca dane sygnałem (QImage, a nie QPixmap);
- każdy wynik niesie numer generacji zapytania, więc spóźniona odpowiedź starego
  wyszukiwania jest ignorowana, zamiast mieszać się z nowym (B4);
- uruchomione wątki są trzymane w rejestrze do końca pracy, a `shutdown()` czeka na
  nie przy zamykaniu programu (brak „QThread destroyed while running").
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

import covers
import metadata as meta
import scanner

log = logging.getLogger("audiobookplayer")

_alive = set()


def start(worker):
    """Uruchamia wątek i trzyma go przy życiu do zakończenia pracy."""
    _alive.add(worker)
    worker.finished.connect(lambda w=worker: _alive.discard(w))
    worker.start()
    return worker


def shutdown(timeout_ms=3000):
    """Czeka na działające wątki; zwraca liczbę tych, które się nie zakończyły."""
    for w in list(_alive):
        w.requestInterruption()
    for w in list(_alive):
        w.wait(timeout_ms)
    return sum(1 for w in _alive if w.isRunning())


# ---------------------------------------------------------------- wyszukiwanie

class SearchWorker(QThread):
    """Wyszukiwanie metadanych/okładek; `with_covers` dociąga brakujące adresy okładek."""
    done = pyqtSignal(int, object)          # (generacja, SearchOutcome)

    def __init__(self, generation, query, lang, with_covers=False, parent=None):
        super().__init__(parent)
        self.generation, self.query, self.lang, self.with_covers = generation, query, lang, with_covers

    def run(self):
        try:
            outcome = meta.search_all(self.query, lang=self.lang)
            if self.with_covers and not self.isInterruptionRequested():
                meta.fill_missing_covers(outcome.results)
        except Exception as e:      # żeby dialog nigdy nie został w stanie „Szukam…"
            log.exception("SearchWorker")
            outcome = meta.SearchOutcome([], {"*": ("error", type(e).__name__)})
        self.done.emit(self.generation, outcome)


class DetailsWorker(QThread):
    done = pyqtSignal(int, dict)

    def __init__(self, generation, result, parent=None):
        super().__init__(parent)
        self.generation, self.result = generation, dict(result)

    def run(self):
        try:
            self.result = meta.fetch_details(self.result)
        except Exception:
            log.exception("DetailsWorker")
        self.done.emit(self.generation, self.result)


# ---------------------------------------------------------------- obrazy

class ImageWorker(QThread):
    """Pobiera listę obrazów równolegle i zwraca każdy gotowy QImage sygnałem."""
    loaded = pyqtSignal(int, int, QImage)   # (generacja, klucz, obraz)

    def __init__(self, generation, items, parent=None):
        super().__init__(parent)
        self.generation, self.items = generation, list(items)   # [(klucz, url)]

    def _one(self, item):
        key, url = item
        if self.isInterruptionRequested():
            return key, None
        data = meta.fetch_image_bytes(url)
        return key, (covers.image_from_bytes(data) if data else None)

    def run(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            for key, img in pool.map(self._one, self.items):
                if img is not None and not self.isInterruptionRequested():
                    self.loaded.emit(self.generation, key, img)


class CoverDownloadWorker(QThread):
    """Pobiera i zapisuje wybraną okładkę (JPEG ≤1000 px)."""
    done = pyqtSignal(bool)

    def __init__(self, url, dest, parent=None):
        super().__init__(parent)
        self.url, self.dest = url, dest

    def run(self):
        data = meta.fetch_image_bytes(self.url)
        self.done.emit(bool(data) and covers.save_cover_bytes(data, self.dest))


class SaveCoversWorker(QThread):
    """Pobiera okładki dla wielu książek naraz (wsadowe uzupełnianie)."""
    progress = pyqtSignal(int, int)
    done = pyqtSignal(dict)                 # {id książki: ścieżka okładki}

    def __init__(self, items, covers_dir, parent=None):
        super().__init__(parent)
        self.items, self.covers_dir = list(items), covers_dir   # [(book_id, url)]

    def run(self):
        saved = {}
        for i, (book_id, url) in enumerate(self.items, 1):
            if self.isInterruptionRequested():
                break
            dest = os.path.join(self.covers_dir, book_id + ".jpg")
            data = meta.fetch_image_bytes(url)
            if data and covers.save_cover_bytes(data, dest):
                saved[book_id] = dest
            self.progress.emit(i, len(self.items))
        self.done.emit(saved)


# ---------------------------------------------------------------- skanowanie

class ScanWorker(QThread):
    """Dodawanie katalogów/plików: przeszukiwanie dysku, odczyt długości i tagów
    (mutagen) oraz okładek osadzonych — wszystko poza wątkiem GUI."""
    progress = pyqtSignal(int, int, str)
    done = pyqtSignal(list)                 # [Book]

    def __init__(self, paths, existing, covers_dir, mode="auto", parent=None):
        super().__init__(parent)
        self.paths, self.existing, self.covers_dir = list(paths), set(existing), covers_dir
        self.mode = mode

    def run(self):
        books = []
        try:
            jobs = scanner.expand_paths(self.paths, self.mode)
            jobs = [(k, p) for k, p in jobs
                    if os.path.normcase(os.path.abspath(p)) not in self.existing]
            saver = covers.cover_saver_for(self.covers_dir)
            for i, (kind, path) in enumerate(jobs, 1):
                if self.isInterruptionRequested():
                    break
                self.progress.emit(i, len(jobs), os.path.basename(path.rstrip("\\/")) or path)
                try:
                    book = scanner.build_book(kind, path, cover_saver=saver)
                except Exception:
                    log.exception("Skanowanie %s", path)
                    continue
                if book:
                    books.append(book)
                    self.existing.add(os.path.normcase(os.path.abspath(path)))
        except Exception:
            log.exception("ScanWorker")
        self.done.emit(books)


# ---------------------------------------------------------------- wsadowe metadane

class BatchMetaWorker(QThread):
    """Dla każdej książki szuka najlepszego dopasowania w serwisach."""
    progress = pyqtSignal(int, int, str)
    proposal = pyqtSignal(dict)             # {id, old_title, old_author, result, score}
    done = pyqtSignal()

    def __init__(self, items, lang, parent=None):
        super().__init__(parent)
        self.items, self.lang = list(items), lang    # [{id,title,author}]

    def run(self):
        for i, it in enumerate(self.items, 1):
            if self.isInterruptionRequested():
                break
            self.progress.emit(i, len(self.items), it["title"])
            try:
                outcome = meta.search_all(f"{it['author']} {it['title']}".strip(), self.lang)
                best, score = meta.best_match(outcome.results, it["title"], it["author"])
                if best:
                    best = meta.fetch_details(dict(best))
                    self.proposal.emit({"id": it["id"], "old_title": it["title"],
                                        "old_author": it["author"], "result": best,
                                        "score": score})
            except Exception:
                log.exception("BatchMetaWorker %s", it.get("title"))
        self.done.emit()
