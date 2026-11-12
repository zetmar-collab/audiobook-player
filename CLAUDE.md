# Audiobook Player — zasady projektu

Odtwarzacz audiobooków (PyQt6), Windows + Linux. Kod w `src\`, testy w `tests\`.

## Krytyczne — nie łamać

- **PyQt6, NIE PySide6.** QMediaPlayer w PySide6 (testowane 6.7.3 i 6.11.1) na tej
  maszynie przerywa odtwarzanie po ~0,5 s (pozycja wraca do 0, oba backendy
  ffmpeg/windows). Nie "migrować" ani nie "ujednolicać" do PySide6.
  Konsekwencja PyQt6: pełne ścieżki enumów (`Qt.AlignmentFlag.AlignCenter`),
  `pyqtSignal`, licencja GPL-3.0.
- **Windows: budować wyłącznie przez `.venvq`** (`.venvq\Scripts\python.exe`).
  Python ze Sklepu Windows ma za długie ścieżki site-packages — `pip install PyQt6`
  poza venv kończy się błędem OSError. Na Linuksie zwykły `venv` wystarczy.
- **Wersja tylko w `src\appinfo.py`.** Skrypty budowania, instalator (`/DMyAppVersion`)
  i manifest MSIX (`Identity Version`) czytają ją stamtąd. Nie edytować wersji ręcznie
  w `installer.iss`/manifeście.
- **Biblioteka nigdy nie jest nadpisywana pustą** (`library.py`): odczyt, który się nie
  udał, zostawia plik w spokoju (`.corrupt-<czas>` lub `save_disabled`). Nie wracać do
  `except Exception: books = []`.
- **Ścieżka danych jest platformowa** (`src\paths.py`): Windows → `%APPDATA%\AudiobookPlayer`,
  Linux/macOS → `$XDG_DATA_HOME/AudiobookPlayer`. Okładki są w `covers\` — tylko pliki z tego
  katalogu wolno kasować (`Library.remove`).
- **Wątki robocze nie dotykają widgetów.** Zwracają dane sygnałem (`QImage`, nie `QPixmap`);
  każdy wynik wyszukiwania niesie numer generacji (`SearchDialogBase`) — odpowiedź ze
  starszej generacji jest ignorowana. Nowe wątki startować przez `workers.start()`.
- **Każdy napis w UI przez `tr()`** (`i18n.py` to tabela par PL/EN; `tests\test_i18n_covers.py`
  pilnuje kluczy i znaczników `{...}`). Dane z metadanych wyświetlać w `plain_label`
  (`widgets.py`), nie w `QLabel` z AutoText.
- Nieobsłużony wyjątek w slocie PyQt6 **zabija proces** (`0xC0000409`) — dlatego `applog.install_excepthook()`
  w `main()`. Nie usuwać.

## Pułapki PyQt6 (każda już raz kosztowała błąd)

- `QPixmapCache.find(klucz)` **zwraca** pixmapę (nie ma parametru wyjściowego jak w C++).
- `QBuffer(QByteArray())` — tymczasowy `QByteArray` zostaje zwolniony → access violation. Trzymać w zmiennej.
- `Regex.Replace(tekst, wzorzec, zamiennik, 1)` w PowerShellu: `1` to `RegexOptions`, nie limit zamian.
  Używać instancji `Regex` i `.Replace(tekst, zamiennik, 1)` (patrz `build_msix.ps1`).
- `QMenu.exec()` blokuje w trybie offscreen — w testach podstawiać.

## Budowanie (Windows)

```powershell
.\build_exe.ps1               # dist\AudiobookPlayer.exe + dist\AudiobookPlayer-portable-<wersja>.zip (onedir)
.\build_installer.ps1         # installer_out\   (sam znajduje ISCC.exe)
.\build_msix.ps1              # msix_out\        (pakiet do MS Store, niepodpisany)
```

- `build_exe.ps1` używa `--specpath build` — bez tego PyInstaller nadpisuje `AudiobookPlayer.spec`
  w katalogu głównym wersją windowsową i kasuje logikę `sys.platform` dla Linuksa.
- `--icon`/`--add-data` muszą być **bezwzględne** (PyInstaller 6.21 + `--specpath` rozwiązuje
  względne względem `build\`).
- Nie wpisywać ścieżki do ISCC.exe na sztywno (raz `Program Files`, raz `%LOCALAPPDATA%\Programs`).
- `upx=False` w spec (UPX zwiększa fałszywe alarmy antywirusów). Do exe dołączane: ikona,
  `LICENSE`, `THIRD_PARTY_NOTICES.md` (GPL wymaga licencji w dystrybucji binarnej — także
  w instalatorze i MSIX).
- Smoke test zbudowanego exe: `AudiobookPlayer.exe --smoke-test` (kod 0; `ABP_SMOKE_MS` wydłuża
  okno życia). Zawsze z tymczasowym `APPDATA`, żeby nie dotykać prawdziwej biblioteki.

### Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pyinstaller --noconfirm AudiobookPlayer.spec   # -> dist/AudiobookPlayer
packaging/linux/install.sh                               # instalacja lokalna (~/.local)
```

Wymaga `libxcb-cursor0` systemowo. AppImage: `packaging/linux/build-appimage.sh`
(wymaga `appimagetool` w `packaging/linux/tools/`, ignorowane w git).
Zależności są **przypięte** w `requirements.txt` — podbijać świadomie (pytest + smoke test).
`PyQt6-Multimedia` nie istnieje na PyPI (QtMultimedia jest w wheelu PyQt6).

## Architektura

- `main.py` okno + skróty + drag&drop; `player_ctl.py` sterownik odtwarzania (bez widgetów);
  `dialogs.py`; `workers.py`; `widgets.py`; `covers.py` (okładki QImage, cache miniatur);
  `library.py`/`models.py`/`scanner.py`/`tags.py` (dane); `metadata.py` (serwisy);
  `singleinstance.py`; `winmedia.py` (globalne klawisze multimedialne, RegisterHotKey);
  `applog.py`; `theme.py`; `i18n.py`; `paths.py`; `appinfo.py`.
- `library.json`: `schema` + `books` + `settings`. Pola książki mają wartości domyślne
  (`models.BOOK_DEFAULTS`) — dodanie pola nie wymaga migracji.
- Źródła metadanych (`metadata.py`), wszystkie równolegle, twardy limit 25 s, cache 10 min, limit
  tempa na host, **uczciwy User-Agent** (sprawdzone: serwisy go akceptują):
  lubimyczytac.pl (`div.book-card`), upolujebooka.pl (`/szukaj,{fraza}.html` + JSON-LD), Audible,
  Apple Books (iTunes Search), Google Books (**bez `langRestrict`**, opcjonalny klucz API; bez klucza
  bywa 429), Open Library (z sieci autora bywa nieosiągalne). `search_all` zwraca `SearchOutcome`
  z błędami źródeł (kody: rate_limit/http/timeout/offline/bad_response/error).
- Obrazy z sieci: `fetch_image_bytes` (limit 8 MB, sprawdzenie sygnatury) → `covers.save_cover_bytes`
  (JPEG ≤1000 px). Nigdy nie zapisywać surowej odpowiedzi serwera.
- Zakładki, rozdziały (`chapters` z M4B/CHAP), prędkość na książkę (`speed`), statystyki
  (`listened_ms`, `settings["stats"]`) są polami książki/ustawień.

## Testowanie

```powershell
.venvq\Scripts\python -m pyflakes src tests
.venvq\Scripts\python -m pytest          # 143 testy, ~30 s, tryb offscreen
```

- Testy z markerem `audio` (postęp odtwarzania na prawdziwym QMediaPlayer) pomijają się bez
  urządzenia wyjściowego (`ABP_TEST_NO_AUDIO=1` symuluje CI).
- Po naprawie błędu napisać test, który bez naprawy **pada** (robiłem testy mutacyjne:
  celowo psuję kod i sprawdzam, czy testy to wykryją). Nie pisać asercji z `or True`.
- Dowolny test uruchamiający aplikację: tymczasowy `APPDATA`.
- CI: `.github/workflows/ci.yml` (testy Windows + Ubuntu; przy tagu `v*` build wydania + smoke test).

## Publikacja

GitHub: `zetmar-collab/audiobook-player` (przez `gh`). Release Windows = exe jednoplikowy +
**archiwum przenośne zip (onedir, zalecane)** + instalator + pakiet MSIX. Release Linux = binarka + AppImage.
Skill `/release X.Y.Z` prowadzi cały proces. Dane użytkownika w katalogu danych platformy — nigdy nie
kasować przy aktualizacjach/odinstalowaniu.

Microsoft Store (Partner Center) — tożsamość pakietu, nie zmieniać:
`Name=MarekZettel-zetmar.PlayerAudiobook`,
`Publisher=CN=15A53D32-C868-48EE-B700-5DBB5449CA1B`,
`PublisherDisplayName=Marek Zettel - zetmar`.
Pakiet wysyłamy **niepodpisany** — Store podpisuje go sam.

Dane zgłoszenia (Partner Center):
- **Opublikowana w Store** (od 1.2.0; 1.3.0 przeszła certyfikację):
  https://apps.microsoft.com/store/detail/9PJRBRTLMP88 — kolejne wersje = „Start update"
  w Partner Center (sekcje bez zmian zostają „Unchanged"), podmiana pakietu, notatki „What's new"
  w obu językach (pl-PL, en-US), „Submit for certification".
- **Plik .msix (~50 MB) trzeba wgrać ręcznie** — narzędzie `file_upload` przeglądarki ma limit 10 MB.
- Product ID: `9PJRBRTLMP88`
- **Zarezerwowana nazwa to „Player Audiobook"** — musi być dokładnie w
  `Package/Properties/DisplayName`, inaczej walidacja odrzuca pakiet.
  Nazwa widoczna dla użytkownika (`uap:VisualElements/DisplayName`) to „Audiobook Player".
- Cena: 0 zł (PLN), 240 rynków, publiczna. Kategoria: Books + reference, dodatkowa: Music.
- Privacy policy URL: `PRIVACY.md` z repo (wymagane).
- Zrzuty do sklepu: `msix\store_screenshots\` (1920×1080; Store wymaga min. 1366×768).
- Opis w pl-PL i en-US — obie wersje trzeba wypełnić, inaczej Store listings zostaje Incomplete.

Test lokalny MSIX: `.\sign_msix.ps1 -Install` podpisuje **kopię** (`*-test-signed.msix`)
i instaluje ją. Certyfikat testowy o tym samym `Subject` (`CN=15A53D32-…`) jest w
`Cert:\CurrentUser\My` (wspólny z projektem „Imieniny i Rocznice") i zaufany w
`LocalMachine\TrustedPeople`. Nie tworzyć drugiego.

Pakiet MSIX **nie wirtualizuje** `%APPDATA%` — wersja ze Store, instalowana i przenośna
dzielą `library.json` (dlatego jest blokada jednej instancji).
