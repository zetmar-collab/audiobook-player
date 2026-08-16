# Audiobook Player — zasady projektu

Odtwarzacz audiobooków (PyQt6), Windows + Linux. Kod w `src\`, gotowy exe/binarka w `dist\`.

## Krytyczne — nie łamać

- **PyQt6, NIE PySide6.** QMediaPlayer w PySide6 (testowane 6.7.3 i 6.11.1) na tej
  maszynie przerywa odtwarzanie po ~0,5 s (pozycja wraca do 0, oba backendy
  ffmpeg/windows). Nie "migrować" ani nie "ujednolicać" do PySide6.
  Konsekwencja PyQt6: pełne ścieżki enumów (`Qt.AlignmentFlag.AlignCenter`),
  `pyqtSignal` zamiast `Signal`, licencja GPL-3.0.
- **Windows: budować wyłącznie przez `.venvq`** (`.venvq\Scripts\python.exe`,
  `.venvq\Scripts\pyinstaller.exe`). Python ze Sklepu Windows ma za długie ścieżki
  site-packages — `pip install PySide6/PyQt6` poza venv kończy się błędem OSError.
  Na Linuksie ten problem nie występuje — zwykły `venv` wystarczy.
- **Ścieżka danych jest platformowa** (`src\library.py::_app_dir`): Windows →
  `%APPDATA%\AudiobookPlayer`, Linux/macOS → `$XDG_DATA_HOME/AudiobookPlayer`
  (domyślnie `~/.local/share/AudiobookPlayer`). Nie wracać do sztywnego `%APPDATA%`.
- Otwieranie lokalizacji na dysku idzie przez `QDesktopServices.openUrl` (Qt,
  działa na obu platformach) — nie `os.startfile` (Windows-only).

## Budowanie

### Windows

```powershell
# exe przenośny (onefile)
.venvq\Scripts\pyinstaller.exe --noconfirm --onefile --windowed `
  --name AudiobookPlayer --icon src\icon.ico --add-data "src\icon.ico;." src\main.py
.\build_installer.ps1     # -> installer_out\   (sam znajduje ISCC.exe)
.\build_msix.ps1          # -> msix_out\        (pakiet do MS Store)
```

Wersje: `#define MyAppVersion` w `installer.iss`, `Identity Version` w
`msix\AppxManifest.xml` (czterocząstkowa, np. `1.1.0.0`), `APP_VERSION` w `src\main.py`.

**Nie wpisywać ścieżki do ISCC.exe na sztywno** — Inno Setup instaluje się raz
w `Program Files`, raz w `%LOCALAPPDATA%\Programs`. Używać `build_installer.ps1`.

Uwaga: pakiet `PyQt6-Multimedia` **nie istnieje** na PyPI — `QtMultimedia`
jest już w wheelu `PyQt6` (razem z `PyQt6-Qt6`). Nie dodawać go do
`requirements.txt`, `pip` i tak zwróci błąd "No matching distribution".

### Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pyinstaller
.venv/bin/pyinstaller --noconfirm AudiobookPlayer.spec   # -> dist/AudiobookPlayer
packaging/linux/install.sh                               # instalacja lokalna (~/.local)
```

`AudiobookPlayer.spec` jest wspólny dla obu platform (wybiera `.ico`/`.png` wg
`sys.platform`). Integracja z pulpitem: `packaging/linux/audiobookplayer.desktop`
+ `src/icon.png` (wygenerowany z `icon.ico`). Qt Multimedia na Linuksie może
wymagać systemowego backendu (GStreamer/ffmpeg) w zależności od dystrybucji —
jeśli dźwięk się nie odtwarza, to pierwsze miejsce do sprawdzenia.

Wymaga `libxcb-cursor0` systemowo (`sudo apt install libxcb-cursor0`) — bez
tego pluginu platformy `xcb` okno się nie otworzy na X11/Wayland (typowy brak
na minimalnych instalacjach; PyInstaller o tym ostrzega przy budowaniu, ale
i tak nie potrafi tego zapakować — to zależność systemowa, nie pythonowa).

### AppImage

`packaging/linux/build-appimage.sh` pakuje `dist/AudiobookPlayer` do
`AudiobookPlayer-x86_64.AppImage` (AppDir ręcznie złożony: `AppRun` + ikona +
`.desktop`, bez `linuxdeploy` — PyInstaller onefile już jest samowystarczalny).
Wymaga jednorazowo pobranego `appimagetool-x86_64.AppImage` w
`packaging/linux/tools/` (ignorowane w git — nie commitować binarki narzędzia).

## Architektura

- `src\main.py` — całe UI + odtwarzacz (QMediaPlayer)
- `src\i18n.py` — tłumaczenia PL/EN (`tr("klucz")`); zmiana języka przebudowuje UI
  przez `MainWindow.rebuild_ui()`, więc **każdy napis w UI musi iść przez `tr()`**
- `src\theme.py` — motyw jasny/ciemny/systemowy (paleta Fusion + QSS);
  kolor tekstu pobocznego brać z `theme.muted_color()`, nie wpisywać „gray".
  Tryb systemowy czyta rejestr Windows; na Linuksie/macOS daje jasny.
- `src\library.py` — model biblioteki, zapis JSON do katalogu danych zależnego
  od platformy (patrz `_app_dir()` powyżej).
  Klucze ustawień: `lang`, `theme`, `speed`, `volume`
- `src\metadata.py` — źródła metadanych, wszystkie best-effort (błąd → pusta lista),
  odpytywane **równolegle** (`search_all`), timeout `(connect=5, read=12)`:
  - PL: lubimyczytac.pl (`div.book-card`), upolujebooka.pl (`/szukaj,{fraza}.html` + JSON-LD)
  - zagraniczne: Audible (`api.audible.com/1.0/catalog/products` — najlepsze dla
    audiobooków), Apple Books (iTunes Search API), Google Books (bywa 429),
    Open Library (z sieci autora nieosiągalne — dlatego krótki timeout połączenia)
- `msix\` — manifest i generator kafelków dla MS Store

## Testowanie

Brak automatycznych testów. Smoke test: uruchomić exe, dodać katalog z audio,
odtworzyć, zamknąć, otworzyć ponownie — pozycja ma być zapamiętana.
Uwaga: w sesjach Claude Code odtwarzanie QMediaPlayer może nie postępować mimo
stanu Playing — testować pozycję z zapasem czasu.

## Publikacja

GitHub: `zetmar-collab/audiobook-player` (przez `gh`).
Release Windows = exe przenośny + instalator z `installer_out\` + pakiet MSIX
z `msix_out\`. Release Linux = binarka z `dist/` + AppImage.
Dane użytkownika w katalogu danych platformy (patrz wyżej) — nigdy nie kasować
przy aktualizacjach/odinstalowaniu.

Microsoft Store (Partner Center) — tożsamość pakietu, nie zmieniać:
`Name=MarekZettel-zetmar.PlayerAudiobook`,
`Publisher=CN=15A53D32-C868-48EE-B700-5DBB5449CA1B`,
`PublisherDisplayName=Marek Zettel - zetmar`.
Pakiet wysyłamy **niepodpisany** — Store podpisuje go sam.
