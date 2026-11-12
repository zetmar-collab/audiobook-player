"""Odczyt metadanych z plików audio (mutagen): długość, tagi, rozdziały, okładka.

Wszystko best-effort — uszkodzony lub nietypowy plik daje puste wartości,
nigdy wyjątek. Moduł nie zależy od Qt.
"""
import logging

log = logging.getLogger("audiobookplayer")

#: Wartości tagów, które nic nie mówią o książce (typowe domyślne ustawienia rippera).
GENERIC_TAGS = {"", "audiobook", "audio book", "audiobooks", "unknown", "unknown album",
                "unknown artist", "album", "artist", "various artists", "track", "title",
                "słuchowisko", "ksiazka", "książka"}


def _first(value):
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def duration_ms(path):
    try:
        import mutagen
        m = mutagen.File(path)
        if m is not None and m.info and getattr(m.info, "length", None):
            return int(m.info.length * 1000)
    except Exception as e:
        log.debug("duration %s: %s", path, e)
    return 0


def read_tags(path):
    """Zwraca {'title','album','artist'} (puste stringi, gdy brak)."""
    out = {"title": "", "album": "", "artist": ""}
    try:
        import mutagen
        m = mutagen.File(path, easy=True)
        if m is not None and m.tags:
            out["title"] = _first(m.tags.get("title"))
            out["album"] = _first(m.tags.get("album"))
            out["artist"] = _first(m.tags.get("albumartist")) or _first(m.tags.get("artist"))
    except Exception as e:
        log.debug("tags %s: %s", path, e)
    return out


def useful(value):
    """Czy wartość tagu nadaje się na tytuł/autora (nie jest śmieciem rippera)."""
    v = (value or "").strip()
    return len(v) >= 2 and v.casefold() not in GENERIC_TAGS


def read_chapters(path):
    """Rozdziały osadzone w pliku: MP4/M4B (atom chpl/QuickTime) i ID3 CHAP.
    Zwraca [{'title': str, 'start_ms': int}], posortowane po czasie."""
    chapters = []
    try:
        import mutagen
        from mutagen.id3 import ID3
        from mutagen.mp4 import MP4
        low = path.lower()
        if low.endswith((".m4b", ".m4a", ".mp4")):
            mp4 = MP4(path)
            ch = getattr(mp4, "chapters", None)
            if ch:
                for c in ch:
                    chapters.append({"title": str(c.title or "").strip(),
                                     "start_ms": int(round(float(c.start) * 1000))})
        elif low.endswith(".mp3"):
            tags = ID3(path)
            for frame in tags.getall("CHAP"):
                title = ""
                sub = getattr(frame, "sub_frames", {}) or {}
                if "TIT2" in sub and sub["TIT2"].text:
                    title = str(sub["TIT2"].text[0]).strip()
                chapters.append({"title": title, "start_ms": int(frame.start_time)})
        _ = mutagen  # import potrzebny tylko, by wcześnie wykryć brak biblioteki
    except Exception as e:
        log.debug("chapters %s: %s", path, e)
        return []
    chapters.sort(key=lambda c: c["start_ms"])
    for i, c in enumerate(chapters, 1):
        if not c["title"]:
            c["title"] = f"{i}"
    return chapters


def extract_cover(path):
    """Bajty okładki osadzonej w pliku (APIC / covr / FLAC picture) albo None."""
    try:
        import mutagen
        low = path.lower()
        if low.endswith((".m4b", ".m4a", ".mp4")):
            from mutagen.mp4 import MP4
            covr = (MP4(path).tags or {}).get("covr")
            if covr:
                return bytes(covr[0])
        elif low.endswith(".mp3"):
            from mutagen.id3 import ID3
            apic = ID3(path).getall("APIC")
            if apic:
                return bytes(apic[0].data)
        elif low.endswith(".flac"):
            from mutagen.flac import FLAC
            pics = FLAC(path).pictures
            if pics:
                return bytes(pics[0].data)
        else:
            m = mutagen.File(path)
            pics = getattr(m, "pictures", None)
            if pics:
                return bytes(pics[0].data)
    except Exception as e:
        log.debug("cover %s: %s", path, e)
    return None
