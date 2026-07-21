---
name: release
description: Buduje exe + instalator Inno Setup i publikuje release na GitHub. Argument: numer wersji (np. 1.1.0). Tylko na wyraźne polecenie użytkownika.
disable-model-invocation: true
---

# Release Audiobook Playera

Argument: numer nowej wersji w formacie X.Y.Z (np. `/release 1.1.0`).
Bez argumentu: zaproponuj wersję (patch +1 względem `MyAppVersion` w `installer.iss`) i poproś o potwierdzenie.

## Kroki (wykonuj po kolei, przerwij przy błędzie)

1. **Czystość repo**: `git status` — jeśli są niezacommitowane zmiany w `src\` lub
   `installer.iss`, zapytaj użytkownika, czy je dołączyć do release'u.

2. **Podbij wersję**: w `installer.iss` ustaw `#define MyAppVersion "X.Y.Z"`.

3. **Build exe** (zawsze przez .venvq):
   ```powershell
   .venvq\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed `
     --name AudiobookPlayer --icon src\icon.ico src\main.py
   ```

4. **Weryfikacja exe**: uruchom `dist\AudiobookPlayer.exe`, odczekaj ~8 s,
   sprawdź `Get-Process AudiobookPlayer` (proces żyje + MainWindowTitle
   "Audiobook Player"), potem `Stop-Process`. Jeśli proces nie żyje — przerwij
   i diagnozuj.

5. **Build instalatora**:
   ```powershell
   & "C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss
   ```
   Wynik: `installer_out\AudiobookPlayer-Setup-X.Y.Z.exe` (sprawdź, że istnieje).

6. **Commit + tag**: commit zmian (minimum `installer.iss`) z opisem zmian od
   ostatniego taga (`git log <ostatni-tag>..HEAD --oneline`), potem
   `git tag vX.Y.Z` i `git push origin main --tags`.

7. **Release na GitHub**:
   ```powershell
   gh release create vX.Y.Z `
     "dist\AudiobookPlayer.exe#AudiobookPlayer.exe (przenośny, bez instalacji)" `
     "installer_out\AudiobookPlayer-Setup-X.Y.Z.exe#Instalator Windows" `
     --title "Audiobook Player X.Y.Z" --notes "<notatki>"
   ```
   Notatki po polsku: sekcja "Do pobrania" (instalator zalecany + przenośny exe)
   i lista zmian od poprzedniej wersji na podstawie git log.

8. **Weryfikacja**: `gh release view vX.Y.Z --json assets` — muszą być 2 pliki
   (~50 MB każdy). Podaj użytkownikowi link do release'u.
