"""Okno główne: panel szczegółów (B6), debounce, grupowanie, filtry, drag&drop,
rozdziały, zakładki, czas całej książki, kopie zapasowe, klawisze."""
import os

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QLabel, QMessageBox

import dialogs
import i18n
import main as appmod
from conftest import make_wav
from models import Book
from widgets import BookItemWidget


@pytest.fixture
def win(qtbot, library):
    w = appmod.MainWindow(library)
    w.ctl.audio.setVolume(0.0)
    qtbot.addWidget(w)
    yield w
    w.ctl.stop(save=False)


def add_books(library, audio_dir, specs):
    books = []
    for title, author in specs:
        p = make_wav(audio_dir / title / "01.wav", seconds=3)
        b = Book.new(str(audio_dir / title), "folder", [p], title=title, author=author)
        b["durations"] = [3000]
        library.books.append(b)
        books.append(b)
    return books


# ---------------------------------------------------------------- B6

def test_details_panel_is_cleared_after_clearing_library(win, library, audio_dir, monkeypatch):
    add_books(library, audio_dir, [("Ksiazka A", "Ala")])
    win.refresh_list()
    win.book_list.setCurrentRow(0)
    assert win.detail_title.text() == "Ksiazka A" and win.chapter_list.count() == 1
    monkeypatch.setattr(dialogs, "confirm", lambda *a, **k: True)
    win.clear_library()
    assert win.book_list.count() == 0
    assert win.detail_title.text() == "" and win.chapter_list.count() == 0   # brak „ducha"


def test_details_panel_cleared_after_removing_only_book(win, library, audio_dir, monkeypatch):
    (b,) = add_books(library, audio_dir, [("Jedyna", "")])
    win.refresh_list()
    win.book_list.setCurrentRow(0)
    monkeypatch.setattr(dialogs, "confirm", lambda *a, **k: True)
    win.remove_book(b)
    assert win.detail_title.text() == "" and library.books == []


# ---------------------------------------------------------------- lista

def test_search_is_debounced(win, library, audio_dir, qtbot, monkeypatch):
    add_books(library, audio_dir, [("Dune", "A"), ("Diuna", "B")])
    win.refresh_list()
    calls = []
    real = win.refresh_list
    monkeypatch.setattr(win, "refresh_list", lambda: (calls.append(1), real()))
    win.search_timer.timeout.disconnect()
    win.search_timer.timeout.connect(win.refresh_list)
    for text in ("d", "du", "dun", "dune"):
        win.search_edit.setText(text)
    assert calls == []                                  # nic nie przebudowano przy pisaniu
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=2000)
    qtbot.wait(300)
    assert len(calls) == 1 and win.book_list.count() == 1


def test_search_ignores_polish_diacritics(win, library, audio_dir):
    add_books(library, audio_dir, [("Żółte światło", "Pilch"), ("Inna", "X")])
    win.search_edit.setText("zolte")
    win.refresh_list()
    assert win.book_list.count() == 1


def test_polish_sort_order_in_list(win, library, audio_dir):
    add_books(library, audio_dir, [("Zebra", ""), ("Łódź", ""), ("Adam", ""), ("Ćma", "")])
    win.sort_combo.setCurrentIndex(win.sort_combo.findData("title"))
    titles = [win.book_from_item(win.book_list.item(i))["title"] for i in range(win.book_list.count())]
    assert titles == ["Adam", "Ćma", "Łódź", "Zebra"]


def test_group_by_author_inserts_non_selectable_headers(win, library, audio_dir):
    add_books(library, audio_dir, [("B1", "Zofia"), ("A1", "Adam"), ("A2", "Adam"), ("N", "")])
    win._toggle_group_authors(True)
    assert win.sort_combo.currentData() == "author"
    items = [win.book_list.item(i) for i in range(win.book_list.count())]
    headers = [it for it in items if not it.data(Qt.ItemDataRole.UserRole)]
    assert [h.text() for h in headers] == ["Adam", "Zofia", "—"]
    assert all(not (h.flags() & Qt.ItemFlag.ItemIsSelectable) for h in headers)
    assert win.book_from_item(headers[0]) is None
    win._toggle_group_authors(False)
    assert win.book_list.count() == 4


def test_filters(win, library, audio_dir):
    a, b, c = add_books(library, audio_dir, [("Nowa", ""), ("WTrakcie", ""), ("Gotowa", "")])
    b["position_ms"] = 1000
    c["finished"] = True
    for flt, expected in (("unplayed", ["Nowa"]), ("in_progress", ["WTrakcie"]),
                          ("finished", ["Gotowa"]), ("all", ["Gotowa", "Nowa", "WTrakcie"])):
        win.filter_combo.setCurrentIndex(win.filter_combo.findData(flt))
        win.sort_combo.setCurrentIndex(win.sort_combo.findData("title"))
        got = sorted(win.book_from_item(win.book_list.item(i))["title"]
                     for i in range(win.book_list.count()))
        assert got == expected, flt


def test_titles_are_shown_literally_not_as_html(qtbot, library):
    b = Book.new("/x", "file", ["/x"], title="<h1>Wielki</h1> & <b>tytul</b>", author="<i>A</i>")
    w = BookItemWidget(b)
    qtbot.addWidget(w)
    texts = {lab.text(): lab.textFormat() for lab in w.findChildren(QLabel)}
    assert "<h1>Wielki</h1> & <b>tytul</b>" in texts
    assert all(fmt == Qt.TextFormat.PlainText for fmt in texts.values())


# ---------------------------------------------------------------- dodawanie

def test_handle_paths_adds_in_background_with_modes(win, library, audio_dir, qtbot):
    make_wav(audio_dir / "Seria" / "CD1" / "01.wav")
    make_wav(audio_dir / "Seria" / "CD2" / "01.wav")
    make_wav(audio_dir / "Inne" / "Ksiazka X" / "a.wav")
    make_wav(audio_dir / "Inne" / "Ksiazka Y" / "a.wav")

    win.handle_paths([str(audio_dir / "Seria")], "auto")           # płyty => jedna książka
    qtbot.waitUntil(lambda: len(library.books) == 1, timeout=8000)
    assert len(library.books[0]["files"]) == 2
    qtbot.waitUntil(lambda: win._scan is None, timeout=3000)

    win.handle_paths([str(audio_dir / "Inne")], "single")          # „Dodaj katalog" => jedna książka
    qtbot.waitUntil(lambda: len(library.books) == 2, timeout=8000)
    qtbot.waitUntil(lambda: win._scan is None, timeout=3000)

    win.handle_paths([str(audio_dir / "Inne")], "many")            # każdy podkatalog osobno
    qtbot.waitUntil(lambda: len(library.books) == 4, timeout=8000)
    assert win.book_list.count() == 4


def test_drop_event_adds_dropped_folder(win, library, audio_dir, qtbot, monkeypatch):
    make_wav(audio_dir / "Przeciagnieta" / "01.wav")
    from PyQt6.QtCore import QMimeData, QUrl
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(audio_dir / "Przeciagnieta"))])

    class FakeDrop:
        def mimeData(self):
            return mime

        def acceptProposedAction(self):
            pass
    win.dropEvent(FakeDrop())
    qtbot.waitUntil(lambda: len(library.books) == 1, timeout=8000)
    assert library.books[0]["title"] == "Przeciagnieta"


def test_scan_skips_already_added_and_reports(win, library, audio_dir, qtbot, monkeypatch):
    (b,) = add_books(library, audio_dir, [("Jest", "")])
    seen = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: seen.append(a[2])))
    win.handle_paths([b["path"]], "single")
    qtbot.waitUntil(lambda: bool(seen), timeout=8000)
    assert "Nie znaleziono nowych" in seen[0] and len(library.books) == 1


def test_second_instance_message_adds_files(win, library, audio_dir, qtbot):
    make_wav(audio_dir / "Z drugiej instancji" / "01.wav")
    win._on_instance_message([str(audio_dir / "Z drugiej instancji")])
    qtbot.waitUntil(lambda: len(library.books) == 1, timeout=8000)


# ---------------------------------------------------------------- odtwarzanie w oknie

@pytest.mark.audio
def test_play_pause_icon_follows_state_and_space_toggles(win, library, audio_dir, qtbot, monkeypatch):
    (b,) = add_books(library, audio_dir, [("Gra", "")])
    win.refresh_list()
    win.book_list.setCurrentRow(0)
    win.toggle_play()                                  # nic nie gra => odtwarza zaznaczoną
    assert win.ctl.current is b
    qtbot.waitUntil(lambda: win.ctl.is_playing, timeout=5000)
    qtbot.waitUntil(lambda: win.ctl._ready, timeout=5000)

    def icon_image():
        return win.play_btn.icon().pixmap(24, 24).toImage()
    playing_icon = icon_image()
    win.ctl.pause()
    qtbot.waitUntil(lambda: icon_image() != playing_icon, timeout=3000)   # ikona = stan odtwarzacza
    win.ctl.resume()
    qtbot.waitUntil(lambda: icon_image() == playing_icon, timeout=3000)

    toggles = []
    monkeypatch.setattr(win, "toggle_play", lambda: toggles.append(1))
    monkeypatch.setattr(win, "isActiveWindow", lambda: True)
    space = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ")
    assert win.eventFilter(win, space) is True and toggles == [1]
    # fokus w polu wyszukiwania => spacja ma trafić do pola, nie do odtwarzacza
    monkeypatch.setattr(appmod.QApplication, "focusWidget", staticmethod(lambda: win.search_edit))
    assert win.eventFilter(win, space) is False and toggles == [1]
    # fokus na przycisku => zachowuje się standardowo (klika przycisk)
    monkeypatch.setattr(appmod.QApplication, "focusWidget", staticmethod(lambda: win.play_btn))
    assert win.eventFilter(win, space) is False and toggles == [1]


@pytest.mark.audio
def test_book_time_label_shows_whole_book_progress(win, library, audio_dir, qtbot):
    p1 = make_wav(audio_dir / "Dluga" / "01.wav", seconds=70)
    p2 = make_wav(audio_dir / "Dluga" / "02.wav", seconds=70)
    b = Book.new(str(audio_dir / "Dluga"), "folder", [p1, p2], title="Dluga")
    b["durations"] = [70000, 70000]
    b["file_index"] = 1
    library.settings["auto_rewind"] = False
    library.books.append(b)
    win.ctl.play_book(b)
    qtbot.waitUntil(lambda: win.ctl._ready and "Książka" in win.book_time_label.text(), timeout=8000)
    text = win.book_time_label.text()
    assert "02:20" in text and "pozostało" in text and text.startswith("Książka: 01:1")
    win.ctl.set_speed(2.0)
    qtbot.waitUntil(lambda: "≈" in win.book_time_label.text(), timeout=5000)


@pytest.mark.audio
def test_chapter_navigation_with_embedded_chapters(win, library, audio_dir, qtbot):
    p = make_wav(audio_dir / "Rozdzialy" / "ksiazka.wav", seconds=30)
    b = Book.new(str(audio_dir / "Rozdzialy"), "file", [p], title="Rozdzialy")
    b["durations"] = [30000]
    b["chapters"] = [{"title": "Wstęp", "file_index": 0, "start_ms": 0},
                     {"title": "Rozdział 1", "file_index": 0, "start_ms": 10000},
                     {"title": "Rozdział 2", "file_index": 0, "start_ms": 20000}]
    library.books.append(b)
    win.refresh_list()
    win.book_list.setCurrentRow(0)
    assert [win.chapter_list.item(i).text() for i in range(3)] == [
        "1. Wstęp  (00:10)", "2. Rozdział 1  (00:10)", "3. Rozdział 2  (00:10)"]
    win.ctl.play_book(b)
    qtbot.waitUntil(lambda: win.ctl._ready, timeout=8000)
    win.next_chapter()
    qtbot.waitUntil(lambda: 9900 <= win.ctl.player.position() <= 13000, timeout=5000)
    assert b.current_chapter_index(0, win.ctl.player.position()) == 1
    qtbot.waitUntil(lambda: win.chapter_list.currentRow() == 1, timeout=3000)
    win.next_chapter()
    qtbot.waitUntil(lambda: win.ctl.player.position() >= 19900, timeout=5000)
    win.prev_chapter()                                  # <5 s od początku rozdziału => poprzedni
    qtbot.waitUntil(lambda: 9900 <= win.ctl.player.position() <= 13000, timeout=5000)
    win.jump_to_chapter(win.chapter_list.item(0))
    qtbot.waitUntil(lambda: win.ctl.player.position() < 3000, timeout=5000)


@pytest.mark.audio
def test_bookmark_flow_from_window(win, library, audio_dir, qtbot, monkeypatch):
    (b,) = add_books(library, audio_dir, [("Zakladki", "")])
    win.add_bookmark()
    assert "podczas odtwarzania" in win.statusBar().currentMessage()
    win.ctl.play_book(b)
    qtbot.waitUntil(lambda: win.ctl._ready, timeout=8000)
    win.add_bookmark()
    assert len(b["bookmarks"]) == 1 and "Zakładka" in win.statusBar().currentMessage()

    class FakeDlg:
        jump_to, changed = (0, 1500), True

        def __init__(self, book, parent=None):
            pass

        def exec(self):
            pass

        def deleteLater(self):
            pass
    monkeypatch.setattr(dialogs, "BookmarksDialog", FakeDlg)
    win.show_bookmarks()
    qtbot.waitUntil(lambda: win.ctl.player.position() >= 1400, timeout=5000)


# ---------------------------------------------------------------- język, motyw, ustawienia

@pytest.mark.audio
def test_language_switch_keeps_state_and_translates(win, library, audio_dir, qtbot):
    (b,) = add_books(library, audio_dir, [("Stan", "")])
    win.ctl.play_book(b)
    qtbot.waitUntil(lambda: win.ctl._ready, timeout=8000)
    win.ctl.start_sleep(end_of_file=True)
    win.apply_language("en")
    assert i18n.language() == "en"
    assert "Add folder" in [a.text() for a in win.toolbar.actions() if a.text()]
    assert win.windowTitle() == "Audiobook Player"
    assert win.ctl.current is b and win.sleep_btn.text() == "⏰ end of file"
    assert win.sort_combo.itemText(0) == "Recently played"
    assert win.filter_combo.itemText(2) == "Unplayed"
    win.apply_language("pl")
    assert win.windowTitle() == "Odtwarzacz audiobooków"


def test_theme_switch_rebuilds_without_losing_list(win, library, audio_dir):
    add_books(library, audio_dir, [("A", ""), ("B", "")])
    win.refresh_list()
    for name in ("dark", "light", "system"):
        win.apply_theme(name)
        assert win.book_list.count() == 2 and library.settings["theme"] == name


def test_settings_toggles_are_persisted(win, library):
    win._set_option("auto_rewind", False)
    win._set_option("per_book_speed", False)
    import library as lib
    again = lib.Library(library.app_dir)
    assert again.settings["auto_rewind"] is False and again.settings["per_book_speed"] is False


def test_google_key_setting_reaches_metadata_module(win, library, monkeypatch):
    import metadata
    class FakeDlg:
        def __init__(self, parent=None): pass
        def setWindowTitle(self, *a): pass
        def setLabelText(self, *a): pass
        def setTextValue(self, v): self.v = v
        def setOkButtonText(self, *a): pass
        def setCancelButtonText(self, *a): pass
        def exec(self): return True
        def textValue(self): return "  KLUCZ123 "
    monkeypatch.setattr(appmod, "QInputDialog", FakeDlg)
    try:
        win.set_google_key()
        assert metadata.CONFIG["google_api_key"] == "KLUCZ123"
        assert library.settings["google_api_key"] == "  KLUCZ123 ".strip()
    finally:
        metadata.configure(google_api_key="")


# ---------------------------------------------------------------- kopie, błędy

def test_backup_export_and_import_through_window(win, library, audio_dir, tmp_path, monkeypatch):
    add_books(library, audio_dir, [("Kopia", "Autor")])
    archive = str(tmp_path / "k.zip")
    monkeypatch.setattr(appmod.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (archive, "")))
    win.export_backup()
    assert os.path.exists(archive)
    library.books.clear()
    monkeypatch.setattr(appmod.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (archive, "")))
    monkeypatch.setattr(dialogs, "confirm", lambda *a, **k: True)
    win.import_backup()
    assert [b["title"] for b in library.books] == ["Kopia"] and win.book_list.count() == 1


def test_import_of_bad_archive_shows_warning_and_keeps_library(win, library, audio_dir, tmp_path, monkeypatch):
    add_books(library, audio_dir, [("Zostaje", "")])
    bad = tmp_path / "zly.zip"
    bad.write_bytes(b"xx")
    shown = []
    monkeypatch.setattr(appmod.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(bad), "")))
    monkeypatch.setattr(dialogs, "confirm", lambda *a, **k: True)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[2])))
    win.import_backup()
    assert shown and [b["title"] for b in library.books] == ["Zostaje"]


def test_startup_warns_about_corrupt_library(qtbot, lib_dir, monkeypatch):
    import library as lib
    with open(os.path.join(lib_dir, "library.json"), "w", encoding="utf-8") as f:
        f.write("{ucięty")
    L = lib.Library(lib_dir)
    L.settings["lang"] = "pl"
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[2])))
    w = appmod.MainWindow(L)
    qtbot.addWidget(w)
    w._startup_checks()
    assert shown and "uszkodzony" in shown[0]


def test_unexpected_error_dialog_mentions_log_path(win, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a[2])))
    win.show_error("KeyError: x")
    import paths
    assert "KeyError: x" in shown[0] and paths.LOG_FILE in shown[0]


@pytest.mark.audio
def test_close_saves_progress_volume_and_library(win, library, audio_dir, qtbot):
    (b,) = add_books(library, audio_dir, [("Zamkniecie", "")])
    win.ctl.play_book(b)
    qtbot.waitUntil(lambda: win.ctl._ready and win.ctl.player.position() > 400, timeout=8000)
    win.vol_slider.setValue(33)
    win.close()
    import library as lib
    again = lib.Library(library.app_dir)
    assert again.books[0]["position_ms"] > 0
    assert again.settings["volume"] == pytest.approx(0.33, abs=0.02)
