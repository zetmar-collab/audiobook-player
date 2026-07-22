# Audiobook Player

Odtwarzacz audiobooków — Windows i Linux. Gotowy program: **`dist\AudiobookPlayer.exe`**
na Windows / **`dist/AudiobookPlayer`** na Linuksie (pojedynczy plik, niczego nie
trzeba instalować).

## Funkcje

- **Biblioteka** — audiobooki jako katalogi (wiele plików = rozdziały) i pojedyncze pliki.
- **Dodawanie**: jeden katalog, wiele katalogów naraz (wskazujesz katalog nadrzędny —
  każdy podkatalog staje się osobnym audiobookiem), pojedyncze pliki (można zaznaczyć kilka).
- **Zapamiętywanie pozycji** — każdy audiobook wznawia się tam, gdzie skończyłeś
  (pozycja zapisywana co 5 sekund, przy pauzie i przy zamknięciu programu).
- **Metadane z internetu** — prawy klik → „Pobierz metadane": szuka w
  lubimyczytac.pl, upolujebooka.pl i Google Books; pobiera tytuł, autora, opis i okładkę.
- **Sortowanie**: ostatnio słuchane / tytuł / autor / ostatnio dodane + wyszukiwarka.
- **Czyszczenie**: całej biblioteki (przycisk na pasku) lub pojedynczego audiobooka
  (prawy klik → „Usuń z biblioteki"). Pliki audio na dysku nigdy nie są kasowane.
- Dodatki: prędkość odtwarzania 0,5–3,0×, przewijanie ±10/±30 s, wyłącznik czasowy
  (sleep timer), lista plików/rozdziałów z możliwością skoku, pasek postępu i %
  przy każdej książce, oznaczanie jako ukończony, „Odtwórz od początku",
  otwieranie lokalizacji na dysku, edycja tytułu/autora ręcznie.

Obsługiwane formaty: mp3, m4a, m4b, aac, wma, wav, flac, ogg, opus.

Dane biblioteki: `%APPDATA%\AudiobookPlayer\library.json` na Windows,
`~/.local/share/AudiobookPlayer/library.json` na Linuksie (+ okładki w `covers/`).
Usunięcie tego katalogu = całkowity reset programu.

## Kod źródłowy i przebudowa

- `src\main.py` — interfejs i odtwarzacz (PyQt6)
- `src\library.py` — model biblioteki i zapis JSON
- `src\metadata.py` — pobieranie metadanych (scrapery + Google Books API)

### Windows (środowisko w `.venvq`)

```powershell
.venvq\Scripts\pyinstaller.exe --noconfirm --onefile --windowed `
  --name AudiobookPlayer --icon src\icon.ico src\main.py
```

### Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pyinstaller
.venv/bin/pyinstaller --noconfirm AudiobookPlayer.spec
```

Wynik: `dist/AudiobookPlayer`. Integracja z pulpitem (menu aplikacji, ikona):

```bash
packaging/linux/install.sh
```

Instaluje binarkę do `~/.local/bin`, plik `.desktop` do `~/.local/share/applications`
i ikonę do `~/.local/share/icons` — bez `sudo`.

Wymagana biblioteka systemowa (Qt6 XCB, często brakuje na minimalnych
instalacjach Debiana/Ubuntu): `sudo apt install libxcb-cursor0`. Bez niej okno
się nie pokaże (błąd `xcb` platform plugin przy starcie na prawdziwym X11/Wayland
— w trybie `QT_QPA_PLATFORM=offscreen` do smoke testów nie jest potrzebna).

### AppImage (Linux, przenośny — jeden plik, bez instalacji)

```bash
# jednorazowo: pobierz appimagetool z github.com/AppImage/AppImageKit/releases
curl -L -o packaging/linux/tools/appimagetool-x86_64.AppImage \
  https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x packaging/linux/tools/appimagetool-x86_64.AppImage

packaging/linux/build-appimage.sh   # -> AudiobookPlayer-x86_64.AppImage
```

Wynikowy plik jest samodzielny (zawiera już `dist/AudiobookPlayer` + ikonę +
`.desktop`) — uruchamia się bezpośrednio (`./AudiobookPlayer-x86_64.AppImage`),
z FUSE lub bez (fallback: `--appimage-extract-and-run`). Wciąż wymaga
`libxcb-cursor0` w systemie (patrz wyżej) — AppImage nie pakuje bibliotek
systemowych spoza aplikacji.

Uwaga techniczna: użyto **PyQt6**, bo w PySide6 (6.7–6.11) backend multimediów
na maszynie deweloperskiej przerywał odtwarzanie po ~0,5 s (pozycja wracała do zera
przy obu backendach ffmpeg/windows); PyQt6 odtwarza poprawnie. `QtMultimedia`
jest już zawarty w wheelu `PyQt6` (nie ma osobnego pakietu do doinstalowania).
Na Linuksie odtwarzanie audio może zależeć od systemowego backendu
GStreamer/ffmpeg w zależności od dystrybucji — w razie problemów z dźwiękiem
to pierwsze miejsce do sprawdzenia.

## Instalator (Windows)

Skrypt Inno Setup: `installer.iss`. Budowanie:

```powershell
& "C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss
```

Wynik: `installer_out\AudiobookPlayer-Setup-<wersja>.exe`. Instalator nie wymaga
uprawnień administratora (instaluje dla bieżącego użytkownika), a przy odinstalowaniu
zostawia bibliotekę użytkownika w `%APPDATA%\AudiobookPlayer`.

## Licencja

GPL-3.0 (wymóg biblioteki PyQt6) — patrz `LICENSE`.
