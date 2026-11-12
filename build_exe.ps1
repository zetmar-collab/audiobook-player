# Buduje pliki wykonywalne dla Windows:
#   dist\AudiobookPlayer.exe                        - wersja jednoplikowa (onefile)
#   dist\AudiobookPlayer-portable-<wersja>.zip      - wersja przenośna (onedir, zalecana)
#
#   .\build_exe.ps1                  # obie
#   .\build_exe.ps1 -OnefileOnly     # tylko exe
#
# Wersja pochodzi z src\appinfo.py. Skrypt używa .venvq oraz --specpath build (inaczej
# PyInstaller nadpisałby wspólny AudiobookPlayer.spec) i ścieżek bezwzględnych
# (PyInstaller 6.21 rozwiązuje względne względem katalogu spec).
param([switch]$OnefileOnly)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venvq\Scripts\python.exe"
$pyi = Join-Path $root ".venvq\Scripts\pyinstaller.exe"
if (-not (Test-Path $py)) { throw "Brak środowiska .venvq — zobacz CLAUDE.md (Budowanie)" }

$version = (& $py -c "import sys; sys.path.insert(0, r'$root\src'); import appinfo; print(appinfo.APP_VERSION)").Trim()
Write-Host "Wersja: $version"

$icon = (Resolve-Path (Join-Path $root "src\icon.ico")).Path
$license = (Resolve-Path (Join-Path $root "LICENSE")).Path
$notices = (Resolve-Path (Join-Path $root "THIRD_PARTY_NOTICES.md")).Path
$main = (Resolve-Path (Join-Path $root "src\main.py")).Path
$common = @("--noconfirm", "--clean", "--windowed", "--name", "AudiobookPlayer",
            "--icon", $icon, "--add-data", "$icon;.", "--add-data", "$license;.",
            "--add-data", "$notices;.", "--specpath", (Join-Path $root "build"))

# --- onefile
Write-Host "`n[1/2] Buduję AudiobookPlayer.exe (onefile)..."
& $pyi @common --onefile --distpath (Join-Path $root "dist") `
    --workpath (Join-Path $root "build\onefile") $main
if ($LASTEXITCODE -ne 0) { throw "Build onefile nie powiódł się" }

if ($OnefileOnly) { return }

# --- onedir -> zip
Write-Host "`n[2/2] Buduję wersję przenośną (onedir) i pakuję do zip..."
$portableDist = Join-Path $root "build\portable_dist"
& $pyi @common --onedir --distpath $portableDist `
    --workpath (Join-Path $root "build\portable_work") $main
if ($LASTEXITCODE -ne 0) { throw "Build onedir nie powiódł się" }

$folder = Join-Path $portableDist "AudiobookPlayer"
Copy-Item -Force $license (Join-Path $folder "LICENSE")
Copy-Item -Force $notices (Join-Path $folder "THIRD_PARTY_NOTICES.md")
$zip = Join-Path $root "dist\AudiobookPlayer-portable-$version.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $folder -DestinationPath $zip -CompressionLevel Optimal
Write-Host "`nGotowe:" -ForegroundColor Green
Get-Item (Join-Path $root "dist\AudiobookPlayer.exe"), $zip |
    Select-Object Name, @{n = 'MB'; e = { [math]::Round($_.Length / 1MB, 1) } } | Format-Table
