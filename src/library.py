"""Biblioteka audiobooków: trwały zapis JSON, kopie zapasowe, sortowanie i filtry.

Katalog danych: %APPDATA%\\AudiobookPlayer na Windows,
$XDG_DATA_HOME/AudiobookPlayer (domyślnie ~/.local/share/AudiobookPlayer) na Linuksie/macOS.

Gwarancje bezpieczeństwa danych:
- plik, którego nie da się wczytać, NIGDY nie jest nadpisywany pustą biblioteką:
  uszkodzony JSON trafia do `library.json.corrupt-<czas>`, a plik zablokowany
  (np. przez antywirus) wyłącza zapis do czasu kolejnego uruchomienia;
- zapis jest atomowy (plik tymczasowy + `os.replace`) z ponowieniami na Windows;
- raz dziennie powstaje kopia w `backups/` (ostatnie 7).
"""
import json
import logging
import os
import shutil
import time
import zipfile

import paths
import scanner
from models import Book, collation_key, fold

log = logging.getLogger("audiobookplayer")
AUDIO_EXTS = scanner.AUDIO_EXTS      # dla zgodności z dotychczasowym kodem

SCHEMA_VERSION = 2
KEEP_DAILY_BACKUPS = 7

# stałe ścieżek zachowane dla zgodności z dotychczasowym kodem i testami
APP_DIR = paths.APP_DIR
LIBRARY_FILE = paths.LIBRARY_FILE
COVERS_DIR = paths.COVERS_DIR


class Library:
    def __init__(self, app_dir=None):
        self.app_dir = app_dir or paths.APP_DIR
        self.file = os.path.join(self.app_dir, "library.json")
        self.covers_dir = os.path.join(self.app_dir, "covers")
        self.backup_dir = os.path.join(self.app_dir, "backups")
        os.makedirs(self.covers_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        self.books = []
        self.settings = {}
        self.load_error = None       # komunikat dla użytkownika po nieudanym wczytaniu
        self.save_disabled = False   # true => nie nadpisuj nieczytelnego pliku
        self.last_save_error = None
        self.load()

    # ------------------------------------------------------------------ odczyt

    def _read_json(self):
        last = None
        for _ in range(4):  # krótkie blokady (antywirus, synchronizacja chmury)
            try:
                with open(self.file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (FileNotFoundError, ValueError):
                raise
            except OSError as e:
                last = e
                time.sleep(0.15)
        raise last

    def _quarantine(self):
        dest = f"{self.file}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            shutil.copy2(self.file, dest)
            return dest
        except OSError as e:
            log.error("Nie udało się skopiować uszkodzonej biblioteki: %s", e)
            return None

    def load(self):
        self.books, self.settings = [], {}
        self.load_error = None
        self.save_disabled = False
        try:
            data = self._read_json()
            if not isinstance(data, dict):
                raise ValueError("główny element nie jest obiektem")
        except FileNotFoundError:
            return
        except ValueError as e:
            saved = self._quarantine()
            self.load_error = (f"Plik biblioteki jest uszkodzony ({e}). "
                               f"Kopia: {saved or 'nie udało się utworzyć'}. "
                               "Biblioteka została uruchomiona jako pusta.")
            log.error(self.load_error)
            return
        except OSError as e:
            self.save_disabled = True
            self.load_error = (f"Nie można odczytać pliku biblioteki ({e}). "
                               "Zmiany nie będą zapisywane, żeby nie nadpisać danych.")
            log.error(self.load_error)
            return

        skipped = 0
        for raw in data.get("books", []):
            if isinstance(raw, dict) and raw.get("files") is not None:
                try:
                    self.books.append(Book.from_dict(raw))
                    continue
                except (TypeError, ValueError, KeyError) as e:
                    log.error("Pominięto uszkodzony wpis biblioteki: %s", e)
            skipped += 1
        settings = data.get("settings", {})
        self.settings = dict(settings) if isinstance(settings, dict) else {}
        if skipped:
            saved = self._quarantine()
            self.load_error = (f"Pominięto uszkodzone wpisy: {skipped}. "
                               f"Oryginał zachowano: {saved or 'brak kopii'}.")
        self._daily_backup()

    def _daily_backup(self):
        if not self.books or not os.path.exists(self.file):
            return
        dest = os.path.join(self.backup_dir, time.strftime("library-%Y%m%d.json"))
        try:
            if not os.path.exists(dest):
                shutil.copy2(self.file, dest)
            old = sorted(n for n in os.listdir(self.backup_dir) if n.startswith("library-"))
            for name in old[:-KEEP_DAILY_BACKUPS]:
                os.remove(os.path.join(self.backup_dir, name))
        except OSError as e:
            log.warning("Kopia dzienna: %s", e)

    # ------------------------------------------------------------------ zapis

    def save(self):
        """Zapisuje bibliotekę. Zwraca True/False; przyczyna w `last_save_error`."""
        if self.save_disabled:
            return False
        data = {"schema": SCHEMA_VERSION, "books": list(self.books), "settings": self.settings}
        tmp = self.file + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            last = None
            for attempt in range(4):
                try:
                    os.replace(tmp, self.file)
                    self.last_save_error = None
                    return True
                except PermissionError as e:   # Windows: plik chwilowo zajęty
                    last = e
                    time.sleep(0.1 * (attempt + 1))
            raise last
        except OSError as e:
            self.last_save_error = str(e)
            log.error("Zapis biblioteki nie powiódł się: %s", e)
            return False

    # ------------------------------------------------------------------ książki

    @staticmethod
    def _norm(path):
        return os.path.normcase(os.path.abspath(path))

    def existing_paths(self):
        return {self._norm(b["path"]) for b in self.books}

    def find_by_path(self, path):
        norm = self._norm(path)
        return next((b for b in self.books if self._norm(b["path"]) == norm), None)

    def book_by_id(self, book_id):
        return next((b for b in self.books if b["id"] == book_id), None)

    def add_book(self, book):
        """Dodaje przygotowaną książkę; zwraca False, gdy ścieżka już jest w bibliotece."""
        if self.find_by_path(book["path"]):
            return False
        self.books.append(book)
        return True

    def add_paths(self, path_list, cover_saver=None, mode="auto"):
        """Synchronicznie dodaje ścieżki (pliki/katalogi); zwraca listę dodanych książek.
        Interfejs używa wersji asynchronicznej (ScanWorker) — ta służy skryptom i testom."""
        added = []
        for kind, path in scanner.expand_paths(path_list, mode):
            if self.find_by_path(path):
                continue
            book = scanner.build_book(kind, path, cover_saver)
            if book and self.add_book(book):
                added.append(book)
        return added

    def add_folder(self, folder):
        """Jeden katalog (rekurencyjnie) = jeden audiobook. Zwraca Book albo None."""
        if self.find_by_path(folder):
            return None
        book = scanner.build_book("folder", folder)
        return book if book and self.add_book(book) else None

    def add_file(self, path):
        if self.find_by_path(path) or not scanner.is_audio(path):
            return None
        book = scanner.build_book("file", path)
        return book if book and self.add_book(book) else None

    def add_parent_folder(self, parent):
        """Każdy podkatalog z audio to osobny audiobook; luźne pliki — pojedyncze."""
        added = []
        try:
            entries = sorted(os.listdir(parent), key=str.lower)
        except OSError:
            return added
        for name in entries:
            full = os.path.join(parent, name)
            if os.path.isdir(full):
                book = self.add_folder(full)
            else:
                book = self.add_file(full)
            if book:
                added.append(book)
        return added

    def _inside_covers(self, path):
        try:
            root = os.path.realpath(self.covers_dir)
            return os.path.commonpath([root, os.path.realpath(path)]) == root
        except ValueError:
            return False

    def remove(self, book):
        """Usuwa audiobook z biblioteki (pliki audio na dysku zostają). Okładkę kasuje
        tylko wtedy, gdy leży w katalogu okładek aplikacji."""
        cover = book.get("cover")
        if cover and self._inside_covers(cover):
            try:
                os.remove(cover)
            except OSError:
                pass
        self.books = [b for b in self.books if b["id"] != book["id"]]

    def clear(self):
        for b in list(self.books):
            self.remove(b)

    def cover_path(self, book_id):
        return os.path.join(self.covers_dir, book_id + ".jpg")

    # ------------------------------------------------------------------ widok

    def sorted_books(self, mode="recent", query="", filter_mode="all"):
        books = self.books
        if query:
            q = fold(query)
            books = [b for b in books if q in fold(b["title"]) or q in fold(b["author"])]
        if filter_mode == "in_progress":
            books = [b for b in books if b.in_progress]
        elif filter_mode == "unplayed":
            books = [b for b in books if b.is_unplayed]
        elif filter_mode == "finished":
            books = [b for b in books if b.get("finished")]

        if mode == "title":
            return sorted(books, key=lambda b: collation_key(b["title"]))
        if mode == "author":
            return sorted(books, key=lambda b: (not b["author"], collation_key(b["author"]),
                                                collation_key(b["title"])))
        if mode == "added":
            return sorted(books, key=lambda b: -b["added_at"])
        return sorted(books, key=lambda b: -(b["last_played_at"] or 0))   # "recent"

    # ------------------------------------------------------------------ statystyki

    def record_listening(self, book, ms):
        """Dolicza `ms` rzeczywistego czasu słuchania do książki i do statystyk dziennych."""
        if ms <= 0:
            return
        book["listened_ms"] = int(book.get("listened_ms", 0)) + int(ms)
        stats = self.settings.setdefault("stats", {"daily": {}, "total_ms": 0})
        day = time.strftime("%Y-%m-%d")
        stats["daily"][day] = int(stats["daily"].get(day, 0)) + int(ms)
        stats["total_ms"] = int(stats.get("total_ms", 0)) + int(ms)
        if len(stats["daily"]) > 400:
            for k in sorted(stats["daily"])[:-400]:
                del stats["daily"][k]

    # ------------------------------------------------------------------ kopie

    def export_backup(self, zip_path):
        """Zapisuje bibliotekę (JSON + okładki) do archiwum zip. Zwraca liczbę książek."""
        self.save()
        data = {"schema": SCHEMA_VERSION, "books": list(self.books), "settings": self.settings}
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("library.json", json.dumps(data, ensure_ascii=False, indent=1))
            for b in self.books:
                cover = b.get("cover")
                if cover and os.path.isfile(cover) and self._inside_covers(cover):
                    z.write(cover, "covers/" + os.path.basename(cover))
        return len(self.books)

    def import_backup(self, zip_path):
        """Zastępuje bibliotekę zawartością archiwum. Bieżący plik trafia najpierw do
        `backups/`. Zwraca liczbę przywróconych książek; wyjątek ValueError, gdy archiwum
        nie jest poprawną kopią."""
        try:
            with zipfile.ZipFile(zip_path) as z:
                names = z.namelist()
                if "library.json" not in names:
                    raise ValueError("w archiwum brak pliku library.json")
                data = json.loads(z.read("library.json").decode("utf-8"))
                if not isinstance(data, dict) or not isinstance(data.get("books", []), list):
                    raise ValueError("nieprawidłowa struktura biblioteki")
                books = [Book.from_dict(b) for b in data.get("books", []) if isinstance(b, dict)]
                extracted = set()
                for name in names:
                    base = os.path.basename(name)
                    # tylko płaskie pliki covers/<nazwa> — żadnych ścieżek z ".."
                    if name.startswith("covers/") and base and name == "covers/" + base:
                        with z.open(name) as src, open(
                                os.path.join(self.covers_dir, base), "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        extracted.add(base)
        except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(str(e)) from e

        if os.path.exists(self.file):
            try:
                shutil.copy2(self.file, os.path.join(
                    self.backup_dir, time.strftime("before-restore-%Y%m%d-%H%M%S.json")))
            except OSError:
                pass
        for b in books:
            base = os.path.basename(b.get("cover") or "")
            b["cover"] = os.path.join(self.covers_dir, base) if base in extracted else ""
        self.books = books
        settings = data.get("settings", {})
        self.settings = dict(settings) if isinstance(settings, dict) else {}
        self.save_disabled = False
        self.save()
        return len(self.books)
