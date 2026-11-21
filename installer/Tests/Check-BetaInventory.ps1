param([Parameter(Mandatory=$true)][string]$InventoryPath)
$ErrorActionPreference='Stop'
$distribution=Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $distribution 'Core\Installer.psm1') -Force
$rows=Get-Content -LiteralPath $InventoryPath -Raw | ConvertFrom-Json
$mods=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($row in $rows) {
    $parts=$row.path.Split('/')
    if ($parts.Count -ge 3 -and $parts[0] -eq 'mods') { [void]$mods.Add($parts[1]) }
}
$rejected=@()
foreach ($row in $rows) { if (-not (Test-PayloadEntry $row.path $mods)) { $rejected+=$row.path } }
if ($rejected.Count) { throw ('Installer would exclude snapshot files: '+($rejected -join ', ')) }
[pscustomobject]@{accepted_player_files=@($rows).Count;enabled_mod_directories=$mods.Count;excluded_by_installer=0} | ConvertTo-Json

