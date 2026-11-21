$ErrorActionPreference='Stop'
Import-Module 'C:\Perdition Sector\Development\Installer\v0.1.2\Core\Installer.psm1' -Force
$root='C:\Perdition Sector'
$mods=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach($line in [IO.File]::ReadAllLines((Join-Path $root 'profiles\FO4ME\modlist.txt'))) {if($line.StartsWith('+')){[void]$mods.Add($line.Substring(1))}}
$bytes=[long]0
foreach($file in Get-ChildItem -LiteralPath $root -File -Recurse -Force) {
 $relative=$file.FullName.Substring($root.Length+1).Replace('\','/')
 if(Test-PayloadEntry $relative $mods){$bytes+=$file.Length}
}
$n=Get-RequiredInstallBytes -PayloadBytes $bytes
[pscustomobject]@{PayloadBytes=$bytes;RequiredBytes=$n;ResultType=$n.GetType().FullName;MatchesReportedRequirement=($n -eq [long]90297237453)} | ConvertTo-Json
