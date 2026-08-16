# Podpisuje pakiet MSIX certyfikatem testowym — wersja DO WYPRÓBOWANIA lokalnie.
#
#   .\sign_msix.ps1                      # podpisuje najnowszy pakiet z msix_out\
#   .\sign_msix.ps1 -Install             # podpisuje i od razu instaluje
#
# UWAGA: podpisany pakiet służy WYŁĄCZNIE do testów na własnym komputerze.
# Do Microsoft Store wysyłamy pakiet NIEPODPISANY (Store podpisuje go sam),
# dlatego skrypt zapisuje podpisaną kopię pod nazwą *-test-signed.msix
# i nie rusza oryginału.
param(
    [string]$Package = "",
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- 1. Pakiet wejściowy: podany albo najnowszy niepodpisany z msix_out\
if (-not $Package) {
    $Package = Get-ChildItem (Join-Path $root "msix_out\*.msix") -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike "*-test-signed.msix" } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $Package -or -not (Test-Path $Package)) {
    throw "Nie znaleziono pakietu .msix — najpierw uruchom .\build_msix.ps1"
}

# --- 2. Publisher z manifestu musi się ZGADZAĆ z Subject certyfikatu,
#        inaczej Windows odrzuci pakiet przy instalacji.
[xml]$manifest = Get-Content (Join-Path $root "msix\AppxManifest.xml")
$publisher = $manifest.Package.Identity.Publisher
Write-Host "Pakiet   : $Package"
Write-Host "Publisher: $publisher"

$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $publisher -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) } |
    Sort-Object NotAfter -Descending | Select-Object -First 1

# --- 3. Brak certyfikatu → utwórz samopodpisany (ważny rok)
if (-not $cert) {
    Write-Host "Brak pasującego certyfikatu — tworzę nowy samopodpisany..."
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $publisher `
        -FriendlyName "Audiobook Player (test)" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyUsage DigitalSignature `
        -NotAfter (Get-Date).AddYears(1) `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
    Write-Host "Utworzono certyfikat $($cert.Thumbprint)"
    Write-Host "Aby Windows go zaakceptował, zaimportuj go raz jako zaufany (wymaga admina):"
    Write-Host '  Import-Certificate -FilePath .\msix_out\AudiobookPlayer-test.cer ' +
               '-CertStoreLocation Cert:\LocalMachine\TrustedPeople'
}
Write-Host "Certyfikat: $($cert.FriendlyName) [$($cert.Thumbprint)], ważny do $($cert.NotAfter)"

# --- 4. Eksport części publicznej (.cer) — tylko ona jest potrzebna do zaufania
$cerPath = Join-Path $root "msix_out\AudiobookPlayer-test.cer"
Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null

# --- 5. Podpisanie kopii pakietu
$signed = [IO.Path]::ChangeExtension($Package, $null).TrimEnd('.') + "-test-signed.msix"
Copy-Item -Force $Package $signed

$signtool = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe" `
    -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $signtool) { throw "Nie znaleziono signtool.exe — zainstaluj Windows SDK" }

& $signtool.FullName sign /fd SHA256 /sha1 $cert.Thumbprint $signed
if ($LASTEXITCODE -ne 0) { throw "Podpisywanie nie powiodło się" }

& $signtool.FullName verify /pa $signed
if ($LASTEXITCODE -ne 0) { throw "Weryfikacja podpisu nie powiodła się" }

Write-Host "`nPodpisano: $signed" -ForegroundColor Green
Write-Host "Certyfikat publiczny: $cerPath"

# --- 6. Opcjonalna instalacja
if ($Install) {
    Write-Host "`nInstaluję pakiet..."
    Add-AppxPackage -Path $signed
    Get-AppxPackage -Name "MarekZettel-zetmar.PlayerAudiobook" |
        Select-Object Name, Version, InstallLocation | Format-List
    Write-Host "Gotowe — aplikacja jest w menu Start jako „Audiobook Player”."
    Write-Host "Odinstalowanie: Get-AppxPackage *PlayerAudiobook* | Remove-AppxPackage"
}
