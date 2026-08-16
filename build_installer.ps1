# Buduje instalator Windows (Inno Setup) z pliku installer.iss.
#
#   .\build_installer.ps1
#
# Wynik: installer_out\AudiobookPlayer-Setup-<wersja>.exe
# Skrypt sam znajduje ISCC.exe — Inno Setup instaluje się raz w "Program Files",
# raz w "%LOCALAPPDATA%\Programs" (zależnie od trybu instalacji), więc ścieżki
# nie wolno wpisywać na sztywno.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$candidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iscc = $cmd.Source }
}
if (-not $iscc) {
    throw "Nie znaleziono ISCC.exe. Zainstaluj Inno Setup: winget install --id JRSoftware.InnoSetup.7"
}

Write-Host "Używam: $iscc"
& $iscc (Join-Path $root "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Kompilacja instalatora nie powiodła się" }

Get-ChildItem (Join-Path $root "installer_out\*.exe") |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
    ForEach-Object { Write-Host "`nGotowe: $($_.FullName)" -ForegroundColor Green }
