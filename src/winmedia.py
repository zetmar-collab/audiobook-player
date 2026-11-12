"""Globalne klawisze multimedialne (Windows): Play/Pauza, Następny, Poprzedni, Stop.

Działa przez RegisterHotKey, więc słuchawki Bluetooth i klawiatury z klawiszami
multimedialnymi sterują programem także wtedy, gdy okno nie jest aktywne.
Skróty są rejestrowane wyłącznie na czas włączenia opcji. Nie jest to integracja
z systemowymi kontrolkami mediów (ekran blokady) — ta wymagałaby dodatkowych
zależności WinRT.
"""
import logging
import sys

from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication

log = logging.getLogger("audiobookplayer")

IS_WINDOWS = sys.platform == "win32"
WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
#: id skrótu -> (nazwa akcji, kod klawisza wirtualnego)
KEYS = {1: ("play_pause", 0xB3), 2: ("next", 0xB0), 3: ("prev", 0xB1), 4: ("stop", 0xB2)}


class MediaKeys(QAbstractNativeEventFilter):
    def __init__(self, handlers):
        super().__init__()
        self.handlers = handlers            # {"play_pause": callable, ...}
        self.registered = set()
        self.active = False

    def enable(self):
        """Rejestruje klawisze. Zwraca liczbę zarejestrowanych (0 = niedostępne/zajęte)."""
        if not IS_WINDOWS or self.active:
            return len(self.registered)
        import ctypes
        app = QCoreApplication.instance()
        app.installNativeEventFilter(self)
        self.active = True
        for hid, (_name, vk) in KEYS.items():
            if ctypes.windll.user32.RegisterHotKey(None, hid, MOD_NOREPEAT, vk):
                self.registered.add(hid)
            else:
                log.info("Klawisz multimedialny %s jest zajęty przez inną aplikację", hex(vk))
        return len(self.registered)

    def disable(self):
        if not IS_WINDOWS or not self.active:
            return
        import ctypes
        for hid in list(self.registered):
            ctypes.windll.user32.UnregisterHotKey(None, hid)
        self.registered.clear()
        app = QCoreApplication.instance()
        if app:
            app.removeNativeEventFilter(self)
        self.active = False

    def nativeEventFilter(self, event_type, message):
        if IS_WINDOWS and bytes(event_type) == b"windows_generic_MSG":
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in KEYS:
                handler = self.handlers.get(KEYS[msg.wParam][0])
                if handler:
                    handler()
                return True, 0
        return False, 0
