"""Okna dialogowe: metadane, okładki, zakładki, wsadowe uzupełnianie, statystyki, tekst."""
import time

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import covers
import i18n
import theme as themes
import workers
from i18n import tr
from util import fmt_ms


# ---------------------------------------------------------------- pomocnicze

def confirm(parent, title, text):
    """Pytanie Tak/Nie z przetłumaczonymi przyciskami (bez zależności od tłumaczeń Qt)."""
    box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=parent)
    yes = box.addButton(tr("yes"), QMessageBox.ButtonRole.YesRole)
    box.addButton(tr("no"), QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(box.buttons()[1])
    box.exec()
    return box.clickedButton() is yes


def format_errors(errors):
    """{źródło: (kod, szczegół)} -> „Google Books (limit zapytań), Audible (brak połączenia)"."""
    parts = []
    for source, (code, detail) in errors.items():
        key = f"err_{code}"
        text = tr(key, detail=detail) if code in {"rate_limit", "http", "timeout", "offline",
                                                  "bad_response", "error"} else str(code)
        name = tr("err_all_sources") if source == "*" else source
        parts.append(f"{name} ({text})")
    return ", ".join(parts)


def search_status(n_results, errors, found_key="meta_found", none_key="meta_none"):
    """Tekst statusu: odróżnia „brak wyników" od „serwisy niedostępne"."""
    if n_results:
        text = tr(found_key, n=n_results)
        if errors:
            text += " · " + tr("meta_unavailable", sources=format_errors(errors))
        return text
    if errors:
        return tr("meta_failed", sources=format_errors(errors))
    return tr(none_key)


def _button_box(ok_text, cancel_text=None):
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    box.button(QDialogButtonBox.StandardButton.Ok).setText(ok_text)
    box.button(QDialogButtonBox.StandardButton.Cancel).setText(cancel_text or tr("cancel"))
    return box


class SearchDialogBase(QDialog):
    """Wspólna logika wyszukiwania. Każde wyszukiwanie ma numer generacji, więc
    spóźniona odpowiedź poprzedniego (np. po dwukrotnym Enterze) jest ignorowana —
    lista i wyniki nigdy się nie rozjeżdżają."""

    with_covers = False
    found_key, none_key = "meta_found", "meta_none"

    def __init__(self, book, title, parent=None):
        super().__init__(parent)
        self.book = book
        self.results = []
        self.generation = 0
        self.image_generation = 0
        self.setWindowTitle(title)

        self.root = QVBoxLayout(self)
        row = QHBoxLayout()
        self.query_edit = QLineEdit(f"{book['author']} {book['title']}".strip())
        self.search_btn = QPushButton(tr("meta_search"))
        self.search_btn.clicked.connect(self.do_search)
        self.query_edit.returnPressed.connect(self.do_search)
        row.addWidget(self.query_edit, 1)
        row.addWidget(self.search_btn)
        self.root.addLayout(row)

        self.list = QListWidget()
        self.status = QLabel("")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)

    def start_search(self):
        self.do_search()

    def do_search(self):
        q = self.query_edit.text().strip()
        if not q:
            return
        self.generation += 1
        self.image_generation += 1
        self.results = []
        self.list.clear()
        self.status.setText(tr("meta_searching"))
        self._on_cleared()
        worker = workers.SearchWorker(self.generation, q, i18n.language(),
                                      with_covers=self.with_covers)
        worker.done.connect(self._on_search_done)
        workers.start(worker)

    def _on_cleared(self):
        pass

    def _accepts(self, result):
        return True

    def _on_search_done(self, generation, outcome):
        if generation != self.generation:          # spóźniona odpowiedź starego zapytania
            return
        self.results = [r for r in outcome.results if self._accepts(r)]
        self.list.clear()
        for i, r in enumerate(self.results):
            author = f" — {r['author']}" if r["author"] else ""
            item = QListWidgetItem(f"[{r['source']}] {r['title']}{author}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._decorate(item, r)
            self.list.addItem(item)
        self.status.setText(search_status(len(self.results), outcome.errors,
                                          self.found_key, self.none_key))
        self._after_results()
        if self.results:
            self.list.setCurrentRow(0)

    def _decorate(self, item, result):
        pass

    def _after_results(self):
        pass

    def current_result(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.results):
            return self.results[row]
        return None

    def done(self, code):
        # po zamknięciu nie przyjmuj już żadnych odpowiedzi
        self.generation += 1
        self.image_generation += 1
        super().done(code)


# ---------------------------------------------------------------- metadane

class MetadataDialog(SearchDialogBase):
    """Wyszukiwanie metadanych w internecie i wybór wyniku."""

    def __init__(self, book, parent=None):
        super().__init__(book, tr("meta_dialog_title", title=book["title"]), parent)
        self.chosen = None
        self.resize(760, 500)

        split = QSplitter()
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
        self.root.addWidget(split, 1)
        self.root.addWidget(self.status)
        box = _button_box(tr("meta_apply"), tr("meta_cancel"))
        box.accepted.connect(self.accept_choice)
        box.rejected.connect(self.reject)
        self.root.addWidget(box)
        self.start_search()

    def _on_cleared(self):
        self.preview_text.clear()
        self.preview_cover.setPixmap(covers.default_cover(160))

    def show_preview(self, row):
        r = self.results[row] if 0 <= row < len(self.results) else None
        if not r:
            return
        self.preview_text.setPlainText(
            f"{r['title']}\n{r['author']}\n{tr('meta_source')}: {r['source']}\n\n{r['description']}")
        self.preview_cover.setPixmap(covers.default_cover(160))
        if r.get("cover_url"):
            self.image_generation += 1
            w = workers.ImageWorker(self.image_generation, [(row, r["cover_url"])])
            w.loaded.connect(self._preview_loaded)
            workers.start(w)

    def _preview_loaded(self, generation, row, image):
        if generation != self.image_generation or row != self.list.currentRow():
            return
        self.preview_cover.setPixmap(QPixmap.fromImage(image).scaledToHeight(
            170, Qt.TransformationMode.SmoothTransformation))

    def accept_choice(self):
        r = self.current_result()
        if not r:
            self.reject()
            return
        self.status.setText(tr("meta_fetching"))
        self.setEnabled(False)
        w = workers.DetailsWorker(self.generation, r)
        w.done.connect(self._on_details)
        workers.start(w)

    def _on_details(self, generation, result):
        if generation != self.generation:
            return
        self.chosen = result
        self.accept()


# ---------------------------------------------------------------- okładka

class CoverDialog(SearchDialogBase):
    """Wizualny wybór okładki z miniaturkami albo wskazanie własnego obrazu."""

    with_covers = True
    found_key, none_key = "cover_found", "cover_none"

    def __init__(self, library, book, parent=None):
        super().__init__(book, tr("cover_dialog_title", title=book["title"]), parent)
        self.library = library
        self.result_path = None
        self.images = {}                       # wiersz -> pełny QImage do podglądu
        self.resize(760, 520)

        split = QSplitter()
        self.list.setIconSize(QSize(60, 84))
        self.list.currentRowChanged.connect(self.show_preview)
        split.addWidget(self.list)
        right = QWidget()
        rlay = QVBoxLayout(right)
        self.preview_cover = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.preview_cover.setFixedHeight(220)
        self.preview_text = QLabel(alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        self.preview_text.setTextFormat(Qt.TextFormat.PlainText)
        self.preview_text.setStyleSheet(f"color: {themes.muted_color()};")
        rlay.addWidget(self.preview_cover)
        rlay.addWidget(self.preview_text)
        rlay.addStretch(1)
        file_btn = QPushButton(tr("cover_from_file"))
        file_btn.clicked.connect(self.choose_file)
        rlay.addWidget(file_btn)
        split.addWidget(right)
        split.setSizes([420, 320])
        self.root.addWidget(split, 1)
        self.root.addWidget(self.status)
        box = _button_box(tr("cover_apply"), tr("meta_cancel"))
        self.ok_btn = box.button(QDialogButtonBox.StandardButton.Ok)
        box.accepted.connect(self.accept_choice)
        box.rejected.connect(self.reject)
        self.root.addWidget(box)
        self.start_search()

    def _accepts(self, result):
        return bool(result.get("cover_url"))       # tylko wyniki z adresem okładki

    def _on_cleared(self):
        self.images.clear()
        self.preview_cover.setPixmap(covers.default_cover(160))
        self.preview_text.setText("")

    def _decorate(self, item, result):
        item.setIcon(QIcon(covers.default_cover(64)))

    def _after_results(self):
        items = [(i, r["cover_url"]) for i, r in enumerate(self.results)]
        if items:
            w = workers.ImageWorker(self.generation, items)
            w.loaded.connect(self._thumb_loaded)
            workers.start(w)

    def _thumb_loaded(self, generation, row, image):
        # miniatura trafia do wiersza tylko, jeśli to nadal ten sam wynik wyszukiwania
        if generation != self.generation or not 0 <= row < self.list.count():
            return
        self.images[row] = image
        pm = QPixmap.fromImage(image).scaled(60, 84, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
        self.list.item(row).setIcon(QIcon(pm))
        if row == self.list.currentRow():
            self.show_preview(row)

    def show_preview(self, row):
        r = self.results[row] if 0 <= row < len(self.results) else None
        if not r:
            return
        self.preview_text.setText(f"{r['title']}\n{r['author']}\n{tr('meta_source')}: {r['source']}")
        img = self.images.get(row)
        if img is not None:
            self.preview_cover.setPixmap(QPixmap.fromImage(img).scaledToHeight(
                210, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview_cover.setPixmap(covers.default_cover(160))

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("cover_dlg_choose_file"), "",
            f"{tr('cover_image_files')} (*.jpg *.jpeg *.png *.webp *.bmp)")
        if not path:
            return
        dest = self.library.cover_path(self.book["id"])
        if covers.save_cover_file(path, dest):
            self.result_path = dest
            self.accept()
        else:
            self.status.setText(tr("cover_file_failed"))

    def accept_choice(self):
        r = self.current_result()
        if not r:
            self.reject()
            return
        dest = self.library.cover_path(self.book["id"])
        self.status.setText(tr("cover_downloading"))
        self.ok_btn.setEnabled(False)
        w = workers.CoverDownloadWorker(r["cover_url"], dest)
        w.done.connect(lambda ok, d=dest: self._on_downloaded(ok, d))
        workers.start(w)

    def _on_downloaded(self, ok, dest):
        if ok:
            self.result_path = dest
            self.accept()
        else:
            self.ok_btn.setEnabled(True)
            self.status.setText(tr("cover_download_failed"))


# ---------------------------------------------------------------- zakładki

class BookmarksDialog(QDialog):
    """Lista zakładek książki: skok, zmiana nazwy, usunięcie. Zmienia `book['bookmarks']`
    w miejscu; wybrany skok zwraca w `jump_to` = (file_index, position_ms)."""

    def __init__(self, book, parent=None):
        super().__init__(parent)
        self.book = book
        self.jump_to = None
        self.changed = False
        self.setWindowTitle(tr("bookmarks_title", title=book["title"]))
        self.resize(460, 360)
        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.go)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, slot in ((tr("bookmark_go"), self.go), (tr("bookmark_rename"), self.rename),
                           (tr("bookmark_delete"), self.delete)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        close = QPushButton(tr("close"))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self.refresh()

    def refresh(self, select_row=None):
        """Odbudowuje listę i zachowuje zaznaczenie (po zmianie nazwy/usunięciu
        użytkownik może od razu wykonać kolejną akcję)."""
        self.list.clear()
        if not self.book["bookmarks"]:
            self.list.addItem(tr("bookmarks_empty"))
            self.list.item(0).setFlags(Qt.ItemFlag.NoItemFlags)
            return
        for bm in self.book["bookmarks"]:
            at = fmt_ms(self.book.offset_ms(bm["file_index"]) + bm["position_ms"])
            item = QListWidgetItem(f"[{at}] {bm['title']}")
            item.setData(Qt.ItemDataRole.UserRole, bm["id"])
            self.list.addItem(item)
        if select_row is not None:
            self.list.setCurrentRow(max(0, min(select_row, self.list.count() - 1)))

    def _selected(self):
        item = self.list.currentItem()
        bid = item.data(Qt.ItemDataRole.UserRole) if item else None
        return next((b for b in self.book["bookmarks"] if b["id"] == bid), None)

    def go(self, *_):
        bm = self._selected()
        if bm:
            self.jump_to = (bm["file_index"], bm["position_ms"])
            self.accept()

    def rename(self):
        bm = self._selected()
        if not bm:
            return
        text, ok = QInputDialog.getText(self, tr("bookmark_rename"), tr("bookmark_name"),
                                        text=bm["title"])
        if ok and text.strip():
            row = self.list.currentRow()
            bm["title"] = text.strip()
            self.changed = True
            self.refresh(select_row=row)

    def delete(self):
        bm = self._selected()
        if bm:
            row = self.list.currentRow()
            self.book["bookmarks"].remove(bm)
            self.changed = True
            self.refresh(select_row=row)


# ---------------------------------------------------------------- wsadowe metadane

class BatchMetadataDialog(QDialog):
    """Szuka najlepszych dopasowań dla wielu książek naraz; użytkownik zatwierdza
    wybrane propozycje, a okładki są pobierane w tle."""

    def __init__(self, library, books, parent=None):
        super().__init__(parent)
        self.library = library
        self.books = {b["id"]: b for b in books}
        self.proposals = {}
        self.applied = 0
        self.setWindowTitle(tr("batch_title"))
        self.resize(820, 460)
        lay = QVBoxLayout(self)
        self.info = QLabel(tr("batch_searching", i=0, n=len(books), title=""))
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.bar = QProgressBar()
        self.bar.setRange(0, max(1, len(books)))
        lay.addWidget(self.info)
        lay.addWidget(self.bar)
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setHeaderLabels([tr("batch_col_book"), tr("batch_col_proposal"),
                                   tr("meta_source"), tr("batch_col_match")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tree, 1)
        self.box = _button_box(tr("batch_apply"), tr("cancel"))
        self.apply_btn = self.box.button(QDialogButtonBox.StandardButton.Ok)
        self.apply_btn.setEnabled(False)
        self.box.accepted.connect(self.apply_selected)
        self.box.rejected.connect(self.reject)
        lay.addWidget(self.box)

        self.worker = workers.BatchMetaWorker(
            [{"id": b["id"], "title": b["title"], "author": b["author"]} for b in books],
            i18n.language())
        self.worker.progress.connect(self._progress)
        self.worker.proposal.connect(self._proposal)
        self.worker.done.connect(self._search_done)
        workers.start(self.worker)

    def _progress(self, i, n, title):
        self.bar.setValue(i)
        self.info.setText(tr("batch_searching", i=i, n=n, title=title))

    def _proposal(self, p):
        r = p["result"]
        item = QTreeWidgetItem([
            f"{p['old_title']}" + (f" — {p['old_author']}" if p["old_author"] else ""),
            f"{r['title']}" + (f" — {r['author']}" if r["author"] else ""),
            r["source"], f"{int(min(p['score'], 1.0) * 100)}%"])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked if p["score"] >= 0.8 else Qt.CheckState.Unchecked)
        item.setData(0, Qt.ItemDataRole.UserRole, p["id"])
        self.proposals[p["id"]] = p
        self.tree.addTopLevelItem(item)

    def _search_done(self):
        self.bar.setValue(self.bar.maximum())
        self.info.setText(tr("batch_done", n=len(self.proposals)) if self.proposals
                          else tr("batch_none"))
        self.apply_btn.setEnabled(bool(self.proposals))

    def apply_selected(self):
        chosen = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                chosen.append(self.proposals[it.data(0, Qt.ItemDataRole.UserRole)])
        if not chosen:
            self.reject()
            return
        self.apply_btn.setEnabled(False)
        self.tree.setEnabled(False)
        self._chosen = chosen
        items = [(p["id"], p["result"]["cover_url"]) for p in chosen if p["result"].get("cover_url")]
        self.info.setText(tr("batch_covers"))
        self.bar.setValue(0)
        self.bar.setMaximum(max(1, len(items)))
        w = workers.SaveCoversWorker(items, self.library.covers_dir)
        w.progress.connect(lambda i, n: self.bar.setValue(i))
        w.done.connect(self._covers_saved)
        workers.start(w)

    def _covers_saved(self, saved):
        for p in self._chosen:
            book = self.books.get(p["id"])
            if not book:
                continue
            r = p["result"]
            if r.get("title"):
                book["title"] = r["title"]
            if r.get("author"):
                book["author"] = r["author"]
            if r.get("description"):
                book["description"] = r["description"]
            if p["id"] in saved:
                book["cover"] = saved[p["id"]]
            self.applied += 1
        self.accept()

    def done(self, code):
        self.worker.requestInterruption()
        super().done(code)


# ---------------------------------------------------------------- statystyki

class StatsDialog(QDialog):
    def __init__(self, library, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("stats_title"))
        self.resize(520, 520)
        stats = library.settings.get("stats", {"daily": {}, "total_ms": 0})
        daily = stats.get("daily", {})
        today = time.strftime("%Y-%m-%d")
        week = sum(v for k, v in daily.items() if k >= time.strftime(
            "%Y-%m-%d", time.localtime(time.time() - 6 * 86400)))
        finished = sum(1 for b in library.books if b.get("finished"))

        lay = QVBoxLayout(self)
        summary = QLabel("\n".join([
            tr("stats_total", t=fmt_ms(stats.get("total_ms", 0))),
            tr("stats_today", t=fmt_ms(daily.get(today, 0))),
            tr("stats_week", t=fmt_ms(week)),
            tr("stats_books", n=len(library.books), done=finished),
        ]))
        summary.setTextFormat(Qt.TextFormat.PlainText)
        lay.addWidget(summary)

        lay.addWidget(QLabel(tr("stats_last_days")))
        days = [time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
                for i in range(13, -1, -1)]
        peak = max([daily.get(d, 0) for d in days] + [1])
        bars = QTextEdit(readOnly=True)
        bars.setMaximumHeight(210)
        bars.setPlainText("\n".join(
            f"{d[5:]}  {'█' * int(24 * daily.get(d, 0) / peak):<24} {fmt_ms(daily.get(d, 0))}"
            for d in days))
        bars.setStyleSheet("font-family: Consolas, monospace;")
        lay.addWidget(bars)

        lay.addWidget(QLabel(tr("stats_top")))
        top = sorted((b for b in library.books if b.get("listened_ms")),
                     key=lambda b: -b["listened_ms"])[:8]
        table = QTableWidget(len(top), 2)
        table.setHorizontalHeaderLabels([tr("batch_col_book"), tr("stats_time")])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, b in enumerate(top):
            table.setItem(i, 0, QTableWidgetItem(b["title"]))
            table.setItem(i, 1, QTableWidgetItem(fmt_ms(b["listened_ms"])))
        lay.addWidget(table, 1)
        close = QPushButton(tr("close"))
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)


# ---------------------------------------------------------------- tekst

class TextViewDialog(QDialog):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 520)
        lay = QVBoxLayout(self)
        view = QTextEdit(readOnly=True)
        view.setPlainText(text)
        lay.addWidget(view, 1)
        close = QPushButton(tr("close"))
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)


def read_resource_text(name):
    import paths
    path = paths.resource_path(name)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


__all__ = ["confirm", "MetadataDialog", "CoverDialog", "BookmarksDialog",
           "BatchMetadataDialog", "StatsDialog", "TextViewDialog", "format_errors",
           "search_status", "read_resource_text"]
