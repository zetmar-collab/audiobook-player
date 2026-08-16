"""Generuje grafiki (kafelki) wymagane przez pakiet MSIX oraz ikonę .ico.

Uruchamiać przez .venvq:
    .venvq\\Scripts\\python.exe msix\\make_assets.py

Logo rysowane jest wektorowo (pałąk + dwie muszle słuchawek), więc nie zależy
od obecności fontu z emoji.
"""
import os
import sys

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap

BG = "#2b6cb0"       # niebieski tła kafelka
FG = "#ffffff"       # biel słuchawek
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Assets")

#: (nazwa pliku, szerokość, wysokość) — zestaw wymagany/zalecany przez MS Store
ASSETS = [
    ("Square44x44Logo.png", 44, 44),
    ("Square44x44Logo.targetsize-24_altform-unplated.png", 24, 24),
    ("Square44x44Logo.targetsize-48.png", 48, 48),
    ("Square44x44Logo.targetsize-256.png", 256, 256),
    ("Square71x71Logo.png", 71, 71),
    ("Square150x150Logo.png", 150, 150),
    ("Square310x310Logo.png", 310, 310),
    ("Wide310x150Logo.png", 310, 150),
    ("StoreLogo.png", 50, 50),
    ("SplashScreen.png", 620, 300),
]


def draw_headphones(painter, cx, cy, size, color=FG):
    """Rysuje symbol słuchawek wyśrodkowany w (cx, cy) o zadanej wysokości."""
    s = size / 100.0
    cy += 7 * s  # wyrównanie środka rysunku (pałąk u góry, muszle w dół)

    radius = 30 * s
    cup_w, cup_h = 20 * s, 34 * s
    cup_top = cy - 6 * s

    # pałąk — górna połowa okręgu (0°..180° liczone od godziny 3 w lewo)
    pen = QPen(QColor(color))
    pen.setWidthF(12 * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    band = QRectF(cx - radius, cup_top - radius, 2 * radius, 2 * radius)
    painter.drawArc(band, 0, 180 * 16)

    # muszle — zaokrąglone prostokąty zwisające z końców pałąka
    painter.setPen(Qt.PenStyle.NoPen)
    for x in (cx - radius - cup_w / 2, cx + radius - cup_w / 2):
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, cup_top, cup_w, cup_h), cup_w / 2, cup_w / 2)
        painter.fillPath(path, QColor(color))


def make(name, w, h):
    pm = QPixmap(w, h)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # tło: zaokrąglony kwadrat (dla kafelków) albo pełne tło (splash/wide)
    unplated = "unplated" in name
    if not unplated:
        radius = min(w, h) * 0.18
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
        p.fillPath(path, QColor(BG))

    glyph = min(w, h) * (0.92 if unplated else 0.62)
    draw_headphones(p, w / 2, h / 2, glyph, FG if not unplated else "#ffffff")
    p.end()

    path_out = os.path.join(OUT, name)
    pm.save(path_out, "PNG")
    return path_out


def main():
    # uchwyt musi żyć do końca funkcji — bez tego Qt zwalnia aplikację i sypie się
    app = QGuiApplication(sys.argv[:1])  # noqa: F841
    os.makedirs(OUT, exist_ok=True)
    for name, w, h in ASSETS:
        make(name, w, h)
    print(f"Zapisano {len(ASSETS)} grafik w {OUT}")

    # ikona aplikacji (.ico) w rozmiarach używanych przez Windows
    ico = QPixmap(256, 256)
    ico.fill(QColor(0, 0, 0, 0))
    p = QPainter(ico)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, 256, 256), 46, 46)
    p.fillPath(path, QColor(BG))
    draw_headphones(p, 128, 128, 160)
    p.end()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(project_root, "src", "icon.ico")
    ico.save(icon_path, "ICO")
    print(f"Zapisano ikonę {icon_path}")


if __name__ == "__main__":
    main()
