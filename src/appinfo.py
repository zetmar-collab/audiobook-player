"""Jedno źródło prawdy o wersji i tożsamości aplikacji.

Skrypty budowania (`build_installer.ps1`, `build_msix.ps1`) czytają `APP_VERSION`
stąd, więc wersję zmienia się wyłącznie w tym pliku.
"""

APP_NAME = "Audiobook Player"
APP_VERSION = "1.4.0"
APP_URL = "https://github.com/zetmar-collab/audiobook-player"
USER_AGENT = f"AudiobookPlayer/{APP_VERSION} (+{APP_URL})"
