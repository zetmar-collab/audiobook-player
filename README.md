# Audiobook Player

Odtwarzacz audiobooków — Windows i Linux. Gotowy program: **`dist\AudiobookPlayer.exe`**
na Windows / **`dist/AudiobookPlayer`** na Linuksie (pojedynczy plik, niczego nie
trzeba instalować).

## Funkcje

- **Język polski i angielski** — Ustawienia → Język (przy pierwszym uruchomieniu
  wykrywany z systemu).
- **Motyw jasny, ciemny i systemowy** — Ustawienia → Motyw.
- **Biblioteka** — audiobooki jako katalogi (wiele plików = rozdziały) i pojedyncze pliki.
- **Dodawanie**: jeden katalog, wiele katalogów naraz (wskazujesz katalog nadrzędny —
  każdy podkatalog staje się osobnym audiobookiem), pojedyncze pliki (można zaznaczyć kilka).
- **Zapamiętywanie pozycji** — każdy audiobook wznawia się tam, gdzie skończyłeś
  (pozycja zapisywana co 5 sekund, przy pauzie i przy zamknięciu programu).
- **Metadane z internetu** — prawy klik → „Pobierz metadane": szuka równolegle
  w serwisach polskich (lubimyczytac.pl, upolujebooka.pl) i zagranicznych
  (Audible, Apple Books, Google Books, Open Library); pobiera tytuł, autora,
  opis i okładkę. Kolejność źródeł zależy od języka interfejsu.
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
- `src\i18n.py` — tłumaczenia PL/EN
- `src\theme.py` — motyw jasny/ciemny
- `src\library.py` — model biblioteki i zapis JSON
- `src\metadata.py` — pobieranie metadanych (serwisy PL + zagraniczne API)
- `msix\` — manifest i grafiki pakietu Microsoft Store

### Windows (środowisko w `.venvq`)

```powershell
.venvq\Scripts\pyinstaller.exe --noconfirm --onefile --windowed `
  --name AudiobookPlayer --icon src\icon.ico --add-data "src\icon.ico;." `
  --specpath build src\main.py
```

`--specpath build` jest ważne: bez niego PyInstaller nadpisuje wspólny
`AudiobookPlayer.spec` wersją windowsową i psuje build linuksowy.

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
.\build_installer.ps1
```

Wynik: `installer_out\AudiobookPlayer-Setup-<wersja>.exe`. Instalator nie wymaga
uprawnień administratora (instaluje dla bieżącego użytkownika), a przy odinstalowaniu
zostawia bibliotekę użytkownika w `%APPDATA%\AudiobookPlayer`.

Wymaga Inno Setup: `winget install --id JRSoftware.InnoSetup.7`.

## Pakiet MSIX (Microsoft Store)

```powershell
.\build_msix.ps1                # albo: .\build_msix.ps1 -Version 1.2.0
```

Wynik: `msix_out\AudiobookPlayer-<wersja>.msix` — **niepodpisany**, bo pakiet
podpisuje sam Store przy publikacji w Partner Center. Skrypt buduje aplikację
w trybie katalogowym (szybszy start niż onefile), generuje kafelki z `msix\Assets`
i pakuje całość przez `makeappx.exe` z Windows SDK.

### Wersja testowa (do wypróbowania na własnym komputerze)

Pakiet wysyłany do Store jest niepodpisany, więc **nie da się go zainstalować lokalnie**.
Do testów podpisz kopię certyfikatem testowym:

```powershell
.\sign_msix.ps1 -Install
```

Skrypt bierze najnowszy pakiet z `msix_out\`, podpisuje **kopię** jako
`AudiobookPlayer-<wersja>-test-signed.msix` (oryginał dla Store zostaje nietknięty),
weryfikuje podpis i instaluje aplikację. Potem jest w menu Start jako „Audiobook Player".

Certyfikat musi mieć `Subject` równy `Publisher` z manifestu — skrypt szuka takiego
w `Cert:\CurrentUser\My`, a gdy go nie ma, tworzy nowy samopodpisany i eksportuje
część publiczną do `msix_out\AudiobookPlayer-test.cer`. Nowy certyfikat trzeba raz
oznaczyć jako zaufany (wymaga uprawnień administratora):

```powershell
Import-Certificate -FilePath .\msix_out\AudiobookPlayer-test.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
```

Odinstalowanie wersji testowej:

```powershell
Get-AppxPackage *PlayerAudiobook* | Remove-AppxPackage
```

Wersja z pakietu MSIX korzysta z **tej samej** biblioteki co wersja instalowana
i przenośna (`%APPDATA%\AudiobookPlayer`) — dane nie są wirtualizowane, więc
audiobooki i postępy odsłuchu są wspólne.

### Tożsamość pakietu

Tożsamość (`msix\AppxManifest.xml`) musi zgadzać się z rezerwacją w Partner Center:

| Pole | Wartość |
|---|---|
| Package/Identity/Name | `MarekZettel-zetmar.PlayerAudiobook` |
| Package/Identity/Publisher | `CN=15A53D32-C868-48EE-B700-5DBB5449CA1B` |
| Package/Properties/PublisherDisplayName | `Marek Zettel - zetmar` |

## Licencja

GPL-3.0 (wymóg biblioteki PyQt6) — patrz `LICENSE`.
