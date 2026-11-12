"""Model, sortowanie, trwałość biblioteki, kopie zapasowe (poprawki B1, B5 i pokrewne)."""
import json
import os
import time
import zipfile

import pytest

import library as lib
import scanner
from conftest import make_wav
from models import Book, collation_key, fold


# ---------------------------------------------------------------- sortowanie / fold

def test_fold_removes_polish_diacritics():
    assert fold("Żółte Światło") == "zolte swiatlo"
    assert fold("Łódź") == "lodz"
    assert fold("ŻÓŁĆ") == "zolc"


def test_polish_alphabetical_order():
    titles = ["Zebra", "Łódź", "Adam", "Świt", "Żółte światło", "Cień", "Ćma"]
    result = sorted(titles, key=collation_key)
    assert result == ["Adam", "Cień", "Ćma", "Łódź", "Świt", "Zebra", "Żółte światło"]


def test_sorted_books_title_author_and_blank_author_last(library):
    for title, author in [("Zebra", "Żak"), ("Ćma", ""), ("Adam", "Ala")]:
        library.books.append(Book.new("/x/" + title, "file", ["/x/" + title], title, author))
    assert [b["title"] for b in library.sorted_books("title")] == ["Adam", "Ćma", "Zebra"]
    assert [b["author"] for b in library.sorted_books("author")] == ["Ala", "Żak", ""]


def test_search_ignores_diacritics_and_case(library):
    library.books.append(Book.new("/p", "file", ["/p"], "Żółte światło", "Jerzy Pilch"))
    assert library.sorted_books(query="zolte")
    assert library.sorted_books(query="PILCH")
    assert not library.sorted_books(query="nieistniejace")


def test_filters(library):
    a = Book.new("/a", "file", ["/a"], "A")
    b = Book.new("/b", "file", ["/b"], "B")
    b["durations"] = [1000]
    b["position_ms"] = 400
    b["last_played_at"] = time.time()
    c = Book.new("/c", "file", ["/c"], "C")
    c["finished"] = True
    library.books += [a, b, c]
    assert [x["title"] for x in library.sorted_books(filter_mode="unplayed")] == ["A"]
    assert [x["title"] for x in library.sorted_books(filter_mode="in_progress")] == ["B"]
    assert [x["title"] for x in library.sorted_books(filter_mode="finished")] == ["C"]


# ---------------------------------------------------------------- Book

def test_book_from_dict_fills_defaults_and_clamps_index():
    b = Book.from_dict({"id": "1", "title": "T", "files": ["a", "b"], "file_index": 9,
                        "durations": [10]})
    assert b["bookmarks"] == [] and b["chapters"] == [] and b["speed"] is None
    assert b["file_index"] == 1
    assert b["durations"] == [10, 0]          # dopełnione do liczby plików


def test_progress_across_files():
    b = Book.from_dict({"id": "1", "files": ["a", "b", "c"], "durations": [100, 200, 300],
                        "file_index": 2, "position_ms": 50})
    assert b.offset_ms() == 300
    assert b.progress_ms == 350
    assert b.total_ms == 600
    assert b.progress_frac == pytest.approx(350 / 600)


def test_chapter_entries_prefer_embedded_chapters():
    b = Book.from_dict({"id": "1", "files": ["x.m4b"], "durations": [1000],
                        "chapters": [{"title": "I", "file_index": 0, "start_ms": 0},
                                     {"title": "II", "file_index": 0, "start_ms": 500}]})
    assert [e[0] for e in b.chapter_entries()] == ["I", "II"]
    assert b.current_chapter_index(0, 499) == 0
    assert b.current_chapter_index(0, 500) == 1
    plain = Book.from_dict({"id": "2", "files": ["a.mp3", "b.mp3"]})
    assert [e[0] for e in plain.chapter_entries()] == ["a.mp3", "b.mp3"]


# ---------------------------------------------------------------- B1: bezpieczeństwo danych

def _write_library(path, n=3):
    books = [Book.new(f"/k/{i}", "file", [f"/k/{i}"], f"Ksiazka {i}") for i in range(n)]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"schema": 2, "books": books, "settings": {"lang": "pl"}}, f)


def test_corrupt_json_is_quarantined_not_destroyed(lib_dir):
    file = os.path.join(lib_dir, "library.json")
    _write_library(file)
    good = open(file, encoding="utf-8").read()
    with open(file, "w", encoding="utf-8") as f:
        f.write(good[:40])                         # ucięty plik
    L = lib.Library(lib_dir)
    assert L.books == [] and L.load_error and "uszkodzony" in L.load_error
    corrupt = [n for n in os.listdir(lib_dir) if ".corrupt-" in n]
    assert len(corrupt) == 1                       # oryginał zachowany
    assert open(os.path.join(lib_dir, corrupt[0]), encoding="utf-8").read() == good[:40]
    assert L.save() is True                        # dalsza praca jest możliwa


def test_unreadable_file_disables_saving_instead_of_overwriting(lib_dir, monkeypatch):
    file = os.path.join(lib_dir, "library.json")
    _write_library(file)
    before = open(file, encoding="utf-8").read()

    def locked(self):
        raise PermissionError("plik zablokowany przez antywirus")
    monkeypatch.setattr(lib.Library, "_read_json", locked)
    L = lib.Library(lib_dir)
    assert L.save_disabled and L.load_error
    L.books.append(Book.new("/n", "file", ["/n"], "Nowa"))
    assert L.save() is False
    assert open(file, encoding="utf-8").read() == before     # NIE nadpisano


def test_malformed_entries_are_skipped_with_copy(lib_dir):
    file = os.path.join(lib_dir, "library.json")
    good = Book.new("/g", "file", ["/g"], "Dobra")
    with open(file, "w", encoding="utf-8") as f:
        json.dump({"books": [good, "to nie obiekt", {"id": "x"}], "settings": {}}, f)
    L = lib.Library(lib_dir)
    assert [b["title"] for b in L.books] == ["Dobra"]
    assert L.load_error and "Pominięto" in L.load_error
    assert any(".corrupt-" in n for n in os.listdir(lib_dir))


def test_roundtrip_and_no_temp_file_left(library):
    library.books.append(Book.new("/p", "file", ["/p"], "T", "A"))
    library.settings["speed"] = 1.25
    assert library.save()
    assert not os.path.exists(library.file + ".tmp")
    again = lib.Library(library.app_dir)
    assert again.books[0]["title"] == "T" and again.settings["speed"] == 1.25
    assert json.load(open(library.file, encoding="utf-8"))["schema"] == lib.SCHEMA_VERSION


def test_save_retries_when_file_is_briefly_locked(library, monkeypatch):
    real = os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("zajęty")
        return real(src, dst)
    monkeypatch.setattr(lib.os, "replace", flaky)
    assert library.save() is True and calls["n"] == 3


def test_save_failure_reports_instead_of_raising(library, monkeypatch):
    monkeypatch.setattr(lib.os, "replace", lambda *a: (_ for _ in ()).throw(PermissionError("x")))
    assert library.save() is False
    assert library.last_save_error


def test_daily_backup_created_and_pruned(lib_dir):
    file = os.path.join(lib_dir, "library.json")
    _write_library(file)
    os.makedirs(os.path.join(lib_dir, "backups"))
    for d in range(1, 12):
        open(os.path.join(lib_dir, "backups", f"library-2020010{d:02d}.json"), "w").close()
    L = lib.Library(lib_dir)
    names = sorted(os.listdir(L.backup_dir))
    assert len(names) == lib.KEEP_DAILY_BACKUPS
    assert time.strftime("library-%Y%m%d.json") in names


# ---------------------------------------------------------------- usuwanie / okładki

def test_remove_deletes_only_covers_inside_covers_dir(library, tmp_path):
    outside = tmp_path / "moje_zdjecie.jpg"
    outside.write_bytes(b"x")
    inside = os.path.join(library.covers_dir, "a.jpg")
    open(inside, "wb").write(b"x")
    a = Book.new("/a", "file", ["/a"], "A")
    a["cover"] = inside
    b = Book.new("/b", "file", ["/b"], "B")
    b["cover"] = str(outside)
    library.books += [a, b]
    library.remove(a)
    library.remove(b)
    assert not os.path.exists(inside)
    assert outside.exists()                         # plik użytkownika nietknięty
    assert library.books == []


# ---------------------------------------------------------------- skanowanie

def test_add_paths_dedupes_and_classifies(library, audio_dir):
    make_wav(audio_dir / "Autor - Tytul" / "01.wav")
    make_wav(audio_dir / "Autor - Tytul" / "02.wav")
    make_wav(audio_dir / "Seria" / "Ksiazka A" / "01.wav")
    make_wav(audio_dir / "Seria" / "Ksiazka B" / "01.wav")
    make_wav(audio_dir / "luzem.wav")
    added = library.add_paths([str(audio_dir / "Autor - Tytul"), str(audio_dir / "Seria")])
    titles = sorted(b["title"] for b in added)
    assert titles == ["Ksiazka A", "Ksiazka B", "Tytul"]
    assert added[0]["author"] == "Autor" or any(b["author"] == "Autor" for b in added)
    assert library.add_paths([str(audio_dir / "Autor - Tytul")]) == []     # duplikat
    assert len(library.books) == 3


def test_multi_disc_order_is_by_full_path(audio_dir):
    for disc in ("CD1", "CD2"):
        for n in ("02", "10", "01"):
            make_wav(audio_dir / "Ksiazka" / disc / f"{n}.wav", seconds=1)
    files = scanner.list_audio_files(str(audio_dir / "Ksiazka"))
    rel = [os.path.relpath(f, audio_dir / "Ksiazka").replace(os.sep, "/") for f in files]
    assert rel == ["CD1/01.wav", "CD1/02.wav", "CD1/10.wav",
                   "CD2/01.wav", "CD2/02.wav", "CD2/10.wav"]


def test_add_parent_folder_and_loose_files(library, audio_dir):
    make_wav(audio_dir / "K1" / "a.wav")
    make_wav(audio_dir / "K2" / "a.wav")
    make_wav(audio_dir / "plik.wav")
    (audio_dir / "pusty").mkdir()
    added = library.add_parent_folder(str(audio_dir))
    assert sorted(b["title"] for b in added) == ["K1", "K2", "plik"]


# ---------------------------------------------------------------- statystyki i kopie

def test_record_listening_updates_book_and_daily_stats(library):
    b = Book.new("/a", "file", ["/a"], "A")
    library.record_listening(b, 5000)
    library.record_listening(b, 2500)
    library.record_listening(b, 0)
    assert b["listened_ms"] == 7500
    stats = library.settings["stats"]
    assert stats["total_ms"] == 7500
    assert stats["daily"][time.strftime("%Y-%m-%d")] == 7500


def test_export_and_import_backup_roundtrip(library, lib_dir, tmp_path):
    cover = library.cover_path("abc")
    open(cover, "wb").write(b"jpegdata")
    b = Book.new("/a", "file", ["/a"], "Zachowana", "Autor")
    b["cover"] = cover
    b["bookmarks"] = [{"id": "1", "file_index": 0, "position_ms": 5, "title": "z", "created": 1}]
    library.books.append(b)
    library.settings["lang"] = "en"
    archive = str(tmp_path / "kopia.zip")
    assert library.export_backup(archive) == 1

    other = lib.Library(str(tmp_path / "inny_komputer"))
    assert other.import_backup(archive) == 1
    got = other.books[0]
    assert got["title"] == "Zachowana" and got["bookmarks"][0]["position_ms"] == 5
    assert os.path.dirname(got["cover"]) == other.covers_dir
    assert open(got["cover"], "rb").read() == b"jpegdata"
    assert other.settings["lang"] == "en"


def test_import_rejects_garbage_and_path_traversal(library, tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"to nie jest zip")
    with pytest.raises(ValueError):
        library.import_backup(str(bad))
    nolib = tmp_path / "nolib.zip"
    with zipfile.ZipFile(nolib, "w") as z:
        z.writestr("cos.txt", "x")
    with pytest.raises(ValueError):
        library.import_backup(str(nolib))

    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("library.json", json.dumps({"books": [], "settings": {}}))
        z.writestr("covers/../../ucieczka.txt", "zle")
        z.writestr("covers/ok.jpg", "dobre")
    library.save()                      # istnieje bieżący plik => import zrobi jego kopię
    library.import_backup(str(evil))
    assert not os.path.exists(os.path.join(os.path.dirname(library.app_dir), "ucieczka.txt"))
    assert not os.path.exists(os.path.join(library.app_dir, "ucieczka.txt"))
    assert os.path.exists(os.path.join(library.covers_dir, "ok.jpg"))
    assert any(n.startswith("before-restore-") for n in os.listdir(library.backup_dir))


def test_guess_title_author():
    assert scanner.guess_title_author("Jerzy Pilch - Żółte światło [PL]") == ("Żółte światło", "Jerzy Pilch")
    assert scanner.guess_title_author("Ksiazka_bez_autora (audiobook)") == ("Ksiazka bez autora", "")


def test_backup_import_rejects_unsafe_ids_and_cover_names(tmp_path):
    """Kopia zapasowa z niezaufanego źródła nie może pisać poza katalogiem okładek."""
    import json
    import zipfile
    import library as lib
    L = lib.Library(str(tmp_path / "data"))
    evil = {"schema": 2, "settings": {}, "books": [
        {"id": r"..\..\evil", "title": "A", "files": [], "cover": "x.jpg"},
        {"id": "ok1", "title": "B", "files": [], "cover": "C:evil.jpg"}]}
    zp = tmp_path / "bad.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("library.json", json.dumps(evil))
        z.writestr("covers/C:evil.jpg", b"x")
        z.writestr(r"covers/..\up.jpg", b"x")
        z.writestr("covers/good-1.jpg", b"x")
    assert L.import_backup(str(zp)) == 2
    assert all(lib._SAFE_ID.match(b["id"]) for b in L.books)
    assert os.listdir(L.covers_dir) == ["good-1.jpg"]
    assert not (tmp_path / "up.jpg").exists()
    assert os.path.dirname(L.cover_path(r"..\..\x")) == L.covers_dir
