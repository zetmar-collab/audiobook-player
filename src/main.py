"""Audiobook Player — odtwarzacz audiobooków na Windows.

Funkcje: biblioteka (katalogi i pojedyncze pliki), zapamiętywanie pozycji,
metadane z lubimyczytac.pl / upolujebooka.pl / Google Books, sortowanie,
prędkość odtwarzania, wyłącznik czasowy (sleep timer), przewijanie ±.
"""
import os
import sys
import time

from PyQt6.QtCore import Qt, QTimer, QUrl, QSize, pyqtSignal as Signal, QThread
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QProgressBar, QPushButton, QSlider, QSplitter, QTextEdit,
    QToolBar, QVBoxLayout, QWidget, QStyle, QInputDialog, QSizePolicy,
)

import library as lib
import metadata as meta


def fmt_ms(ms):
    s = max(0, int(ms // 1000))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def default_cover(size=96):
    pm = QPixmap(size, size)
    pm.fill(QColor("#39424e"))
    p = QPainter(pm)
    p.setPen(QColor("#aab6c2"))
    f = QFont()
    f.setPointSize(int(size * 0.45))
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "🎧")
    p.end()
    return pm


# ------------------------------------------------------------ wątek metadanych

class SearchWorker(QThread):
    done = Signal(list)

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.query = query

    def run(self):
        self.done.emit(meta.search_all(self.query))


class ApplyWorker(QThread):
    done = Signal(dict)

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = dict(result)

    def run(self):
        self.done.emit(meta.fetch_details(self.result))


# ------------------------------------------------------------ dialog metadanych

class MetadataDialog(QDialog):
    """Wyszukiwanie metadanych w internecie i wybór wyniku."""

    def __init__(self, book, parent=None):
        super().__init__(parent)
        self.book = book
        self.results = []
        self.chosen = None
        self.setWindowTitle(f"Metadane — {book['title']}")
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.query_edit = QLineEdit(f"{book['author']} {book['title']}".strip())
        self.search_btn = QPushButton("Szukaj")
        self.search_btn.clicked.connect(self.do_search)
        row.addWidget(self.query_edit, 1)
        row.addWidget(self.search_btn)
        layout.addLayout(row)

        split = QSplitter()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.show_preview)
        split.addWidget(self.list)
        right = QWidget()
        rlay = QVBoxLayout(right)
        self.preview_cover = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.preview_cover.setFixedHeight(180)
        self.preview_text = QTextEdit(readOnly=True)
        rlay.addWidget(self.preview_cover)
        rlay.addWidget(self.preview_text, 1)
        split.addWidget(right)
        split.setSizes([340, 380])
        layout.addWidget(split, 1)

        self.status = QLabel("")
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Zastosuj")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Anuluj")
        buttons.accepted.connect(self.accept_choice)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.query_edit.returnPressed.connect(self.do_search)
        self.do_search()

    def do_search(self):
        q = self.query_edit.text().strip()
        if not q:
            return
        self.status.setText("Szukam…")
        self.search_btn.setEnabled(False)
        self.list.clear()
        self.worker = SearchWorker(q, self)
        self.worker.done.connect(self.on_results)
        self.worker.start()

    def on_results(self, results):
        self.results = results
        self.search_btn.setEnabled(True)
        self.status.setText(f"Znaleziono {len(results)} wyników" if results
                            else "Brak wyników — zmień zapytanie.")
        for r in results:
            author = f" — {r['author']}" if r["author"] else ""
            QListWidgetItem(f"[{r['source']}] {r['title']}{author}", self.list)
        if results:
            self.list.setCurrentRow(0)

    def show_preview(self, row):
        if row < 0 or row >= len(self.results):
            return
        r = self.results[row]
        self.preview_text.setPlainText(
            f"{r['title']}\n{r['author']}\nŹródło: {r['source']}\n\n{r['description']}")
        self.preview_cover.setPixmap(default_cover(160))
        if r.get("cover_url"):
            def load(url=r["cover_url"], row_=row):
                import requests as rq
                try:
                    data = rq.get(url, headers=meta.HEADERS, timeout=10).content
                    pm = QPixmap()
                    if pm.loadFromData(data) and self.list.currentRow() == row_:
                        self.preview_cover.setPixmap(
                            pm.scaledToHeight(170, Qt.TransformationMode.SmoothTransformation))
                except Exception:
                    pass
            import threading
            threading.Thread(target=load, daemon=True).start()

    def accept_choice(self):
        row = self.list.currentRow()
        if row < 0:
            self.reject()
            return
        self.status.setText("Pobieram szczegóły…")
        self.setEnabled(False)
        self.apply_worker = ApplyWorker(self.results[row], self)
        self.apply_worker.done.connect(self.on_details)
        self.apply_worker.start()

    def on_details(self, result):
        self.chosen = result
        self.accept()


# ------------------------------------------------------------ element listy

class BookItemWidget(QWidget):
    def __init__(self, book):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        cover = QLabel()
        cover.setFixedSize(56, 56)
        pm = None
        if book.get("cover") and os.path.exists(book["cover"]):
            pm = QPixmap(book["cover"])
        if pm is None or pm.isNull():
            pm = default_cover(56)
        cover.setPixmap(pm.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(cover)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(book["title"])
        f = title.font()
        f.setBold(True)
        title.setFont(f)
        author = QLabel(book["author"] or "—")
        author.setStyleSheet("color: gray;")
        info_bits = []
        if book["kind"] == "folder":
            info_bits.append(f"{len(book['files'])} plików")
        if book.total_ms:
            info_bits.append(fmt_ms(book.total_ms))
        if book.get("finished"):
            info_bits.append("✔ ukończony")
        info = QLabel(" · ".join(info_bits))
        info.setStyleSheet("color: gray; font-size: 11px;")
        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(int(book.progress_frac * 1000))
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        col.addWidget(title)
        col.addWidget(author)
        col.addWidget(info)
        col.addWidget(bar)
        lay.addLayout(col, 1)

        pct = QLabel(f"{int(book.progress_frac * 100)}%")
        pct.setStyleSheet("color: gray;")
        lay.addWidget(pct)


# ------------------------------------------------------------ okno główne

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audiobook Player")
        self.resize(1000, 680)
        self.library = lib.Library()
        self.current = None  # aktualnie odtwarzany Book

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(self.library.settings.get("volume", 0.9))
        self.player.positionChanged.connect(self.on_position)
        self.player.mediaStatusChanged.connect(self.on_media_status)
        self.player.errorOccurred.connect(self.on_player_error)
        self.pending_seek = None
        self.slider_down = False

        self.save_timer = QTimer(self, interval=5000, timeout=self.save_progress)
        self.sleep_timer = QTimer(self, singleShot=True, timeout=self.on_sleep_timeout)

        self._build_ui()
        self.refresh_list()

    # ---------------------------------------------------------------- UI

    def _build_ui(self):
        tb = QToolBar("Główny", movable=False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        style = self.style()

        def act(text, icon, slot):
            a = QAction(style.standardIcon(icon), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        act("Dodaj katalog", QStyle.StandardPixmap.SP_DirOpenIcon, self.add_folder)
        act("Dodaj wiele katalogów", QStyle.StandardPixmap.SP_DirIcon, self.add_many)
        act("Dodaj plik", QStyle.StandardPixmap.SP_FileIcon, self.add_file)
        tb.addSeparator()
        act("Wyczyść bibliotekę", QStyle.StandardPixmap.SP_TrashIcon, self.clear_library)
        tb.addSeparator()

        tb.addWidget(QLabel(" Sortuj: "))
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Ostatnio słuchane", "recent")
        self.sort_combo.addItem("Tytuł", "title")
        self.sort_combo.addItem("Autor", "author")
        self.sort_combo.addItem("Ostatnio dodane", "added")
        self.sort_combo.currentIndexChanged.connect(self.refresh_list)
        tb.addWidget(self.sort_combo)
        self.search_edit = QLineEdit(placeholderText="Szukaj w bibliotece…", clearButtonEnabled=True)
        self.search_edit.setMaximumWidth(240)
        self.search_edit.textChanged.connect(self.refresh_list)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(self.search_edit)

        # środek: lista książek + panel rozdziałów
        split = QSplitter()
        self.book_list = QListWidget()
        self.book_list.setIconSize(QSize(56, 56))
        self.book_list.itemDoubleClicked.connect(self.play_selected)
        self.book_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.book_list.customContextMenuRequested.connect(self.book_menu)
        split.addWidget(self.book_list)

        right = QWidget()
        rlay = QVBoxLayout(right)
        self.detail_cover = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.detail_cover.setMinimumHeight(150)
        self.detail_title = QLabel(alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        f = self.detail_title.font()
        f.setPointSize(12)
        f.setBold(True)
        self.detail_title.setFont(f)
        self.detail_author = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.detail_author.setStyleSheet("color: gray;")
        self.chapter_list = QListWidget()
        self.chapter_list.itemDoubleClicked.connect(self.jump_to_chapter)
        self.detail_desc = QTextEdit(readOnly=True)
        self.detail_desc.setMaximumHeight(130)
        rlay.addWidget(self.detail_cover)
        rlay.addWidget(self.detail_title)
        rlay.addWidget(self.detail_author)
        rlay.addWidget(QLabel("Pliki / rozdziały:"))
        rlay.addWidget(self.chapter_list, 1)
        rlay.addWidget(self.detail_desc)
        split.addWidget(right)
        split.setSizes([620, 380])
        self.book_list.currentItemChanged.connect(lambda *_: self.show_details())

        # dolny pasek odtwarzacza
        bottom = QWidget()
        blay = QVBoxLayout(bottom)
        blay.setContentsMargins(8, 4, 8, 6)

        srow = QHBoxLayout()
        self.pos_label = QLabel("00:00")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(lambda: setattr(self, "slider_down", True))
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.dur_label = QLabel("00:00")
        srow.addWidget(self.pos_label)
        srow.addWidget(self.slider, 1)
        srow.addWidget(self.dur_label)
        blay.addLayout(srow)

        crow = QHBoxLayout()
        self.now_label = QLabel("Nic nie odtwarzam")
        self.now_label.setMinimumWidth(220)
        crow.addWidget(self.now_label, 1)

        def btn(icon, tip, slot, text=None):
            b = QPushButton(text) if text else QPushButton()
            if not text:
                b.setIcon(self.style().standardIcon(icon))
            b.setToolTip(tip)
            b.clicked.connect(slot)
            crow.addWidget(b)
            return b

        btn(QStyle.StandardPixmap.SP_MediaSkipBackward, "Poprzedni plik", self.prev_file)
        btn(None, "Cofnij 30 s", lambda: self.skip(-30000), "−30s")
        btn(None, "Cofnij 10 s", lambda: self.skip(-10000), "−10s")
        self.play_btn = btn(QStyle.StandardPixmap.SP_MediaPlay, "Odtwórz / pauza", self.toggle_play)
        btn(None, "Do przodu 10 s", lambda: self.skip(10000), "+10s")
        btn(None, "Do przodu 30 s", lambda: self.skip(30000), "+30s")
        btn(QStyle.StandardPixmap.SP_MediaSkipForward, "Następny plik", self.next_file)

        crow.addSpacing(12)
        crow.addWidget(QLabel("Prędkość:"))
        self.speed_combo = QComboBox()
        for s in ["0.5", "0.75", "0.9", "1.0", "1.1", "1.25", "1.5", "1.75", "2.0", "2.5", "3.0"]:
            self.speed_combo.addItem(f"{s}×", float(s))
        self.speed_combo.setCurrentText(f"{self.library.settings.get('speed', 1.0):g}×")
        self.speed_combo.currentIndexChanged.connect(self.on_speed)

        crow.addWidget(self.speed_combo)
        crow.addSpacing(12)
        crow.addWidget(QLabel("🔊"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.audio.volume() * 100))
        self.vol_slider.setFixedWidth(90)
        self.vol_slider.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        crow.addWidget(self.vol_slider)
        crow.addSpacing(12)
        self.sleep_btn = QPushButton("⏰ Usypianie")
        self.sleep_btn.setToolTip("Zatrzymaj odtwarzanie po zadanym czasie")
        self.sleep_btn.clicked.connect(self.set_sleep_timer)
        crow.addWidget(self.sleep_btn)
        blay.addLayout(crow)

        central = QWidget()
        clay = QVBoxLayout(central)
        clay.setContentsMargins(0, 0, 0, 0)
        clay.addWidget(split, 1)
        clay.addWidget(bottom)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Gotowy")

    # ---------------------------------------------------------------- lista

    def refresh_list(self):
        selected_id = self.current["id"] if self.current else None
        cur_item = self.book_list.currentItem()
        if cur_item:
            selected_id = cur_item.data(Qt.ItemDataRole.UserRole)
        self.book_list.clear()
        mode = self.sort_combo.currentData()
        for book in self.library.sorted_books(mode, self.search_edit.text()):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, book["id"])
            widget = BookItemWidget(book)
            item.setSizeHint(widget.sizeHint())
            self.book_list.addItem(item)
            self.book_list.setItemWidget(item, widget)
            if book["id"] == selected_id:
                self.book_list.setCurrentItem(item)

    def book_from_item(self, item):
        if not item:
            return None
        bid = item.data(Qt.ItemDataRole.UserRole)
        return next((b for b in self.library.books if b["id"] == bid), None)

    def selected_book(self):
        return self.book_from_item(self.book_list.currentItem())

    def show_details(self):
        book = self.selected_book() or self.current
        if not book:
            return
        pm = None
        if book.get("cover") and os.path.exists(book["cover"]):
            pm = QPixmap(book["cover"])
        if pm is None or pm.isNull():
            pm = default_cover(140)
        self.detail_cover.setPixmap(
            pm.scaledToHeight(150, Qt.TransformationMode.SmoothTransformation))
        self.detail_title.setText(book["title"])
        self.detail_author.setText(book["author"] or "—")
        self.detail_desc.setPlainText(book.get("description") or "")
        self.chapter_list.clear()
        for i, f in enumerate(book["files"]):
            dur = book["durations"][i] if i < len(book["durations"]) else 0
            mark = "▶ " if (self.current is book and book["file_index"] == i) else ""
            QListWidgetItem(f"{mark}{i + 1}. {os.path.basename(f)}  ({fmt_ms(dur)})",
                            self.chapter_list)
        if self.current is book:
            self.chapter_list.setCurrentRow(book["file_index"])

    # ---------------------------------------------------------------- dodawanie

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Wybierz katalog z audiobookiem")
        if not folder:
            return
        b = self.library.add_folder(folder)
        if b:
            self.statusBar().showMessage(f"Dodano: {b['title']}", 5000)
        else:
            QMessageBox.information(self, "Audiobook Player",
                                    "Katalog już jest w bibliotece albo nie zawiera plików audio.")
        self.library.save()
        self.refresh_list()

    def add_many(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Wybierz katalog nadrzędny — każdy podkatalog stanie się audiobookiem")
        if not folder:
            return
        added = self.library.add_parent_folder(folder)
        self.statusBar().showMessage(f"Dodano {len(added)} audiobooków", 5000)
        if not added:
            QMessageBox.information(self, "Audiobook Player",
                                    "Nie znaleziono nowych audiobooków w podkatalogach.")
        self.library.save()
        self.refresh_list()

    def add_file(self):
        exts = " ".join(f"*{e}" for e in sorted(lib.AUDIO_EXTS))
        paths, _ = QFileDialog.getOpenFileNames(self, "Wybierz plik(i) audio", "",
                                                f"Pliki audio ({exts})")
        count = 0
        for p in paths:
            if self.library.add_file(p):
                count += 1
        if paths:
            self.statusBar().showMessage(f"Dodano {count} plików", 5000)
            self.library.save()
            self.refresh_list()

    # ---------------------------------------------------------------- usuwanie

    def clear_library(self):
        if not self.library.books:
            return
        if QMessageBox.question(
                self, "Wyczyść bibliotekę",
                f"Usunąć wszystkie {len(self.library.books)} pozycji z biblioteki?\n"
                "Pliki audio na dysku NIE zostaną skasowane.") == QMessageBox.StandardButton.Yes:
            self.stop_playback()
            self.library.clear()
            self.library.save()
            self.refresh_list()

    def remove_book(self, book):
        if QMessageBox.question(
                self, "Usuń audiobook",
                f"Usunąć „{book['title']}” z biblioteki?\n"
                "Pliki audio na dysku NIE zostaną skasowane.") == QMessageBox.StandardButton.Yes:
            if self.current is book:
                self.stop_playback()
            self.library.remove(book)
            self.library.save()
            self.refresh_list()

    # ---------------------------------------------------------------- menu

    def book_menu(self, pos):
        item = self.book_list.itemAt(pos)
        book = self.book_from_item(item)
        if not book:
            return
        menu = QMenu(self)
        menu.addAction("▶ Odtwórz (wznów)", lambda: self.play_book(book))
        menu.addAction("Odtwórz od początku", lambda: self.play_book(book, restart=True))
        menu.addSeparator()
        menu.addAction("Pobierz metadane z internetu…", lambda: self.fetch_metadata(book))
        menu.addAction("Edytuj tytuł/autora…", lambda: self.edit_metadata(book))
        menu.addSeparator()
        if book.get("finished"):
            menu.addAction("Oznacz jako nieukończony", lambda: self.set_finished(book, False))
        else:
            menu.addAction("Oznacz jako ukończony", lambda: self.set_finished(book, True))
        menu.addAction("Wyzeruj postęp", lambda: self.reset_progress(book))
        menu.addSeparator()
        menu.addAction("Otwórz lokalizację na dysku",
                       lambda: os.startfile(book["path"] if book["kind"] == "folder"
                                            else os.path.dirname(book["path"])))
        menu.addAction("Usuń z biblioteki", lambda: self.remove_book(book))
        menu.exec(self.book_list.mapToGlobal(pos))

    def set_finished(self, book, val):
        book["finished"] = val
        if val:
            book["file_index"] = 0
            book["position_ms"] = 0
        self.library.save()
        self.refresh_list()

    def reset_progress(self, book):
        book["file_index"] = 0
        book["position_ms"] = 0
        book["finished"] = False
        self.library.save()
        self.refresh_list()

    def edit_metadata(self, book):
        title, ok = QInputDialog.getText(self, "Tytuł", "Tytuł:", text=book["title"])
        if not ok:
            return
        author, ok = QInputDialog.getText(self, "Autor", "Autor:", text=book["author"])
        if not ok:
            return
        book["title"] = title.strip() or book["title"]
        book["author"] = author.strip()
        self.library.save()
        self.refresh_list()
        self.show_details()

    def fetch_metadata(self, book):
        dlg = MetadataDialog(book, self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.chosen:
            return
        r = dlg.chosen
        if r.get("title"):
            book["title"] = r["title"]
        if r.get("author"):
            book["author"] = r["author"]
        if r.get("description"):
            book["description"] = r["description"]
        if r.get("cover_url"):
            dest = os.path.join(lib.COVERS_DIR, book["id"] + ".jpg")
            if meta.download_cover(r["cover_url"], dest):
                book["cover"] = dest
        self.library.save()
        self.refresh_list()
        self.show_details()
        self.statusBar().showMessage("Metadane zaktualizowane", 5000)

    # ---------------------------------------------------------------- odtwarzanie

    def play_selected(self, item):
        book = self.book_from_item(item)
        if book:
            self.play_book(book)

    def play_book(self, book, restart=False):
        self.save_progress()
        if restart:
            book["file_index"] = 0
            book["position_ms"] = 0
            book["finished"] = False
        self.current = book
        book["last_played_at"] = time.time()
        self.load_current_file(seek_ms=book["position_ms"])
        self.player.play()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.save_timer.start()
        self.update_now_label()
        self.refresh_list()
        self.show_details()

    def load_current_file(self, seek_ms=0):
        book = self.current
        idx = max(0, min(book["file_index"], len(book["files"]) - 1))
        book["file_index"] = idx
        path = book["files"][idx]
        if not os.path.exists(path):
            self.statusBar().showMessage(f"Brak pliku: {path}", 8000)
            return
        self.pending_seek = seek_ms if seek_ms > 0 else None
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.setPlaybackRate(self.speed_combo.currentData() or 1.0)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.save_progress()
        elif self.current:
            self.player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            book = self.selected_book()
            if book:
                self.play_book(book)

    def stop_playback(self):
        self.save_progress()
        self.player.stop()
        self.player.setSource(QUrl())
        self.current = None
        self.save_timer.stop()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.now_label.setText("Nic nie odtwarzam")

    def skip(self, delta_ms):
        if self.current:
            self.player.setPosition(max(0, self.player.position() + delta_ms))

    def next_file(self):
        if not self.current:
            return
        if self.current["file_index"] + 1 < len(self.current["files"]):
            self.current["file_index"] += 1
            self.current["position_ms"] = 0
            self.load_current_file()
            self.player.play()
            self.update_now_label()
            self.show_details()
        else:
            self.finish_book()

    def prev_file(self):
        if not self.current:
            return
        # jeśli >5 s w pliku — wróć na jego początek, inaczej poprzedni plik
        if self.player.position() > 5000 or self.current["file_index"] == 0:
            self.player.setPosition(0)
        else:
            self.current["file_index"] -= 1
            self.current["position_ms"] = 0
            self.load_current_file()
            self.player.play()
            self.update_now_label()
            self.show_details()

    def finish_book(self):
        book = self.current
        self.stop_playback()
        if book:
            book["finished"] = True
            book["file_index"] = 0
            book["position_ms"] = 0
            self.library.save()
            self.refresh_list()
            self.statusBar().showMessage(f"Ukończono: {book['title']} 🎉", 8000)

    def jump_to_chapter(self, item):
        book = self.selected_book() or self.current
        if not book:
            return
        row = self.chapter_list.row(item)
        book["file_index"] = row
        book["position_ms"] = 0
        if self.current is not book:
            self.current = book
            book["last_played_at"] = time.time()
        self.load_current_file()
        self.player.play()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.save_timer.start()
        self.update_now_label()
        self.show_details()

    def update_now_label(self):
        if not self.current:
            return
        b = self.current
        chapter = ""
        if len(b["files"]) > 1:
            chapter = f"  ·  plik {b['file_index'] + 1}/{len(b['files'])}"
        self.now_label.setText(f"▶ {b['title']}{chapter}")

    # ---------------------------------------------------------------- zdarzenia playera

    def on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self.pending_seek:
            self.player.setPosition(self.pending_seek)
            self.pending_seek = None
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next_file()

    def on_player_error(self, _err, err_str):
        self.statusBar().showMessage(f"Błąd odtwarzania: {err_str}", 8000)

    def on_position(self, pos):
        if not self.slider_down:
            self.slider.setRange(0, self.player.duration())
            self.slider.setValue(pos)
        self.pos_label.setText(fmt_ms(pos))
        self.dur_label.setText(fmt_ms(self.player.duration()))

    def on_slider_released(self):
        self.slider_down = False
        self.player.setPosition(self.slider.value())

    def on_speed(self):
        rate = self.speed_combo.currentData() or 1.0
        self.player.setPlaybackRate(rate)
        self.library.settings["speed"] = rate

    # ---------------------------------------------------------------- sleep timer

    def set_sleep_timer(self):
        options = ["Wyłącz", "15 minut", "30 minut", "45 minut", "60 minut", "90 minut"]
        choice, ok = QInputDialog.getItem(self, "Wyłącznik czasowy",
                                          "Zatrzymaj odtwarzanie po:", options, 0, False)
        if not ok:
            return
        self.sleep_timer.stop()
        self.sleep_btn.setText("⏰ Usypianie")
        if choice != "Wyłącz":
            minutes = int(choice.split()[0])
            self.sleep_timer.start(minutes * 60 * 1000)
            self.sleep_btn.setText(f"⏰ {minutes} min")
            self.statusBar().showMessage(f"Odtwarzanie zatrzyma się za {minutes} min", 5000)

    def on_sleep_timeout(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.save_progress()
        self.sleep_btn.setText("⏰ Usypianie")
        self.statusBar().showMessage("Wyłącznik czasowy: odtwarzanie zatrzymane", 8000)

    # ---------------------------------------------------------------- zapis

    def save_progress(self):
        if self.current and self.player.source().isValid():
            self.current["position_ms"] = self.player.position()
            self.current["last_played_at"] = time.time()
            self.library.settings["volume"] = self.audio.volume()
            self.library.save()

    def closeEvent(self, event):
        self.save_progress()
        self.library.settings["volume"] = self.audio.volume()
        self.library.save()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Audiobook Player")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
