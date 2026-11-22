$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$distribution=Split-Path -Parent $PSScriptRoot
$module=Import-Module (Join-Path $distribution 'Core\Updates.psm1') -Force -PassThru
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$work=Join-Path ([IO.Path]::GetTempPath()) ('Perdition Update Tests '+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($work)
$script:Passed=0
function Check([bool]$Condition,[string]$Message) {
    if (-not $Condition) { throw ('FAILED: '+$Message) };$script:Passed++;Write-Host ('PASS: '+$Message)
}
function Rejected([scriptblock]$Action,[string]$Message) {
    $failed=$false;try { & $Action | Out-Null } catch { $failed=$true };Check $failed $Message
}
function HashText([string]$Text) {
    $hasher=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-','').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}
function Put([string]$Path,[string]$Text) {
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path))
    [IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))
}
function Bundle([string]$Id,$Files) {
    $archive=Join-Path $work ($Id+'-'+[guid]::NewGuid().ToString('N')+'.zip')
    $zip=[IO.Compression.ZipFile]::Open($archive,[IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach($file in $Files) {
            $entry=$zip.CreateEntry($file.Path);$s=$entry.Open()
            try { $data=[Text.Encoding]::UTF8.GetBytes($file.New);$s.Write($data,0,$data.Length) }
            finally { $s.Dispose() }
        }
    } finally { $zip.Dispose() }
    $definitions=@(foreach($file in $Files) {
        @{path=$file.Path;sha256=(HashText $file.New);bytes=[Text.Encoding]::UTF8.GetByteCount($file.New);
          previous_sha256=$(if ($file.Old) { HashText $file.Old } else { '' })}
    })
    return [pscustomobject]@{Archive=$archive;Definition=([pscustomobject]@{
        id=$Id;name=$Id;url=('https://raw.githubusercontent.com/jjc71ps4/Perdition-Sector/main/updates/'+$Id+'.zip');
        sha256=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant();
        bytes=(Get-Item -LiteralPath $archive).Length;files=$definitions})}
}
function Case($Bundles) {
    $root=Join-Path $work ([guid]::NewGuid().ToString('N')+' installed game')
    Put (Join-Path $root 'ModOrganizer.exe') 'fixture'
    Put (Join-Path $root 'overwrite\Perdition Sector World.esp') 'world fixture'
    Put (Join-Path $root 'profiles\FO4ME\fallout4prefs.ini') 'personal resolution'
    Put (Join-Path $root 'profiles\FO4ME\saves\private.fos') 'save fixture'
    Put (Join-Path $root 'overwrite\Scripts\PSRadioQuestScript.pex') 'old radio'
    $source=Join-Path $root 'source.json'
    $config=@{schema_version=1;base_snapshot_tag='fixture';base_archive_sha256=('a'*64);
      world_plugin_sha256=(HashText 'world fixture');index_url='https://raw.githubusercontent.com/jjc71ps4/Perdition-Sector/main/updates/beta.json'}
    Put $source ($config | ConvertTo-Json)
    $index=[pscustomobject]@{schema_version=1;base_snapshot_tag='fixture';base_archive_sha256=('a'*64);
      updates=@($Bundles | ForEach-Object { $_.Definition })}
    $archives=@{};foreach($b in $Bundles) { $archives[$b.Definition.id]=$b.Archive }
    & $module {param($Index,$Archives)
        $script:FixtureIndex=$Index;$script:FixtureArchives=$Archives;$script:Downloads=0
        function script:Get-PSUpdateIndex([string]$Url) { return $script:FixtureIndex }
        function script:Get-PSUpdateArchive($Update,[string]$Cache) { $script:Downloads++;return $script:FixtureArchives[$Update.id] }
    } $index $archives
    return [pscustomobject]@{Root=$root;Source=$source;Index=$index;Config=$config}
}
function Run($Case) { return @(Invoke-PerditionUpdates -InstallRoot $Case.Root -SourceManifest $Case.Source) }
function Radio($Case) { return [IO.File]::ReadAllText((Join-Path $Case.Root 'overwrite\Scripts\PSRadioQuestScript.pex')) }

$radio='overwrite/Scripts/PSRadioQuestScript.pex'
$bundle=Bundle 'radio-v1' @(@{Path=$radio;Old='old radio';New='new radio'})
$c=Case @($bundle);$result=Run $c
Check ((Radio $c) -ceq 'new radio') 'Verified patch changes the intended file'
Check ($result[0].status -eq 'applied') 'Successful application returns a receipt'
Check ([IO.File]::ReadAllText((Join-Path $result[0].receipt.backup 'overwrite\Scripts\PSRadioQuestScript.pex')) -ceq 'old radio') 'Original file is backed up'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'overwrite\Perdition Sector World.esp')) -ceq 'world fixture') 'World plugin is preserved'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'profiles\FO4ME\fallout4prefs.ini')) -ceq 'personal resolution') 'Player display settings are preserved'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'profiles\FO4ME\saves\private.fos')) -ceq 'save fixture') 'Player save is preserved'
$again=Run $c
Check ($again[0].status -eq 'already_current') 'Repeat update is idempotent'
Check ((& $module { $script:Downloads }) -eq 1) 'Already-current content avoids another download'

$c=Case @($bundle);Put (Join-Path $c.Root 'overwrite\Scripts\PSRadioQuestScript.pex') 'custom script'
Rejected { Run $c } 'Custom script is rejected before mutation'
Check ((Radio $c) -ceq 'custom script') 'Custom script remains intact'
Check ((& $module { $script:Downloads }) -eq 0) 'Custom-script rejection avoids downloading'

$c=Case @($bundle);Put (Join-Path $c.Root 'overwrite\Perdition Sector World.esp') 'different world'
Rejected { Run $c } 'Wrong World build is rejected'
Check ((Radio $c) -ceq 'old radio') 'Wrong-build rejection preserves radio'

$c=Case @($bundle);$c.Index.base_snapshot_tag='different'
Rejected { Run $c } 'Mismatched base snapshot is rejected'

$c=Case @($bundle);$c.Index.updates[0].sha256='0'*64
Rejected { Run $c } 'Corrupt archive checksum is rejected'
Check ((Radio $c) -ceq 'old radio') 'Corrupt archive leaves installed files intact'
$bundle=Bundle 'radio-v1' @(@{Path=$radio;Old='old radio';New='new radio'})
$c=Case @($bundle);$c.Index.updates[0].files[0].sha256='0'*64
Rejected { Run $c } 'Wrong extracted-file checksum is rejected'
Check ((Radio $c) -ceq 'old radio') 'Extracted-file rejection precedes replacement'
$bundle=Bundle 'radio-v1' @(@{Path=$radio;Old='old radio';New='new radio'})

foreach($bad in @('../outside.pex','overwrite/../outside.pex','overwrite/Scripts/radio.pex:stream','profiles/FO4ME/saves/private.fos','overwrite/saves/private.fos','C:\outside.pex')) {
    $c=Case @($bundle);$original=$c.Index.updates[0].files[0].path;$c.Index.updates[0].files[0].path=$bad
    Rejected { Run $c } ('Unsafe destination rejected: '+$bad)
    $c.Index.updates[0].files[0].path=$original
}
$c=Case @($bundle);$c.Index.updates[0].url='https://example.com/radio.zip'
Rejected { Run $c } 'Off-repository download URL is rejected'
$bundle.Definition.url='https://raw.githubusercontent.com/jjc71ps4/Perdition-Sector/main/updates/radio-v1.zip'

$extra=Bundle 'extra-zip' @(@{Path=$radio;Old='old radio';New='new radio'},@{Path='overwrite/Scripts/extra.pex';Old='';New='extra'})
$c=Case @($extra);$c.Index.updates[0].files=@($c.Index.updates[0].files[0])
Rejected { Run $c } 'Unlisted archive entry is rejected before mutation'
Check ((Radio $c) -ceq 'old radio') 'Unexpected ZIP entry cannot change the radio'

$second='overwrite/Scripts/Second.pex'
$two=Bundle 'two-files' @(@{Path=$radio;Old='old radio';New='new radio'},@{Path=$second;Old='old second';New='new second'})
$c=Case @($two);Put (Join-Path $c.Root $second) 'custom second'
Rejected { Run $c } 'All installed-file preconditions are checked before any replacement'
Check ((Radio $c) -ceq 'old radio') 'A later custom file prevents partial application'

$c=Case @($two);Put (Join-Path $c.Root $second) 'old second'
& $module {
    $script:OriginalSetter=${function:Set-PSUpdateFile}
    function script:Set-PSUpdateFile([string]$Source,[string]$Target) {
        if ($Target.EndsWith('Second.pex')) { throw 'Fixture write failure' }
        & $script:OriginalSetter $Source $Target
    }
}
Rejected { Run $c } 'A mid-transaction write failure is reported'
& $module { Set-Item -Path Function:script:Set-PSUpdateFile -Value $script:OriginalSetter }
Check ((Radio $c) -ceq 'old radio') 'Earlier replacement is rolled back after a later write failure'
Check ([IO.File]::ReadAllText((Join-Path $c.Root $second)) -ceq 'old second') 'Other original file remains intact after rollback'

$added=Bundle 'new-file' @(@{Path='overwrite/Scripts/Added.pex';Old='';New='added script'})
$c=Case @($added);$r=Run $c
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'overwrite/Scripts/Added.pex')) -ceq 'added script') 'New files require and accept an absent predecessor'

$first=Bundle 'history-1' @(@{Path=$radio;Old='old radio';New='radio one'})
$last=Bundle 'history-2' @(@{Path=$radio;Old='radio one';New='radio two'})
$c=Case @($first,$last);$r=Run $c
Check ((Radio $c) -ceq 'radio two') 'Ordered patches advance a fresh base through both versions'
$r=Run $c
Check ((Radio $c) -ceq 'radio two' -and @($r | Where-Object {$_.status -ne 'already_current'}).Count -eq 0) 'A later installed version is never downgraded by earlier history'
Check ((& $module { $script:Downloads }) -eq 2) 'Repeating a complete patch history downloads nothing'

$mixed=Bundle 'mixed-history-1' @(@{Path=$radio;Old='old radio';New='radio one'},@{Path=$second;Old='';New='new second'})
$c=Case @($mixed,$last);Put (Join-Path $c.Root $radio) 'radio two';$r=Run $c
Check ((Radio $c) -ceq 'radio two') 'Mixed update preserves an already-installed later file'
Check ([IO.File]::ReadAllText((Join-Path $c.Root $second)) -ceq 'new second') 'Mixed update can still supply its missing companion file'

$bundle=Bundle 'radio-v1' @(@{Path=$radio;Old='old radio';New='new radio'})
$junctionChecked=$false
foreach($existing in @('C:\Users\All Users','C:\Documents and Settings')) {
    $item=Get-Item -LiteralPath $existing -Force -ErrorAction SilentlyContinue
    if ($item -and (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        Rejected { & $module {param($Path) Assert-PSUpdateUnlinked $Path} $existing } 'Native path guard rejects an existing Windows junction without creating or writing one'
        $junctionChecked=$true;break
    }
}

$report=@{passed=$script:Passed;fixture_root=$work;full_game_install_run=$false;live_download_tested=$false;
          existing_native_junction_checked=$junctionChecked;junction_creation_test='Environment denied creation; existing junction used read-only when available'}
$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'update_test_results.json') -Encoding UTF8
Write-Host ('Completed '+$script:Passed+' update checks.')
