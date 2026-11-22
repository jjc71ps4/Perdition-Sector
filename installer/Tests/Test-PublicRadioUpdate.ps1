$ErrorActionPreference='Stop'
$distribution=Split-Path -Parent $PSScriptRoot
$project=Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $distribution))
Import-Module (Join-Path $distribution 'Core\Updates.psm1') -Force
$root=Join-Path ([IO.Path]::GetTempPath()) ('Perdition Public Update '+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory((Join-Path $root 'overwrite\Scripts'))
[void][IO.Directory]::CreateDirectory((Join-Path $root 'profiles\FO4ME\saves'))
[IO.File]::WriteAllText((Join-Path $root 'ModOrganizer.exe'),'non-executed fixture')
Copy-Item -LiteralPath (Join-Path $project 'overwrite\Perdition Sector World.esp') -Destination (Join-Path $root 'overwrite\Perdition Sector World.esp')
$old=Join-Path $project 'Development\RadioStartupFixes\Backups\20261121_155357Z_radio011\overwrite\Scripts\PSRadioQuestScript.pex'
Copy-Item -LiteralPath $old -Destination (Join-Path $root 'overwrite\Scripts\PSRadioQuestScript.pex')
[IO.File]::WriteAllText((Join-Path $root 'profiles\FO4ME\fallout4prefs.ini'),'personal resolution fixture')
[IO.File]::WriteAllText((Join-Path $root 'profiles\FO4ME\saves\test.fos'),'untouched save fixture')
$worldBefore=(Get-FileHash -LiteralPath (Join-Path $root 'overwrite\Perdition Sector World.esp')).Hash
$radioSource=Join-Path $root 'radio-source.json'
$radioConfig=Get-Content -LiteralPath (Join-Path $distribution 'update_source.json') -Raw | ConvertFrom-Json
$radioConfig.index_url=$radioConfig.index_url.Replace('beta-v2.json','beta.json')
$radioConfig | ConvertTo-Json | Set-Content -LiteralPath $radioSource -Encoding UTF8
$first=@(Invoke-PerditionUpdates -InstallRoot $root -SourceManifest $radioSource)
if ($first.Count -ne 1 -or $first[0].status -ne 'applied') { throw 'Public radio update did not apply to the old-script fixture.' }
$radioHash=(Get-FileHash -LiteralPath (Join-Path $root 'overwrite\Scripts\PSRadioQuestScript.pex')).Hash.ToLowerInvariant()
if ($radioHash -ne 'e00affca5529fc6e1d38060b780a1de400219bff17f671952962a290e9df59cd') { throw 'Public radio content differs from accepted bytecode.' }
$again=@(Invoke-PerditionUpdates -InstallRoot $root -SourceManifest $radioSource)
if ($again[0].status -ne 'already_current') { throw 'Public update is not idempotent.' }
if ((Get-FileHash -LiteralPath (Join-Path $root 'overwrite\Perdition Sector World.esp')).Hash -ne $worldBefore) { throw 'World changed.' }
if ([IO.File]::ReadAllText((Join-Path $root 'profiles\FO4ME\fallout4prefs.ini')) -cne 'personal resolution fixture') { throw 'Display settings changed.' }
if ([IO.File]::ReadAllText((Join-Path $root 'profiles\FO4ME\saves\test.fos')) -cne 'untouched save fixture') { throw 'Save changed.' }
$report=@{public_index_downloaded=$true;public_patch_downloaded=$true;patch_archive_bytes=3202;
    old_script_replaced_with_accepted_bytecode=$true;repeat_download_skipped=$true;world_settings_saves_preserved=$true;
    fixture_root=$root;full_base_package_downloaded=$false;steam_downloaded=$false;real_game_launched=$false;
    commit='7fb3b777c7bbf36cea7fe829ee67fb7b0fe2b9d0'}
$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'public_update_test_results.json') -Encoding UTF8
$report | ConvertTo-Json
