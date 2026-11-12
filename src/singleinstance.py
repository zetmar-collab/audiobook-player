"""Jedna instancja aplikacji + przekazywanie ścieżek do już działającego okna.

Rozwiązuje dwa problemy naraz: dwie kopie (Store, instalator, przenośna) nie nadpisują
sobie `library.json`, a „Otwórz za pomocą…" / przeciągnięcie pliku na ikonę dodaje
audiobook w istniejącym oknie zamiast otwierać drugie.
"""
import getpass
import json
import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger("audiobookplayer")


def _user():
    try:
        return getpass.getuser()
    except Exception:
        return "user"


class SingleInstance(QObject):
    messageReceived = pyqtSignal(list)      # lista ścieżek od drugiej instancji ([] = tylko pokaż okno)

    def __init__(self, key="AudiobookPlayer", parent=None):
        super().__init__(parent)
        self.name = f"{key}-{_user()}"
        self.server = None

    def send_to_running(self, paths, timeout=600):
        """Jeśli działa już inna instancja — przekazuje jej ścieżki i zwraca True."""
        sock = QLocalSocket(self)
        sock.connectToServer(self.name)
        if not sock.waitForConnected(timeout):
            return False
        sock.write(json.dumps({"paths": list(paths)}).encode("utf-8"))
        sock.flush()
        sock.waitForBytesWritten(timeout)
        sock.disconnectFromServer()
        return True

    def listen(self):
        QLocalServer.removeServer(self.name)    # sprzątanie po awarii (Linux/macOS)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_connection)
        ok = self.server.listen(self.name)
        if not ok:
            log.warning("Nie udało się uruchomić serwera instancji: %s", self.server.errorString())
        return ok

    def _on_connection(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.waitForReadyRead(500)
            raw = bytes(sock.readAll()).decode("utf-8", "replace")
            sock.deleteLater()
            try:
                data = json.loads(raw)
                paths = [str(p) for p in data.get("paths", [])]
            except (ValueError, AttributeError):
                paths = []
            self.messageReceived.emit(paths)
