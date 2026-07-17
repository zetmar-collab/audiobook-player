# Audiobook Player

Odtwarzacz audiobooków na Windows. Gotowy program: **`dist\AudiobookPlayer.exe`**
(pojedynczy plik, niczego nie trzeba instalować).

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

Dane biblioteki: `%APPDATA%\AudiobookPlayer\library.json` (+ okładki w `covers\`).
Usunięcie tego katalogu = całkowity reset programu.

## Kod źródłowy i przebudowa

- `src\main.py` — interfejs i odtwarzacz (PyQt6)
- `src\library.py` — model biblioteki i zapis JSON
- `src\metadata.py` — pobieranie metadanych (scrapery + Google Books API)

Przebudowa exe (środowisko w `.venvq`):

```powershell
.venvq\Scripts\pyinstaller.exe --noconfirm --onefile --windowed `
  --name AudiobookPlayer --icon src\icon.ico src\main.py
```

Uwaga techniczna: użyto **PyQt6**, bo w PySide6 (6.7–6.11) backend multimediów
na tej maszynie przerywał odtwarzanie po ~0,5 s (pozycja wracała do zera przy obu
backendach ffmpeg/windows); PyQt6 odtwarza poprawnie.

## Instalator

Skrypt Inno Setup: `installer.iss`. Budowanie:

```powershell
& "C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss
```

Wynik: `installer_out\AudiobookPlayer-Setup-<wersja>.exe`. Instalator nie wymaga
uprawnień administratora (instaluje dla bieżącego użytkownika), a przy odinstalowaniu
zostawia bibliotekę użytkownika w `%APPDATA%\AudiobookPlayer`.

## Licencja

GPL-3.0 (wymóg biblioteki PyQt6) — patrz `LICENSE`.
