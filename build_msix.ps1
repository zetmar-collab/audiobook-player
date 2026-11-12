# Buduje pakiet MSIX dla Microsoft Store.
#
#   .\build_msix.ps1              # wersja z src\appinfo.py (jedno źródło prawdy)
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

# --- 1. Wersja: z parametru albo z src\appinfo.py; manifest jest synchronizowany
$py = Join-Path $venv "Scripts\python.exe"
if (-not $Version) {
    $Version = (& $py -c "import sys; sys.path.insert(0, r'$root\src'); import appinfo; print(appinfo.APP_VERSION)").Trim()
}
$manifestPath = Join-Path $root "msix\AppxManifest.xml"
[xml]$manifest = Get-Content $manifestPath -Encoding UTF8
if ($manifest.Package.Identity.Version -ne "$Version.0") {
    # podmiana tekstu zamiast XmlDocument.Save — zachowuje formatowanie pliku (czytelne diffy)
    $text = [IO.File]::ReadAllText($manifestPath, [Text.Encoding]::UTF8)
    # wzorzec ograniczony do elementu <Identity> — w pliku jest też MinVersion="10.0..."
    $rx = New-Object Text.RegularExpressions.Regex('(<Identity\b[^>]*?\bVersion=")\d+\.\d+\.\d+\.\d+(")',
                                                   [Text.RegularExpressions.RegexOptions]::Singleline)
    $text = $rx.Replace($text, "`${1}$Version.0`$2", 1)
    [IO.File]::WriteAllText($manifestPath, $text, (New-Object Text.UTF8Encoding($false)))
    [xml]$manifest = Get-Content $manifestPath -Encoding UTF8
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
$icon = (Resolve-Path (Join-Path $root "src\icon.ico")).Path
$license = (Resolve-Path (Join-Path $root "LICENSE")).Path
$notices = (Resolve-Path (Join-Path $root "THIRD_PARTY_NOTICES.md")).Path
& (Join-Path $venv "Scripts\pyinstaller.exe") --noconfirm --clean --windowed `
    --name AudiobookPlayer --icon $icon `
    --add-data "$icon;." --add-data "$license;." --add-data "$notices;." `
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
# GPL wymaga dołączenia tekstu licencji do dystrybucji binarnej
Copy-Item -Force $license (Join-Path $layout "LICENSE")
Copy-Item -Force $notices (Join-Path $layout "THIRD_PARTY_NOTICES.md")

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
