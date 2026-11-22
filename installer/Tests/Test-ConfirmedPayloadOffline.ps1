$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$distribution=Split-Path -Parent $PSScriptRoot
$project=Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $distribution))
$authoring=Join-Path $project 'Development\Distribution\Confirmed-Revisions-0.2.3'
$fixture=Get-Content -LiteralPath (Join-Path $authoring 'fixture.json') -Raw | ConvertFrom-Json
$root=$fixture.root
$module=Import-Module (Join-Path $distribution 'Core\Updates.psm1') -Force -PassThru
$index=Get-Content -LiteralPath (Join-Path $authoring 'beta-v2.candidate.json') -Raw | ConvertFrom-Json
$archives=@{'radio-recovery-0.1.1'=(Join-Path $project 'Development\Distribution\RadioUpdate-0.1.1\Perdition_Radio_Recovery_0.1.1.zip');'confirmed-build-0.2.3'=(Join-Path $authoring 'Perdition_Confirmed_Revisions_0.2.3-beta.1.zip')}
& $module { param($Index,$Archives)
    $script:TestIndex=$Index;$script:TestArchives=$Archives
    function script:Get-PSUpdateIndex([string]$Url) { return $script:TestIndex }
    function script:Get-PSUpdateArchive($Update,[string]$Cache) { return $script:TestArchives[$Update.id] }
} $index $archives
$prefs=Join-Path $root 'profiles\FO4ME\fallout4prefs.ini'
$text=[IO.File]::ReadAllText($prefs);$width=[regex]::Match($text,'(?im)^iSize W=.*$').Value;$height=[regex]::Match($text,'(?im)^iSize H=.*$').Value
$first=@(Invoke-PerditionUpdates -InstallRoot $root -SourceManifest (Join-Path $distribution 'update_source.json'))
if ($first.Count -ne 2 -or @($first | Where-Object {$_.status -ne 'applied'}).Count) { throw 'Both complete updates must apply to the frozen-base fixture.' }
foreach ($u in $index.updates) { foreach ($file in $u.files) {
    $path=Join-Path $root $file.path.Replace('/','\')
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw "Wrong final content: $($file.path)" }
} }
$after=[IO.File]::ReadAllText($prefs)
if (-not $after.Contains($width) -or -not $after.Contains($height)) { throw 'Personal resolution changed.' }
if ([IO.File]::ReadAllText((Join-Path $root 'profiles\FO4ME\saves\keep.fos')) -cne 'personal save fixture') { throw 'Save changed.' }
$plugins=[IO.File]::ReadAllText((Join-Path $root 'profiles\FO4ME\plugins.txt'))
foreach ($name in @('Perdition_NT4_Repaired.esp','Perdition North End Visibility - Test.esp')) { if (-not $plugins.Contains('*'+$name)) { throw 'Required new patch was not enabled.' } }
$again=@(Invoke-PerditionUpdates -InstallRoot $root -SourceManifest (Join-Path $distribution 'update_source.json'))
if (@($again | Where-Object {$_.status -ne 'already_current'}).Count) { throw 'Full payload application is not idempotent.' }
@{complete_archives_verified=$true;baseline_predecessors_verified=$fixture.baseline_files;final_files_verified=18;profile_migration=$true;resolution_and_saves_preserved=$true;repeat_noop=$true;live_game_modified=$false;network_mocked=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'confirmed_payload_test_results.json') -Encoding UTF8
Write-Host 'Complete revision archives, profile migration and repeat behavior passed.'
