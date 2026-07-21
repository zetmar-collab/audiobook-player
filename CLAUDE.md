# Audiobook Player — zasady projektu

Odtwarzacz audiobooków na Windows (PyQt6). Kod w `src\`, gotowy exe w `dist\`.

## Krytyczne — nie łamać

- **PyQt6, NIE PySide6.** QMediaPlayer w PySide6 (testowane 6.7.3 i 6.11.1) na tej
  maszynie przerywa odtwarzanie po ~0,5 s (pozycja wraca do 0, oba backendy
  ffmpeg/windows). Nie "migrować" ani nie "ujednolicać" do PySide6.
  Konsekwencja PyQt6: pełne ścieżki enumów (`Qt.AlignmentFlag.AlignCenter`),
  `pyqtSignal` zamiast `Signal`, licencja GPL-3.0.
- **Budować wyłącznie przez `.venvq`** (`.venvq\Scripts\python.exe`,
  `.venvq\Scripts\pyinstaller.exe`). Python ze Sklepu Windows ma za długie ścieżki
  site-packages — `pip install PySide6/PyQt6` poza venv kończy się błędem OSError.

## Budowanie

```powershell
.venvq\Scripts\pyinstaller.exe --noconfirm --onefile --windowed `
  --name AudiobookPlayer --icon src\icon.ico src\main.py
& "C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss   # -> installer_out\
```

Wersja instalatora: `#define MyAppVersion` w `installer.iss`.

## Architektura

- `src\main.py` — całe UI + odtwarzacz (QMediaPlayer); UI po polsku
- `src\library.py` — model biblioteki, zapis JSON do `%APPDATA%\AudiobookPlayer\library.json`
- `src\metadata.py` — scrapery: lubimyczytac.pl (selektory `div.book-card`),
  upolujebooka.pl (GET `/szukaj,{fraza}.html`, szczegóły z JSON-LD schema.org/Book),
  Google Books API (bez klucza — bywa limit 429). Wszystkie best-effort, błędy → pusta lista.

## Testowanie

Brak automatycznych testów. Smoke test: uruchomić exe, dodać katalog z audio,
odtworzyć, zamknąć, otworzyć ponownie — pozycja ma być zapamiętana.
Uwaga: w sesjach Claude Code odtwarzanie QMediaPlayer może nie postępować mimo
stanu Playing — testować pozycję z zapasem czasu.

## Publikacja

GitHub: `zetmar-collab/audiobook-player` (przez `gh`). Release = exe przenośny
+ instalator z `installer_out\`. Dane użytkownika w `%APPDATA%\AudiobookPlayer\`
— nigdy nie kasować przy aktualizacjach/odinstalowaniu.
