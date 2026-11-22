param([string]$InstallRoot='',[switch]$NonInteractive)
$ErrorActionPreference='Stop'
try {
    if (-not $InstallRoot) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog=New-Object Windows.Forms.FolderBrowserDialog
        $dialog.Description='Select your installed Perdition Sector folder (containing ModOrganizer.exe).'
        $dialog.ShowNewFolderButton=$false
        if ($dialog.ShowDialog() -ne [Windows.Forms.DialogResult]::OK) { exit 0 }
        $InstallRoot=$dialog.SelectedPath
    }
    Import-Module (Join-Path $PSScriptRoot 'Updates.psm1') -Force
    $source=Join-Path $PSScriptRoot 'update_source.json'
    if (-not (Test-Path -LiteralPath $source)) { $source=Join-Path (Split-Path -Parent $PSScriptRoot) 'update_source.json' }
    Write-Host 'Close Fallout 4 and Mod Organizer before applying updates.'
    $result=@(Invoke-PerditionUpdates -InstallRoot $InstallRoot -SourceManifest $source)
    Install-PSUpdaterRuntime -InstallRoot $InstallRoot -CoreRoot $PSScriptRoot -SourceManifest $source
    Write-Host 'Perdition Sector is up to date. Fully restart the game before playing.'
    if ($NonInteractive) { $result | ConvertTo-Json -Depth 10 }
    else { [void](Read-Host 'Press Enter to close') }
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if (-not $NonInteractive) { [void](Read-Host 'Press Enter to close') }
    exit 1
}
