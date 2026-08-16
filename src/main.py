"""Audiobook Player — odtwarzacz audiobooków (Windows/Linux).

Funkcje: biblioteka (katalogi i pojedyncze pliki), zapamiętywanie pozycji,
metadane z serwisów polskich i zagranicznych, sortowanie, prędkość odtwarzania,
wyłącznik czasowy (sleep timer), przewijanie ±, język PL/EN, motyw jasny/ciemny.
"""
import os
import sys
import time

from PyQt6.QtCore import Qt, QTimer, QUrl, QSize, pyqtSignal as Signal, QThread
from PyQt6.QtGui import (QAction, QActionGroup, QDesktopServices, QIcon, QPixmap,
                         QPainter, QColor, QFont)
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QProgressBar, QPushButton, QSlider, QSplitter, QTextEdit,
    QToolBar, QVBoxLayout, QWidget, QStyle, QInputDialog, QSizePolicy,
)

import i18n
import library as lib
import metadata as meta
import theme as themes
from i18n import tr

APP_VERSION = "1.2.0"

#: Minuty dla wyłącznika czasowego; None = wyłączony.
SLEEP_OPTIONS = [None, 15, 30, 45, 60, 90]


def fmt_ms(ms):
    s = max(0, int(ms // 1000))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def default_cover(size=96):
    pm = QPixmap(size, size)
    pm.fill(QColor(themes.COVER_BG[themes.active()]))
    p = QPainter(pm)
    p.setPen(QColor(themes.COVER_FG[themes.active()]))
    f = QFont()
    f.setPointSize(int(size * 0.45))
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "🎧")
    p.end()
    return pm


def app_icon():
    """Ikona okna — z pliku obok exe/skryptu, inaczej rysowana zastępcza.

    Windows używa .ico, Linux .png (patrz AudiobookPlayer.spec).
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for name in ("icon.ico", "icon.png"):
        path = os.path.join(base, name)
        if os.path.exists(path):
            return QIcon(path)
    return QIcon(default_cover(64))


# ------------------------------------------------------------ wątek metadanych

class SearchWorker(QThread):
    done = Signal(list)

    def __init__(self, query, parent=None):
        super().__init__(parent)
        self.query = query

    def run(self):
        self.done.emit(meta.search_all(self.query, lang=i18n.language()))


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
        self.setWindowTitle(tr("meta_dialog_title", title=book["title"]))
        self.resize(760, 500)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.query_edit = QLineEdit(f"{book['author']} {book['title']}".strip())
        self.search_btn = QPushButton(tr("meta_search"))
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
        split.setSizes([360, 400])
        layout.addWidget(split, 1)

        self.status = QLabel("")
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("meta_apply"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("meta_cancel"))
        buttons.accepted.connect(self.accept_choice)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.query_edit.returnPressed.connect(self.do_search)
        self.do_search()

    def do_search(self):
        q = self.query_edit.text().strip()
        if not q:
            return
        self.status.setText(tr("meta_searching"))
        self.search_btn.setEnabled(False)
        self.list.clear()
        self.worker = SearchWorker(q, self)
        self.worker.done.connect(self.on_results)
        self.worker.start()

    def on_results(self, results):
        self.results = results
        self.search_btn.setEnabled(True)
        self.status.setText(tr("meta_found", n=len(results)) if results else tr("meta_none"))
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
            f"{r['title']}\n{r['author']}\n{tr('meta_source')}: {r['source']}\n\n"
            f"{r['description']}")
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
        self.status.setText(tr("meta_fetching"))
        self.setEnabled(False)
        self.apply_worker = ApplyWorker(self.results[row], self)
        self.apply_worker.done.connect(self.on_details)
        self.apply_worker.start()

    def on_details(self, result):
        self.chosen = result
        self.accept()


# ------------------------------------------------------------ element listy

class BookItemWidget(QWidget):
    def __init__(self, book, playing=False):
        super().__init__()
        muted = themes.muted_color()
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
        title = QLabel(("▶ " if playing else "") + book["title"])
        f = title.font()
        f.setBold(True)
        title.setFont(f)
        author = QLabel(book["author"] or tr("no_author"))
        author.setStyleSheet(f"color: {muted};")
        info_bits = []
        if book["kind"] == "folder":
            info_bits.append(i18n.plural_files(len(book["files"])))
        if book.total_ms:
            info_bits.append(fmt_ms(book.total_ms))
        if book.get("finished"):
            info_bits.append(tr("badge_finished"))
        info = QLabel(" · ".join(info_bits))
        info.setStyleSheet(f"color: {muted}; font-size: 11px;")
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
        pct.setStyleSheet(f"color: {muted};")
        lay.addWidget(pct)


# ------------------------------------------------------------ okno główne

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.library = lib.Library()
        self.current = None  # aktualnie odtwarzany Book

        # język i motyw z ustawień (przy pierwszym uruchomieniu — z systemu)
        lang = self.library.settings.get("lang") or i18n.detect_system_language()
        i18n.set_language(lang)
        self.library.settings["lang"] = lang
        self.theme_name = self.library.settings.get("theme", "system")

        self.setWindowTitle(tr("app_title"))
        self.setWindowIcon(app_icon())
        self.resize(1020, 700)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(self.library.settings.get("volume", 0.9))
        self.player.positionChanged.connect(self.on_position)
        self.player.mediaStatusChanged.connect(self.on_media_status)
        self.player.errorOccurred.connect(self.on_player_error)
        self.pending_seek = None
        self.slider_down = False
        self.toolbar = None

        self.save_timer = QTimer(self, interval=5000, timeout=self.save_progress)
        self.sleep_timer = QTimer(self, singleShot=True, timeout=self.on_sleep_timeout)

        self._build_ui()
        self.refresh_list()

    # ---------------------------------------------------------------- UI

    def _build_menu(self):
        bar = self.menuBar()
        bar.clear()

        settings_menu = bar.addMenu(tr("menu_settings"))

        lang_menu = settings_menu.addMenu(tr("menu_language"))
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        for code, label in i18n.LANGUAGES:
            a = QAction(label, self, checkable=True)
            a.setChecked(code == i18n.language())
            a.triggered.connect(lambda _checked, c=code: self.apply_language(c))
            lang_group.addAction(a)
            lang_menu.addAction(a)

        theme_menu = settings_menu.addMenu(tr("menu_theme"))
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for code, key in (("light", "theme_light"), ("dark", "theme_dark"),
                          ("system", "theme_system")):
            a = QAction(tr(key), self, checkable=True)
            a.setChecked(code == self.theme_name)
            a.triggered.connect(lambda _checked, c=code: self.apply_theme(c))
            theme_group.addAction(a)
            theme_menu.addAction(a)

        help_menu = bar.addMenu(tr("menu_help"))
        about = QAction(tr("menu_about"), self)
        about.triggered.connect(self.show_about)
        help_menu.addAction(about)

    def _build_ui(self):
        self._build_menu()

        tb = QToolBar(tr("toolbar_main"), movable=False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        self.toolbar = tb
        style = self.style()

        def act(text, icon, slot):
            a = QAction(style.standardIcon(icon), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        act(tr("add_folder"), QStyle.StandardPixmap.SP_DirOpenIcon, self.add_folder)
        act(tr("add_many"), QStyle.StandardPixmap.SP_DirIcon, self.add_many)
        act(tr("add_file"), QStyle.StandardPixmap.SP_FileIcon, self.add_file)
        tb.addSeparator()
        act(tr("clear_library"), QStyle.StandardPixmap.SP_TrashIcon, self.clear_library)
        tb.addSeparator()

        tb.addWidget(QLabel(tr("sort")))
        self.sort_combo = QComboBox()
        self.sort_combo.addItem(tr("sort_recent"), "recent")
        self.sort_combo.addItem(tr("sort_title"), "title")
        self.sort_combo.addItem(tr("sort_author"), "author")
        self.sort_combo.addItem(tr("sort_added"), "added")
        self.sort_combo.currentIndexChanged.connect(self.refresh_list)
        tb.addWidget(self.sort_combo)
        self.search_edit = QLineEdit(placeholderText=tr("search_placeholder"),
                                     clearButtonEnabled=True)
        self.search_edit.setMaximumWidth(240)
        self.search_edit.textChanged.connect(self.refresh_list)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(self.search_edit)

        # środek: lista książek + panel szczegółów
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
        self.detail_author.setStyleSheet(f"color: {themes.muted_color()};")
        self.chapter_list = QListWidget()
        self.chapter_list.itemDoubleClicked.connect(self.jump_to_chapter)
        self.detail_desc = QTextEdit(readOnly=True)
        self.detail_desc.setMaximumHeight(130)
        rlay.addWidget(self.detail_cover)
        rlay.addWidget(self.detail_title)
        rlay.addWidget(self.detail_author)
        rlay.addWidget(QLabel(tr("files_chapters")))
        rlay.addWidget(self.chapter_list, 1)
        rlay.addWidget(self.detail_desc)
        split.addWidget(right)
        split.setSizes([620, 400])
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
        self.now_label = QLabel(tr("nothing_playing"))
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

        btn(QStyle.StandardPixmap.SP_MediaSkipBackward, tr("prev_file"), self.prev_file)
        btn(None, tr("back_30"), lambda: self.skip(-30000), "−30s")
        btn(None, tr("back_10"), lambda: self.skip(-10000), "−10s")
        self.play_btn = btn(QStyle.StandardPixmap.SP_MediaPlay, tr("play_pause"),
                            self.toggle_play)
        btn(None, tr("fwd_10"), lambda: self.skip(10000), "+10s")
        btn(None, tr("fwd_30"), lambda: self.skip(30000), "+30s")
        btn(QStyle.StandardPixmap.SP_MediaSkipForward, tr("next_file"), self.next_file)

        crow.addSpacing(12)
        crow.addWidget(QLabel(tr("speed")))
        self.speed_combo = QComboBox()
        for s in ["0.5", "0.75", "0.9", "1.0", "1.1", "1.25", "1.5", "1.75", "2.0", "2.5", "3.0"]:
            self.speed_combo.addItem(f"{s}×", float(s))
        idx = self.speed_combo.findData(float(self.library.settings.get("speed", 1.0)))
        self.speed_combo.setCurrentIndex(idx if idx >= 0 else self.speed_combo.findData(1.0))
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
        self.sleep_btn = QPushButton(tr("sleep_btn"))
        self.sleep_btn.setToolTip(tr("sleep_tooltip"))
        self.sleep_btn.clicked.connect(self.set_sleep_timer)
        crow.addWidget(self.sleep_btn)
        blay.addLayout(crow)

        central = QWidget()
        clay = QVBoxLayout(central)
        clay.setContentsMargins(0, 0, 0, 0)
        clay.addWidget(split, 1)
        clay.addWidget(bottom)
        self.setCentralWidget(central)
        self.statusBar().showMessage(tr("ready"))

    def rebuild_ui(self):
        """Przebudowuje interfejs po zmianie języka/motywu, zachowując stan."""
        sort_mode = self.sort_combo.currentData() if self.toolbar else "recent"
        query = self.search_edit.text() if self.toolbar else ""
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

        if self.toolbar:
            self.removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
        old_central = self.takeCentralWidget()
        if old_central:
            old_central.deleteLater()

        self.setWindowTitle(tr("app_title"))
        self._build_ui()

        idx = self.sort_combo.findData(sort_mode)
        if idx >= 0:
            self.sort_combo.setCurrentIndex(idx)
        self.search_edit.setText(query)
        self.refresh_list()
        if self.current:
            self.update_now_label()
            self.show_details()
            if playing:
                self.play_btn.setIcon(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.on_position(self.player.position())

    # ---------------------------------------------------------------- ustawienia

    def apply_language(self, lang):
        if lang == i18n.language():
            return
        i18n.set_language(lang)
        self.library.settings["lang"] = lang
        self.library.save()
        self.rebuild_ui()

    def apply_theme(self, name):
        self.theme_name = name
        self.library.settings["theme"] = name
        self.library.save()
        themes.apply_theme(QApplication.instance(), name)
        self.rebuild_ui()

    def show_about(self):
        QMessageBox.about(self, tr("about_title"), tr("about_text", version=APP_VERSION))

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
            widget = BookItemWidget(book, playing=(self.current is book))
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
        self.detail_author.setText(book["author"] or tr("no_author"))
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
        folder = QFileDialog.getExistingDirectory(self, tr("dlg_choose_folder"))
        if not folder:
            return
        b = self.library.add_folder(folder)
        if b:
            self.statusBar().showMessage(tr("added_book", title=b["title"]), 5000)
        else:
            QMessageBox.information(self, tr("app_title"), tr("info_folder_exists"))
        self.library.save()
        self.refresh_list()

    def add_many(self):
        folder = QFileDialog.getExistingDirectory(self, tr("dlg_choose_parent"))
        if not folder:
            return
        added = self.library.add_parent_folder(folder)
        self.statusBar().showMessage(tr("added_books", n=len(added)), 5000)
        if not added:
            QMessageBox.information(self, tr("app_title"), tr("info_no_new"))
        self.library.save()
        self.refresh_list()

    def add_file(self):
        exts = " ".join(f"*{e}" for e in sorted(lib.AUDIO_EXTS))
        paths, _ = QFileDialog.getOpenFileNames(self, tr("dlg_choose_files"), "",
                                                f"{tr('audio_files')} ({exts})")
        count = 0
        for p in paths:
            if self.library.add_file(p):
                count += 1
        if paths:
            self.statusBar().showMessage(tr("added_files", n=count), 5000)
            self.library.save()
            self.refresh_list()

    # ---------------------------------------------------------------- usuwanie

    def clear_library(self):
        if not self.library.books:
            return
        if QMessageBox.question(
                self, tr("clear_title"),
                tr("clear_question", n=len(self.library.books))
        ) == QMessageBox.StandardButton.Yes:
            self.stop_playback()
            self.library.clear()
            self.library.save()
            self.refresh_list()

    def remove_book(self, book):
        if QMessageBox.question(
                self, tr("remove_title"), tr("remove_question", title=book["title"])
        ) == QMessageBox.StandardButton.Yes:
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
        menu.addAction(tr("ctx_play"), lambda: self.play_book(book))
        menu.addAction(tr("ctx_play_start"), lambda: self.play_book(book, restart=True))
        menu.addSeparator()
        menu.addAction(tr("ctx_metadata"), lambda: self.fetch_metadata(book))
        menu.addAction(tr("ctx_edit"), lambda: self.edit_metadata(book))
        menu.addSeparator()
        if book.get("finished"):
            menu.addAction(tr("ctx_mark_undone"), lambda: self.set_finished(book, False))
        else:
            menu.addAction(tr("ctx_mark_done"), lambda: self.set_finished(book, True))
        menu.addAction(tr("ctx_reset"), lambda: self.reset_progress(book))
        menu.addSeparator()
        menu.addAction(tr("ctx_open_location"),
                       lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(
                           book["path"] if book["kind"] == "folder"
                           else os.path.dirname(book["path"]))))
        menu.addAction(tr("ctx_remove"), lambda: self.remove_book(book))
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
        title, ok = QInputDialog.getText(self, tr("edit_title"), tr("edit_title_label"),
                                         text=book["title"])
        if not ok:
            return
        author, ok = QInputDialog.getText(self, tr("edit_author"), tr("edit_author_label"),
                                          text=book["author"])
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
        self.statusBar().showMessage(tr("meta_updated"), 5000)

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
            self.statusBar().showMessage(tr("missing_file", path=path), 8000)
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
        self.now_label.setText(tr("nothing_playing"))

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
            self.statusBar().showMessage(tr("finished_msg", title=book["title"]), 8000)

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
            chapter = tr("file_x_of_y", i=b["file_index"] + 1, n=len(b["files"]))
        self.now_label.setText(f"▶ {b['title']}{chapter}")

    # ---------------------------------------------------------------- zdarzenia playera

    def on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self.pending_seek:
            self.player.setPosition(self.pending_seek)
            self.pending_seek = None
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next_file()

    def on_player_error(self, _err, err_str):
        self.statusBar().showMessage(tr("play_error", err=err_str), 8000)

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
        labels = [tr("sleep_off")] + [tr("sleep_minutes", n=m) for m in SLEEP_OPTIONS[1:]]
        choice, ok = QInputDialog.getItem(self, tr("sleep_title"), tr("sleep_prompt"),
                                          labels, 0, False)
        if not ok:
            return
        minutes = SLEEP_OPTIONS[labels.index(choice)]
        self.sleep_timer.stop()
        self.sleep_btn.setText(tr("sleep_btn"))
        if minutes:
            self.sleep_timer.start(minutes * 60 * 1000)
            self.sleep_btn.setText(tr("sleep_short", n=minutes))
            self.statusBar().showMessage(tr("sleep_will_stop", n=minutes), 5000)

    def on_sleep_timeout(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.save_progress()
        self.sleep_btn.setText(tr("sleep_btn"))
        self.statusBar().showMessage(tr("sleep_stopped"), 8000)

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
    # motyw musi być ustawiony przed utworzeniem okna, żeby paleta objęła widgety
    saved = lib.Library()
    themes.apply_theme(app, saved.settings.get("theme", "system"))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
