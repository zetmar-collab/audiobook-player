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
.venvq\Scripts\pyinstaller.exe --noconfirm --onefile --windowed `
  --name AudiobookPlayer --icon src\icon.ico src\main.py
& "C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss   # -> installer_out\
```

Wersja instalatora: `#define MyAppVersion` w `installer.iss`.

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

- `src\main.py` — całe UI + odtwarzacz (QMediaPlayer); UI po polsku
- `src\library.py` — model biblioteki, zapis JSON do katalogu danych zależnego
  od platformy (patrz `_app_dir()` powyżej)
- `src\metadata.py` — scrapery: lubimyczytac.pl (selektory `div.book-card`),
  upolujebooka.pl (GET `/szukaj,{fraza}.html`, szczegóły z JSON-LD schema.org/Book),
  Google Books API (bez klucza — bywa limit 429). Wszystkie best-effort, błędy → pusta lista.

## Testowanie

Brak automatycznych testów. Smoke test: uruchomić exe, dodać katalog z audio,
odtworzyć, zamknąć, otworzyć ponownie — pozycja ma być zapamiętana.
Uwaga: w sesjach Claude Code odtwarzanie QMediaPlayer może nie postępować mimo
stanu Playing — testować pozycję z zapasem czasu.

## Publikacja

GitHub: `zetmar-collab/audiobook-player` (przez `gh`). Release Windows = exe
przenośny + instalator z `installer_out\`. Release Linux = binarka z `dist/`
(+ ew. AppImage w przyszłości). Dane użytkownika w katalogu danych platformy
(patrz wyżej) — nigdy nie kasować przy aktualizacjach/odinstalowaniu.
