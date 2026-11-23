$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$distribution=Split-Path -Parent $PSScriptRoot
$module=Import-Module (Join-Path $distribution 'Core\Installer.psm1') -Force -PassThru
$work=Join-Path ([IO.Path]::GetTempPath()) ('Perdition Steam Batch Tests '+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($work)
$script:Passed=0
function Check([bool]$Value,[string]$Name) { if (-not $Value) { throw ('FAILED: '+$Name) };$script:Passed++;Write-Host ('PASS: '+$Name) }
function Reject([scriptblock]$Action,[string]$Name) { $failed=$false;try { & $Action } catch { $failed=$true };Check $failed $Name }
$recipe=Get-Content -LiteralPath (Join-Path $distribution 'release.json') -Raw | ConvertFrom-Json
$source=Join-Path $work 'FakeDownloader.cs'
[IO.File]::WriteAllText($source,@'
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
[assembly:System.Reflection.AssemblyFileVersion("1.10.163.0")]
class FakeDownloader {
 static string Value(string[] args,string flag) { int i=Array.IndexOf(args,flag);return i>=0 && i+1<args.Length ? args[i+1] : ""; }
 static List<string> Values(string[] args,string flag) {
  var values=new List<string>();int i=Array.IndexOf(args,flag);
  if(i>=0) for(i++;i<args.Length && !args[i].StartsWith("-");i++) values.Add(args[i]);
  return values;
 }
 static int Main(string[] args) {
  var encoded=Array.ConvertAll(args,a=>Convert.ToBase64String(Encoding.UTF8.GetBytes(a)));
  File.AppendAllText("calls.txt",String.Join("\t",encoded)+Environment.NewLine);
  var depots=Values(args,"-depot");var manifests=Values(args,"-manifest");
  if(depots.Count==0 || depots.Count!=manifests.Count) return 11;
  bool qr=Array.IndexOf(args,"-qr")>=0;
  string user=Value(args,"-username");
  if(qr && user.Length>0) return 16;
  if(!qr && user.Length==0) return 17;
  if(qr) File.AppendAllText("qr-events.txt","one QR authentication\n");
  File.WriteAllText("fixture-session.txt","downloader-owned token fixture");
  File.WriteAllText(Path.Combine(Value(args,"-dir"),"partial-download.bin"),"keep completed chunks");
  if(File.Exists("fail-request.txt")) return 23;
  return 0;
 }
}
'@)
$downloader=Join-Path $work 'FakeDownloader.exe'
& (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /target:exe ('/out:'+$downloader) $source
if($LASTEXITCODE -ne 0){throw 'Downloader fixture compilation failed.'}
$game=Join-Path $work 'Fallout With Spaces'
$session=Join-Path $work 'Steam Session'
[void][IO.Directory]::CreateDirectory($game)
[void][IO.Directory]::CreateDirectory($session)
[IO.File]::Copy($downloader,(Join-Path $game 'Fallout4.exe'))
$required=& $module { $script:RequiredGameFiles }
foreach($name in $required) {
 $path=Join-Path $game $name
 [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))
 [IO.File]::WriteAllText($path,'fixture game asset')
}
function Read-Calls {
 foreach($line in [IO.File]::ReadAllLines((Join-Path $session 'calls.txt'))) {
  $values=@($line.Split("`t") | ForEach-Object {[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_))})
  $depotIndex=$values.IndexOf('-depot');$manifestIndex=$values.IndexOf('-manifest');$dirIndex=$values.IndexOf('-dir')
  [pscustomobject]@{Values=$values;Qr=($values -contains '-qr');Depots=@($values[($depotIndex+1)..($manifestIndex-1)]);Manifests=@($values[($manifestIndex+1)..($dirIndex-1)])}
 }
}
$state=@{stage='';completed_depots=@()};$statePath=Join-Path $work 'state.json'
$locationBefore=(Get-Location).Path
# Deliberately leave a stale legacy hint and no actual downloader token.
# The old installer trusted the hint, disabled QR, then asked for a password.
$hint=Join-Path $session 'remembered_account.json'
[IO.File]::WriteAllText($hint,'{"product":"PerditionSteamSession","account_name":"STALE_ACCOUNT","user_context":"stale"}')
$hintBefore=[IO.File]::ReadAllText($hint)
Invoke-SteamDepotDownloads -Downloader $downloader -Manifest $recipe -GameRoot $game -SessionRoot $session -UseQr -State $state -StatePath $statePath
$calls=@(Read-Calls)
Check ($calls.Count -eq 1) 'All fourteen depots share one native downloader process'
Check ($calls[0].Qr -and $calls[0].Values -notcontains '-username') 'Stale account hint cannot turn QR into password login'
Check ($calls[0].Values -notcontains '-password') 'QR command contains no password flag'
Check (($calls[0].Depots -join '|') -ceq ($recipe.depots.depot -join '|')) 'All fourteen depot IDs retain their order'
Check (($calls[0].Manifests -join '|') -ceq ($recipe.depots.manifest -join '|')) 'All fourteen manifest IDs retain exact precision and pairing'
Check ($calls[0].Values -contains '-validate' -and $calls[0].Values -contains '-remember-password') 'Single session retains file validation and downloader-managed persistence'
Check (@([IO.File]::ReadAllLines((Join-Path $session 'qr-events.txt'))).Count -eq 1) 'One batch requests one QR authentication'
Check ($state.completed_depots.Count -eq 14) 'Successful verified batch marks all fourteen depots complete'
Check ((Get-Location).Path -eq $locationBefore) 'Successful batch restores caller location'
Check ([IO.File]::ReadAllText($hint) -ceq $hintBefore) 'Legacy installer hint is ignored and left untouched'
Check ((Resolve-GameInstallPlan -InstallRoot $work -UseQr).DownloadSteam) 'QR game selection works without a login name'

[IO.File]::Delete((Join-Path $session 'calls.txt'))
[IO.File]::WriteAllText((Join-Path $session 'fail-request.txt'),'simulate authentication loss')
$state=@{stage='';completed_depots=@('legacy-completed')};$failure=''
try { Invoke-SteamDepotDownloads -Downloader $downloader -Manifest $recipe -GameRoot $game -SessionRoot $session -SteamUser 'MUST_NOT_BE_SENT' -UseQr -State $state -StatePath $statePath } catch { $failure=$_.Exception.Message }
Check ($failure.Contains('fresh QR code') -and $failure.Contains('No Steam password is needed')) 'Authentication failure explains fresh QR recovery'
Check (@(Read-Calls).Count -eq 1 -and $state.completed_depots.Count -eq 0) 'Failed batch stops without inventing completed depots'
Check ((Read-Calls).Values -notcontains 'MUST_NOT_BE_SENT') 'QR mode never sends a typed login name'
Check ([IO.File]::ReadAllText((Join-Path $game 'partial-download.bin')) -eq 'keep completed chunks') 'Failed batch retains downloaded game data'
Check ([IO.File]::ReadAllText((Join-Path $session 'fixture-session.txt')) -eq 'downloader-owned token fixture') 'Failed batch retains downloader-owned credentials'
Check ((Get-Location).Path -eq $locationBefore) 'Failed batch restores caller location'
[IO.File]::Delete((Join-Path $session 'fail-request.txt'))
[IO.File]::Delete((Join-Path $session 'calls.txt'))
Invoke-SteamDepotDownloads -Downloader $downloader -Manifest $recipe -GameRoot $game -SessionRoot $session -UseQr -State $state -StatePath $statePath
Check (@(Read-Calls).Count -eq 1 -and (Read-Calls).Qr) 'Resume after authentication failure requests fresh QR even with saved credentials'
Check ($state.completed_depots.Count -eq 14) 'Resumed batch completes normally'

[IO.File]::Delete((Join-Path $game 'Data\DLCNukaWorld.esm'))
$state=@{stage='';completed_depots=@()}
Reject {Invoke-SteamDepotDownloads -Downloader $downloader -Manifest $recipe -GameRoot $game -SessionRoot $session -UseQr -State $state -StatePath $statePath} 'Native success cannot hide a missing DLC'
Check ($state.completed_depots.Count -eq 0) 'Incomplete game is never marked verified'
[IO.File]::WriteAllText((Join-Path $game 'Data\DLCNukaWorld.esm'),'restored fixture')

Reject {New-SteamDepotArguments -DepotId @('1','2') -ManifestId @('3') -UseQr} 'Mismatched depot and manifest counts fail before authentication'
Reject {New-SteamDepotArguments -DepotId @('1','1') -ManifestId @('3','4') -UseQr} 'Duplicate depots are rejected'
Reject {New-SteamDepotArguments -DepotId @('1','-username') -ManifestId @('3','4') -UseQr} 'Unexpected argument text cannot enter the depot list'
Reject {New-SteamDepotArguments -DepotId @() -ManifestId @() -UseQr} 'Empty depot batch is rejected'
Reject {Invoke-SteamDepotDownloads -Downloader $downloader -Manifest $recipe -GameRoot $game -SessionRoot $session -State $state -StatePath $statePath} 'Password mode still requires an explicit login name'
$passwordArgs=@(New-SteamDepotArguments -DepotId @($recipe.depots.depot) -ManifestId @($recipe.depots.manifest) -GameRoot $game -LoginId 123456 -SteamUser 'fixture')
Check ($passwordArgs -contains '-username' -and $passwordArgs -notcontains '-qr') 'Explicit password mode remains available'
$result=[ordered]@{passed=$script:Passed;failed=0;fixture_directory=$work;tested_utc=[DateTime]::UtcNow.ToString('o');live_steam_installation='not performed'}
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'steam_session_results.json') -Encoding UTF8
$result | ConvertTo-Json
