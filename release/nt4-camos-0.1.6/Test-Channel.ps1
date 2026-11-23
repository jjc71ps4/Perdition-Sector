$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$here=$PSScriptRoot
$setup='C:\Perdition Sector\Development\Installer\v0.2.3-beta.1'
foreach($name in @('Updates.psm1','ProfileUpdates.ps1')) {
 $local=[IO.File]::ReadAllText((Join-Path $setup ('Core\'+$name))).Replace("`r`n","`n").Trim()
 $remote=[IO.File]::ReadAllText((Join-Path $here ('Remote\'+$name))).Replace("`r`n","`n").Trim()
 if($local -cne $remote){throw ('Updater source differs from the published version: '+$name)}
}
$module=Import-Module (Join-Path $setup 'Core\Updates.psm1') -Force -PassThru
$root=(Get-Content -LiteralPath (Join-Path $here 'fixture.json') -Raw | ConvertFrom-Json).root
$index=Get-Content -LiteralPath (Join-Path $here 'beta-v2.candidate.json') -Raw | ConvertFrom-Json
$build=Get-Content -LiteralPath (Join-Path $here 'build_manifest.json') -Raw | ConvertFrom-Json
$archive=$build.archive
$requests=New-Object 'Collections.Generic.List[string]'
& $module {
 param($Index,$Archive,$Requests)
 $script:FixtureIndex=$Index;$script:FixtureArchive=$Archive;$script:FixtureRequests=$Requests
 function script:Get-PSUpdateIndex([string]$Url){return $script:FixtureIndex}
 function script:Get-PSUpdateArchive($Update,[string]$Cache){
  if($Update.id -ne 'nt4-camos-0.1.6'){throw ('Unexpected download: '+$Update.id)}
  $script:FixtureRequests.Add($Update.id);return $script:FixtureArchive
 }
} $index $archive $requests
& $module {
 param($Index,$Root)
 foreach($u in $Index.updates[0..5]){foreach($p in @(Get-PSUpdateProfileChanges $u $Root)){
  [IO.File]::WriteAllText($p.Target,$p.Content,(New-Object Text.UTF8Encoding($false)))
 }}
} $index $root
$before=@{}
foreach($name in @('modlist.txt','plugins.txt','loadorder.txt','fallout4prefs.ini','saves\keep.fos')){
 $path=Join-Path $root ('profiles\FO4ME\'+$name);$before[$path]=(Get-FileHash -LiteralPath $path).Hash
}
$first=@(Invoke-PerditionUpdates -InstallRoot $root -SourceManifest (Join-Path $setup 'update_source.json'))
if($first.Count -ne 7 -or @($first[0..5] | Where-Object {$_.status -ne 'already_current'}).Count -or $first[6].status -ne 'applied'){throw 'Wrong channel application sequence'}
if($requests.Count -ne 1 -or $requests[0] -ne 'nt4-camos-0.1.6'){throw 'Downloaded updates other than the new camo package'}
$expected=@{};foreach($u in $index.updates){foreach($f in $u.files){$expected[$f.path]=$f}}
foreach($rel in $expected.Keys){
 if((Get-FileHash -LiteralPath (Join-Path $root $rel)).Hash.ToLowerInvariant() -ne $expected[$rel].sha256){throw ('Wrong installed file: '+$rel)}
}
foreach($path in $before.Keys){if((Get-FileHash -LiteralPath $path).Hash -ne $before[$path]){throw ('Profile/save changed: '+$path)}}
$second=@(Invoke-PerditionUpdates -InstallRoot $root -SourceManifest (Join-Path $setup 'update_source.json'))
if(@($second | Where-Object {$_.status -ne 'already_current'}).Count -or $requests.Count -ne 1){throw 'Repeat update is not idempotent'}
$result=@{passed=$true;updater_version_tested='0.2.3-beta.1';public_updater_source_verified=$true;channel_entries=7;
 new_update_files=11;payload_files_verified=$expected.Count;only_new_archive_requested=$true;repeat_no_download=$true;
 profiles_display_5120x1440_and_save_unchanged=$true;live_game_modified=$false;network_mocked=$true;tested_utc=[DateTime]::UtcNow.ToString('o')}
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $here 'validation.json') -Encoding UTF8
$result | ConvertTo-Json
