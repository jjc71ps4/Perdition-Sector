param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [string]$PackagePath,
    [string]$SteamUser='',
    [int]$Width=1920,
    [int]$Height=1080,
    [switch]$UseQr,
    [switch]$DesktopShortcut,
    [switch]$EnableEnb,
    [switch]$DownloadPackage
)
$ErrorActionPreference='Stop'
$distribution=Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $PSScriptRoot 'Installer.psm1') -Force
try {
    if ($DownloadPackage) {
        $destination=Assert-InstallDestination $InstallRoot $distribution
        $PackagePath=Resolve-OnlinePackage -SourceManifest (Join-Path $distribution 'package_source.json') -CacheRoot ($destination.Root+'.DownloadCache')
    }
    Invoke-PerditionInstallation -InstallRoot $InstallRoot -PackagePath $PackagePath -SteamUser $SteamUser -Width $Width -Height $Height -UseQr:$UseQr -DesktopShortcut:$DesktopShortcut -EnableEnb:$EnableEnb -DistributionRoot $distribution
    Write-Host "`nPress Enter to close this window."
    [void](Read-Host)
    exit 0
} catch {
    Write-Host "`n$($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Existing files and any completed downloads are retained. Correct the problem and rerun setup to resume.'
    Write-Host 'Press Enter to close this window.'
    [void](Read-Host)
    exit 1
}
