$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$distribution=Split-Path -Parent $PSScriptRoot
$module=Import-Module (Join-Path $distribution 'Core\Installer.psm1') -Force -PassThru
$work=Join-Path ([IO.Path]::GetTempPath()) ('Perdition Steam Recovery '+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($work)
$script:Passed=0
function Check([bool]$Value,[string]$Name) { if (-not $Value) { throw ('FAILED: '+$Name) };$script:Passed++;Write-Host ('PASS: '+$Name) }
$recipe=Get-Content -LiteralPath (Join-Path $distribution 'release.json') -Raw | ConvertFrom-Json
$source=Join-Path $work 'RecoveryDownloader.cs'
[IO.File]::WriteAllText($source,@'
using System;
using System.IO;
using System.Text;
using System.Threading;
[assembly:System.Reflection.AssemblyFileVersion("1.10.163.0")]
class RecoveryDownloader {
 static string Value(string[] args,string flag) { int i=Array.IndexOf(args,flag);return i>=0 && i+1<args.Length ? args[i+1] : ""; }
 static void LoggedOn(bool qr) {
  if(qr) Console.WriteLine("Success! Next time you can login with -username TEST_ACCOUNT -remember-password instead of -qr.");
  else Console.WriteLine("Logging 'TEST_ACCOUNT' into Steam3...");
  Console.WriteLine(" Done!");
  Console.WriteLine("Using Steam3 suggested CellID: 2");
  Console.WriteLine("Got 295 licenses for account!");
  Console.WriteLine("Got AppInfo for 377160");
 }
 static int PollFailure() {
  Console.Error.WriteLine("Failed to authenticate with Steam: Failed to poll status with result FileNotFound.");
  Console.WriteLine("A task was canceled.");Console.WriteLine("Disconnected from Steam");return 1;
 }
 static int Main(string[] args) {
  var encoded=Array.ConvertAll(args,a=>Convert.ToBase64String(Encoding.UTF8.GetBytes(a)));
  File.AppendAllText("calls.txt",String.Join("\t",encoded)+Environment.NewLine);
  int count=File.ReadAllLines("calls.txt").Length;
  bool qr=Array.IndexOf(args,"-qr")>=0;
  string scenario=File.ReadAllText("scenario.txt"),user=Value(args,"-username");
  File.WriteAllText(Path.Combine(Value(args,"-dir"),"partial-download.bin"),"retained game data");
  if(qr) {
   if(user.Length>0)return 91;
   Console.WriteLine("Use the Steam Mobile App to sign in with this QR code:");
   Console.WriteLine("\u2588\u2580\u2584");
   if(scenario=="always-expired" || (scenario=="qr-expired" && count==1))return PollFailure();
   File.WriteAllText("fixture-token.txt","private-token-fixture-must-not-be-logged");
   LoggedOn(true);
   if(scenario=="poll-race" || (scenario=="race-token-revoked" && count==1))return PollFailure();
  } else {
   if(user!="TEST_ACCOUNT")return 92;
   if(!File.Exists("fixture-token.txt")) {
    Console.Write("Enter account password for \"TEST_ACCOUNT\": ");
    if(Console.ReadLine()==null)File.WriteAllText("stdin-closed.txt","yes");
    Console.WriteLine();Console.Out.Flush();
    Thread.Sleep(15000);return 93;
   }
   if(scenario=="rejected-token" || scenario=="race-token-revoked") {
    File.Delete("fixture-token.txt");Console.WriteLine("Access token was rejected (Expired).");return 1;
   }
   LoggedOn(false);
  }
  if(scenario=="network-error") {Console.WriteLine("Connection timeout downloading depot manifest.");return 23;}
  return 0;
 }
}
'@)
$downloader=Join-Path $work 'RecoveryDownloader.exe'
& (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /target:exe ('/out:'+$downloader) $source
if($LASTEXITCODE -ne 0){throw 'Recovery fixture compilation failed'}
$game=Join-Path $work 'Fallout With Spaces'
[void][IO.Directory]::CreateDirectory($game)
[IO.File]::Copy($downloader,(Join-Path $game 'Fallout4.exe'))
foreach($name in (& $module {$script:RequiredGameFiles})) {
 $path=Join-Path $game $name
 [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))
 [IO.File]::WriteAllText($path,'fixture game asset')
}
$context=& $module {Get-SteamSessionContext}
function Run-Case([string]$Scenario,[switch]$Hint,[switch]$Token) {
 $session=Join-Path $work $Scenario
 [void][IO.Directory]::CreateDirectory($session)
 [IO.File]::WriteAllText((Join-Path $session 'scenario.txt'),$Scenario)
 if($Hint) {
  @{product='PerditionSteamSession';account_name='TEST_ACCOUNT';user_context=$context} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $session 'remembered_account.json') -Encoding UTF8
 }
 if($Token){[IO.File]::WriteAllText((Join-Path $session 'fixture-token.txt'),'private-token-fixture-must-not-be-logged')}
 $state=@{stage='';completed_depots=@()};$message=''
 $captured=New-Object IO.StringWriter
 $console=[Console]::Out
 $clock=[Diagnostics.Stopwatch]::StartNew()
 try {
  [Console]::SetOut($captured)
  try { Invoke-SteamDepotDownloads -Downloader $downloader -Manifest $recipe -GameRoot $game -SessionRoot $session -UseQr -State $state -StatePath (Join-Path $session 'state.json') }
  catch { $message=$_.Exception.Message }
 } finally {[Console]::SetOut($console);$clock.Stop()}
 $calls=@(foreach($line in [IO.File]::ReadAllLines((Join-Path $session 'calls.txt'))) {
  $values=@($line.Split("`t") | ForEach-Object {[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_))})
  $di=$values.IndexOf('-depot');$mi=$values.IndexOf('-manifest');$dir=$values.IndexOf('-dir')
  [pscustomobject]@{Values=$values;Qr=($values -contains '-qr');User=if($values -contains '-username'){$values[$values.IndexOf('-username')+1]}else{''};Depots=@($values[($di+1)..($mi-1)]);Manifests=@($values[($mi+1)..($dir-1)]);LoginId=$values[$values.IndexOf('-loginid')+1]}
 })
 return [pscustomobject]@{Session=$session;Calls=$calls;Error=$message;State=$state;Output=$captured.ToString();Seconds=$clock.Elapsed.TotalSeconds}
}
$fresh=Run-Case 'fresh'
Check (-not $fresh.Error -and $fresh.Calls.Count -eq 1 -and $fresh.Calls[0].Qr) 'Fresh install uses one QR process for every package'
Check ($fresh.Output.Contains([string][char]0x2588+[char]0x2580+[char]0x2584)) 'Live process forwarding preserves Unicode QR graphics'
Check ($fresh.State.completed_depots.Count -eq 14) 'Fresh QR run verifies all fourteen depots'
$hint=Get-Content -LiteralPath (Join-Path $fresh.Session 'remembered_account.json') -Raw | ConvertFrom-Json
Check ($hint.account_name -eq 'TEST_ACCOUNT' -and $hint.user_context -eq $context) 'Successful Steam account is remembered for this Windows user'
Check (($hint.PSObject.Properties.Name | Sort-Object) -join '|' -eq 'account_name|product|updated_utc|user_context') 'Installer hint contains no password or token'

$race=Run-Case 'poll-race'
Check (-not $race.Error -and $race.Calls.Count -eq 2) 'Reported post-login FileNotFound poll failure recovers automatically'
Check ($race.Calls[0].Qr -and -not $race.Calls[1].Qr -and $race.Calls[1].User -eq 'TEST_ACCOUNT') 'Recovery uses the successfully authenticated account token'
Check (@($race.Calls | Where-Object {$_.Qr}).Count -eq 1) 'Post-login polling race needs only one QR authentication'
Check ($race.State.completed_depots.Count -eq 14) 'Recovered token process verifies the complete game and DLC batch'
Check (@($race.Calls.LoginId | Select-Object -Unique).Count -eq 1) 'Recovery retains one Steam login ID'
Check (@($race.Calls | Where-Object {($_.Depots -join '|') -cne ($recipe.depots.depot -join '|') -or ($_.Manifests -join '|') -cne ($recipe.depots.manifest -join '|')}).Count -eq 0) 'Every recovery attempt preserves all exact depot and manifest pairs'

$stale=Run-Case 'no-token' -Hint
Check (-not $stale.Error -and $stale.Calls.Count -eq 2) 'Stale account hint without a real token falls back to QR'
Check (-not $stale.Calls[0].Qr -and $stale.Calls[1].Qr) 'A missing token triggers fresh QR rather than interactive password login'
Check ([IO.File]::Exists((Join-Path $stale.Session 'stdin-closed.txt'))) 'Token attempt receives closed standard input'
Check (-not $stale.Output.Contains('Enter account password')) 'No password prompt reaches the user in QR mode'
Check ($stale.Seconds -lt 10) 'Missing-token child is stopped without waiting for user input'

$rejected=Run-Case 'rejected-token' -Hint -Token
Check (-not $rejected.Error -and $rejected.Calls.Count -eq 2 -and $rejected.Calls[1].Qr) 'Rejected saved token automatically requests fresh QR'
Check ($rejected.State.completed_depots.Count -eq 14) 'Fresh QR after token rejection completes the batch'
$saved=Run-Case 'valid-token' -Hint -Token
Check (-not $saved.Error -and $saved.Calls.Count -eq 1 -and -not $saved.Calls[0].Qr) 'A valid remembered session resumes without any QR scan'

$expired=Run-Case 'qr-expired'
Check (-not $expired.Error -and $expired.Calls.Count -eq 2) 'QR expiration before successful authentication receives one automatic fresh code'
Check (@($expired.Calls | Where-Object {$_.Qr}).Count -eq 2) 'Expired QR is retried in QR mode'
$bounded=Run-Case 'always-expired'
Check ($bounded.Error.Contains('Steam download or verification stopped') -and $bounded.Calls.Count -eq 2) 'Repeated authentication failures stop after two QR attempts'
Check ($bounded.State.completed_depots.Count -eq 0) 'Failed authentication cannot mark a depot completed'
Check ([IO.File]::ReadAllText((Join-Path $game 'partial-download.bin')) -eq 'retained game data') 'Repeated authentication failure retains partial game files'

$network=Run-Case 'network-error'
Check ($network.Error -and $network.Calls.Count -eq 1) 'A depot network error is not treated as a fresh-login request'
Check ($network.State.completed_depots.Count -eq 0) 'Failed download remains incomplete'
$revoked=Run-Case 'race-token-revoked'
Check (-not $revoked.Error -and $revoked.Calls.Count -eq 3) 'Post-login poll failure followed by token rejection recovers with fresh QR'
Check ($revoked.Calls[0].Qr -and -not $revoked.Calls[1].Qr -and $revoked.Calls[2].Qr) 'Recovery sequence keeps token and QR modes mutually exclusive'

foreach($case in @($fresh,$race,$stale,$rejected,$saved,$expired,$bounded,$network,$revoked)) {
 Check (-not $case.Output.Contains('private-token-fixture-must-not-be-logged')) ('Credentials are not logged: '+[IO.Path]::GetFileName($case.Session))
 Check (@($case.Calls | Where-Object {$_.Values -contains '-password' -or ($_.Qr -and $_.Values -contains '-username') -or $_.Values -notcontains '-validate'}).Count -eq 0) ('Safe authentication arguments and file validation: '+[IO.Path]::GetFileName($case.Session))
}
$summary=[ordered]@{passed=$script:Passed;failed=0;fixture_directory=$work;reported_failure_reproduced_and_recovered=$true;live_steam_download='not performed';tested_utc=[DateTime]::UtcNow.ToString('o')}
$summary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'steam_recovery_results.json') -Encoding UTF8
$summary | ConvertTo-Json
