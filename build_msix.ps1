# Buduje pakiet MSIX dla Microsoft Store.
#
#   .\build_msix.ps1              # wersja z AppxManifest.xml
#   .\build_msix.ps1 -Version 1.2.0
#
# Wynik: msix_out\AudiobookPlayer-<wersja>.msix (NIEPODPISANY — Store podpisuje
# pakiet sam przy publikacji; do testu lokalnego trzeba podpisać własnym certyfikatem).
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".venvq"
$layout = Join-Path $root "build\msix_layout"
$outDir = Join-Path $root "msix_out"

# --- 1. Wersja: z parametru albo z manifestu
$manifestPath = Join-Path $root "msix\AppxManifest.xml"
[xml]$manifest = Get-Content $manifestPath
if ($Version) {
    $manifest.Package.Identity.Version = "$Version.0"
    $manifest.Save($manifestPath)
    Write-Host "Ustawiono wersję pakietu na $Version.0"
}
$pkgVersion = $manifest.Package.Identity.Version
$shortVersion = ($pkgVersion -split '\.')[0..2] -join '.'

# --- 2. Grafiki kafelków
Write-Host "`n[1/4] Generuję grafiki kafelków..."
& (Join-Path $venv "Scripts\python.exe") (Join-Path $root "msix\make_assets.py")
if ($LASTEXITCODE -ne 0) { throw "Nie udało się wygenerować grafik" }

# --- 3. Build aplikacji w trybie katalogowym (onedir — zalecany dla Store:
#        szybszy start i brak rozpakowywania do %TEMP% przy każdym uruchomieniu)
Write-Host "`n[2/4] Buduję aplikację (PyInstaller, onedir)..."
& (Join-Path $venv "Scripts\pyinstaller.exe") --noconfirm --clean --windowed `
    --name AudiobookPlayer --icon (Join-Path $root "src\icon.ico") `
    --add-data "$(Join-Path $root 'src\icon.ico');." `
    --distpath (Join-Path $root "build\msix_dist") `
    --workpath (Join-Path $root "build\msix_work") `
    --specpath (Join-Path $root "build") `
    (Join-Path $root "src\main.py")
if ($LASTEXITCODE -ne 0) { throw "Build PyInstaller nie powiódł się" }

# --- 4. Układ pakietu: pliki aplikacji + manifest + Assets
Write-Host "`n[3/4] Składam zawartość pakietu..."
if (Test-Path $layout) { Remove-Item -Recurse -Force $layout }
New-Item -ItemType Directory -Force -Path $layout | Out-Null
Copy-Item -Recurse -Force (Join-Path $root "build\msix_dist\AudiobookPlayer\*") $layout
Copy-Item -Force $manifestPath (Join-Path $layout "AppxManifest.xml")
Copy-Item -Recurse -Force (Join-Path $root "msix\Assets") (Join-Path $layout "Assets")

$exe = Join-Path $layout "AudiobookPlayer.exe"
if (-not (Test-Path $exe)) { throw "Brak AudiobookPlayer.exe w układzie pakietu" }

# --- 5. makeappx z Windows SDK
Write-Host "`n[4/4] Pakuję do MSIX..."
$makeappx = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe" `
    -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) { throw "Nie znaleziono makeappx.exe — zainstaluj Windows SDK" }

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$msix = Join-Path $outDir "AudiobookPlayer-$shortVersion.msix"
& $makeappx.FullName pack /d $layout /p $msix /o
if ($LASTEXITCODE -ne 0) { throw "makeappx nie powiódł się" }

Write-Host "`nGotowe: $msix" -ForegroundColor Green
Write-Host "Pakiet jest niepodpisany — wyślij go do Partner Center (Store podpisze go sam)."
