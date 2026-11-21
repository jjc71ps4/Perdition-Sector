$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$distribution=Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $distribution 'Core\Installer.psm1') -Force
Add-Type -AssemblyName System.IO.Compression.FileSystem
$work=Join-Path ([IO.Path]::GetTempPath()) ('Perdition Installer Tests '+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($work)
$script:Passed=0
function Assert-Check([bool]$Condition,[string]$Name) { if (-not $Condition) { throw ('FAILED: '+$Name) };$script:Passed++;Write-Host ('PASS: '+$Name) }
function Assert-Rejected([scriptblock]$Action,[string]$Name) { $rejected=$false;try { & $Action } catch { $rejected=$true };Assert-Check $rejected $Name }
function Write-FixtureZip([string]$Path,$Files) {
    $zip=[IO.Compression.ZipFile]::Open($Path,[IO.Compression.ZipArchiveMode]::Create)
    try { foreach($name in $Files.Keys) { $entry=$zip.CreateEntry($name);$stream=$entry.Open();try { $bytes=[Text.Encoding]::UTF8.GetBytes($Files[$name]);$stream.Write($bytes,0,$bytes.Length) } finally {$stream.Dispose()} } } finally {$zip.Dispose()}
}
$files=[ordered]@{
    'Perdition Sector/ModOrganizer.exe'='fixture'
    'Perdition Sector/ModOrganizer.ini'='private account data must not be copied'
    'Perdition Sector/CreationKit.exe'='editor'
    'Perdition Sector/tools/FO4Edit.exe'='editor'
    'Perdition Sector/dlls/runtime.dll'='runtime'
    'Perdition Sector/mods/Live/Live.esp'='plugin'
    'Perdition Sector/mods/Live/meta.ini'='metadata'
    'Perdition Sector/mods/Disabled/Disabled.esp'='disabled'
    'Perdition Sector/mods/F4SE/Scripts/Game.pex'='extender declarations'
    'Perdition Sector/mods/F4SE/f4se_0_06_23/src/developer.cpp'='developer source'
    'Perdition Sector/overwrite/Perdition Sector World.esp'='world fixture'
    'Perdition Sector/overwrite/Scripts/PSRadioQuestScript.pex'='compiled gameplay script'
    'Perdition Sector/overwrite/Scripts/Source/User/PSRadioQuestScript.psc'='source'
    'Perdition Sector/profiles/FO4ME/modlist.txt'="+Live`r`n+F4SE`r`n-Disabled`r`n"
    'Perdition Sector/profiles/FO4ME/plugins.txt'="*Live.esp`r`n*Perdition Sector World.esp"
    'Perdition Sector/profiles/FO4ME/loadorder.txt'='Live.esp'
    'Perdition Sector/profiles/FO4ME/fallout4.ini'="[General]`r`nfoo=keep`r`n"
    'Perdition Sector/profiles/FO4ME/fallout4custom.ini'="[General]`r`nsIntroSequence=wrong.bk2`r`n"
    'Perdition Sector/profiles/FO4ME/fallout4prefs.ini'="[Display]`r`niSize W=1000`r`niSize H=800`r`nsD3DDevice=Old GPU`r`n[Other]`r`nkeep=yes`r`n"
    'Perdition Sector/profiles/FO4ME/settings.ini'="[General]`r`nLocalSettings=false`r`n"
    'Perdition Sector/profiles/FO4ME/saves/private.fos'='private save'
    'Perdition Sector/logs/private.log'='private log'
}
$package=Join-Path $work 'fixture.zip';Write-FixtureZip $package $files
$debugManifest=[pscustomobject]@{full_package_verification=$false}
Assert-Check (-not (Test-FullPackageVerificationEnabled $debugManifest)) 'Debug configuration disables the full archive test'
Assert-Check (Test-FullPackageVerificationEnabled ([pscustomobject]@{})) 'Release verification defaults on when no override exists'
Assert-Check (Test-FullPackageVerificationEnabled ([pscustomobject]@{full_package_verification=$true})) 'Release can explicitly enable the full archive test'
Assert-Rejected {Test-FullPackageVerificationEnabled ([pscustomobject]@{full_package_verification='false'})} 'Verification setting rejects ambiguous string values'
Invoke-PackageArchiveCheck -PackagePath (Join-Path $work 'does-not-exist.zip') -DistributionRoot (Join-Path $work 'no-tools') -Manifest $debugManifest
Assert-Check $true 'Disabled archive test does not open the ZIP or launch 7-Zip'
Invoke-PackageArchiveCheck -PackagePath $package -DistributionRoot $distribution -Manifest ([pscustomobject]@{})
Assert-Check $true 'Default release path still performs a real archive test'
$shipped=Get-Content -LiteralPath (Join-Path $distribution 'release.json') -Raw | ConvertFrom-Json
Assert-Check (-not (Test-FullPackageVerificationEnabled $shipped)) 'Shipped debug candidate skips the long archive test'
$steamArgs=@(New-SteamDepotArguments -DepotId '377161' -ManifestId '7497069378349273908' -GameRoot 'C:\Example Install\_Fallout4' -LoginId 123456 -SteamUser 'TEST_ACCOUNT')
Assert-Check ($steamArgs -contains '-username' -and $steamArgs -notcontains '-qr') 'Password login never sends the QR flag'
Assert-Check ($steamArgs[$steamArgs.IndexOf('-username')+1] -eq 'TEST_ACCOUNT') 'Password mode passes the Steam login name separately'
Assert-Check ($steamArgs[$steamArgs.IndexOf('-manifest')+1] -ceq '7497069378349273908') 'Steam manifest ID stays exact in the downloader command'
Assert-Check ($steamArgs -contains '-remember-password') 'Password mode can reuse the downloader session'
$qrArgs=@(New-SteamDepotArguments -DepotId '377161' -ManifestId '7497069378349273908' -GameRoot 'C:\Example Install\_Fallout4' -LoginId 123456 -SteamUser 'MUST_NOT_BE_SENT' -UseQr)
Assert-Check ($qrArgs -contains '-qr' -and $qrArgs -notcontains '-username') 'QR login never sends the conflicting username flag'
Assert-Check ($qrArgs -notcontains 'MUST_NOT_BE_SENT') 'QR login omits the username value even when one was supplied'
$qrNoName=@(New-SteamDepotArguments -DepotId '377161' -ManifestId '7497069378349273908' -GameRoot 'C:\Example Install\_Fallout4' -LoginId 123456 -UseQr)
Assert-Check ($qrNoName -contains '-qr') 'QR mode accepts an empty username'
Assert-Rejected {New-SteamDepotArguments -DepotId '377161' -ManifestId '7497069378349273908' -GameRoot 'C:\Example Install\_Fallout4' -LoginId 123456} 'Password mode requires a username'
$recorderSource=Join-Path $work 'RecordArguments.cs'
[IO.File]::WriteAllText($recorderSource,'using System; using System.Text; class RecordArguments { static void Main(string[] args) { foreach(string arg in args) Console.WriteLine(Convert.ToBase64String(Encoding.UTF8.GetBytes(arg))); } }')
$recorder=Join-Path $work 'RecordArguments.exe'
& (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /target:exe ('/out:'+$recorder) $recorderSource
if($LASTEXITCODE -ne 0){throw 'Argument recorder compilation failed'}
$received=@(& $recorder @qrArgs | ForEach-Object {[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_))})
Assert-Check (($received -join '|') -ceq ($qrArgs -join '|')) 'Native process receives the exact QR-mode command arguments'
$received=@(& $recorder @steamArgs | ForEach-Object {[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_))})
Assert-Check (($received -join '|') -ceq ($steamArgs -join '|')) 'Native process receives the exact password-mode command arguments'
$fakeSource=Join-Path $work 'FakeDepotDownloader.cs'
[IO.File]::WriteAllText($fakeSource,@'
using System;
using System.IO;
using System.Text;
class FakeDepotDownloader {
 static string Value(string[] args,string flag) { int i=Array.IndexOf(args,flag); return i>=0 && i+1<args.Length ? args[i+1] : ""; }
 static int Main(string[] args) {
  string[] encoded=Array.ConvertAll(args,a=>Convert.ToBase64String(Encoding.UTF8.GetBytes(a)));
  File.AppendAllText("calls.txt",String.Join("\t",encoded)+Environment.NewLine);
  bool qr=Array.IndexOf(args,"-qr")>=0;
  string user=Value(args,"-username"),depot=Value(args,"-depot");
  if(qr && user.Length>0) return 16;
  if(qr) File.WriteAllText("fixture-session.txt",File.ReadAllText("qr-account.txt"));
  else if(!File.Exists("fixture-session.txt") || !String.Equals(File.ReadAllText("fixture-session.txt"),user,StringComparison.OrdinalIgnoreCase)) return 17;
  if(File.Exists("fail-depot.txt") && File.ReadAllText("fail-depot.txt")==depot) return 23;
  return 0;
 }
}
'@)
$fakeDownloader=Join-Path $work 'FakeDepotDownloader.exe'
& (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /target:exe ('/out:'+$fakeDownloader) $fakeSource
if($LASTEXITCODE -ne 0){throw 'Fake downloader compilation failed'}
function Get-FixtureDepotCalls([string]$Session) {
    foreach($line in [IO.File]::ReadAllLines((Join-Path $Session 'calls.txt'))) {
        $values=@($line.Split("`t") | ForEach-Object {[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_))})
        $user='';if($values -contains '-username'){$user=$values[$values.IndexOf('-username')+1]}
        [pscustomobject]@{Qr=($values -contains '-qr');User=$user;Depot=$values[$values.IndexOf('-depot')+1];Manifest=$values[$values.IndexOf('-manifest')+1];LoginId=$values[$values.IndexOf('-loginid')+1];Remember=($values -contains '-remember-password');Validate=($values -contains '-validate')}
    }
}
$fakeSession=Join-Path $work 'Steam Session Fixture';[void][IO.Directory]::CreateDirectory($fakeSession)
[IO.File]::WriteAllText((Join-Path $fakeSession 'qr-account.txt'),'TEST_ACCOUNT')
$fakeGame=Join-Path $work 'Fake Game';$fakeStatePath=Join-Path $work 'steam-state.json'
$fakeState=@{stage='';completed_depots=@()}
$locationBefore=(Get-Location).Path
Invoke-SteamDepotDownloads -Downloader $fakeDownloader -Manifest $shipped -GameRoot $fakeGame -SessionRoot $fakeSession -SteamUser 'TEST_ACCOUNT' -UseQr -State $fakeState -StatePath $fakeStatePath
$calls=@(Get-FixtureDepotCalls $fakeSession)
Assert-Check ($calls.Count -eq 14) 'Session flow invokes every pinned depot'
Assert-Check ($calls[0].Qr -and -not $calls[0].User) 'Only the first package begins with QR authentication'
Assert-Check (@($calls | Where-Object {$_.Qr}).Count -eq 1) 'Fourteen-package installation requests QR exactly once'
Assert-Check (@($calls | Select-Object -Skip 1 | Where-Object {$_.Qr -or $_.User -ne 'TEST_ACCOUNT'}).Count -eq 0) 'Remaining thirteen packages select the remembered account by login name'
Assert-Check (@($calls | Where-Object {$_.Qr -and $_.User}).Count -eq 0) 'No package combines QR and username flags'
Assert-Check (@($calls | Where-Object {-not $_.Remember -or -not $_.Validate}).Count -eq 0) 'Every package retains remembered authentication and Steam file validation'
Assert-Check (@($calls.LoginId | Select-Object -Unique).Count -eq 1) 'One installation uses a stable Steam login ID'
Assert-Check (($calls.Depot -join '|') -ceq ($shipped.depots.depot -join '|')) 'All depot IDs remain in their configured order'
Assert-Check (($calls.Manifest -join '|') -ceq ($shipped.depots.manifest -join '|')) 'All manifest IDs reach the native downloader without precision loss'
Assert-Check ($fakeState.completed_depots.Count -eq 14) 'Only successful depots are marked completed'
Assert-Check ((Get-Location).Path -eq $locationBefore) 'Successful download sequence restores the caller location'
$hintPath=Join-Path $fakeSession 'remembered_account.json'
$hint=Get-Content -LiteralPath $hintPath -Raw | ConvertFrom-Json
Assert-Check (($hint.PSObject.Properties.Name | Sort-Object) -join '|' -eq 'account_name|product|updated_utc|user_context') 'Installer account hint contains no password or authentication token'
Assert-Check ($hint.account_name -eq 'TEST_ACCOUNT' -and $hint.user_context -match '^[0-9a-f]{64}$') 'Account hint is tied to this Windows user and computer'
[IO.File]::Delete((Join-Path $fakeSession 'calls.txt'))
Invoke-SteamDepotDownloads -Downloader $fakeDownloader -Manifest $shipped -GameRoot $fakeGame -SessionRoot $fakeSession -SteamUser 'test_account' -UseQr -State $fakeState -StatePath $fakeStatePath
$calls=@(Get-FixtureDepotCalls $fakeSession)
Assert-Check ($calls.Count -eq 14 -and @($calls | Where-Object {$_.Qr}).Count -eq 0) 'Retry reuses the saved account without QR, including different account-name casing'
$oneDepot=[pscustomobject]@{depots=@($shipped.depots[0])}
foreach($invalidHint in @('different-account','different-context','malformed')) {
    $hint=Get-Content -LiteralPath $hintPath -Raw | ConvertFrom-Json
    if($invalidHint -eq 'different-account'){$hint.account_name='OTHER_ACCOUNT'}
    if($invalidHint -eq 'different-context'){$hint.user_context='other-computer'}
    if($invalidHint -eq 'malformed'){[IO.File]::WriteAllText($hintPath,'invalid json')}
    else {$hint | ConvertTo-Json | Set-Content -LiteralPath $hintPath -Encoding UTF8}
    [IO.File]::Delete((Join-Path $fakeSession 'calls.txt'))
    Invoke-SteamDepotDownloads -Downloader $fakeDownloader -Manifest $oneDepot -GameRoot $fakeGame -SessionRoot $fakeSession -SteamUser 'TEST_ACCOUNT' -UseQr -State $fakeState -StatePath $fakeStatePath
    $calls=@(Get-FixtureDepotCalls $fakeSession)
    Assert-Check ($calls.Count -eq 1 -and $calls[0].Qr) ('Fresh QR is allowed for an unusable account hint: '+$invalidHint)
}
[IO.File]::Delete((Join-Path $fakeSession 'calls.txt'))
[IO.File]::WriteAllText((Join-Path $fakeSession 'fail-depot.txt'),[string]$shipped.depots[1].depot)
[IO.File]::WriteAllText((Join-Path $fakeGame 'retained-game-data.bin'),'preserve completed download')
$fakeState=@{stage='';completed_depots=@()}
Assert-Rejected {Invoke-SteamDepotDownloads -Downloader $fakeDownloader -Manifest $shipped -GameRoot $fakeGame -SessionRoot $fakeSession -SteamUser 'TEST_ACCOUNT' -UseQr -State $fakeState -StatePath $fakeStatePath} 'Download error stops the sequence and is reported'
Assert-Check (@(Get-FixtureDepotCalls $fakeSession).Count -eq 2 -and $fakeState.completed_depots.Count -eq 1) 'Failed depot is not marked complete and later depots do not start'
Assert-Check (-not [IO.File]::Exists($hintPath)) 'Failure clears only the installer account hint to allow fresh QR on retry'
Assert-Check ([IO.File]::Exists((Join-Path $fakeSession 'fixture-session.txt')) -and [IO.File]::ReadAllText((Join-Path $fakeGame 'retained-game-data.bin')) -eq 'preserve completed download') 'Failure preserves downloader session and downloaded game data'
Assert-Check ((Get-Location).Path -eq $locationBefore) 'Failed download sequence restores the caller location'
Assert-Rejected {Invoke-SteamDepotDownloads -Downloader $fakeDownloader -Manifest $shipped -GameRoot $fakeGame -SessionRoot $fakeSession -UseQr -State $fakeState -StatePath $fakeStatePath} 'Multi-package QR flow requires an account name for subsequent token reuse'
$reportedRequirement=[long]90297237453
$reportedPayload=$reportedRequirement-[long](45GB)
$required=Get-RequiredInstallBytes -PayloadBytes $reportedPayload
Assert-Check ($required -eq $reportedRequirement) 'Reported 90,297,237,453-byte disk requirement does not overflow'
Assert-Check ($required -is [long]) 'Disk-space result uses Int64'
Assert-Check ((Get-RequiredInstallBytes -PayloadBytes $reportedPayload -ExistingBytes ([long](10GB))) -eq ($reportedRequirement-[long](10GB))) 'Existing installation credit uses 64-bit arithmetic'
Assert-Check ((Get-RequiredInstallBytes -PayloadBytes $reportedPayload -ExistingBytes ([long](1TB))) -eq [long]0) 'Existing data cannot produce a negative required-space result'
Assert-Check ((Get-RequiredInstallBytes -PayloadBytes ([long](4TB))) -eq ([long](4TB)+[long](45GB))) 'Multi-terabyte sizes retain exact integer values'
Assert-Rejected {Get-RequiredInstallBytes -PayloadBytes -1} 'Negative payload byte count rejected'
Assert-Rejected {Get-RequiredInstallBytes -PayloadBytes 1 -ExistingBytes -1} 'Negative existing byte count rejected'
$normalPath=Assert-InstallPathPolicy 'C:\Perdition Sector'
Assert-Check ($normalPath -eq 'C:\Perdition Sector') 'C:\Perdition Sector is a valid installation location'
Assert-Check ((Assert-InstallPathPolicy 'C:\Perdition Sector\') -eq $normalPath) 'Trailing separator preserves a valid destination'
Assert-Check ((Assert-InstallPathPolicy 'C:\Folder\..\Perdition Sector') -eq $normalPath) 'Destination normalization preserves a valid folder'
Assert-Rejected {Assert-InstallPathPolicy 'C:\'} 'Drive root is rejected'
Assert-Rejected {Assert-InstallPathPolicy 'relative-folder'} 'Relative destination is rejected'
foreach($folder in @([Environment]::GetFolderPath('Windows'),[Environment]::GetFolderPath('ProgramFiles'),[Environment]::GetFolderPath('ProgramFilesX86'))) {
    if ($folder) {
        Assert-Rejected {Assert-InstallPathPolicy $folder} ('Protected folder rejected: '+$folder)
        Assert-Rejected {Assert-InstallPathPolicy (Join-Path $folder 'Perdition Sector')} ('Protected child rejected: '+$folder)
        Assert-Check ((Assert-InstallPathPolicy ($folder+' Backup\Perdition Sector')) -eq ($folder+' Backup\Perdition Sector')) ('Similar prefix remains allowed: '+$folder)
    }
}
$emptyTarget=Join-Path $work 'New Destination'
Assert-Check ((Assert-InstallDestination $emptyTarget ([IO.Path]::GetPathRoot($work))).Root -eq $emptyTarget) 'Setup at C:\ does not ban other C: destinations'
Assert-Check ((Assert-InstallDestination $emptyTarget $work).Root -eq $emptyTarget) 'Destination beneath the setup folder is allowed'
$setupOnly=Join-Path $work 'Setup Only';[void][IO.Directory]::CreateDirectory((Join-Path $setupOnly 'Core'))
foreach($name in @('PerditionSetup.exe','Setup.ps1','release.json','Core\Installer.psm1')) { [IO.File]::WriteAllText((Join-Path $setupOnly $name),'setup fixture') }
$before=@(Get-ChildItem -LiteralPath $setupOnly -Recurse -File).Count
Assert-Check ((Assert-InstallDestination $setupOnly $setupOnly).Root -eq $setupOnly) 'Installer may share a setup-only destination'
Assert-Check (@(Get-ChildItem -LiteralPath $setupOnly -Recurse -File).Count -eq $before) 'Destination validation creates no installation files'
$localPackage=Join-Path $setupOnly 'Baseline.zip';[IO.File]::Copy($package,$localPackage)
Assert-Check ((Assert-InstallDestination $setupOnly $setupOnly $localPackage).Root -eq $setupOnly) 'Selected package ZIP may remain beside setup'
[IO.File]::WriteAllText((Join-Path $setupOnly 'ModOrganizer.exe'),'existing game')
Assert-Rejected {Assert-InstallDestination $setupOnly $setupOnly $localPackage} 'Existing MO2 build rejected even beside setup'
[IO.File]::Delete((Join-Path $setupOnly 'ModOrganizer.exe'))
[void][IO.Directory]::CreateDirectory((Join-Path $setupOnly 'mods'))
Assert-Rejected {Assert-InstallDestination $setupOnly $setupOnly $localPackage} 'Existing mods folder rejected without installer ownership'
$info=Get-PackageInformation $package
Assert-Check ($info.Mods.Count -eq 2) 'Enabled mod selection follows the profile'
$target=Join-Path $work 'Install With Spaces';[void][IO.Directory]::CreateDirectory($target)
Expand-PerditionPackage $package $target $info
Expand-PerditionPackage $package $target $info
Assert-Check ([IO.File]::Exists((Join-Path $target 'overwrite\Perdition Sector World.esp'))) 'Repeated extraction safely replaces installer files'
Assert-Check ([IO.File]::Exists((Join-Path $target 'mods\Live\Live.esp'))) 'Runtime mod extracted'
Assert-Check ([IO.File]::Exists((Join-Path $target 'overwrite\Scripts\PSRadioQuestScript.pex'))) 'Compiled gameplay script extracted'
Assert-Check (-not [IO.File]::Exists((Join-Path $target 'CreationKit.exe'))) 'Creation Kit excluded'
Assert-Check (-not [IO.Directory]::Exists((Join-Path $target 'tools'))) 'Development tools excluded'
Assert-Check (-not [IO.File]::Exists((Join-Path $target 'ModOrganizer.ini'))) 'Original MO2 account configuration excluded'
Assert-Check (-not [IO.Directory]::Exists((Join-Path $target 'mods\Disabled'))) 'Disabled mods excluded'
Assert-Check (-not [IO.Directory]::Exists((Join-Path $target 'mods\F4SE\f4se_0_06_23'))) 'Extender development source excluded'
Assert-Check (-not [IO.Directory]::Exists((Join-Path $target 'profiles\FO4ME\saves'))) 'Personal saves excluded'
Assert-Check (-not [IO.Directory]::Exists((Join-Path $target 'overwrite\Scripts\Source'))) 'Papyrus source excluded from player installation'
New-MO2Configuration $target 2560 1440
$config=[IO.File]::ReadAllText((Join-Path $target 'ModOrganizer.ini'))
Assert-Check ($config.Contains(($target.Replace('\','/')+'/_Fallout4/f4se_loader.exe'))) 'F4SE path generated for the chosen folder'
Assert-Check (-not $config.Contains('Creation Kit')) 'Player executable menu excludes Creation Kit'
Assert-Check ($config.Contains('size=3')) 'Player executable menu contains three entries'
$prefs=[IO.File]::ReadAllText((Join-Path $target 'profiles\FO4ME\fallout4prefs.ini'))
Assert-Check ($prefs.Contains('iSize W=2560') -and $prefs.Contains('iSize H=1440')) 'Chosen resolution applied'
Assert-Check (-not $prefs.Contains('Old GPU')) 'Original GPU name removed'
Assert-Check ($prefs.Contains('keep=yes')) 'Unrelated display profile settings preserved'
$grass=[regex]::Match($prefs,'(?ms)^\[Grass\]\r?\n(.*?)(?=^\[|\z)').Groups[1].Value
Assert-Check ($grass -match '(?m)^fGrassStartFadeDistance=7000\r?$' -and $grass -match '(?m)^fGrassMaxStartFadeDistance=7000\.0000\r?$' -and $grass -match '(?m)^fGrassMinStartFadeDistance=7000\.0000\r?$') 'Missing True Grass section receives all three required fade distances'
Set-IniValue (Join-Path $target 'profiles\FO4ME\fallout4prefs.ini') 'Grass' 'fGrassStartFadeDistance' '500'
Set-IniValue (Join-Path $target 'profiles\FO4ME\fallout4prefs.ini') 'Grass' 'fGrassMaxStartFadeDistance' '1000'
Set-IniValue (Join-Path $target 'profiles\FO4ME\fallout4prefs.ini') 'Grass' 'fGrassMinStartFadeDistance' '0'
New-MO2Configuration $target 2560 1440
$prefs=[IO.File]::ReadAllText((Join-Path $target 'profiles\FO4ME\fallout4prefs.ini'))
Assert-Check ($prefs.Contains('fGrassStartFadeDistance=7000') -and $prefs.Contains('fGrassMaxStartFadeDistance=7000.0000') -and $prefs.Contains('fGrassMinStartFadeDistance=7000.0000')) 'Reconfiguration repairs stale grass distances in the selected MO2 profile'
Assert-Check ([IO.File]::ReadAllText((Join-Path $target 'profiles\FO4ME\settings.ini')).Contains('LocalSettings=true')) 'Profile-specific game INIs remain enabled'
$custom=[IO.File]::ReadAllText((Join-Path $target 'profiles\FO4ME\fallout4custom.ini'))
Assert-Check ($custom.Contains('sIntroSequence=GameIntro_V3_B.bk2') -and $custom.Contains('fChancesToPlayAlternateIntro=0.0000')) 'Startup fixes carried into the player profile'
Assert-Check ([IO.File]::ReadAllText((Join-Path $target 'Launcher\Start-Perdition.ps1')).Contains('moshortcut://:F4SE')) 'Game launcher preserves MO2 virtualization'
Assert-Check ([IO.File]::ReadAllText((Join-Path $target 'Launch Perdition Sector.cmd')).Contains('Launcher\Start-Perdition.ps1')) 'Game launcher calls the approved splash helper'
Assert-Check ([IO.File]::ReadAllText((Join-Path $target 'ModOrganizer.ini')).Contains('use_splash=false')) 'MO2 duplicate splash is disabled'
Assert-Rejected {Get-SafeChildPath $target '..\escape.txt'} 'Parent traversal rejected'
Assert-Rejected {Get-SafeChildPath $target 'C:\escape.txt'} 'Absolute paths rejected'
Assert-Rejected {Get-SafeChildPath $target 'safe.txt:stream'} 'NTFS alternate data stream paths rejected'
$malicious=Join-Path $work 'malicious.zip';Write-FixtureZip $malicious @{'../escape.txt'='bad'}
Assert-Rejected {Expand-CheckedZip $malicious (Join-Path $work 'Safe')} 'ZIP traversal rejected during extraction'
Assert-Check (-not [IO.File]::Exists((Join-Path $work 'escape.txt'))) 'Rejected archive wrote no escaped file'
$overlay=Join-Path $work 'overlay.zip'
Write-FixtureZip $overlay @{'Shared/CustomControlMap.txt'='bindings';'ENB/d3d11.dll'='known enb hook';'ENB/enbseries/shader.fx'='shader'}
$game=Join-Path $target '_Fallout4';[void][IO.Directory]::CreateDirectory($game)
Install-GameRootOverlay $overlay $game $false
Assert-Check ([IO.File]::Exists((Join-Path $game 'CustomControlMap.txt'))) 'Shared controls installed with ENB disabled'
Assert-Check (-not [IO.File]::Exists((Join-Path $game 'd3d11.dll'))) 'ENB disabled option installs no hook'
Install-GameRootOverlay $overlay $game $true
Assert-Check ([IO.File]::Exists((Join-Path $game 'd3d11.dll')) -and [IO.File]::Exists((Join-Path $game 'enbseries\shader.fx'))) 'ENB enabled option installs hook and shaders'
Install-GameRootOverlay $overlay $game $false
Assert-Check (-not [IO.File]::Exists((Join-Path $game 'd3d11.dll')) -and [IO.File]::Exists((Join-Path $target 'Optional\ENB\d3d11.dll'))) 'Reconfiguration safely deactivates the known ENB hook'
[IO.File]::WriteAllText((Join-Path $game 'd3d11.dll'),'custom unknown hook')
Assert-Rejected {Install-GameRootOverlay $overlay $game $false} 'Unknown hook is preserved'
$release=Get-Content -LiteralPath (Join-Path $distribution 'release.json') -Raw | ConvertFrom-Json
Assert-Check ($release.depots.Count -eq 14) 'All fourteen Steam depots present'
Assert-Check (@($release.depots | Where-Object {$_.manifest -isnot [string]}).Count -eq 0) 'Manifest IDs retain exact string precision'
Assert-Check (-not $release.default_enb_enabled) 'ENB defaults to disabled'
$existing=Join-Path $work 'Existing Project';[void][IO.Directory]::CreateDirectory($existing)
[IO.File]::WriteAllText((Join-Path $existing 'valuable.txt'),'preserve')
Assert-Rejected {Invoke-PerditionInstallation -InstallRoot $existing -PackagePath $package -SteamUser 'fixture' -DistributionRoot $distribution} 'Existing project folder cannot become an install target'
Assert-Check ([IO.File]::ReadAllText((Join-Path $existing 'valuable.txt')) -eq 'preserve') 'Rejected installation preserved the existing folder'
$cache=Join-Path $work 'Multipart Cache';[void][IO.Directory]::CreateDirectory($cache)
$packageBytes=[IO.File]::ReadAllBytes($package)
$partSize=[int][Math]::Ceiling($packageBytes.Length/3)
$parts=@();$sha=[Security.Cryptography.SHA256]::Create()
for($offset=0;$offset -lt $packageBytes.Length;$offset+=$partSize) {
    $size=[Math]::Min($partSize,$packageBytes.Length-$offset);$bytes=New-Object byte[] $size
    [Array]::Copy($packageBytes,$offset,$bytes,0,$size)
    $name='payload.zip.'+($parts.Count+1).ToString('000')
    [IO.File]::WriteAllBytes((Join-Path $cache $name),$bytes)
    $parts += @{filename=$name;sha256=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant();bytes=$size;url=('https://example.invalid/'+$name)}
}
$archiveHash=(Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash.ToLowerInvariant()
$source=@{archive_name='payload.zip';archive_sha256=$archiveHash;archive_bytes=$packageBytes.Length;parts=$parts}
$sourcePath=Join-Path $work 'package_source.json';$source | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $sourcePath -Encoding UTF8
@{product='PerditionPackageCache';archive_sha256=$archiveHash} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $cache 'perdition_download_cache.json') -Encoding UTF8
$joined=Resolve-OnlinePackage $sourcePath $cache
Assert-Check ((Get-FileHash -LiteralPath $joined -Algorithm SHA256).Hash -eq $archiveHash) 'Verified cached download parts assembled correctly'
Assert-Check (@(Get-ChildItem -LiteralPath $cache -Filter 'payload.zip.0*' -File).Count -eq 0) 'Completed archive retained without duplicate part storage'
Assert-Check ((Resolve-OnlinePackage $sourcePath $cache) -eq $joined) 'Completed package cache reused without a download'
$source.archive_bytes++;$source | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $sourcePath -Encoding UTF8
Assert-Rejected {Resolve-OnlinePackage $sourcePath $cache} 'Inconsistent online package sizes rejected before downloading'
$sha.Dispose()
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class TestWindowsArguments {
 [DllImport("shell32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr CommandLineToArgvW(string value,out int count);
 [DllImport("kernel32.dll")] public static extern IntPtr LocalFree(IntPtr value);
}
'@
$values=@('C:\Path With Spaces\','name&text','value"quoted','',"O'Name",'C:\trailing\\')
$command='fixture.exe '+(($values | ForEach-Object {ConvertTo-WindowsArgument $_}) -join ' ')
$argc=0;$argv=[TestWindowsArguments]::CommandLineToArgvW($command,[ref]$argc)
try {
    Assert-Check ($argc -eq ($values.Count+1)) 'Windows command line preserves argument count'
    for($i=0;$i -lt $values.Count;$i++) {
        $pointer=[Runtime.InteropServices.Marshal]::ReadIntPtr($argv,($i+1)*[IntPtr]::Size)
        $value=[Runtime.InteropServices.Marshal]::PtrToStringUni($pointer)
        Assert-Check ($value -ceq $values[$i]) ('Windows argument round trip '+$i)
    }
} finally {[void][TestWindowsArguments]::LocalFree($argv)}
$exportTools=Join-Path $work 'Export Tools';[void][IO.Directory]::CreateDirectory($exportTools)
[void][IO.Directory]::CreateDirectory((Join-Path $exportTools 'Core'))
[void][IO.Directory]::CreateDirectory((Join-Path $exportTools 'Tools'))
foreach($name in @('Build-Payload.ps1')) {[IO.File]::Copy((Join-Path $distribution $name),(Join-Path $exportTools $name))}
[IO.File]::Copy((Join-Path $distribution 'Core\Installer.psm1'),(Join-Path $exportTools 'Core\Installer.psm1'))
foreach($name in @('7z.exe','7z.dll')) {[IO.File]::Copy((Join-Path $distribution ('Tools\'+$name)),(Join-Path $exportTools ('Tools\'+$name)))}
@{version='0.1.0';world_plugin_sha256=$info.WorldHash} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $exportTools 'release.json') -Encoding UTF8
$export=Join-Path $work 'Exported Player Release'
& (Join-Path $exportTools 'Build-Payload.ps1') -SourceZip $package -OutputDirectory $export -PartBytes 1024
$exported=Get-PackageInformation (Join-Path $export 'Perdition_Payload_v0.1.0.zip')
Assert-Check ($exported.Files -eq $info.Files) 'Player package exporter preserves the selected runtime file set'
$published=Get-Content -LiteralPath (Join-Path $export 'package_source.pending.json') -Raw | ConvertFrom-Json
Assert-Check (@($published.parts).Count -gt 1 -and @($published.parts | Where-Object {$_.bytes -gt 1024}).Count -eq 0) 'Release exporter creates bounded download parts'
Assert-Check ($published.archive_sha256 -eq (Get-FileHash -LiteralPath (Join-Path $export 'Perdition_Payload_v0.1.0.zip')).Hash.ToLowerInvariant()) 'Exported manifest checksum matches the final player archive'
$summary=[ordered]@{passed=$script:Passed;failed=0;fixture_directory=$work;tested_utc=[DateTime]::UtcNow.ToString('o');live_steam_installation='not performed'}
$summary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'test_results.json') -Encoding UTF8
$summary | ConvertTo-Json
