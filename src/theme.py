"""Motyw jasny/ciemny dla stylu Fusion.

`apply_theme(app, "dark" | "light" | "system")` — ustawia paletę i drobne
poprawki arkusza stylów. Tryb "system" czyta ustawienie Windows
(Personalizacja → Kolory → Tryb aplikacji).
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

THEMES = ["light", "dark", "system"]

#: Kolor tekstu pobocznego (autor, czas, opis) — używany też w widgetach listy.
MUTED = {"light": "#6b7280", "dark": "#9aa4b2"}
#: Tło zastępczej okładki, gdy książka nie ma pobranej grafiki.
COVER_BG = {"light": "#cbd5e1", "dark": "#39424e"}
COVER_FG = {"light": "#64748b", "dark": "#aab6c2"}

_active = "light"


def active():
    """Faktycznie użyty motyw ('light'/'dark') — 'system' jest już rozwiązany."""
    return _active


def windows_prefers_dark():
    """Czy Windows ma włączony ciemny tryb aplikacji."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except Exception:
        return False


def resolve(theme):
    if theme == "system":
        return "dark" if windows_prefers_dark() else "light"
    return theme if theme in ("light", "dark") else "light"


def _dark_palette():
    p = QPalette()
    window = QColor("#1f2225")
    base = QColor("#181a1c")
    alt = QColor("#26292d")
    text = QColor("#e6e8ea")
    disabled = QColor("#6b7280")
    accent = QColor("#3b82f6")

    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, alt)
    p.setColor(QPalette.ColorRole.ToolTipBase, alt)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, alt)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor("#ff5555"))
    p.setColor(QPalette.ColorRole.Link, accent)
    p.setColor(QPalette.ColorRole.Highlight, accent)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled)

    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return p


_DARK_QSS = """
QToolTip { color: #e6e8ea; background-color: #26292d; border: 1px solid #3a3f45; }
QToolBar { border: none; padding: 3px; }
QListWidget { border: 1px solid #33383d; }
QTextEdit, QLineEdit { border: 1px solid #33383d; border-radius: 3px; }
QProgressBar { background-color: #33383d; border: none; border-radius: 2px; }
QProgressBar::chunk { background-color: #3b82f6; border-radius: 2px; }
QSlider::groove:horizontal { height: 4px; background: #33383d; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #e6e8ea; width: 12px; margin: -5px 0; border-radius: 6px;
}
QStatusBar { color: #9aa4b2; }
"""

_LIGHT_QSS = """
QToolBar { border: none; padding: 3px; }
QProgressBar { background-color: #e2e8f0; border: none; border-radius: 2px; }
QProgressBar::chunk { background-color: #2563eb; border-radius: 2px; }
QSlider::groove:horizontal { height: 4px; background: #cbd5e1; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #334155; width: 12px; margin: -5px 0; border-radius: 6px;
}
"""


def apply_theme(app, theme):
    """Ustawia motyw aplikacji; zwraca faktycznie zastosowany ('light'/'dark')."""
    global _active
    _active = resolve(theme)
    app.setStyle("Fusion")
    if _active == "dark":
        app.setPalette(_dark_palette())
        app.setStyleSheet(_DARK_QSS)
    else:
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet(_LIGHT_QSS)
    return _active


def muted_color():
    return MUTED[_active]
