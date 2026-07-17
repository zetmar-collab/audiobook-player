"""Model biblioteki audiobooków + trwały zapis do JSON w %APPDATA%."""
import json
import os
import re
import time
import uuid

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudiobookPlayer")
LIBRARY_FILE = os.path.join(APP_DIR, "library.json")
COVERS_DIR = os.path.join(APP_DIR, "covers")

AUDIO_EXTS = {".mp3", ".m4a", ".m4b", ".aac", ".wma", ".wav", ".flac", ".ogg", ".opus"}


def _natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", os.path.basename(s))]


def list_audio_files(folder):
    """Rekurencyjnie zbiera pliki audio z katalogu, posortowane naturalnie."""
    files = []
    for root, _dirs, names in os.walk(folder):
        for n in names:
            if os.path.splitext(n)[1].lower() in AUDIO_EXTS:
                files.append(os.path.join(root, n))
    files.sort(key=_natural_key)
    return files


def file_duration_ms(path):
    try:
        import mutagen
        m = mutagen.File(path)
        if m is not None and m.info and getattr(m.info, "length", None):
            return int(m.info.length * 1000)
    except Exception:
        pass
    return 0


def guess_title_author(name):
    """Z nazwy katalogu/pliku próbuje wyciągnąć autora i tytuł ("Autor - Tytuł")."""
    base = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", name)
    base = re.sub(r"[\[\(].*?[\]\)]", "", base)  # usuń [PL], (audiobook) itp.
    base = base.replace("_", " ").strip(" -.")
    parts = re.split(r"\s+-\s+", base, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip(), parts[0].strip()
    return base, ""


class Book(dict):
    """Słownik z wygodnymi akcesorami — serializuje się wprost do JSON."""

    @staticmethod
    def new(path, kind, files):
        title, author = guess_title_author(os.path.basename(path))
        return Book(
            id=uuid.uuid4().hex,
            path=path,
            kind=kind,  # "folder" lub "file"
            files=files,
            durations=[file_duration_ms(f) for f in files],
            title=title or os.path.basename(path),
            author=author,
            description="",
            cover="",
            file_index=0,
            position_ms=0,
            finished=False,
            added_at=time.time(),
            last_played_at=0.0,
        )

    @property
    def total_ms(self):
        return sum(self.get("durations") or [0])

    @property
    def progress_ms(self):
        d = self.get("durations") or []
        return sum(d[: self.get("file_index", 0)]) + self.get("position_ms", 0)

    @property
    def progress_frac(self):
        if self.get("finished"):
            return 1.0
        t = self.total_ms
        return min(1.0, self.progress_ms / t) if t else 0.0


class Library:
    def __init__(self):
        os.makedirs(APP_DIR, exist_ok=True)
        os.makedirs(COVERS_DIR, exist_ok=True)
        self.books = []
        self.settings = {}
        self.load()

    def load(self):
        try:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.books = [Book(b) for b in data.get("books", [])]
            self.settings = data.get("settings", {})
        except Exception:
            self.books = []
            self.settings = {}

    def save(self):
        tmp = LIBRARY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"books": self.books, "settings": self.settings}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, LIBRARY_FILE)

    def find_by_path(self, path):
        norm = os.path.normcase(os.path.abspath(path))
        for b in self.books:
            if os.path.normcase(os.path.abspath(b["path"])) == norm:
                return b
        return None

    def add_folder(self, folder):
        """Dodaje jeden katalog jako jeden audiobook. Zwraca Book albo None."""
        if self.find_by_path(folder):
            return None
        files = list_audio_files(folder)
        if not files:
            return None
        b = Book.new(folder, "folder", files)
        self.books.append(b)
        return b

    def add_file(self, path):
        if self.find_by_path(path):
            return None
        if os.path.splitext(path)[1].lower() not in AUDIO_EXTS:
            return None
        b = Book.new(path, "file", [path])
        self.books.append(b)
        return b

    def add_parent_folder(self, parent):
        """Każdy podkatalog z audio staje się osobnym audiobookiem;
        pliki luzem w katalogu nadrzędnym są dodawane pojedynczo."""
        added = []
        try:
            entries = sorted(os.listdir(parent), key=str.lower)
        except OSError:
            return added
        for name in entries:
            full = os.path.join(parent, name)
            if os.path.isdir(full):
                b = self.add_folder(full)
                if b:
                    added.append(b)
            elif os.path.splitext(name)[1].lower() in AUDIO_EXTS:
                b = self.add_file(full)
                if b:
                    added.append(b)
        return added

    def remove(self, book):
        """Usuwa audiobook z biblioteki (pliki na dysku zostają)."""
        if book.get("cover"):
            try:
                os.remove(book["cover"])
            except OSError:
                pass
        self.books = [b for b in self.books if b["id"] != book["id"]]

    def clear(self):
        for b in list(self.books):
            self.remove(b)

    def sorted_books(self, mode, query=""):
        books = self.books
        if query:
            q = query.lower()
            books = [b for b in books if q in b["title"].lower() or q in b["author"].lower()]
        if mode == "title":
            return sorted(books, key=lambda b: b["title"].lower())
        if mode == "author":
            return sorted(books, key=lambda b: (b["author"].lower(), b["title"].lower()))
        if mode == "added":
            return sorted(books, key=lambda b: -b["added_at"])
        # "recent" — ostatnio słuchane
        return sorted(books, key=lambda b: -(b["last_played_at"] or 0))
