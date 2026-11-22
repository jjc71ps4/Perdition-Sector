$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$distribution=Split-Path -Parent $PSScriptRoot
$module=Import-Module (Join-Path $distribution 'Core\Installer.psm1') -Force -PassThru
Add-Type -AssemblyName System.IO.Compression.FileSystem
$work=Join-Path ([IO.Path]::GetTempPath()) ('Perdition Existing Game Tests '+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($work)
$script:Passed=0
function Check([bool]$Value,[string]$Name) { if (-not $Value) { throw ('FAILED: '+$Name) }; $script:Passed++;Write-Host ('PASS: '+$Name) }
function Reject([scriptblock]$Action,[string]$Name) { $failed=$false;try { & $Action } catch { $failed=$true };Check $failed $Name }
function Write-Zip([string]$Path,$Files) {
    $zip=[IO.Compression.ZipFile]::Open($Path,[IO.Compression.ZipArchiveMode]::Create)
    try { foreach ($name in $Files.Keys) { $entry=$zip.CreateEntry($name);$stream=$entry.Open();try { $bytes=[Text.Encoding]::UTF8.GetBytes($Files[$name]);$stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() } } } finally { $zip.Dispose() }
}
$game=Join-Path $work 'Existing Fallout 4 With Spaces'
[void][IO.Directory]::CreateDirectory((Join-Path $game 'Data'))
$source=Join-Path $work 'Runtime.cs'
[IO.File]::WriteAllText($source,'[assembly:System.Reflection.AssemblyFileVersion("1.10.163.0")] class Runtime { static void Main() {} }')
$exe=Join-Path $game 'Fallout4.exe'
& (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /target:winexe ('/out:'+$exe) $source
if ($LASTEXITCODE -ne 0) { throw 'Fixture runtime compilation failed.' }
$required=& $module { $script:RequiredGameFiles }
foreach ($name in $required) {
    $path=Join-Path $game $name
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))
    [IO.File]::WriteAllText($path,'fixture game asset')
}
$beforeExe=(Get-FileHash -LiteralPath $exe).Hash
$validated=Assert-CompatibleGameFolder $game
Check ($validated.GameRoot -eq $game -and $validated.Version -eq '1.10.163.0') 'Valid downgraded game and DLCs accepted'
Reject {Assert-CompatibleGameFolder ''} 'Missing game selection rejected'
Reject {Assert-CompatibleGameFolder (Join-Path $work 'Missing')} 'Absent game shows prerequisite error'
Reject {Assert-CompatibleGameFolder (Join-Path $game 'Data')} 'Selecting the Data folder instead of the game root is rejected'
$dlc=Join-Path $game 'Data\DLCNukaWorld.esm'
[IO.File]::Delete($dlc)
Reject {Assert-CompatibleGameFolder $game} 'Missing DLC blocks installation'
[IO.File]::WriteAllText($dlc,'fixture game asset')
$texture=Join-Path $game 'Data\Fallout4 - Textures9.ba2'
[IO.File]::Delete($texture)
Reject {Assert-CompatibleGameFolder $game} 'Missing base-game archive blocks installation'
[IO.File]::WriteAllText($texture,'fixture game asset')
$wrong=Join-Path $work 'Wrong Runtime'
[void][IO.Directory]::CreateDirectory($wrong)
[IO.File]::WriteAllText($source,'[assembly:System.Reflection.AssemblyFileVersion("1.10.999.0")] class Runtime { static void Main() {} }')
& (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /target:winexe ('/out:'+(Join-Path $wrong 'Fallout4.exe')) $source
if ($LASTEXITCODE -ne 0) { throw 'Wrong-version fixture compilation failed.' }
Reject {Assert-CompatibleGameFolder $wrong} 'Unsupported runtime rejected'
Check ((Get-DetectedGameFolder -CandidatePaths @($wrong,$game)) -eq $game) 'Detection skips an incompatible installation and finds the downgraded game'
Check ((Get-DetectedGameFolder -CandidatePaths @($wrong)) -eq '') 'Detection reports no compatible game when only a wrong runtime exists'
$plan=Resolve-GameInstallPlan -InstallRoot (Join-Path $work 'Perdition') -UseExistingGame -ExistingGameRoot $game
Check (-not $plan.DownloadSteam -and $plan.GameRoot -eq $game) 'Existing mode chooses the selected folder without Steam credentials'
$fresh=Resolve-GameInstallPlan -InstallRoot (Join-Path $work 'Perdition') -SteamUser 'fixture'
Check ($fresh.DownloadSteam -and $fresh.GameRoot.EndsWith('\_Fallout4')) 'Steam option retains the separate game download'
Reject {Resolve-GameInstallPlan -InstallRoot (Join-Path $work 'Perdition')} 'Steam mode still requires its login name'
Check (((Get-RequiredInstallBytes -PayloadBytes 10GB)-(Get-RequiredInstallBytes -PayloadBytes 10GB -UseExistingGame)) -eq 44GB) 'Existing mode does not require a second 44 GB game copy'
$untouched=Join-Path $work 'Must Not Be Created'
$message=''
try { Invoke-PerditionInstallation -InstallRoot $untouched -PackagePath 'missing.zip' -DistributionRoot $distribution -UseExistingGame -ExistingGameRoot $wrong } catch { $message=$_.Exception.Message }
Check ($message.Contains('Perdition Sector requires downgraded Fallout 4') -and -not [IO.Directory]::Exists($untouched)) 'Wrong game fails before package access or installation writes'

$payload=Join-Path $work 'payload.zip'
Write-Zip $payload ([ordered]@{
    'Perdition Sector/ModOrganizer.exe'='fixture'
    'Perdition Sector/splash.png'='fixture artwork'
    'Perdition Sector/mods/Live/Live.esp'='fixture plugin'
    'Perdition Sector/overwrite/Perdition Sector World.esp'='fixture world'
    'Perdition Sector/profiles/FO4ME/modlist.txt'="+Live`r`n"
    'Perdition Sector/profiles/FO4ME/plugins.txt'="*Live.esp`r`n*Perdition Sector World.esp"
    'Perdition Sector/profiles/FO4ME/fallout4.ini'="[General]`r`n"
    'Perdition Sector/profiles/FO4ME/fallout4custom.ini'="[General]`r`n"
    'Perdition Sector/profiles/FO4ME/fallout4prefs.ini'="[Display]`r`n"
    'Perdition Sector/profiles/FO4ME/settings.ini'="[General]`r`n"
})
$fixture=Join-Path $work 'Setup Fixture'
[void][IO.Directory]::CreateDirectory((Join-Path $fixture 'Tools'))
foreach ($name in @('7z.exe','7z.dll')) { [IO.File]::Copy((Join-Path $distribution ('Tools\'+$name)),(Join-Path $fixture ('Tools\'+$name))) }
$overlay=Join-Path $fixture 'RootOverlay.zip'
Write-Zip $overlay @{'Shared/CustomControlMap.txt'='PS controls';'ENB/d3d11.dll'='bundled hook'}
$f4se=Join-Path $work 'F4SEFixture.zip'
$f4seFiles=[ordered]@{}
foreach ($name in @('f4se_loader.exe','f4se_1_10_163.dll','f4se_steam_loader.dll','f4se_readme.txt','f4se_whatsnew.txt')) { $f4seFiles['f4se_0_06_23/'+$name]='new F4SE fixture' }
$f4seFiles['f4se_0_06_23/Data/Scripts/F4SE.pex']='new F4SE declarations'
Write-Zip $f4se $f4seFiles
$info=Get-PackageInformation $payload
$recipe=Get-Content -LiteralPath (Join-Path $distribution 'release.json') -Raw | ConvertFrom-Json
$recipe.world_plugin_sha256=$info.WorldHash
$recipe.game_exe_sha256='not-the-fixture-exe-hash'
$recipe.root_overlay_sha256=(Get-FileHash -LiteralPath $overlay).Hash.ToLowerInvariant()
$recipe | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $fixture 'release.json') -Encoding UTF8
[IO.File]::WriteAllText((Join-Path $game 'f4se_loader.exe'),'original F4SE')
[IO.File]::WriteAllText((Join-Path $game 'CustomControlMap.txt'),'original controls')
& $module {
    param($archive)
    $script:FixtureF4SE=$archive
    $script:SeenDependencies=@()
    function script:Install-VisualCppRuntimeIfNeeded { param($CacheRoot) }
    function script:Invoke-SteamDepotDownloads { throw 'Steam must never run in existing-game mode.' }
    function script:Get-VerifiedDownload {
        param($Dependency,$CacheRoot)
        $script:SeenDependencies+=$Dependency.filename
        if ($Dependency.filename -ne 'f4se_0_06_23.7z') { throw 'Unexpected download: '+$Dependency.filename }
        return $script:FixtureF4SE
    }
} $f4se
# Exercise the actual new update module through the complete installer fixture.
# Only its network transport is replaced inside this temporary distribution.
$fixtureCore=Join-Path $fixture 'Core';[void][IO.Directory]::CreateDirectory($fixtureCore)
foreach($name in @('Updates.psm1','Update-Perdition.ps1','ProfileUpdates.ps1','Update-Installed.cmd')) {
    Copy-Item -LiteralPath (Join-Path $distribution ('Core\'+$name)) -Destination (Join-Path $fixtureCore $name)
}
$updateZip=Join-Path $fixtureCore 'fixture_update.zip'
Write-Zip $updateZip @{'overwrite/Scripts/PSRadioQuestScript.pex'='fixture corrected radio'}
$hashAlgorithm=[Security.Cryptography.SHA256]::Create()
try { $radioHash=([BitConverter]::ToString($hashAlgorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes('fixture corrected radio')))).Replace('-','').ToLowerInvariant() }
finally { $hashAlgorithm.Dispose() }
$updateSource=@{schema_version=1;base_snapshot_tag='fixture';base_archive_sha256=('a'*64);
    world_plugin_sha256=$info.WorldHash;index_url='https://raw.githubusercontent.com/jjc71ps4/Perdition-Sector/main/updates/beta.json'}
$updateSource | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $fixture 'update_source.json') -Encoding UTF8
$updateIndex=@{schema_version=1;base_snapshot_tag='fixture';base_archive_sha256=('a'*64);updates=@(@{
    id='fixture-radio';name='Fixture radio';url='https://raw.githubusercontent.com/jjc71ps4/Perdition-Sector/main/updates/fixture.zip';
    bytes=(Get-Item -LiteralPath $updateZip).Length;sha256=(Get-FileHash -LiteralPath $updateZip).Hash.ToLowerInvariant();
    files=@(@{path='overwrite/Scripts/PSRadioQuestScript.pex';bytes=23;previous_sha256='';sha256=$radioHash})})}
$updateIndex | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $fixtureCore 'fixture_index.json') -Encoding UTF8
@'
function Get-PSUpdateIndex([string]$Url) { return (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'fixture_index.json') -Raw | ConvertFrom-Json) }
function Get-PSUpdateArchive($Update,[string]$Cache) { return (Join-Path $PSScriptRoot 'fixture_update.zip') }
'@ | Add-Content -LiteralPath (Join-Path $fixtureCore 'Updates.psm1') -Encoding UTF8
$install=Join-Path $work 'Perdition Installation'
Invoke-PerditionInstallation -InstallRoot $install -PackagePath $payload -DistributionRoot $fixture -UseExistingGame -ExistingGameRoot $game -Width 2560 -Height 1600
$calls=@(& $module { $script:SeenDependencies })
Check ($calls.Count -eq 1 -and $calls[0] -eq 'f4se_0_06_23.7z') 'Actual existing-game install requests only F4SE, never DepotDownloader or Steam'
Check (-not [IO.Directory]::Exists((Join-Path $install '_Fallout4'))) 'Existing game is reused directly without duplicating the installation'
Check (-not [IO.Directory]::Exists((Join-Path $install '_Installer\SteamSession'))) 'Existing mode creates no Steam authentication session'
$config=[IO.File]::ReadAllText((Join-Path $install 'ModOrganizer.ini'))
Check ($config.Contains($game.Replace('\','/')+'/f4se_loader.exe') -and $config.Contains($game.Replace('\','/')+'/Fallout4.exe')) 'MO2 F4SE and game entries point to the selected existing folder'
Check ([IO.File]::Exists((Join-Path $install 'mods\Live\Live.esp')) -and [IO.File]::Exists((Join-Path $install 'overwrite\Perdition Sector World.esp'))) 'Perdition files are deployed even when Steam downloads are skipped'
Check ((Get-FileHash -LiteralPath $exe).Hash -eq $beforeExe) 'Existing Fallout4.exe is unchanged'
Check ([IO.File]::ReadAllText((Join-Path $game 'CustomControlMap.txt')) -eq 'PS controls') 'Required PS control file is applied to the selected game'
Check ([IO.File]::ReadAllText((Join-Path $install '_Installer\ExistingGameBackup\CustomControlMap.txt')) -eq 'original controls') 'Original controls are backed up in the Perdition install folder'
Check ([IO.File]::ReadAllText((Join-Path $install '_Installer\ExistingGameBackup\f4se_loader.exe')) -eq 'original F4SE') 'Existing F4SE loader is backed up before replacement'
$result=Get-Content -LiteralPath (Join-Path $install '_Installer\result.json') -Raw | ConvertFrom-Json
Check ($result.success -and $result.use_existing_game -and $result.game_root -eq $game) 'Successful result records the selected runtime folder'
Check ([IO.File]::ReadAllText((Join-Path $install 'overwrite\Scripts\PSRadioQuestScript.pex')) -ceq 'fixture corrected radio') 'Complete installer applies the verified incremental patch after base extraction'
Check ([IO.File]::Exists((Join-Path $install 'Update Perdition Sector.cmd'))) 'Fresh installation receives its update command'
Check ([IO.File]::Exists((Join-Path $install 'Updater\Updates.psm1')) -and [IO.File]::Exists((Join-Path $install 'Updater\update_source.json'))) 'Fresh installation receives the updater and channel configuration'
Invoke-PerditionInstallation -InstallRoot $install -PackagePath $payload -DistributionRoot $fixture -UseExistingGame -ExistingGameRoot $game
Check ([IO.File]::ReadAllText((Join-Path $install '_Installer\ExistingGameBackup\f4se_loader.exe')) -eq 'original F4SE') 'Retry preserves the original backup instead of replacing it'
Check ([IO.File]::ReadAllText((Join-Path $install 'overwrite\Scripts\PSRadioQuestScript.pex')) -ceq 'fixture corrected radio') 'Installer retry preserves the already-current incremental patch'
Install-GameRootOverlay $overlay $game $true -OptionalRoot (Join-Path $install 'Optional\ENB')
Install-GameRootOverlay $overlay $game $false -OptionalRoot (Join-Path $install 'Optional\ENB')
Check ([IO.File]::Exists((Join-Path $install 'Optional\ENB\d3d11.dll')) -and -not [IO.Directory]::Exists((Join-Path $work 'Optional'))) 'Optional ENB storage stays under Perdition when the game is elsewhere'
# New update mods must be validated from the migrated profile, not the frozen base inventory.
$newMod=Join-Path $install 'mods\After Snapshot'
[void][IO.Directory]::CreateDirectory($newMod)
[IO.File]::WriteAllText((Join-Path $newMod 'AfterSnapshot.esp'),'new patch fixture')
$modlist=Join-Path $install 'profiles\FO4ME\modlist.txt'
[IO.File]::WriteAllText($modlist,([IO.File]::ReadAllText($modlist)).TrimEnd()+"`r`n+After Snapshot`r`n")
$plugins=Join-Path $install 'profiles\FO4ME\plugins.txt'
[IO.File]::WriteAllText($plugins,([IO.File]::ReadAllText($plugins)).TrimEnd()+"`r`n*AfterSnapshot.esp`r`n")
& $module { param($Root,$Info,$Recipe,$Game,$Hash) Assert-InstalledBuild $Root $Info $Recipe -GameRoot $Game -ExpectedExistingExeHash $Hash } $install $info $recipe $game $beforeExe
Check $true 'Final verification recognizes a plugin enabled after the frozen snapshot'
Check ([IO.File]::Exists((Join-Path $install 'Updater\ProfileUpdates.ps1'))) 'Installed updater includes its profile migration helper'
$summary=[ordered]@{passed=$script:Passed;failed=0;fixture_directory=$work;live_game_modified=$false;live_steam_or_github_download=$false;tested_utc=[DateTime]::UtcNow.ToString('o')}
$summary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'existing_game_test_results.json') -Encoding UTF8
$summary | ConvertTo-Json
