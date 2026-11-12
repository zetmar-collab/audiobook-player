# Licencje i uznania — Audiobook Player

Audiobook Player jest wolnym oprogramowaniem na licencji **GNU GPL v3** (pełny tekst
w pliku `LICENSE`). Kod źródłowy: https://github.com/zetmar-collab/audiobook-player

Program korzysta z poniższych komponentów. Dostarczany plik wykonywalny zawiera ich
kod binarny; kod źródłowy każdego z nich jest dostępny pod podanym adresem.

| Komponent | Licencja | Źródło |
|---|---|---|
| PyQt6 (powiązania Pythona z Qt) | GPL-3.0 | https://www.riverbankcomputing.com/software/pyqt/ |
| Qt 6 (biblioteki, w tym Qt Multimedia z FFmpeg) | LGPL-3.0 / GPL-3.0 | https://www.qt.io/ |
| FFmpeg (w Qt Multimedia) | LGPL-2.1+ | https://ffmpeg.org/ |
| mutagen | GPL-2.0-or-later | https://github.com/quodlibet/mutagen |
| requests | Apache-2.0 | https://github.com/psf/requests |
| urllib3 | MIT | https://github.com/urllib3/urllib3 |
| certifi | MPL-2.0 | https://github.com/certifi/python-certifi |
| charset-normalizer | MIT | https://github.com/jawah/charset_normalizer |
| idna | BSD-3-Clause | https://github.com/kjd/idna |
| Beautiful Soup 4 | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| soupsieve | MIT | https://github.com/facelessuser/soupsieve |
| Python (interpreter i biblioteka standardowa) | PSF-2.0 | https://www.python.org/ |
| PyInstaller (bootloader w pliku wykonywalnym) | GPL-2.0 z wyjątkiem dla programów pakowanych | https://pyinstaller.org/ |

## Dane z serwisów zewnętrznych

Okładki, opisy i dane książek pobierane na wyraźną prośbę użytkownika pochodzą z serwisów
lubimyczytac.pl, upolujebooka.pl, Audible, Apple Books, Google Books i Open Library. Należą
do ich właścicieli; program zapisuje je wyłącznie lokalnie, na urządzeniu użytkownika.
Program nie jest powiązany z tymi serwisami ani przez nie rekomendowany.

## Prawo do zamiany biblioteki Qt

Zgodnie z LGPL użytkownik może zastąpić biblioteki Qt własną wersją. Wersja
uruchomieniowa Qt jest dołączona jako osobne pliki DLL (w pakiecie MSIX i w katalogu
wersji przenośnej `_internal`); w pliku jednoplikowym `AudiobookPlayer.exe` znajdują się
one w archiwum, które można rozpakować narzędziem `pyinstxtractor`. Skrypty budowania są
w repozytorium.
