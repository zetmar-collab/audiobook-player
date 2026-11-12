---
name: release
description: Testuje, buduje exe + archiwum przenośne + instalator + MSIX i publikuje release na GitHub. Argument: numer wersji (np. 1.5.0). Tylko na wyraźne polecenie użytkownika.
disable-model-invocation: true
---

# Release Audiobook Playera

Argument: numer nowej wersji w formacie X.Y.Z (np. `/release 1.5.0`).
Bez argumentu: zaproponuj wersję (patch +1 względem `APP_VERSION` w `src\appinfo.py`) i poproś o potwierdzenie.

## Kroki (wykonuj po kolei, przerwij przy błędzie)

1. **Czystość repo**: `git status` — jeśli są niezacommitowane zmiany w `src\`, zapytaj
   użytkownika, czy je dołączyć do release'u.

2. **Testy** (muszą przejść przed jakimkolwiek buildem):
   ```powershell
   .venvq\Scripts\python -m pyflakes src tests
   .venvq\Scripts\python -m pytest
   ```

3. **Podbij wersję w JEDNYM miejscu**: `APP_VERSION = "X.Y.Z"` w `src\appinfo.py`.
   Instalator (`/DMyAppVersion`) i manifest MSIX (`Identity Version`) synchronizują się
   same przy budowaniu — nie edytować ich ręcznie.

4. **Budowanie** (zawsze przez .venvq; skrypty używają `--specpath build` i ścieżek
   bezwzględnych — nie wpisuj komend PyInstallera ręcznie):
   ```powershell
   .\build_exe.ps1          # dist\AudiobookPlayer.exe + dist\AudiobookPlayer-portable-X.Y.Z.zip
   .\build_installer.ps1    # installer_out\AudiobookPlayer-Setup-X.Y.Z.exe
   .\build_msix.ps1         # msix_out\AudiobookPlayer-X.Y.Z.msix
   ```
   Sprawdź, że `git status AudiobookPlayer.spec` jest czysty (spec dla Linuksa nietknięty).

5. **Smoke test zbudowanych plików** (z tymczasowym `APPDATA`, żeby nie dotykać biblioteki
   użytkownika): `AudiobookPlayer.exe --smoke-test` oraz ten sam test dla exe z rozpakowanego
   archiwum przenośnego — oba muszą zwrócić kod 0. Sprawdź też w manifeście wewnątrz `.msix`:
   `Identity.Version == X.Y.Z.0`, `MinVersion == 10.0.17763.0`, `DisplayName == Player Audiobook`.

6. **Commit + tag**: commit zmian z opisem zmian od ostatniego taga
   (`git log <ostatni-tag>..HEAD --oneline`), potem `git tag vX.Y.Z` i
   `git push origin main --tags`. CI zbuduje wydanie i zrobi smoke test (tag musi się
   zgadzać z `appinfo.py`).

7. **Release na GitHub**:
   ```powershell
   gh release create vX.Y.Z `
     "dist\AudiobookPlayer-portable-X.Y.Z.zip#Wersja przenośna (zalecana — rozpakuj i uruchom)" `
     "installer_out\AudiobookPlayer-Setup-X.Y.Z.exe#Instalator Windows" `
     "dist\AudiobookPlayer.exe#AudiobookPlayer.exe (pojedynczy plik)" `
     "msix_out\AudiobookPlayer-X.Y.Z.msix#Pakiet MSIX (Microsoft Store)" `
     --title "Audiobook Player X.Y.Z" --notes-file <plik z notatkami>
   ```
   Notatki po polsku: sekcja „Do pobrania" i lista zmian na podstawie git log; na górze link
   do Store. Użyj `--notes-file` (polskie znaki i nowe linie w `--notes` psują się w PowerShellu).

8. **Weryfikacja**: `gh release view vX.Y.Z --json assets` — muszą być 4 pliki (~50 MB każdy).
   Podaj użytkownikowi link do release'u.

9. **Microsoft Store** (osobny krok, tylko gdy użytkownik chce): Partner Center →
   Application overview → „Start update" → Packages: **wgraj `.msix` ręcznie** (narzędzie
   `file_upload` przeglądarki ma limit 10 MB, plik ma ~50 MB) → Store listings: „What's new"
   w pl-PL i en-US → „Submit for certification".
