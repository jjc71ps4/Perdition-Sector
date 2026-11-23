$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$here=$PSScriptRoot
$project='C:\Perdition Sector'
$setup=Join-Path $project 'Development\Installer\v0.2.3-beta.1'
foreach ($name in @('Updates.psm1','ProfileUpdates.ps1')) {
 $local=[IO.File]::ReadAllText((Join-Path $setup ('Core\'+$name))).Replace("`r`n","`n").Trim()
 $remote=[IO.File]::ReadAllText((Join-Path $here ('Remote\'+$name))).Replace("`r`n","`n").Trim()
 if ($local -cne $remote) {throw ('Updater differs from published version: '+$name)}
}
$module=Import-Module (Join-Path $setup 'Core\Updates.psm1') -Force -PassThru
$root=(Get-Content -LiteralPath (Join-Path $here 'fixture.json') -Raw | ConvertFrom-Json).root
$index=Get-Content -LiteralPath (Join-Path $here 'beta-v2.candidate.json') -Raw | ConvertFrom-Json
$archives=@{}
$manifest=Get-Content -LiteralPath (Join-Path $here 'build_manifest.json') -Raw | ConvertFrom-Json
for ($i=0;$i -lt $manifest.artifacts.Count;$i++) {$archives[$manifest.update_ids[$i]]=Join-Path $here $manifest.artifacts[$i].filename}
$requests=New-Object 'Collections.Generic.List[string]'
& $module {
 param($Index,$Archives,$Requests)
 $script:FixtureIndex=$Index;$script:FixtureArchives=$Archives;$script:FixtureRequests=$Requests
 function script:Get-PSUpdateIndex([string]$Url) {return $script:FixtureIndex}
 function script:Get-PSUpdateArchive($Update,[string]$Cache) {$script:FixtureRequests.Add($Update.id);return $script:FixtureArchives[$Update.id]}
} $index $archives $requests
# Seed profile actions from the three already-published updates, including the
# updater's UTF-8 normalization, to model an installation current on that channel.
& $module {
 param($Index,$Root)
 foreach($u in $Index.updates[0..2]) {foreach($p in @(Get-PSUpdateProfileChanges $u $Root)) {[IO.File]::WriteAllText($p.Target,$p.Content,(New-Object Text.UTF8Encoding($false)))}}
} $index $root
$prefs=Join-Path $root 'profiles\FO4ME\fallout4prefs.ini'
$before=[IO.File]::ReadAllBytes($prefs)
$first=@(Invoke-PerditionUpdates -InstallRoot $root -SourceManifest (Join-Path $setup 'update_source.json'))
if ($first.Count -ne 6 -or @($first[0..2] | Where-Object {$_.status -ne 'already_current'}).Count -or @($first[3..5] | Where-Object {$_.status -ne 'applied'}).Count) {throw 'Unexpected update application statuses'}
if (($requests -join '|') -cne ($manifest.update_ids -join '|')) {throw 'Downloaded unexpected updates or wrong order'}
$expected=@{};foreach($update in $index.updates){foreach($file in $update.files){$expected[$file.path]=$file}}
foreach ($rel in $expected.Keys) {if ((Get-FileHash -LiteralPath (Join-Path $root $rel)).Hash.ToLowerInvariant() -ne $expected[$rel].sha256) {throw ('Installed hash mismatch: '+$rel)}}
$plugins=[IO.File]::ReadAllText((Join-Path $root 'profiles\FO4ME\plugins.txt'))
$mods=[IO.File]::ReadAllText((Join-Path $root 'profiles\FO4ME\modlist.txt'))
foreach($area in @('Lexington','Concord')) {if (-not $plugins.Contains(('*PS'+$area+'Optimization.esp')) -or -not $mods.Contains(('+Perdition '+$area+' Optimization - Test'))) {throw ('Profile missing '+$area)}}
if ($plugins.IndexOf('*PSLexingtonOptimization.esp') -gt $plugins.IndexOf('*PSConcordOptimization.esp')) {throw 'Concord must load after Lexington'}
if ([Convert]::ToBase64String($before) -cne [Convert]::ToBase64String([IO.File]::ReadAllBytes($prefs))) {throw 'Personal display settings changed'}
if ([IO.File]::ReadAllText((Join-Path $root 'profiles\FO4ME\saves\keep.fos')) -cne 'personal save fixture') {throw 'Personal save changed'}
$second=@(Invoke-PerditionUpdates -InstallRoot $root -SourceManifest (Join-Path $setup 'update_source.json'))
if (@($second | Where-Object {$_.status -ne 'already_current'}).Count -or $requests.Count -ne 3) {throw 'Repeat update is not idempotent'}
$result=@{passed=$true;updater_version_tested='0.2.3-beta.1';public_updater_and_profile_source_verified=$true;channel_entries=6;new_updates=3;payload_files_verified=$expected.Count;only_missing_archives_requested=$true;profile_enable_and_master_order_verified=$true;repeat_no_download=$true;display_5120x1440_and_saves_unchanged=$true;live_game_modified=$false;network_mocked=$true;ultrawide_native_test='pending';tested_utc=[DateTime]::UtcNow.ToString('o')}
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $here 'validation.json') -Encoding UTF8
$result | ConvertTo-Json
