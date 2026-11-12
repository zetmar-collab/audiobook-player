"""Wspólne ustawienia testów: tryb offscreen Qt, ścieżka do src, narzędzia do plików audio."""
import os
import struct
import sys
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.*=false")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import pytest  # noqa: E402


def pytest_collection_modifyitems(config, items):
    """Testy z markerem `audio` wymagają urządzenia wyjściowego (postęp odtwarzania);
    na CI bez karty dźwiękowej są pomijane z czytelnym powodem."""
    try:
        from PyQt6.QtMultimedia import QMediaDevices
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        has_audio = bool(QMediaDevices.audioOutputs()) and app is not None
    except Exception:
        has_audio = False
    if os.environ.get("ABP_TEST_NO_AUDIO"):       # symulacja CI bez karty dźwiękowej
        has_audio = False
    if has_audio:
        return
    skip = pytest.mark.skip(reason="brak urządzenia wyjściowego audio (CI bez karty dźwiękowej)")
    for item in items:
        if "audio" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _reset_global_state():
    """Każdy test startuje z polskim interfejsem; po teście kończymy wątki robocze."""
    import i18n
    i18n.set_language("pl")
    yield
    try:
        import workers
        workers.shutdown(5000)
    except ImportError:
        pass


@pytest.fixture
def lib_dir(tmp_path):
    d = tmp_path / "appdata"
    d.mkdir()
    return str(d)


@pytest.fixture
def library(lib_dir):
    import library as lib
    L = lib.Library(lib_dir)
    L.settings["lang"] = "pl"      # testy sprawdzają polskie napisy niezależnie od języka systemu
    return L


def make_wav(path, seconds=2, rate=8000):
    """Cichy, poprawny plik WAV (nie wydaje dźwięku podczas testów)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * rate * seconds)
    return str(path)


def make_mp3(path, frames=40, **id3_tags):
    """Minimalny poprawny MP3 (ramki MPEG-1 L3 128 kb/s) z opcjonalnymi tagami ID3.

    id3_tags: title, album, artist, cover (bajty), chapters=[(tytuł, start_ms, koniec_ms)]
    """
    from mutagen.id3 import APIC, CHAP, ID3, TALB, TIT2, TPE1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frame = b"\xff\xfb\x90\x00" + b"\x00" * 413
    with open(path, "wb") as f:
        f.write(frame * frames)
    tags = ID3()
    if id3_tags.get("title"):
        tags.add(TIT2(encoding=3, text=id3_tags["title"]))
    if id3_tags.get("album"):
        tags.add(TALB(encoding=3, text=id3_tags["album"]))
    if id3_tags.get("artist"):
        tags.add(TPE1(encoding=3, text=id3_tags["artist"]))
    if id3_tags.get("cover"):
        tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="c", data=id3_tags["cover"]))
    for i, (title, start, end) in enumerate(id3_tags.get("chapters", [])):
        tags.add(CHAP(element_id=f"ch{i}", start_time=start, end_time=end,
                      start_offset=0xFFFFFFFF, end_offset=0xFFFFFFFF,
                      sub_frames=[TIT2(encoding=3, text=title)]))
    if len(tags):
        tags.save(path)
    return str(path)


@pytest.fixture
def audio_dir(tmp_path):
    return tmp_path / "audio"
