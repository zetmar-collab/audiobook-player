"""Model audiobooka oraz klucze sortowania/wyszukiwania odporne na diakrytyki."""
import copy
import time
import unicodedata
import re
import uuid

# Litery, które nie rozkładają się w NFD na "bazę + akcent", a trzeba je zrównać.
_SPECIAL = str.maketrans({"ł": "l", "đ": "d", "ø": "o", "æ": "ae", "œ": "oe", "ı": "i"})


def fold(text):
    """Małe litery bez diakrytyków: 'Żółte Światło' -> 'zolte swiatlo'."""
    s = (text or "").casefold().translate(_SPECIAL)
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def collation_key(text):
    """Klucz sortowania zgodny z polską kolejnością alfabetu
    (Ćma po Cień, Łódź po Lublin, Żółte po Zebra) — bez zależności od locale."""
    return (fold(text), (text or "").casefold())


#: Wartości domyślne pól książki. Wpisy ze starszych wersji biblioteki są
#: uzupełniane tym słownikiem, dzięki czemu dodanie pola nie wymaga migracji.
BOOK_DEFAULTS = {
    "path": "",
    "kind": "file",            # "folder" lub "file"
    "files": [],
    "durations": [],
    "title": "",
    "author": "",
    "description": "",
    "cover": "",
    "file_index": 0,
    "position_ms": 0,
    "finished": False,
    "added_at": 0.0,
    "last_played_at": 0.0,
    "speed": None,             # prędkość zapamiętana dla tej książki (None = domyślna)
    "bookmarks": [],           # [{id, file_index, position_ms, title, created}]
    "chapters": [],            # [{title, file_index, start_ms}] z tagów plików
    "listened_ms": 0,          # łączny czas słuchania (statystyki)
}


class Book(dict):
    """Słownik z wygodnymi akcesorami — serializuje się wprost do JSON."""

    @classmethod
    def from_dict(cls, data):
        book = cls(copy.deepcopy(BOOK_DEFAULTS))
        book.update(data)
        bid = str(data.get("id") or "")
        # id trafia do nazw plików okładek — przyjmujemy tylko bezpieczne znaki
        book["id"] = bid if re.fullmatch(r"[0-9A-Za-z_-]{1,64}", bid) else uuid.uuid4().hex
        if not book["added_at"]:
            book["added_at"] = time.time()
        # spójność: długości muszą odpowiadać liczbie plików
        n = len(book["files"])
        dur = list(book["durations"])[:n]
        book["durations"] = dur + [0] * (n - len(dur))
        if book["files"]:
            book["file_index"] = max(0, min(int(book["file_index"] or 0), n - 1))
        else:
            book["file_index"] = 0
        return book

    @classmethod
    def new(cls, path, kind, files, title="", author=""):
        return cls.from_dict({
            "id": uuid.uuid4().hex, "path": path, "kind": kind, "files": files,
            "title": title, "author": author, "added_at": time.time(),
        })

    # ------------------------------------------------------------ postęp
    @property
    def total_ms(self):
        return sum(self.get("durations") or [0])

    def offset_ms(self, file_index=None):
        """Czas od początku książki do początku pliku `file_index`."""
        idx = self["file_index"] if file_index is None else file_index
        return sum(self.get("durations", [])[:idx])

    @property
    def progress_ms(self):
        return self.offset_ms() + self.get("position_ms", 0)

    @property
    def progress_frac(self):
        if self.get("finished"):
            return 1.0
        t = self.total_ms
        return min(1.0, self.progress_ms / t) if t else 0.0

    @property
    def is_unplayed(self):
        return not self.get("finished") and not self.get("last_played_at") \
            and self.progress_ms == 0

    @property
    def in_progress(self):
        return not self.get("finished") and (self.progress_ms > 0 or bool(self.get("last_played_at")))

    # ------------------------------------------------------------ rozdziały
    def chapter_entries(self):
        """Lista (tytuł, file_index, start_ms): rozdziały z tagów, a gdy ich brak —
        po prostu pliki książki."""
        import os
        if self.get("chapters"):
            return [(c["title"], int(c["file_index"]), int(c["start_ms"]))
                    for c in self["chapters"]]
        return [(os.path.basename(f), i, 0) for i, f in enumerate(self["files"])]

    def current_chapter_index(self, file_index, position_ms):
        entries = self.chapter_entries()
        current = 0
        for i, (_t, fi, start) in enumerate(entries):
            if (fi, start) <= (file_index, position_ms):
                current = i
        return current
