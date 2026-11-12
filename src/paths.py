"""Ścieżki danych użytkownika i zasobów dołączonych do aplikacji."""
import os
import sys


def _app_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "AudiobookPlayer")


APP_DIR = _app_dir()
LIBRARY_FILE = os.path.join(APP_DIR, "library.json")
COVERS_DIR = os.path.join(APP_DIR, "covers")
BACKUP_DIR = os.path.join(APP_DIR, "backups")
LOG_FILE = os.path.join(APP_DIR, "error.log")


def resource_path(name):
    """Plik dołączony do aplikacji (LICENSE, ikona…): obok exe (PyInstaller),
    obok źródeł albo w katalogu głównym repozytorium. Zwraca None, gdy go nie ma."""
    here = os.path.dirname(os.path.abspath(__file__))
    bases = [getattr(sys, "_MEIPASS", None), here, os.path.dirname(here)]
    for base in bases:
        if base:
            path = os.path.join(base, name)
            if os.path.exists(path):
                return path
    return None
