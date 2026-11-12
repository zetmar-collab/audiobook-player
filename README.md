# Audiobook Player

[![Pobierz z Microsoft Store](https://get.microsoft.com/images/pl%20light.svg)](https://apps.microsoft.com/store/detail/9PJRBRTLMP88?cid=DevShareMCLPCS)

Odtwarzacz audiobooków — Windows i Linux. Darmowy, bez kont, reklam i telemetrii.

**Windows:** najprościej [zainstalować z Microsoft Store](https://apps.microsoft.com/store/detail/9PJRBRTLMP88?cid=DevShareMCLPCS)
(aktualizacje automatyczne). Alternatywnie z [sekcji Releases](https://github.com/zetmar-collab/audiobook-player/releases):
instalator, **archiwum przenośne `.zip`** (rozpakuj i uruchom — startuje szybciej niż pojedynczy exe
i rzadziej budzi alarmy antywirusa) albo pojedynczy `AudiobookPlayer.exe`.

**Linux:** binarka lub AppImage z [sekcji Releases](https://github.com/zetmar-collab/audiobook-player/releases),
albo budowanie ze źródeł (instrukcja niżej).

## Funkcje

**Biblioteka**
- Audiobooki jako katalogi (wiele plików = rozdziały) i pojedyncze pliki; podkatalogi `CD1`/`CD2`/`Part 1`
  składają się w jedną książkę, w kolejności „naturalnej" po całej ścieżce.
- **Dodawanie:** „Dodaj katalog" (zawsze jedna książka), „Dodaj wiele katalogów" (każdy podkatalog to osobna
  książka), pojedyncze pliki, **przeciągnięcie plików i katalogów na okno**, „Otwórz za pomocą…" z Eksploratora.
  Skanowanie (długości, tagi) odbywa się w tle — okno się nie zawiesza.
- **Tagi z plików:** tytuł, autor i **okładka osadzona** (ID3/MP4/FLAC) są odczytywane automatycznie,
  jeśli nazwa katalogu nie ma postaci „Autor - Tytuł".
- **Rozdziały z plików M4B i MP3 (CHAP)** — jeden duży plik ma pełną nawigację po rozdziałach.
- Sortowanie (ostatnio słuchane / tytuł / autor / ostatnio dodane) zgodne z polskim alfabetem,
  filtry (wszystkie / w trakcie / nieodsłuchane / ukończone), grupowanie po autorze,
  wyszukiwarka niewrażliwa na wielkość liter i polskie znaki („zolte" znajdzie „Żółte").

**Odtwarzanie**
- Zapamiętywanie pozycji (co 5 s, przy pauzie i zamknięciu), **czas całej książki** — przebyty,
  całkowity, pozostały i pozostały przy bieżącej prędkości.
- Prędkość 0,5–3,0× **zapamiętywana osobno dla każdej książki**; przewijanie ±10/±30 s;
  **auto-cofnięcie po dłuższej przerwie** (3–30 s zależnie od długości przerwy).
- **Zakładki** (Ctrl+B) z nazwą, listą, zmianą nazwy i skokiem.
- **Wyłącznik czasowy** 15–90 min albo „do końca pliku", z płynnym wyciszaniem i odliczaniem.
- Brakujący plik (odłączony dysk) nie psuje postępu — program pomija go i informuje.
- **Skróty klawiszowe** (Pomoc → Skróty) i **globalne klawisze multimedialne** (Windows) —
  słuchawki Bluetooth sterują programem. Klawisze są przejmowane tylko, gdy książka jest załadowana.

**Metadane i okładki**
- Prawy klik → „Pobierz metadane": równolegle lubimyczytac.pl, upolujebooka.pl, Audible, Apple Books,
  Google Books i Open Library; tytuł, autor, opis, okładka. Gdy serwis jest niedostępny, program
  mówi który i dlaczego (limit zapytań, brak połączenia) zamiast „brak wyników".
- „Pobierz okładkę": wizualny wybór z miniaturkami albo własny obraz z dysku. Okładki są
  normalizowane do JPEG ≤1000 px.
- „Uzupełnij metadane brakujących książek…": wsadowe wyszukiwanie z **zatwierdzaniem propozycji**
  przed zapisem.
- Opcjonalny klucz API Google Books (Ustawienia) zwiększa limit zapytań.

**Dane i bezpieczeństwo**
- Biblioteka nigdy nie jest nadpisywana pustą, gdy nie da się jej wczytać: uszkodzony plik trafia do
  `library.json.corrupt-<czas>`, a raz dziennie powstaje kopia w `backups/` (ostatnie 7).
- Kopia zapasowa na życzenie: Biblioteka → „Zapisz kopię…" / „Przywróć z kopii…" (zip z biblioteką
  i okładkami).
- Jedna instancja programu: drugie uruchomienie przekazuje pliki do działającego okna.
- Nieoczekiwany błąd nie zamyka programu — jest zapisywany w `error.log` i pokazywany w oknie.
- Statystyki słuchania (dziś, 7 dni, najczęściej słuchane) liczone wyłącznie lokalnie.
- Interfejs po polsku i angielsku, motyw jasny / ciemny / systemowy.

Obsługiwane formaty: mp3, m4a, m4b, aac, wma, wav, flac, ogg, opus.

Dane biblioteki: `%APPDATA%\AudiobookPlayer\` na Windows, `~/.local/share/AudiobookPlayer/` na Linuksie
(`library.json`, `covers\`, `backups\`, `error.log`). Usunięcie tego katalogu = całkowity reset programu.
Prywatność: [PRIVACY.md](PRIVACY.md).

## Rozwój

Moduły w `src\`:

| Plik | Rola |
|---|---|
| `main.py` | okno główne, menu, skróty, drag&drop, punkt startowy |
| `player_ctl.py` | sterownik odtwarzania (QMediaPlayer, wznawianie, zakładki, usypianie, statystyki) — bez widgetów |
| `dialogs.py` | metadane, okładki, zakładki, wsadowe uzupełnianie, statystyki |
| `workers.py` | wątki robocze; numery generacji zapytań, bezpieczne zamykanie |
| `library.py`, `models.py`, `scanner.py`, `tags.py` | dane: zapis/odczyt, sortowanie, skanowanie, tagi mutagen |
| `metadata.py` | serwisy zewnętrzne (równolegle, z cache, limitem tempa, kodami błędów) |
| `covers.py`, `widgets.py`, `theme.py`, `i18n.py` | obrazy i cache miniatur, widgety, motyw, tłumaczenia |
| `singleinstance.py`, `winmedia.py`, `applog.py`, `paths.py`, `appinfo.py` | instancja, klawisze multimedialne, logi, ścieżki, **wersja** |

**Wersję zmienia się wyłącznie w `src\appinfo.py`** — skrypty budowania, instalator i manifest MSIX
czytają ją stamtąd.

### Środowisko i testy

```powershell
python -m venv .venvq
.venvq\Scripts\pip install -r requirements-dev.txt     # wersje przypięte
.venvq\Scripts\python -m pyflakes src tests
.venvq\Scripts\python -m pytest                        # 143 testy, ~30 s (tryb offscreen)
```

Testy z markerem `audio` (postęp odtwarzania) pomijają się same, gdy brak urządzenia wyjściowego
(np. runnery CI); symulacja lokalna: `$env:ABP_TEST_NO_AUDIO=1`. CI (`.github/workflows/ci.yml`)
uruchamia testy na Windows i Ubuntu, a przy tagu `v*` buduje wydanie i robi smoke test exe.
Test uruchomienia zbudowanej aplikacji: `AudiobookPlayer.exe --smoke-test` (kod 0).

### Budowanie — Windows (środowisko `.venvq`)

```powershell
.\build_exe.ps1               # dist\AudiobookPlayer.exe + dist\AudiobookPlayer-portable-<wersja>.zip
.\build_installer.ps1         # installer_out\AudiobookPlayer-Setup-<wersja>.exe
.\build_msix.ps1              # msix_out\AudiobookPlayer-<wersja>.msix (Microsoft Store)
```

Skrypt `build_exe.ps1` używa `--specpath build` (bez tego PyInstaller nadpisuje wspólny
`AudiobookPlayer.spec` wersją windowsową i psuje build linuksowy) oraz ścieżek bezwzględnych
(PyInstaller 6.21 rozwiązuje względne względem `build\`, nie katalogu roboczego).

### Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
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

Skrypt Inno Setup: `installer.iss` (wersję podaje `build_installer.ps1` z `appinfo.py`).
Instalator nie wymaga uprawnień administratora (instaluje dla bieżącego użytkownika),
dopisuje program do listy „Otwórz za pomocą" dla plików audio (bez przejmowania domyślnych
skojarzeń), dołącza `LICENSE` i `THIRD_PARTY_NOTICES.md`, a przy odinstalowaniu zostawia
bibliotekę użytkownika w `%APPDATA%\AudiobookPlayer`.

Wymaga Inno Setup: `winget install --id JRSoftware.InnoSetup.7`.

## Pakiet MSIX (Microsoft Store)

Wynik: `msix_out\AudiobookPlayer-<wersja>.msix` — **niepodpisany**, bo pakiet
podpisuje sam Store przy publikacji w Partner Center. Skrypt buduje aplikację
w trybie katalogowym (szybszy start niż onefile), generuje kafelki z `msix\Assets`,
synchronizuje wersję manifestu z `appinfo.py` i pakuje całość przez `makeappx.exe`
z Windows SDK. Manifest deklaruje skojarzenia plików audio („Otwórz za pomocą").

**Wysyłka do Partner Center:** plik ma ~50 MB, więc przeglądarkowe narzędzia automatyzacji
(limit 10 MB) go nie wgrają — przeciągnij `.msix` na pole „Packages" ręcznie.

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

GPL-3.0 (wymóg biblioteki PyQt6) — patrz [LICENSE](LICENSE). Licencje używanych bibliotek:
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) (dostępne też w programie: Pomoc → Licencje i uznania).
