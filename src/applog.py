"""Logowanie błędów i globalna obsługa nieobsłużonych wyjątków.

PyQt6 wywołuje `abort()`, gdy wyjątek w slocie nie ma obsługi — wersja okienkowa
znika wtedy bez śladu. `install_excepthook` zapisuje traceback do pliku
`error.log` i pokazuje komunikat zamiast zamykać program.
"""
import logging
import os
import sys
import threading
import time
import traceback
from logging.handlers import RotatingFileHandler

import paths

log = logging.getLogger("audiobookplayer")
_notify = None          # callback(str) pokazujący komunikat użytkownikowi
_last_notified = 0.0
_in_hook = False


def setup_logging(log_file=None):
    log_file = log_file or paths.LOG_FILE
    log.setLevel(logging.INFO)
    if any(isinstance(h, RotatingFileHandler) for h in log.handlers):
        return log
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handler = RotatingFileHandler(log_file, maxBytes=256 * 1024, backupCount=2,
                                      encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    except OSError:
        pass  # brak możliwości zapisu logu nie może blokować aplikacji
    return log


def set_notifier(callback):
    global _notify
    _notify = callback


def _handle(exc_type, exc, tb):
    global _last_notified, _in_hook
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    log.critical("Nieobsłużony wyjątek:\n%s", text)
    if _in_hook:
        return
    _in_hook = True
    try:
        now = time.time()
        if _notify and now - _last_notified > 10:   # nie zalewaj okienkami
            _last_notified = now
            _notify(f"{exc_type.__name__}: {exc}")
    except Exception:
        pass
    finally:
        _in_hook = False


def install_excepthook():
    sys.excepthook = _handle
    if hasattr(threading, "excepthook"):
        threading.excepthook = lambda a: _handle(a.exc_type, a.exc_value, a.exc_traceback)
