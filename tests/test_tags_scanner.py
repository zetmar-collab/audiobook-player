"""Odczyt tagów, rozdziałów i okładek osadzonych; budowanie książki ze skanera."""
import os

import scanner
import tags
from conftest import make_mp3, make_wav

COVER = b"\xff\xd8\xff\xe0JFIF-fake-cover"


def test_read_tags_and_duration(audio_dir):
    p = make_mp3(str(audio_dir / "a.mp3"), title="Rozdzial 1", album="Wiedzmin",
                 artist="Andrzej Sapkowski")
    t = tags.read_tags(p)
    assert t == {"title": "Rozdzial 1", "album": "Wiedzmin", "artist": "Andrzej Sapkowski"}
    assert tags.duration_ms(p) > 500


def test_tags_on_untagged_or_broken_files_do_not_raise(audio_dir):
    wav = make_wav(audio_dir / "x.wav")
    assert tags.read_tags(wav) == {"title": "", "album": "", "artist": ""}
    junk = audio_dir / "junk.mp3"
    junk.write_bytes(b"to nie jest mp3")
    assert tags.read_tags(str(junk))["title"] == ""
    assert tags.duration_ms(str(junk)) == 0
    assert tags.read_chapters(str(junk)) == []
    assert tags.extract_cover(str(junk)) is None
    assert tags.duration_ms(str(audio_dir / "nie_istnieje.mp3")) == 0


def test_useful_filters_generic_tag_values():
    assert tags.useful("Wiedźmin")
    for junk in ("", " ", "Audiobook", "Unknown Album", "Various Artists", "x"):
        assert not tags.useful(junk)


def test_id3_chapters_sorted(audio_dir):
    p = make_mp3(str(audio_dir / "c.mp3"),
                 chapters=[("Drugi", 5000, 9000), ("Pierwszy", 0, 5000)])
    ch = tags.read_chapters(p)
    assert [c["title"] for c in ch] == ["Pierwszy", "Drugi"]
    assert [c["start_ms"] for c in ch] == [0, 5000]


def test_extract_embedded_cover(audio_dir):
    p = make_mp3(str(audio_dir / "k.mp3"), cover=COVER)
    assert tags.extract_cover(p) == COVER
    assert tags.extract_cover(make_mp3(str(audio_dir / "n.mp3"))) is None


def test_mp4_chapters_read_through_mutagen_api(monkeypatch, audio_dir):
    """MP4/M4B: sprawdzamy mapowanie obiektów Chapter z mutagen (bez budowania pliku M4B)."""
    class Chap:
        def __init__(self, start, title):
            self.start, self.title = start, title

    class FakeMP4:
        chapters = [Chap(0.0, "Wstęp"), Chap(61.5, "Rozdział 1")]

        def __init__(self, path):
            pass
    import mutagen.mp4
    monkeypatch.setattr(mutagen.mp4, "MP4", FakeMP4)
    got = tags.read_chapters(str(audio_dir / "ksiazka.m4b"))
    assert got == [{"title": "Wstęp", "start_ms": 0}, {"title": "Rozdział 1", "start_ms": 61500}]


def test_build_book_uses_folder_pattern_over_tags(audio_dir):
    make_mp3(str(audio_dir / "Autor Folder - Tytul Folder" / "01.mp3"),
             album="Inny Album", artist="Inny Artysta")
    book = scanner.build_book("folder", str(audio_dir / "Autor Folder - Tytul Folder"))
    assert (book["title"], book["author"]) == ("Tytul Folder", "Autor Folder")


def test_build_book_falls_back_to_tags_when_folder_has_no_pattern(audio_dir):
    make_mp3(str(audio_dir / "nagranie_123" / "01.mp3"), album="Prawdziwy Tytul",
             artist="Prawdziwy Autor")
    book = scanner.build_book("folder", str(audio_dir / "nagranie_123"))
    assert (book["title"], book["author"]) == ("Prawdziwy Tytul", "Prawdziwy Autor")
    assert book["durations"][0] > 0


def test_build_book_ignores_generic_tags(audio_dir):
    make_mp3(str(audio_dir / "Moja Ksiazka" / "01.mp3"), album="Audiobook",
             artist="Unknown Artist")
    book = scanner.build_book("folder", str(audio_dir / "Moja Ksiazka"))
    assert (book["title"], book["author"]) == ("Moja Ksiazka", "")


def test_build_book_collects_chapters_and_cover(audio_dir):
    d = audio_dir / "Duza Ksiazka"
    make_mp3(str(d / "a.mp3"), chapters=[("Pierwszy", 0, 1000)], cover=COVER)
    make_mp3(str(d / "b.mp3"), chapters=[("Drugi", 0, 1000)])
    saved = {}
    book = scanner.build_book("folder", str(d),
                              cover_saver=lambda data, bid: saved.setdefault(bid, data) and "C:/c.jpg")
    assert [(c["title"], c["file_index"]) for c in book["chapters"]] == [("Pierwszy", 0), ("Drugi", 1)]
    assert book["cover"] == "C:/c.jpg" and saved[book["id"]] == COVER


def test_build_book_empty_folder_returns_none(audio_dir):
    (audio_dir / "pusty").mkdir(parents=True)
    assert scanner.build_book("folder", str(audio_dir / "pusty")) is None


def test_expand_paths_ignores_non_audio_and_missing(audio_dir):
    make_wav(audio_dir / "a" / "1.wav")
    (audio_dir / "a" / "notatki.txt").write_text("x")
    jobs = scanner.expand_paths([str(audio_dir / "a" / "notatki.txt"),
                                 str(audio_dir / "brak"), str(audio_dir / "a")])
    assert jobs == [("folder", os.path.abspath(str(audio_dir / "a")))]
