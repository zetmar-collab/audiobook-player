"""Widgety wielokrotnego użytku w oknie głównym."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

import covers
import i18n
import theme as themes
from i18n import tr
from util import fmt_ms

_default_cache = {}


def cached_default_cover(size):
    """Zastępcza okładka rysowana raz na (motyw, rozmiar) — nie przy każdym odświeżeniu listy."""
    key = (themes.active(), size)
    if key not in _default_cache:
        _default_cache[key] = covers.default_cover(size)
    return _default_cache[key]


def plain_label(text="", **kw):
    """QLabel pokazujący dane dosłownie: tytuł z `<b>` czy `&` pochodzący z metadanych
    lub nazwy katalogu nie jest interpretowany jako HTML."""
    label = QLabel(text, **kw)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class BookItemWidget(QWidget):
    def __init__(self, book, playing=False):
        super().__init__()
        muted = themes.muted_color()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        cover = QLabel()
        cover.setFixedSize(56, 56)
        cover.setPixmap(covers.scaled_pixmap(book.get("cover"), 56, 56) or cached_default_cover(56))
        lay.addWidget(cover)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = plain_label(("▶ " if playing else "") + book["title"])
        f = title.font()
        f.setBold(True)
        title.setFont(f)
        author = plain_label(book["author"] or tr("no_author"))
        author.setStyleSheet(f"color: {muted};")
        bits = []
        if book["kind"] == "folder":
            bits.append(i18n.plural_files(len(book["files"])))
        if book.total_ms:
            bits.append(fmt_ms(book.total_ms))
        if book.get("finished"):
            bits.append(tr("badge_finished"))
        if book.get("bookmarks"):
            bits.append(tr("bookmarks_count", n=len(book["bookmarks"])))
        info = plain_label(" · ".join(bits))
        info.setStyleSheet(f"color: {muted}; font-size: 11px;")
        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(int(book.progress_frac * 1000))
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        for w in (title, author, info, bar):
            col.addWidget(w)
        lay.addLayout(col, 1)

        self._bar = bar
        pct = plain_label(f"{int(book.progress_frac * 100)}%")
        pct.setStyleSheet(f"color: {muted};")
        pct.setFixedWidth(44)          # stała szerokość: paski postępu w całej liście kończą się równo
        pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(pct)
        self._muted_labels = [(author, ""), (info, "font-size: 11px;"), (pct, "")]
        self._muted = muted

    def set_selected(self, selected):
        """Na zaznaczonym (niebieskim) wierszu szary tekst byłby nieczytelny — zmieniamy
        kolory na kontrastowe i odwracamy pasek postępu."""
        color = "#ffffff" if selected else self._muted
        for label, extra in self._muted_labels:
            label.setStyleSheet(f"color: {color}; {extra}")
        if selected:
            self._bar.setStyleSheet("QProgressBar { background-color: rgba(255,255,255,70); }"
                                    "QProgressBar::chunk { background-color: #ffffff; }")
        else:
            self._bar.setStyleSheet("")
