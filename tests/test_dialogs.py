"""Dialogi: wyścig zapytań (B4), błędy źródeł, okładki, zakładki, wsadowe metadane, statystyki."""
import os
import time

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QLabel

import dialogs
import i18n
import metadata as meta
from models import Book
from test_i18n_covers import _jpeg_bytes


def res(title, source="S", cover="http://x/c.jpg", author=""):
    return {"source": source, "title": title, "author": author, "description": "opis",
            "cover_url": cover, "url": ""}


@pytest.fixture
def book(library):
    b = Book.new("/k/Autor - Dune", "file", ["/k/a.mp3"], title="Dune", author="Frank Herbert")
    library.books.append(b)
    return b


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    meta.clear_cache()
    monkeypatch.setattr(meta, "fetch_image_bytes", lambda url, **k: None)
    yield
    meta.clear_cache()


def slow_then_fast(monkeypatch, stale_title="STARE", fresh_title="NOWE"):
    calls = {"n": 0}

    def fake(query, lang="pl", use_cache=True):
        calls["n"] += 1
        if calls["n"] == 1:
            time.sleep(0.8)
            return meta.SearchOutcome([res(f"{stale_title}-{i}") for i in range(3)], {})
        time.sleep(0.05)
        return meta.SearchOutcome([res(f"{fresh_title}-{i}") for i in range(2)], {})
    monkeypatch.setattr(meta, "search_all", fake)


# ---------------------------------------------------------------- B4

@pytest.mark.parametrize("kind", ["cover", "metadata"])
def test_late_answer_of_old_search_is_ignored(qtbot, monkeypatch, library, book, kind):
    slow_then_fast(monkeypatch)
    dlg = (dialogs.CoverDialog(library, book) if kind == "cover"
           else dialogs.MetadataDialog(book))
    qtbot.addWidget(dlg)
    qtbot.wait(150)
    dlg.do_search()                                    # Enter drugi raz
    qtbot.waitUntil(lambda: dlg.list.count() == 2, timeout=5000)
    qtbot.wait(1200)                                   # spóźniona odpowiedź starego zapytania
    assert [r["title"] for r in dlg.results] == ["NOWE-0", "NOWE-1"]
    assert dlg.list.count() == 2                       # lista zgodna z wynikami
    dlg.list.setCurrentRow(0)
    assert dlg.current_result()["title"] == "NOWE-0"
    assert "NOWE-0" in dlg.list.item(0).text()


def test_closing_dialog_ignores_pending_results(qtbot, monkeypatch, library, book):
    slow_then_fast(monkeypatch)
    dlg = dialogs.CoverDialog(library, book)
    qtbot.addWidget(dlg)
    dlg.reject()
    qtbot.wait(1200)
    assert dlg.results == [] and dlg.list.count() == 0


def test_status_distinguishes_no_results_from_unavailable_sources(qtbot, monkeypatch, library, book):
    monkeypatch.setattr(meta, "search_all", lambda q, lang="pl", use_cache=True: meta.SearchOutcome(
        [], {"Audible": ("offline", ""), "Google Books": ("rate_limit", 429)}))
    dlg = dialogs.MetadataDialog(book)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: "Audible" in dlg.status.text(), timeout=5000)
    assert "brak połączenia" in dlg.status.text() and "limit zapytań" in dlg.status.text()
    monkeypatch.setattr(meta, "search_all",
                        lambda q, lang="pl", use_cache=True: meta.SearchOutcome([], {}))
    dlg.do_search()
    qtbot.waitUntil(lambda: "Brak wyników" in dlg.status.text(), timeout=5000)


def test_search_status_variants_in_both_languages():
    ok = dialogs.search_status(3, {"Audible": ("timeout", "")})
    assert "Znaleziono wyników: 3" in ok and "Audible (przekroczono czas)" in ok
    i18n.set_language("en")
    assert "Couldn't get any results" in dialogs.search_status(0, {"X": ("http", 503)})
    assert "HTTP error 503" in dialogs.search_status(0, {"X": ("http", 503)})
    assert dialogs.search_status(0, {}) == "No results — try a different query."
    assert "all services" in dialogs.format_errors({"*": ("error", "Boom")})


def test_worker_exception_does_not_leave_dialog_stuck(qtbot, monkeypatch, library, book):
    def boom(*a, **k):
        raise RuntimeError("awaria")
    monkeypatch.setattr(meta, "search_all", boom)
    dlg = dialogs.MetadataDialog(book)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: "Szukam" not in dlg.status.text(), timeout=5000)
    assert "RuntimeError" in dlg.status.text()


# ---------------------------------------------------------------- okładki

def test_cover_dialog_only_lists_results_with_cover_url(qtbot, monkeypatch, library, book):
    monkeypatch.setattr(meta, "search_all", lambda q, lang="pl", use_cache=True: meta.SearchOutcome(
        [res("Z okładką"), res("Bez okładki", cover="")], {}))
    dlg = dialogs.CoverDialog(library, book)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.list.count() == 1, timeout=5000)
    assert dlg.results[0]["title"] == "Z okładką"


def test_stale_thumbnail_is_not_applied(qtbot, monkeypatch, library, book):
    monkeypatch.setattr(meta, "search_all", lambda q, lang="pl", use_cache=True: meta.SearchOutcome(
        [res("A"), res("B")], {}))
    dlg = dialogs.CoverDialog(library, book)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.list.count() == 2, timeout=5000)
    img = QImage(10, 10, QImage.Format.Format_RGB32)
    img.fill(QColor("red"))
    dlg._thumb_loaded(dlg.generation - 1, 0, img)      # miniatura ze starego wyszukiwania
    assert 0 not in dlg.images
    dlg._thumb_loaded(dlg.generation, 5, img)          # wiersz spoza listy
    assert 5 not in dlg.images
    dlg._thumb_loaded(dlg.generation, 1, img)
    assert 1 in dlg.images


def test_cover_dialog_downloads_and_normalizes_selected_cover(qtbot, monkeypatch, library, book):
    jpeg = _jpeg_bytes(2400, 1600)
    monkeypatch.setattr(meta, "search_all", lambda q, lang="pl", use_cache=True: meta.SearchOutcome(
        [res("Dune")], {}))
    monkeypatch.setattr(meta, "fetch_image_bytes", lambda url, **k: jpeg)
    dlg = dialogs.CoverDialog(library, book)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.list.count() == 1, timeout=5000)
    with qtbot.waitSignal(dlg.accepted, timeout=8000):
        dlg.accept_choice()
    assert dlg.result_path == library.cover_path(book["id"])
    img = QImage(dlg.result_path)
    assert max(img.width(), img.height()) <= 1000


def test_cover_download_failure_reenables_button(qtbot, monkeypatch, library, book):
    monkeypatch.setattr(meta, "search_all", lambda q, lang="pl", use_cache=True: meta.SearchOutcome(
        [res("Dune")], {}))
    dlg = dialogs.CoverDialog(library, book)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.list.count() == 1, timeout=5000)
    dlg.accept_choice()
    qtbot.waitUntil(lambda: dlg.ok_btn.isEnabled(), timeout=8000)
    assert "Nie udało się pobrać" in dlg.status.text() and dlg.result_path is None


def test_cover_from_disk_file(qtbot, monkeypatch, library, book, tmp_path):
    src = tmp_path / "moja.png"
    big = QImage(3000, 2000, QImage.Format.Format_RGB32)
    big.fill(QColor("green"))
    big.save(str(src), "PNG")
    monkeypatch.setattr(meta, "search_all",
                        lambda q, lang="pl", use_cache=True: meta.SearchOutcome([], {}))
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(src), "")))
    dlg = dialogs.CoverDialog(library, book)
    qtbot.addWidget(dlg)
    dlg.choose_file()
    assert dlg.result_path and max(QImage(dlg.result_path).size().width(), 1) <= 1000
    # zły plik
    bad = tmp_path / "zly.png"
    bad.write_bytes(b"nie obraz")
    dlg.result_path = None
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(bad), "")))
    dlg.choose_file()
    assert dlg.result_path is None and "Nie udało się wczytać" in dlg.status.text()


# ---------------------------------------------------------------- metadane

def test_metadata_dialog_returns_details(qtbot, monkeypatch, library, book):
    monkeypatch.setattr(meta, "search_all", lambda q, lang="pl", use_cache=True: meta.SearchOutcome(
        [res("Dune", "Audible", author="Frank Herbert")], {}))
    monkeypatch.setattr(meta, "fetch_details", lambda r: {**r, "description": "Pełny opis"})
    dlg = dialogs.MetadataDialog(book)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.list.count() == 1, timeout=5000)
    with qtbot.waitSignal(dlg.accepted, timeout=5000):
        dlg.accept_choice()
    assert dlg.chosen["description"] == "Pełny opis" and dlg.chosen["author"] == "Frank Herbert"


# ---------------------------------------------------------------- zakładki

def make_bookmarked(library):
    b = Book.from_dict({"id": "b1", "title": "K", "files": ["a", "b"], "durations": [60000, 60000],
                        "bookmarks": [
                            {"id": "x1", "file_index": 0, "position_ms": 5000, "title": "Pierwsza", "created": 1},
                            {"id": "x2", "file_index": 1, "position_ms": 1000, "title": "Druga", "created": 2}]})
    library.books.append(b)
    return b


def test_bookmarks_dialog_lists_with_book_level_time_and_jumps(qtbot, library):
    b = make_bookmarked(library)
    dlg = dialogs.BookmarksDialog(b)
    qtbot.addWidget(dlg)
    assert dlg.list.item(0).text() == "[00:05] Pierwsza"
    assert dlg.list.item(1).text() == "[01:01] Druga"      # 60 s (plik 1) + 1 s
    dlg.list.setCurrentRow(1)
    dlg.go()
    assert dlg.jump_to == (1, 1000)


def test_bookmarks_dialog_rename_delete_and_empty_state(qtbot, library, monkeypatch):
    b = make_bookmarked(library)
    dlg = dialogs.BookmarksDialog(b)
    qtbot.addWidget(dlg)
    monkeypatch.setattr(dialogs.QInputDialog, "getText", staticmethod(lambda *a, **k: ("  Nowa nazwa ", True)))
    dlg.list.setCurrentRow(0)
    dlg.rename()
    assert b["bookmarks"][0]["title"] == "Nowa nazwa" and dlg.changed
    dlg.delete()
    assert [x["id"] for x in b["bookmarks"]] == ["x2"]
    dlg.list.setCurrentRow(0)
    dlg.delete()
    assert b["bookmarks"] == []
    assert "Brak zakładek" in dlg.list.item(0).text()
    dlg.go()                                              # nic nie zaznaczone => brak skoku
    assert dlg.jump_to is None


# ---------------------------------------------------------------- wsadowe metadane

def test_batch_dialog_proposes_checks_confident_and_applies(qtbot, monkeypatch, library):
    a = Book.new("/a", "file", ["/a"], title="Dune", author="Frank Herbert")
    b = Book.new("/b", "file", ["/b"], title="Zupełnie nieznana pozycja", author="")
    library.books += [a, b]

    def fake_search(q, lang="pl", use_cache=True):
        if "Dune" in q:
            return meta.SearchOutcome([res("Dune", "Audible", author="Frank Herbert")], {})
        return meta.SearchOutcome([res("Całkiem inny tytuł")], {})
    monkeypatch.setattr(meta, "search_all", fake_search)
    monkeypatch.setattr(meta, "fetch_details", lambda r: {**r, "title": "Dune (pełny)"})
    monkeypatch.setattr(meta, "fetch_image_bytes", lambda url, **k: _jpeg_bytes())

    dlg = dialogs.BatchMetadataDialog(library, [a, b])
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.apply_btn.isEnabled(), timeout=8000)
    assert dlg.tree.topLevelItemCount() == 1             # niepewne dopasowanie odrzucone
    item = dlg.tree.topLevelItem(0)
    assert item.checkState(0) == Qt.CheckState.Checked
    with qtbot.waitSignal(dlg.accepted, timeout=10000):
        dlg.apply_selected()
    assert dlg.applied == 1
    assert a["title"] == "Dune (pełny)" and a["description"] == "opis"
    assert os.path.exists(a["cover"]) and os.path.dirname(a["cover"]) == library.covers_dir
    assert b["cover"] == "" and b["title"] == "Zupełnie nieznana pozycja"


def test_batch_dialog_unchecked_proposals_change_nothing(qtbot, monkeypatch, library):
    a = Book.new("/a", "file", ["/a"], title="Dune", author="")
    library.books.append(a)
    monkeypatch.setattr(meta, "search_all", lambda q, lang="pl", use_cache=True: meta.SearchOutcome(
        [res("Dune!")], {}))
    monkeypatch.setattr(meta, "fetch_details", lambda r: dict(r))
    dlg = dialogs.BatchMetadataDialog(library, [a])
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg.apply_btn.isEnabled(), timeout=8000)
    dlg.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
    dlg.apply_selected()
    assert dlg.applied == 0 and a["description"] == ""


# ---------------------------------------------------------------- statystyki, tekst

def test_stats_dialog_builds_with_and_without_data(qtbot, library):
    dlg = dialogs.StatsDialog(library)                    # pusta biblioteka
    qtbot.addWidget(dlg)
    b = Book.new("/a", "file", ["/a"], title="Słuchana")
    library.books.append(b)
    library.record_listening(b, 90_000)
    b["finished"] = True
    dlg2 = dialogs.StatsDialog(library)
    qtbot.addWidget(dlg2)
    labels = " ".join(w.text() for w in dlg2.findChildren(QLabel))
    assert "01:30" in labels and "ukończone: 1" in labels and "Dzisiaj: 01:30" in labels


def test_text_view_and_resource_reader(qtbot, tmp_path):
    dlg = dialogs.TextViewDialog("Tytuł", "Treść\nlicencji")
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Tytuł"
    assert dialogs.read_resource_text("plik_ktorego_nie_ma.xyz") is None
    assert "GNU GENERAL PUBLIC LICENSE" in (dialogs.read_resource_text("LICENSE") or "")
