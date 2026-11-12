"""Audiobook Player — okno główne i punkt startowy aplikacji.

Logika odtwarzania jest w `player_ctl.PlayerController`, okna dialogowe w `dialogs`,
dane w `library`, sieć w `metadata`/`workers`. Ten plik składa z nich interfejs.
"""
import os
import sys
import time

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import (QAction, QActionGroup, QDesktopServices, QIcon, QKeySequence,
                         QPixmapCache)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressDialog,
    QPushButton, QSizePolicy, QSlider, QSplitter, QStyle, QTextEdit, QToolBar, QVBoxLayout,
    QWidget, QToolButton,
)

import appinfo
import applog
import covers
import dialogs
import i18n
import library as lib
import metadata as meta
import paths
import theme as themes
import winmedia
import workers
from i18n import tr
from player_ctl import PlayerController
from singleinstance import SingleInstance
from util import fmt_ms
from widgets import BookItemWidget, cached_default_cover, plain_label

APP_VERSION = appinfo.APP_VERSION

#: Opcje wyłącznika czasowego w minutach.
SLEEP_MINUTES = [15, 30, 45, 60, 90]
SPEEDS = ["0.5", "0.75", "0.9", "1.0", "1.1", "1.25", "1.5", "1.75", "2.0", "2.5", "3.0"]


def app_icon():
    """Ikona okna: .ico (Windows) albo .png (Linux) z zasobów aplikacji."""
    for name in ("icon.ico", "icon.png"):
        path = paths.resource_path(name)
        if path:
            return QIcon(path)
    return QIcon(covers.default_cover(64))


class MainWindow(QMainWindow):
    def __init__(self, library, single=None):
        super().__init__()
        self.library = library

        # język i motyw z ustawień (przy pierwszym uruchomieniu — z systemu)
        lang = library.settings.get("lang") or i18n.detect_system_language()
        i18n.set_language(lang)
        library.settings["lang"] = lang
        self.theme_name = library.settings.get("theme", "system")
        meta.configure(google_api_key=library.settings.get("google_api_key", ""))

        self.setWindowTitle(tr("app_title"))
        self.setWindowIcon(app_icon())
        self.resize(1020, 700)
        self.setAcceptDrops(True)

        self.ctl = PlayerController(library, self)
        self.ctl.stateChanged.connect(self._on_state)
        self.ctl.bookChanged.connect(self._on_book_changed)
        self.ctl.fileChanged.connect(self._on_file_changed)
        self.ctl.positionChanged.connect(self._on_position)
        self.ctl.libraryChanged.connect(self.refresh_list)
        self.ctl.speedChanged.connect(self._sync_speed)
        self.ctl.sleepChanged.connect(self._on_sleep)
        self.ctl.message.connect(lambda m: self.statusBar().showMessage(m, 9000))

        self.slider_down = False
        self.toolbar = None
        self._actions = []
        self._sleep_state = -1
        self._scan = None
        self._scan_progress = None

        self.search_timer = QTimer(self, singleShot=True, interval=200)
        self.search_timer.timeout.connect(self.refresh_list)

        self.media_keys = winmedia.MediaKeys({
            "play_pause": self.toggle_play, "next": self.next_chapter,
            "prev": self.prev_chapter, "stop": self.ctl.pause})

        self._build_ui()
        self.refresh_list()
        QApplication.instance().installEventFilter(self)
        if single is not None:
            single.messageReceived.connect(self._on_instance_message)
        QTimer.singleShot(0, self._startup_checks)

    # ---------------------------------------------------------------- start

    def _startup_checks(self):
        if self.library.load_error:
            QMessageBox.warning(self, tr("app_title"),
                                tr("load_warning", detail=self.library.load_error))

    def show_error(self, text):
        QMessageBox.critical(self, tr("app_title"),
                             tr("unexpected_error", err=text, log=paths.LOG_FILE))

    def _on_instance_message(self, paths_list):
        """Druga instancja przekazała pliki (np. „Otwórz za pomocą…") albo tylko prosi o okno."""
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if paths_list:
            self.handle_paths(paths_list)

    # ---------------------------------------------------------------- UI

    def _clear_actions(self):
        for a in self._actions:
            self.removeAction(a)
            a.deleteLater()
        self._actions = []

    def _act(self, text, slot, shortcut=None, checkable=False, checked=False, in_window=False):
        a = QAction(text, self, checkable=checkable)
        if checkable:
            a.setChecked(checked)
            a.toggled.connect(slot)
        else:
            a.triggered.connect(lambda _c=False, s=slot: s())
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
            a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        if in_window:
            self.addAction(a)
        self._actions.append(a)
        return a

    def _build_menu(self):
        self._clear_actions()
        bar = self.menuBar()
        bar.clear()
        s = self.library.settings

        m = bar.addMenu(tr("menu_library"))
        m.addAction(self._act(tr("add_folder"), self.add_folder, "Ctrl+O"))
        m.addAction(self._act(tr("add_many"), self.add_many))
        m.addAction(self._act(tr("add_file"), self.add_file))
        m.addSeparator()
        m.addAction(self._act(tr("clear_library"), self.clear_library))   # destrukcyjne: tylko w menu
        m.addAction(self._act(tr("batch_menu"), self.batch_metadata))
        m.addAction(self._act(tr("stats_menu"), self.show_stats))
        m.addSeparator()
        m.addAction(self._act(tr("backup_export"), self.export_backup))
        m.addAction(self._act(tr("backup_import"), self.import_backup))
        m.addAction(self._act(tr("open_data_folder"), lambda: self._open_folder(paths.APP_DIR)))

        m = bar.addMenu(tr("menu_playback"))
        m.addAction(self._act(f"{tr('play_pause')}\tSpace", self.toggle_play))
        m.addAction(self._act(tr("back_10"), lambda: self.ctl.skip(-10000), "Ctrl+Left", in_window=True))
        m.addAction(self._act(tr("fwd_10"), lambda: self.ctl.skip(10000), "Ctrl+Right", in_window=True))
        m.addAction(self._act(tr("back_30"), lambda: self.ctl.skip(-30000), "Ctrl+Shift+Left", in_window=True))
        m.addAction(self._act(tr("fwd_30"), lambda: self.ctl.skip(30000), "Ctrl+Shift+Right", in_window=True))
        m.addAction(self._act(tr("prev_chapter"), self.prev_chapter, "Ctrl+PgUp", in_window=True))
        m.addAction(self._act(tr("next_chapter"), self.next_chapter, "Ctrl+PgDown", in_window=True))
        m.addSeparator()
        m.addAction(self._act(tr("volume_up"), lambda: self._volume(+5), "Ctrl+Up", in_window=True))
        m.addAction(self._act(tr("volume_down"), lambda: self._volume(-5), "Ctrl+Down", in_window=True))
        m.addSeparator()
        m.addAction(self._act(tr("bookmark_add"), self.add_bookmark, "Ctrl+B"))
        m.addAction(self._act(tr("bookmarks_open"), self.show_bookmarks, "Ctrl+Shift+B"))
        self._act("", self.focus_search, "Ctrl+F", in_window=True)
        self._act("", self.remove_selected, "Delete", in_window=True)

        m = bar.addMenu(tr("menu_settings"))
        lang_menu = m.addMenu(tr("menu_language"))
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        for code, label in i18n.LANGUAGES:
            a = QAction(label, self, checkable=True)
            a.setChecked(code == i18n.language())
            a.triggered.connect(lambda _c, c=code: self.apply_language(c))
            lang_group.addAction(a)
            lang_menu.addAction(a)
        theme_menu = m.addMenu(tr("menu_theme"))
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for code, key in (("light", "theme_light"), ("dark", "theme_dark"), ("system", "theme_system")):
            a = QAction(tr(key), self, checkable=True)
            a.setChecked(code == self.theme_name)
            a.triggered.connect(lambda _c, c=code: self.apply_theme(c))
            theme_group.addAction(a)
            theme_menu.addAction(a)
        m.addSeparator()
        m.addAction(self._act(tr("opt_auto_rewind"), lambda v: self._set_option("auto_rewind", v),
                              checkable=True, checked=s.get("auto_rewind", True)))
        m.addAction(self._act(tr("opt_per_book_speed"), lambda v: self._set_option("per_book_speed", v),
                              checkable=True, checked=s.get("per_book_speed", True)))
        if winmedia.IS_WINDOWS:
            m.addAction(self._act(tr("opt_media_keys"), self._toggle_media_keys, checkable=True,
                                  checked=s.get("media_keys", True)))
        m.addAction(self._act(tr("opt_group_authors"), self._toggle_group_authors, checkable=True,
                              checked=s.get("group_authors", False)))
        m.addSeparator()
        m.addAction(self._act(tr("opt_google_key"), self.set_google_key))

        m = bar.addMenu(tr("menu_help"))
        m.addAction(self._act(tr("menu_shortcuts"), self.show_shortcuts))
        m.addAction(self._act(tr("menu_licenses"), self.show_licenses))
        m.addAction(self._act(tr("open_logs"), lambda: self._open_folder(paths.APP_DIR)))
        m.addSeparator()
        m.addAction(self._act(tr("menu_about"), self.show_about))

    def _build_ui(self):
        self._build_menu()
        tb = QToolBar(tr("toolbar_main"), movable=False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        self.toolbar = tb
        style = self.style()

        def tool(text, icon, slot):
            a = QAction(style.standardIcon(icon), text, self)
            a.triggered.connect(lambda _c=False, s=slot: s())
            tb.addAction(a)

        tool(tr("add_folder"), QStyle.StandardPixmap.SP_DirOpenIcon, self.add_folder)
        tool(tr("add_many"), QStyle.StandardPixmap.SP_DirIcon, self.add_many)
        tool(tr("add_file"), QStyle.StandardPixmap.SP_FileIcon, self.add_file)
        tb.addSeparator()

        tb.addWidget(QLabel(tr("sort")))
        self.sort_combo = QComboBox()
        for key, data in (("sort_recent", "recent"), ("sort_title", "title"),
                          ("sort_author", "author"), ("sort_added", "added")):
            self.sort_combo.addItem(tr(key), data)
        self.sort_combo.currentIndexChanged.connect(self.refresh_list)
        tb.addWidget(self.sort_combo)
        tb.addWidget(QLabel(tr("filter")))
        self.filter_combo = QComboBox()
        for key, data in (("filter_all", "all"), ("filter_in_progress", "in_progress"),
                          ("filter_unplayed", "unplayed"), ("filter_finished", "finished")):
            self.filter_combo.addItem(tr(key), data)
        self.filter_combo.currentIndexChanged.connect(self.refresh_list)
        tb.addWidget(self.filter_combo)

        self.search_edit = QLineEdit(placeholderText=tr("search_placeholder"), clearButtonEnabled=True)
        self.search_edit.setMaximumWidth(240)
        self.search_edit.textChanged.connect(lambda _t: self.search_timer.start())   # debounce
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(self.search_edit)

        # środek: lista książek + panel szczegółów
        split = QSplitter()
        self.book_list = QListWidget()
        self.book_list.setIconSize(QSize(56, 56))
        self.book_list.itemActivated.connect(self.play_selected)       # Enter i dwuklik
        self.book_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.book_list.customContextMenuRequested.connect(self.book_menu)
        split.addWidget(self.book_list)

        right = QWidget()
        rlay = QVBoxLayout(right)
        self.detail_cover = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.detail_cover.setMinimumHeight(150)
        self.detail_title = plain_label(alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        f = self.detail_title.font()
        f.setPointSize(12)
        f.setBold(True)
        self.detail_title.setFont(f)
        self.detail_author = plain_label(alignment=Qt.AlignmentFlag.AlignCenter)
        self.detail_author.setStyleSheet(f"color: {themes.muted_color()};")
        self.chapter_label = QLabel(tr("files_chapters"))
        self.chapter_list = QListWidget()
        self.chapter_list.itemActivated.connect(self.jump_to_chapter)
        self.detail_desc = QTextEdit(readOnly=True, placeholderText=tr("no_description"))
        self.detail_desc.setMaximumHeight(130)
        for w, stretch in ((self.detail_cover, 0), (self.detail_title, 0), (self.detail_author, 0),
                           (self.chapter_label, 0), (self.chapter_list, 1), (self.detail_desc, 0)):
            rlay.addWidget(w, stretch)
        split.addWidget(right)
        split.setSizes([620, 400])
        self.book_list.currentItemChanged.connect(lambda *_: self.show_details())
        self.book_list.currentItemChanged.connect(self._restyle_selection)

        # dolny pasek odtwarzacza
        bottom = QWidget()
        blay = QVBoxLayout(bottom)
        blay.setContentsMargins(8, 4, 8, 6)

        self.now_label = plain_label(tr("nothing_playing"))
        f = self.now_label.font()
        f.setBold(True)
        self.now_label.setFont(f)
        self.book_time_label = plain_label("")
        self.book_time_label.setStyleSheet(f"color: {themes.muted_color()};")
        info_row = QHBoxLayout()
        info_row.addWidget(self.now_label, 1)
        info_row.addWidget(self.book_time_label)
        blay.addLayout(info_row)

        srow = QHBoxLayout()
        self.pos_label = QLabel("00:00")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(lambda: setattr(self, "slider_down", True))
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.dur_label = QLabel("00:00")
        srow.addWidget(self.pos_label)
        srow.addWidget(self.slider, 1)
        srow.addWidget(self.dur_label)
        blay.addLayout(srow)

        crow = QHBoxLayout()
        crow.addStretch(1)

        def btn(icon, tip, slot, text=None):
            b = QPushButton(text) if text else QPushButton()
            if not text:
                b.setIcon(style.standardIcon(icon))
            b.setToolTip(tip)
            b.setAccessibleName(tip)             # czytniki ekranu czytają tę nazwę
            b.clicked.connect(lambda _c=False, s=slot: s())
            crow.addWidget(b)
            return b

        btn(QStyle.StandardPixmap.SP_MediaSkipBackward, tr("prev_chapter"), self.prev_chapter)
        btn(None, tr("back_30"), lambda: self.ctl.skip(-30000), "−30s")
        btn(None, tr("back_10"), lambda: self.ctl.skip(-10000), "−10s")
        self.play_btn = btn(QStyle.StandardPixmap.SP_MediaPlay, tr("play_pause"), self.toggle_play)
        btn(None, tr("fwd_10"), lambda: self.ctl.skip(10000), "+10s")
        btn(None, tr("fwd_30"), lambda: self.ctl.skip(30000), "+30s")
        btn(QStyle.StandardPixmap.SP_MediaSkipForward, tr("next_chapter"), self.next_chapter)
        crow.addSpacing(6)
        btn(None, tr("bookmark_add"), self.add_bookmark, tr("bookmark_btn_add"))
        btn(None, tr("bookmarks_open"), self.show_bookmarks, tr("bookmark_btn_list"))

        crow.addStretch(1)
        crow.addWidget(QLabel(tr("speed")))
        self.speed_combo = QComboBox()
        for sp in SPEEDS:
            self.speed_combo.addItem(f"{sp}×", float(sp))
        self.speed_combo.currentIndexChanged.connect(self._on_speed_chosen)
        crow.addWidget(self.speed_combo)

        crow.addSpacing(10)
        vol_icon = QLabel()
        vol_icon.setPixmap(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume).pixmap(18, 18))
        crow.addWidget(vol_icon)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setFixedWidth(90)
        self.vol_slider.setAccessibleName(tr("volume"))
        self.vol_slider.valueChanged.connect(lambda v: self.ctl.set_volume(v / 100))
        crow.addWidget(self.vol_slider)

        crow.addSpacing(10)
        self.sleep_btn = QToolButton()
        self.sleep_btn.setToolTip(tr("sleep_tooltip"))
        self.sleep_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.sleep_btn.setMenu(self._build_sleep_menu())
        crow.addWidget(self.sleep_btn)
        blay.addLayout(crow)

        central = QWidget()
        clay = QVBoxLayout(central)
        clay.setContentsMargins(0, 0, 0, 0)
        clay.addWidget(split, 1)
        clay.addWidget(bottom)
        self.setCentralWidget(central)
        self.statusBar().showMessage(tr("ready"))
        self._sync_ui()

    def _build_sleep_menu(self):
        menu = QMenu(self)
        menu.addAction(tr("sleep_off"), self.ctl.cancel_sleep)
        for m in SLEEP_MINUTES:
            menu.addAction(tr("sleep_minutes", n=m), lambda mm=m: self.ctl.start_sleep(minutes=mm))
        menu.addAction(tr("sleep_end_of_file"), lambda: self.ctl.start_sleep(end_of_file=True))
        return menu

    def _sync_ui(self):
        """Ustawia widgety zgodnie ze stanem sterownika — po zbudowaniu/przebudowie UI."""
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(int(self.ctl.audio.volume() * 100))
        self.vol_slider.blockSignals(False)
        self._sync_speed(self.ctl.rate_for(self.ctl.current))
        self._on_state(self.ctl.is_playing)
        self._on_sleep(self._sleep_state)
        if self.ctl.current:
            self._update_now_label()
            self._on_position(self.ctl.player.position(), self.ctl.player.duration())

    def rebuild_ui(self):
        """Przebudowuje interfejs po zmianie języka/motywu, zachowując stan."""
        sort_mode = self.sort_combo.currentData() if self.toolbar else "recent"
        filter_mode = self.filter_combo.currentData() if self.toolbar else "all"
        query = self.search_edit.text() if self.toolbar else ""
        if self.toolbar:
            self.removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
        old = self.takeCentralWidget()
        if old:
            old.deleteLater()
        self.setWindowTitle(tr("app_title"))
        self._build_ui()
        for combo, data in ((self.sort_combo, sort_mode), (self.filter_combo, filter_mode)):
            idx = combo.findData(data)
            if idx >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)
        self.search_edit.blockSignals(True)
        self.search_edit.setText(query)
        self.search_edit.blockSignals(False)
        self.refresh_list()
        self.show_details()

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

    def _set_option(self, key, value):
        self.library.settings[key] = bool(value)
        self.library.save()

    def _toggle_media_keys(self, enabled):
        self._set_option("media_keys", enabled)
        self._update_media_keys()

    def _update_media_keys(self):
        """Klawisze multimedialne przejmujemy tylko, gdy coś jest załadowane — inaczej
        wyłączalibyśmy je innym odtwarzaczom, gdy audiobook nie jest w użyciu."""
        want = (winmedia.IS_WINDOWS and self.library.settings.get("media_keys", True)
                and self.ctl.current is not None)
        if want:
            self.media_keys.enable()
        else:
            self.media_keys.disable()

    def _toggle_group_authors(self, enabled):
        self._set_option("group_authors", enabled)
        if enabled:
            self.sort_combo.setCurrentIndex(self.sort_combo.findData("author"))
        self.refresh_list()

    def set_google_key(self):
        dlg = QInputDialog(self)
        dlg.setWindowTitle(tr("opt_google_key"))
        dlg.setLabelText(tr("google_key_prompt"))
        dlg.setTextValue(self.library.settings.get("google_api_key", ""))
        dlg.setOkButtonText(tr("ok"))
        dlg.setCancelButtonText(tr("cancel"))
        if dlg.exec():
            key = dlg.textValue().strip()
            self.library.settings["google_api_key"] = key
            meta.configure(google_api_key=key)
            meta.clear_cache()
            self.library.save()

    def show_about(self):
        QMessageBox.about(self, tr("about_title"), tr("about_text", version=APP_VERSION))

    def show_shortcuts(self):
        dialogs.TextViewDialog(tr("menu_shortcuts"), tr("shortcuts_text"), self).exec()

    def show_licenses(self):
        text = dialogs.read_resource_text("THIRD_PARTY_NOTICES.md") or tr("licenses_missing")
        lic = dialogs.read_resource_text("LICENSE")
        if lic:
            text += "\n\n" + "=" * 70 + "\n\n" + lic
        dialogs.TextViewDialog(tr("menu_licenses"), text, self).exec()

    def _open_folder(self, path):
        # ścieżka może pochodzić z importowanej kopii zapasowej — otwieramy tylko
        # istniejący katalog lokalny (bez UNC/sieci), nigdy plik do uruchomienia
        if not path:
            return
        if os.name == "nt":
            # normalizacja przed jakimkolwiek dostępem do dysku; dozwolona tylko litera
            # dysku ("C:") — odrzuca UNC, \\?\UNC\..., \\.\... i ścieżki względne
            p = os.path.abspath(path).replace("/", "\\")
            drive = os.path.splitdrive(p)[0]
            if p.startswith("\\\\") or not (len(drive) == 2 and drive[1] == ":"):
                return
            path = p
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        if os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ---------------------------------------------------------------- lista

    def _selected_id(self):
        item = self.book_list.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole):
            return item.data(Qt.ItemDataRole.UserRole)
        return self.ctl.current["id"] if self.ctl.current else None

    def refresh_list(self):
        selected_id = self._selected_id()
        mode = self.sort_combo.currentData()
        books = self.library.sorted_books(mode, self.search_edit.text(),
                                          self.filter_combo.currentData())
        group = bool(self.library.settings.get("group_authors")) and mode == "author"
        self.book_list.setUpdatesEnabled(False)
        self.book_list.blockSignals(True)
        self.book_list.clear()
        last_author = None
        target = None
        for book in books:
            if group and book["author"] != last_author:
                last_author = book["author"]
                header = QListWidgetItem(last_author or tr("no_author"))
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                f = header.font()
                f.setBold(True)
                header.setFont(f)
                self.book_list.addItem(header)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, book["id"])
            widget = BookItemWidget(book, playing=(self.ctl.current is book))
            item.setSizeHint(widget.sizeHint())
            self.book_list.addItem(item)
            self.book_list.setItemWidget(item, widget)
            if book["id"] == selected_id:
                target = item
        if not books:                      # pusty stan: podpowiedź zamiast pustego pola
            hint = QListWidgetItem(tr("empty_library_hint") if not self.library.books
                                   else tr("no_match_hint"))
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            hint.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setSizeHint(QSize(300, 120))
            self.book_list.addItem(hint)
        self.book_list.blockSignals(False)
        if target:
            self.book_list.setCurrentItem(target)
            self._restyle_selection(target, None)
        self.book_list.setUpdatesEnabled(True)
        self.show_details()

    def _restyle_selection(self, current, previous):
        for item, selected in ((previous, False), (current, True)):
            w = self.book_list.itemWidget(item) if item else None
            if w is not None and hasattr(w, "set_selected"):
                w.set_selected(selected)

    def book_from_item(self, item):
        bid = item.data(Qt.ItemDataRole.UserRole) if item else None
        return self.library.book_by_id(bid) if bid else None

    def selected_book(self):
        return self.book_from_item(self.book_list.currentItem())

    def _clear_details(self):
        self.detail_cover.setPixmap(cached_default_cover(140))
        self.detail_title.setText("")
        self.detail_author.setText("")
        self.detail_desc.clear()
        self.chapter_list.clear()

    def show_details(self):
        book = self.selected_book() or self.ctl.current
        if not book or book not in self.library.books:
            self._clear_details()                    # po usunięciu nie zostaje „duch" książki
            return
        pm = covers.scaled_pixmap(book.get("cover"), 150 * 2, 150) or cached_default_cover(140)
        self.detail_cover.setPixmap(pm)
        self.detail_title.setText(book["title"])
        self.detail_author.setText(book["author"] or tr("no_author"))
        self.detail_desc.setPlainText(book.get("description") or "")
        self.chapter_list.clear()
        durations = book["durations"]
        entries = book.chapter_entries()
        embedded = bool(book.get("chapters"))
        for i, (title, fi, start) in enumerate(entries):
            file_len = durations[fi] if fi < len(durations) else 0
            if embedded:        # długość rozdziału = do początku następnego w tym samym pliku
                nxt = entries[i + 1] if i + 1 < len(entries) else None
                end = nxt[2] if nxt and nxt[1] == fi else file_len
                length = max(0, end - start)
            else:
                length = file_len
            QListWidgetItem(f"{i + 1}. {title}  ({fmt_ms(length)})", self.chapter_list)
        self._highlight_chapter()

    def _highlight_chapter(self):
        b = self.ctl.current
        shown = self.selected_book() or b
        if not b or shown is not b:
            return
        idx = b.current_chapter_index(b["file_index"], self.ctl.player.position())
        if 0 <= idx < self.chapter_list.count() and self.chapter_list.currentRow() != idx:
            self.chapter_list.blockSignals(True)
            self.chapter_list.setCurrentRow(idx)
            self.chapter_list.blockSignals(False)

    # ---------------------------------------------------------------- dodawanie

    def handle_paths(self, path_list, mode="auto"):
        """Dodaje pliki/katalogi w tle (odczyt tagów i długości poza wątkiem GUI)."""
        if self._scan is not None:
            self.statusBar().showMessage(tr("scan_busy"), 5000)
            return
        progress = QProgressDialog(tr("scanning"), tr("cancel"), 0, 0, self)
        progress.setWindowTitle(tr("app_title"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)
        worker = workers.ScanWorker(path_list, self.library.existing_paths(),
                                    self.library.covers_dir, mode)
        worker.progress.connect(self._on_scan_progress)
        worker.done.connect(self._on_scan_done)
        progress.canceled.connect(worker.requestInterruption)
        self._scan, self._scan_progress = worker, progress
        workers.start(worker)

    def _on_scan_progress(self, i, n, name):
        if self._scan_progress:
            self._scan_progress.setMaximum(n)
            self._scan_progress.setValue(i - 1)
            self._scan_progress.setLabelText(tr("scanning_item", i=i, n=n, name=name))

    def _on_scan_done(self, books):
        if self._scan_progress:
            self._scan_progress.close()
            self._scan_progress.deleteLater()
        self._scan = self._scan_progress = None
        added = [b for b in books if self.library.add_book(b)]
        if added:
            self.library.save()
            self.refresh_list()
            self.statusBar().showMessage(
                tr("added_book", title=added[0]["title"]) if len(added) == 1
                else tr("added_books", n=len(added)), 6000)
        else:
            QMessageBox.information(self, tr("app_title"), tr("info_no_new"))

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("dlg_choose_folder"))
        if folder:
            self.handle_paths([folder], "single")

    def add_many(self):
        folder = QFileDialog.getExistingDirectory(self, tr("dlg_choose_parent"))
        if folder:
            self.handle_paths([folder], "many")

    def add_file(self):
        exts = " ".join(f"*{e}" for e in sorted(lib.AUDIO_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, tr("dlg_choose_files"), "",
                                                f"{tr('audio_files')} ({exts})")
        if files:
            self.handle_paths(files, "single")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        dropped = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if dropped:
            event.acceptProposedAction()
            self.handle_paths(dropped, "auto")

    # ---------------------------------------------------------------- usuwanie

    def clear_library(self):
        if not self.library.books:
            return
        if dialogs.confirm(self, tr("clear_title"),
                           tr("clear_question", n=len(self.library.books))):
            self.ctl.stop()
            self.library.clear()
            self.library.save()
            self.refresh_list()

    def remove_book(self, book):
        if dialogs.confirm(self, tr("remove_title"), tr("remove_question", title=book["title"])):
            if self.ctl.current is book:
                self.ctl.stop()
            self.library.remove(book)
            self.library.save()
            self.refresh_list()

    def remove_selected(self):
        if self.book_list.hasFocus():
            book = self.selected_book()
            if book:
                self.remove_book(book)

    def focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    # ---------------------------------------------------------------- menu książki

    def book_menu(self, pos):
        book = self.book_from_item(self.book_list.itemAt(pos))
        if not book:
            return
        menu = QMenu(self)
        menu.addAction(tr("ctx_play"), lambda: self.ctl.play_book(book))
        menu.addAction(tr("ctx_play_start"), lambda: self.ctl.play_book(book, restart=True))
        menu.addSeparator()
        menu.addAction(tr("ctx_metadata"), lambda: self.fetch_metadata(book))
        menu.addAction(tr("ctx_cover"), lambda: self.fetch_cover(book))
        menu.addAction(tr("ctx_edit"), lambda: self.edit_metadata(book))
        menu.addAction(tr("ctx_bookmarks"), lambda: self.show_bookmarks(book))
        menu.addSeparator()
        if book.get("finished"):
            menu.addAction(tr("ctx_mark_undone"), lambda: self.set_finished(book, False))
        else:
            menu.addAction(tr("ctx_mark_done"), lambda: self.set_finished(book, True))
        menu.addAction(tr("ctx_reset"), lambda: self.reset_progress(book))
        menu.addSeparator()
        menu.addAction(tr("ctx_open_location"), lambda: self._open_folder(
            book["path"] if book["kind"] == "folder" else os.path.dirname(book["path"])))
        menu.addAction(tr("ctx_remove"), lambda: self.remove_book(book))
        menu.exec(self.book_list.mapToGlobal(pos))

    def set_finished(self, book, val):
        book["finished"] = val
        if val:
            book["file_index"] = book["position_ms"] = 0
        self.library.save()
        self.refresh_list()

    def reset_progress(self, book):
        book.update(file_index=0, position_ms=0, finished=False)
        self.library.save()
        self.refresh_list()

    def _ask_text(self, title, label, text):
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue(text)
        dlg.setOkButtonText(tr("ok"))
        dlg.setCancelButtonText(tr("cancel"))
        return (dlg.textValue(), True) if dlg.exec() else ("", False)

    def edit_metadata(self, book):
        title, ok = self._ask_text(tr("edit_title"), tr("edit_title_label"), book["title"])
        if not ok:
            return
        author, ok = self._ask_text(tr("edit_author"), tr("edit_author_label"), book["author"])
        if not ok:
            return
        book["title"] = title.strip() or book["title"]
        book["author"] = author.strip()
        self.library.save()
        self.refresh_list()

    def fetch_metadata(self, book):
        dlg = dialogs.MetadataDialog(book, self)
        accepted = dlg.exec() == dlg.DialogCode.Accepted
        chosen = dlg.chosen
        dlg.deleteLater()
        if not accepted or not chosen:
            return
        for key in ("title", "author", "description"):
            if chosen.get(key):
                book[key] = chosen[key]
        self.library.save()
        self.refresh_list()
        self.statusBar().showMessage(tr("meta_updated"), 5000)
        if chosen.get("cover_url"):                  # okładka w tle — okno się nie blokuje
            dest = self.library.cover_path(book["id"])
            w = workers.CoverDownloadWorker(chosen["cover_url"], dest)
            w.done.connect(lambda ok, b=book, d=dest: self._cover_ready(b, d, ok))
            workers.start(w)

    def _cover_ready(self, book, dest, ok):
        if ok and book in self.library.books:
            book["cover"] = dest
            QPixmapCache.clear()
            self.library.save()
            self.refresh_list()
            self.statusBar().showMessage(tr("cover_updated"), 5000)

    def fetch_cover(self, book):
        dlg = dialogs.CoverDialog(self.library, book, self)
        accepted = dlg.exec() == dlg.DialogCode.Accepted
        path = dlg.result_path
        dlg.deleteLater()
        if not accepted or not path:
            return
        book["cover"] = path
        QPixmapCache.clear()                  # ten sam plik, nowa zawartość
        self.library.save()
        self.refresh_list()
        self.statusBar().showMessage(tr("cover_updated"), 5000)

    def batch_metadata(self):
        todo = [b for b in self.library.books if not b.get("cover") or not b.get("description")]
        if not todo:
            QMessageBox.information(self, tr("app_title"), tr("batch_nothing"))
            return
        if not dialogs.confirm(self, tr("batch_title"), tr("batch_confirm", n=len(todo))):
            return
        dlg = dialogs.BatchMetadataDialog(self.library, todo, self)
        dlg.exec()
        applied = dlg.applied
        dlg.deleteLater()
        if applied:
            QPixmapCache.clear()
            self.library.save()
            self.refresh_list()
            self.statusBar().showMessage(tr("batch_applied", n=applied), 6000)

    def show_stats(self):
        dialogs.StatsDialog(self.library, self).exec()

    # ---------------------------------------------------------------- kopie zapasowe

    def export_backup(self):
        name = time.strftime("audiobook-library-%Y%m%d.zip")
        path, _ = QFileDialog.getSaveFileName(self, tr("backup_export"), name, "ZIP (*.zip)")
        if not path:
            return
        try:
            n = self.library.export_backup(path)
            self.statusBar().showMessage(tr("backup_saved", n=n, path=path), 8000)
        except OSError as e:
            QMessageBox.warning(self, tr("app_title"), tr("backup_failed", err=str(e)))

    def import_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("backup_import"), "", "ZIP (*.zip)")
        if not path:
            return
        if not dialogs.confirm(self, tr("backup_import"), tr("backup_import_confirm")):
            return
        self.ctl.stop()
        try:
            n = self.library.import_backup(path)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, tr("app_title"), tr("backup_failed", err=str(e)))
            return
        QPixmapCache.clear()
        self.refresh_list()
        self.statusBar().showMessage(tr("backup_restored", n=n), 8000)

    # ---------------------------------------------------------------- odtwarzanie

    def play_selected(self, item):
        book = self.book_from_item(item)
        if book:
            self.ctl.play_book(book)

    def toggle_play(self):
        if self.ctl.current:
            self.ctl.toggle()
        else:
            book = self.selected_book()
            if book:
                self.ctl.play_book(book)

    def _volume(self, delta):
        self.vol_slider.setValue(max(0, min(100, self.vol_slider.value() + delta)))

    def _chapter_context(self):
        b = self.ctl.current
        if not b:
            return None
        entries = b.chapter_entries()
        return b, entries, b.current_chapter_index(b["file_index"], self.ctl.player.position())

    def next_chapter(self):
        ctx = self._chapter_context()
        if not ctx:
            return
        b, entries, idx = ctx
        if b.get("chapters") and idx + 1 < len(entries):
            _t, fi, start = entries[idx + 1]
            self.ctl.jump_to(b, fi, start)
        else:
            self.ctl.next_file()

    def prev_chapter(self):
        ctx = self._chapter_context()
        if not ctx:
            return
        b, entries, idx = ctx
        if not b.get("chapters"):
            self.ctl.prev_file()
            return
        _t, fi, start = entries[idx]
        if idx == 0 or (b["file_index"] == fi and self.ctl.player.position() - start > 5000):
            self.ctl.jump_to(b, fi, start)               # wróć na początek rozdziału
        else:
            _t, pfi, pstart = entries[idx - 1]
            self.ctl.jump_to(b, pfi, pstart)

    def jump_to_chapter(self, item):
        book = self.selected_book() or self.ctl.current
        if not book:
            return
        entries = book.chapter_entries()
        row = self.chapter_list.row(item)
        if 0 <= row < len(entries):
            _t, fi, start = entries[row]
            self.ctl.jump_to(book, fi, start)

    def add_bookmark(self):
        if not self.ctl.add_bookmark():
            self.statusBar().showMessage(tr("bookmark_need_playing"), 5000)

    def show_bookmarks(self, book=None):
        book = book if isinstance(book, dict) else (self.ctl.current or self.selected_book())
        if not book:
            self.statusBar().showMessage(tr("bookmark_need_book"), 5000)
            return
        dlg = dialogs.BookmarksDialog(book, self)
        dlg.exec()
        target, changed = dlg.jump_to, dlg.changed
        dlg.deleteLater()
        if changed:
            self.library.save()
            self.refresh_list()
        if target:
            self.ctl.jump_to(book, *target)

    # ---------------------------------------------------------------- zdarzenia sterownika

    def _on_state(self, playing):
        icon = QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay
        self.play_btn.setIcon(self.style().standardIcon(icon))

    def _on_book_changed(self, book):
        if book is None:
            self.now_label.setText(tr("nothing_playing"))
            self.book_time_label.setText("")
            self.pos_label.setText("00:00")
            self.dur_label.setText("00:00")
            self.slider.setRange(0, 0)
        self._update_media_keys()
        self.refresh_list()

    def _on_file_changed(self):
        self._update_now_label()
        self.show_details()

    def _update_now_label(self):
        b = self.ctl.current
        if not b:
            return
        chapter = ""
        if len(b["files"]) > 1:
            chapter = tr("file_x_of_y", i=b["file_index"] + 1, n=len(b["files"]))
        self.now_label.setText(f"▶ {b['title']}{chapter}")

    def _on_position(self, pos, dur):
        if not self.slider_down:
            self.slider.setRange(0, max(0, dur))
            self.slider.setValue(pos)
        self.pos_label.setText(fmt_ms(pos))
        self.dur_label.setText(fmt_ms(dur))
        b = self.ctl.current
        if not b or b.total_ms <= 0:
            self.book_time_label.setText("")
            return
        elapsed = b.offset_ms() + pos
        remaining = max(0, b.total_ms - elapsed)
        text = tr("book_time", elapsed=fmt_ms(elapsed), total=fmt_ms(b.total_ms),
                  remaining=fmt_ms(remaining))
        rate = self.speed_combo.currentData() or 1.0
        if abs(rate - 1.0) > 0.01:
            text += "  " + tr("book_time_eta", eta=fmt_ms(remaining / rate))
        self.book_time_label.setText(text)
        self._highlight_chapter()

    def _on_slider_released(self):
        self.slider_down = False
        self.ctl.seek_in_file(self.slider.value())

    def _on_speed_chosen(self):
        self.ctl.set_speed(self.speed_combo.currentData() or 1.0)

    def _sync_speed(self, rate):
        """Ustawia listę prędkości bez wywoływania ponownego zapisu."""
        idx = min(range(self.speed_combo.count()),
                  key=lambda i: abs(self.speed_combo.itemData(i) - rate))
        self.speed_combo.blockSignals(True)
        self.speed_combo.setCurrentIndex(idx)
        self.speed_combo.blockSignals(False)

    def _on_sleep(self, seconds):
        self._sleep_state = seconds
        if seconds == -1:
            self.sleep_btn.setText(tr("sleep_btn"))
        elif seconds == -2:
            self.sleep_btn.setText(tr("sleep_eof_short"))
        else:
            self.sleep_btn.setText(f"⏰ {fmt_ms(seconds * 1000)}")

    # ---------------------------------------------------------------- klawisze, zamykanie

    def eventFilter(self, obj, event):
        """Spacja steruje odtwarzaniem, gdy nie pisze się w polu tekstowym i nie jest
        wciśnięty przycisk (przycisk zachowuje się wtedy standardowo)."""
        if (event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space
                and not event.modifiers() and self.isActiveWindow()
                and QApplication.activeModalWidget() is None):
            fw = QApplication.focusWidget()
            if fw is None or isinstance(fw, (QListWidget, QSlider, QMainWindow, QToolBar)):
                self.toggle_play()
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self.media_keys.disable()
        self.ctl.save_progress()
        self.library.settings["volume"] = self.ctl.audio.volume()
        self.library.save()
        super().closeEvent(event)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    applog.setup_logging()
    applog.install_excepthook()
    app = QApplication(argv)
    app.setApplicationName(appinfo.APP_NAME)
    app.setApplicationVersion(appinfo.APP_VERSION)

    smoke = "--smoke-test" in argv               # start, chwila działania, wyjście z kodem 0
    open_paths = [a for a in argv[1:] if not a.startswith("-")]
    single = SingleInstance("AudiobookPlayer-smoke" if smoke else "AudiobookPlayer")
    if single.send_to_running(open_paths):       # jest już okno — przekaż pliki i wyjdź
        return 0
    single.listen()

    library = lib.Library()
    themes.apply_theme(app, library.settings.get("theme", "system"))
    win = MainWindow(library, single)
    applog.set_notifier(win.show_error)
    win.show()
    if open_paths:
        QTimer.singleShot(300, lambda: win.handle_paths(open_paths, "auto"))
    if smoke:                                    # ABP_SMOKE_MS: dłuższe okno do testów 2 procesów
        QTimer.singleShot(int(os.environ.get("ABP_SMOKE_MS", 2000)), app.quit)
    code = app.exec()
    if workers.shutdown(3000):                   # zawieszona operacja sieciowa — nie czekaj dłużej
        os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())
