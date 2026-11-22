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

$profile=[pscustomobject]@{schema_version=1;enable_mods=@('Visibility');disable_mods=@('Redundant');enable_plugins=@('Visibility.esp','NT4.esp');settings=@(
    [pscustomobject]@{section='Display';key='fMeshLODLevel1FadeDist';value='3500';previous_values=@('999999','3500')},
    [pscustomobject]@{section='Display';key='fMeshLODLevel2FadeDist';value='2000';previous_values=@('999999','2000')},
    [pscustomobject]@{section='Display';key='fMeshLODFadeScalar';value='1';previous_values=@('3','1')},
    [pscustomobject]@{section='LOD';key='fLODFadeOutMultObjects';value='15';previous_values=@('30','15')})}
function ProfileCase {
    $bundle=Bundle 'profile-update' @(@{Path='mods/Visibility/Visibility.esp';Old='';New='patch'})
    $bundle.Definition | Add-Member -NotePropertyName profile_changes -NotePropertyValue $profile
    $c=Case @($bundle);$c.Index.schema_version=2
    Put (Join-Path $c.Root 'profiles/FO4ME/modlist.txt') "# MO2`r`n+Redundant`r`n+Keep Me`r`n"
    Put (Join-Path $c.Root 'profiles/FO4ME/plugins.txt') "# plugins`r`n*Keep.esp`r`n"
    Put (Join-Path $c.Root 'profiles/FO4ME/loadorder.txt') "Keep.esp`r`n"
    Put (Join-Path $c.Root 'profiles/FO4ME/fallout4prefs.ini') "[Display]`r`niSize W=2560`r`niSize H=1440`r`nfMeshLODLevel1FadeDist=999999.0000`r`nfMeshLODLevel2FadeDist=999999.0000`r`nfMeshLODFadeScalar=3.0000`r`n[LOD]`r`nfLODFadeOutMultObjects=30.0000`r`n[Custom]`r`nMine=keep`r`n"
    return $c
}
$c=ProfileCase;$result=Run $c
$prefs=[IO.File]::ReadAllText((Join-Path $c.Root 'profiles/FO4ME/fallout4prefs.ini'))
Check ($prefs.Contains('fMeshLODLevel1FadeDist=3500.0000') -and $prefs.Contains('fMeshLODLevel2FadeDist=2000.0000') -and $prefs.Contains('fMeshLODFadeScalar=1.0000') -and $prefs.Contains('fLODFadeOutMultObjects=15.0000')) 'Confirmed distance values migrate together'
Check ($prefs.Contains('iSize W=2560') -and $prefs.Contains('iSize H=1440') -and $prefs.Contains('Mine=keep')) 'Resolution and unrelated settings are preserved'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'profiles/FO4ME/modlist.txt')).Contains("-Redundant`r`n")) 'Only the named redundant mod is disabled'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'profiles/FO4ME/plugins.txt')).Contains('*NT4.esp')) 'New attachment plugin is enabled'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'profiles/FO4ME/loadorder.txt')).Contains('Visibility.esp')) 'New visibility plugin enters load order'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'profiles/FO4ME/saves/private.fos')) -ceq 'save fixture') 'Saves are preserved'
Check ((Run $c)[0].status -eq 'already_current') 'Content and migration are idempotent'
Check ((& $module { $script:Downloads }) -eq 1) 'Repeated update avoids download'
Check (Test-Path -LiteralPath (Join-Path $result[0].receipt.backup 'profiles/FO4ME/fallout4prefs.ini')) 'Profile has a rollback copy'

$c=ProfileCase;$path=Join-Path $c.Root 'profiles/FO4ME/fallout4prefs.ini';Put $path (([IO.File]::ReadAllText($path)).Replace('999999.0000','7777.0000'))
Rejected { Run $c } 'Unrecognized custom distances are rejected before mutation'
Check (-not (Test-Path -LiteralPath (Join-Path $c.Root 'mods/Visibility/Visibility.esp'))) 'Custom-setting rejection installs no companion files'

$c=ProfileCase
# Fail after the asset is written, while the same transaction is applying its profile.
& $module {
    $script:OriginalUpdateWriter=${function:Set-PSUpdateFile}
    function script:Set-PSUpdateFile([string]$Source,[string]$Target) {
        if ($Target.EndsWith('plugins.txt')) { throw 'Fixture write failure' }
        & $script:OriginalUpdateWriter $Source $Target
    }
}
Rejected { Run $c } 'Profile write failure fails the whole update'
Check (-not (Test-Path -LiteralPath (Join-Path $c.Root 'mods/Visibility/Visibility.esp'))) 'Asset is rolled back when profile application fails'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'profiles/FO4ME/modlist.txt')).Contains('+Redundant')) 'Earlier profile writes are rolled back too'
& $module { Set-Item Function:script:Set-PSUpdateFile $script:OriginalUpdateWriter }

$c=ProfileCase
Install-PSUpdaterRuntime -InstallRoot $c.Root -CoreRoot (Join-Path $distribution 'Core') -SourceManifest (Join-Path $distribution 'update_source.json')
Check (Test-Path -LiteralPath (Join-Path $c.Root 'Updater/ProfileUpdates.ps1')) 'Existing installs receive the new profile migration runtime'
Check ([IO.File]::ReadAllText((Join-Path $c.Root 'Updater/update_source.json')).Contains('beta-v2.json')) 'Existing installs retain the new update channel for future checks'
Check (Test-Path -LiteralPath (Join-Path $c.Root 'Update Perdition Sector.cmd')) 'Existing installs receive a persistent update command'
@{passed=$script:Passed;game_install_run=$false;scope='Profile migration, personal settings, idempotency and combined rollback'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'profile_update_test_results.json') -Encoding UTF8
Write-Host ('Completed '+$script:Passed+' profile migration checks.')

