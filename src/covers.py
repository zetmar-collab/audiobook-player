"""Okładki: wczytywanie, normalizacja, zapis oraz cache miniatur (Qt).

Okładki zapisujemy zawsze jako JPEG o rozmiarze do 1000 px — surowe zdjęcie 20 Mpx
wybrane z dysku nie spowalnia listy i nie zajmuje dziesiątek MB na książkę.
Funkcje obrazowe używają QImage (bezpiecznego w wątkach roboczych), a QPixmap
powstaje tylko w wątku GUI.
"""
import logging
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap, QPixmapCache

import theme as themes

log = logging.getLogger("audiobookplayer")

MAX_COVER_SIDE = 1000
JPEG_QUALITY = 90

QPixmapCache.setCacheLimit(65536)      # 64 MB miniatur w pamięci


def default_cover(size=96):
    """Zastępcza okładka (słuchawki) w kolorach bieżącego motywu."""
    pm = QPixmap(size, size)
    pm.fill(QColor(themes.COVER_BG[themes.active()]))
    p = QPainter(pm)
    p.setPen(QColor(themes.COVER_FG[themes.active()]))
    f = QFont()
    f.setPointSize(max(6, int(size * 0.45)))
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "🎧")
    p.end()
    return pm


def image_from_bytes(data):
    img = QImage()
    return img if img.loadFromData(data) and not img.isNull() else None


def _flatten_on_white(img):
    """JPEG nie ma kanału alfa — przezroczystość wypełniamy bielą, nie czernią."""
    out = QImage(img.size(), QImage.Format.Format_RGB32)
    out.fill(QColor("white"))
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    return out


def normalize(img):
    if max(img.width(), img.height()) > MAX_COVER_SIDE:
        img = img.scaled(MAX_COVER_SIDE, MAX_COVER_SIDE, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    return _flatten_on_white(img)


def save_cover_image(img, dest):
    """Zapisuje QImage jako okładkę JPEG. Zwraca True tylko, gdy plik naprawdę powstał."""
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        ok = normalize(img).save(dest, "JPG", JPEG_QUALITY)
        return bool(ok) and os.path.getsize(dest) > 0
    except OSError as e:
        log.error("Zapis okładki %s: %s", dest, e)
        return False


def save_cover_bytes(data, dest):
    img = image_from_bytes(data)
    return bool(img) and save_cover_image(img, dest)


def save_cover_file(path, dest):
    img = QImage(path)
    return (not img.isNull()) and save_cover_image(img, dest)


def cover_saver_for(covers_dir):
    """Funkcja (bajty, id książki) -> ścieżka okładki albo '' — dla skanera."""
    def save(data, book_id):
        dest = os.path.join(covers_dir, book_id + ".jpg")
        return dest if save_cover_bytes(data, dest) else ""
    return save


def scaled_pixmap(path, width, height):
    """Miniatura okładki z pamięciowego cache'u (klucz: ścieżka + czas zmiany + rozmiar).
    Zwraca None, gdy pliku nie ma lub nie da się go odczytać."""
    if not path:
        return None
    try:
        mtime = os.stat(path).st_mtime_ns
    except OSError:
        return None
    key = f"{path}|{mtime}|{width}x{height}"
    cached = QPixmapCache.find(key)           # PyQt6: zwraca QPixmap albo None
    if cached is not None and not cached.isNull():
        return cached
    pm = QPixmap(path)
    if pm.isNull():
        return None
    pm = pm.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                   Qt.TransformationMode.SmoothTransformation)
    QPixmapCache.insert(key, pm)
    return pm
