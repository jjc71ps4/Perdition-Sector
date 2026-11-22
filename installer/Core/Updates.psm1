$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
. (Join-Path $PSScriptRoot 'ProfileUpdates.ps1')

function Get-PSUpdateHash([string]$Path) {
    if (-not [IO.File]::Exists($Path)) { return '' }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-PSUpdatePath([string]$Root,[string]$Relative) {
    $relativePath=$Relative.Replace('\','/')
    $parts=$relativePath.Split('/')
    if ($relativePath -notmatch '^(mods|overwrite)/' -or $parts -contains '..' -or $parts -contains '.' -or
        $parts -contains '' -or $parts -contains 'saves' -or $parts -contains '__MO_Saves' -or
        $relativePath.Contains(':') -or $relativePath.IndexOf([char]0) -ge 0) { throw "Unsafe update path: $Relative" }
    $base=[IO.Path]::GetFullPath($Root).TrimEnd('\')+'\'
    $path=[IO.Path]::GetFullPath([IO.Path]::Combine($base,$relativePath.Replace('/','\')))
    if (-not $path.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)) { throw 'Update path escapes the installation.' }
    Assert-PSUpdateUnlinked $path
    return $path
}

function Assert-PSUpdateUnlinked([string]$Path) {
    $cursor=[IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Updates require ordinary folders, not linked paths: $cursor"
            }
        }
        $parent=[IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break };$cursor=$parent
    }
}

function Assert-PSUpdateUrl([string]$Url) {
    $uri=[Uri]$Url
    if ($uri.Scheme -ne 'https' -or $uri.UserInfo -or -not (
        ($uri.Host -eq 'raw.githubusercontent.com' -and $uri.AbsolutePath.StartsWith('/jjc71ps4/Perdition-Sector/',[StringComparison]::Ordinal)) -or
        ($uri.Host -eq 'github.com' -and $uri.AbsolutePath.StartsWith('/jjc71ps4/Perdition-Sector/releases/download/',[StringComparison]::Ordinal)))) {
        throw 'Updates must come from the Perdition Sector GitHub repository over HTTPS.'
    }
}

function Get-PSUpdateIndex([string]$Url) {
    Assert-PSUpdateUrl $Url
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    $client=New-Object Net.WebClient
    try {
        $client.Headers['User-Agent']='PerditionSectorUpdater/0.2.3'
        $client.Headers['Cache-Control']='no-cache'
        return ($client.DownloadString($Url) | ConvertFrom-Json)
    } finally { $client.Dispose() }
}

function Get-PSUpdateArchive($Update,[string]$Cache) {
    Assert-PSUpdateUrl $Update.url
    Assert-PSUpdateUnlinked $Cache
    [void][IO.Directory]::CreateDirectory($Cache)
    $path=Join-Path $Cache ($Update.id+'.zip')
    if ((Get-PSUpdateHash $path) -eq $Update.sha256 -and (Get-Item -LiteralPath $path).Length -eq [long]$Update.bytes) { return $path }
    $temporary=$path+'.download'
    $client=New-Object Net.WebClient
    try { $client.Headers['User-Agent']='PerditionSectorUpdater/0.2.3';$client.DownloadFile($Update.url,$temporary) }
    finally { $client.Dispose() }
    if ((Get-PSUpdateHash $temporary) -ne $Update.sha256 -or (Get-Item -LiteralPath $temporary).Length -ne [long]$Update.bytes) {
        throw 'Update download failed its size or SHA-256 check.'
    }
    if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) }
    [IO.File]::Move($temporary,$path)
    return $path
}

function Assert-PSUpdateDefinition($Update,[string]$Root) {
    if ($Update.id -notmatch '^[a-z0-9][a-z0-9.-]{0,79}$' -or
        $Update.sha256 -notmatch '^[0-9a-f]{64}$' -or [long]$Update.bytes -le 0 -or
        [long]$Update.bytes -gt 500MB -or @($Update.files).Count -eq 0) { throw 'Invalid update definition.' }
    Assert-PSUpdateUrl $Update.url
    $seen=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    [long]$size=0
    foreach ($file in $Update.files) {
        [void](Get-PSUpdatePath $Root ([string]$file.path))
        if ($file.path.Contains('\') -or -not $seen.Add($file.path.Replace('\','/')) -or $file.sha256 -notmatch '^[0-9a-f]{64}$' -or
            ($file.previous_sha256 -and $file.previous_sha256 -notmatch '^[0-9a-f]{64}$') -or
            [long]$file.bytes -lt 0 -or [long]$file.bytes -gt 500MB) { throw 'Invalid or duplicate update file.' }
        $size += [long]$file.bytes
    }
    if ($size -gt 500MB) { throw 'Update is too large for the incremental updater.' }
}

function Set-PSUpdateFile([string]$Source,[string]$Target) {
    Assert-PSUpdateUnlinked $Target
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target))
    $temporary=$Target+'.ps-update.tmp'
    if (Test-Path -LiteralPath $temporary) { throw "An update temporary file already exists: $temporary" }
    [IO.File]::Copy($Source,$temporary,$false)
    if ([IO.File]::Exists($Target)) { [IO.File]::Replace($temporary,$Target,[System.Management.Automation.Language.NullString]::Value) }
    else { [IO.File]::Move($temporary,$Target) }
}

function Install-PSUpdateArchive($Update,[string]$Archive,[string]$Root,[string]$WorkRoot,[hashtable]$Later=@{}) {
    if ((Get-PSUpdateHash $Archive) -ne $Update.sha256 -or (Get-Item -LiteralPath $Archive).Length -ne [long]$Update.bytes) {
        throw 'Update archive verification failed.'
    }
    $transaction=Join-Path $WorkRoot ($Update.id+'-'+[guid]::NewGuid().ToString('N'))
    Assert-PSUpdateUnlinked $transaction
    $stage=Join-Path $transaction 'Staged';$backup=Join-Path $transaction 'Backup'
    $zip=[IO.Compression.ZipFile]::OpenRead($Archive)
    $plan=New-Object Collections.Generic.List[object]
    try {
        if ($zip.Entries.Count -ne @($Update.files).Count) { throw 'Update ZIP contains unexpected files.' }
        $seen=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        foreach ($entry in $zip.Entries) {
            $name=$entry.FullName.Replace('\','/')
            if (-not $seen.Add($name)) { throw 'Update ZIP contains duplicate paths.' }
            $definition=@($Update.files | Where-Object { $_.path -ceq $name })
            if ($definition.Count -ne 1 -or $entry.Length -ne [long]$definition[0].bytes) { throw 'Update ZIP does not match its manifest.' }
            $target=Get-PSUpdatePath $Root $name
            $staged=Get-PSUpdatePath $stage $name
            $saved=Get-PSUpdatePath $backup $name
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($staged))
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$staged,$false)
            if ((Get-PSUpdateHash $staged) -ne $definition[0].sha256) { throw 'An extracted update file failed verification.' }
            $before=Get-PSUpdateHash $target
            $satisfiedLater=$Later.ContainsKey($name) -and $Later[$name] -contains $before
            if ($before -ne $definition[0].sha256 -and $before -ne [string]$definition[0].previous_sha256 -and -not $satisfiedLater) {
                throw "An installed file has custom changes; it was preserved: $name"
            }
            $after=if ($satisfiedLater) { $before } else { $definition[0].sha256 }
            $plan.Add([pscustomobject]@{Target=$target;Staged=$staged;Backup=$saved;Before=$before;After=$after;Relative=$name})
        }
    } finally { $zip.Dispose() }
    foreach ($profile in @(Get-PSUpdateProfileChanges $Update $Root)) {
        $staged=Join-Path $stage $profile.Relative.Replace('/','\')
        $saved=Join-Path $backup $profile.Relative.Replace('/','\')
        [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($staged))
        [IO.File]::WriteAllText($staged,$profile.Content,(New-Object Text.UTF8Encoding($false)))
        $plan.Add([pscustomobject]@{Target=$profile.Target;Staged=$staged;Backup=$saved;Before=$profile.Before;After=$profile.After;Relative=$profile.Relative})
    }
    # Every archive entry and every profile precondition is checked before mutation.
    foreach ($item in $plan) {
        if ((Get-PSUpdateHash $item.Target) -ne $item.Before) { throw 'An installed file changed while preparing the update.' }
        if ($item.Before -and $item.Before -ne $item.After) {
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($item.Backup))
            [IO.File]::Copy($item.Target,$item.Backup,$false)
        }
    }
    $applied=New-Object Collections.Generic.List[object]
    try {
        foreach ($item in $plan) {
            if ($item.Before -eq $item.After) { continue }
            Set-PSUpdateFile $item.Staged $item.Target
            $applied.Add($item)
            if ((Get-PSUpdateHash $item.Target) -ne $item.After) { throw 'Installed update verification failed.' }
        }
    } catch {
        foreach ($item in $applied) {
            if ($item.Before) { [IO.File]::Copy($item.Backup,$item.Target,$true) }
            else { [IO.File]::Delete($item.Target) }
        }
        throw
    }
    [void][IO.Directory]::CreateDirectory($transaction)
    $receipt=@{id=$Update.id;applied_utc=[DateTime]::UtcNow.ToString('o');files=@($plan.ToArray());backup=$backup}
    [IO.File]::WriteAllText((Join-Path $transaction 'receipt.json'),($receipt | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
    return $receipt
}

function Invoke-PerditionUpdates {
    param([Parameter(Mandatory=$true)][string]$InstallRoot,[Parameter(Mandatory=$true)][string]$SourceManifest)
    $root=[IO.Path]::GetFullPath($InstallRoot);Assert-PSUpdateUnlinked $root
    if (-not [IO.File]::Exists((Join-Path $root 'ModOrganizer.exe'))) { throw 'Choose the installed Perdition folder containing ModOrganizer.exe.' }
    $source=Get-Content -LiteralPath $SourceManifest -Raw | ConvertFrom-Json
    if ($source.schema_version -ne 1 -or $source.base_archive_sha256 -notmatch '^[0-9a-f]{64}$' -or
        $source.world_plugin_sha256 -notmatch '^[0-9a-f]{64}$') { throw 'Invalid update source configuration.' }
    if ((Get-PSUpdateHash (Join-Path $root 'overwrite\Perdition Sector World.esp')) -ne $source.world_plugin_sha256) {
        throw 'This update channel requires its matching Perdition build; the World plugin was preserved.'
    }
    Assert-PSUpdateUrl $source.index_url
    Write-Host 'Checking Perdition Sector updates...'
    $index=Get-PSUpdateIndex $source.index_url
    if ($index.schema_version -notin @(1,2) -or $index.base_snapshot_tag -ne $source.base_snapshot_tag -or
        $index.base_archive_sha256 -ne $source.base_archive_sha256) { throw 'Update channel does not match the installed base package.' }
    $ids=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($update in $index.updates) {
        Assert-PSUpdateDefinition $update $root
        if (-not $ids.Add($update.id)) { throw 'Duplicate update ID.' }
    }
    $results=New-Object Collections.Generic.List[object]
    for ($number=0;$number -lt @($index.updates).Count;$number++) {
        $update=@($index.updates)[$number]
        # An installation at a later revision must never be downgraded by an
        # earlier entry when the public channel retains an ordered patch history.
        $later=@{}
        for ($next=$number+1;$next -lt @($index.updates).Count;$next++) {
            foreach ($future in @($index.updates)[$next].files) {
                $key=$future.path.Replace('\','/')
                if ($later.ContainsKey($key)) { $later[$key]=@($later[$key])+@($future.sha256) }
                else { $later[$key]=@($future.sha256) }
            }
        }
        $pending=$false
        foreach ($file in $update.files) {
            $hash=Get-PSUpdateHash (Get-PSUpdatePath $root $file.path)
            if ($hash -eq $file.sha256) { continue }
            if ($later.ContainsKey($file.path) -and $later[$file.path] -contains $hash) { continue }
            if ($hash -ne [string]$file.previous_sha256) { throw "An installed file has custom changes; it was preserved: $($file.path)" }
            $pending=$true
        }
        foreach ($profile in @(Get-PSUpdateProfileChanges $update $root)) { if ($profile.Before -ne $profile.After) { $pending=$true } }
        if (-not $pending) {
            Write-Host ($update.name+' is already installed.')
            $results.Add([pscustomobject]@{id=$update.id;status='already_current'});continue
        }
        Write-Host ('Downloading '+$update.name+'...')
        $work=Join-Path $root '_Installer\Updates';Assert-PSUpdateUnlinked $work
        $archive=Get-PSUpdateArchive $update (Join-Path $work 'Cache')
        $receipt=Install-PSUpdateArchive $update $archive $root $work $later
        Write-Host ($update.name+' installed.')
        $results.Add([pscustomobject]@{id=$update.id;status='applied';receipt=$receipt})
    }
    return $results.ToArray()
}

function Install-PSUpdaterRuntime {
    param([string]$InstallRoot,[string]$CoreRoot,[string]$SourceManifest)
    Assert-PSUpdateUnlinked $InstallRoot
    $updater=Join-Path $InstallRoot 'Updater';Assert-PSUpdateUnlinked $updater
    $backup=Join-Path $InstallRoot ('_Installer\\Updates\\UpdaterRuntime-'+[guid]::NewGuid().ToString('N'))
    Assert-PSUpdateUnlinked $backup
    $sources=@{}
    foreach ($name in @('Updates.psm1','ProfileUpdates.ps1','Update-Perdition.ps1')) { $sources[(Join-Path $updater $name)]=Join-Path $CoreRoot $name }
    $sources[(Join-Path $updater 'update_source.json')]=$SourceManifest
    $command=Join-Path $CoreRoot 'Update-Installed.cmd'
    if ([IO.File]::Exists($command)) { $sources[(Join-Path $InstallRoot 'Update Perdition Sector.cmd')]=$command }
    $plan=New-Object Collections.Generic.List[object]
    foreach ($target in $sources.Keys) {
        Assert-PSUpdateUnlinked $target
        $source=$sources[$target];$before=Get-PSUpdateHash $target;$after=Get-PSUpdateHash $source
        if (-not $after) { throw 'An updater runtime component is missing.' }
        if ($before -eq $after) { continue }
        $saved=Join-Path $backup ([IO.Path]::GetFileName($target))
        $plan.Add([pscustomobject]@{Target=$target;Source=$source;Before=$before;After=$after;Backup=$saved})
    }
    foreach ($item in $plan) {
        if ($item.Before) { [void][IO.Directory]::CreateDirectory($backup);[IO.File]::Copy($item.Target,$item.Backup,$false) }
    }
    $applied=New-Object Collections.Generic.List[object]
    try {
        foreach ($item in $plan) {
            if ((Get-PSUpdateHash $item.Target) -ne $item.Before) { throw 'An updater component changed during preparation.' }
            Set-PSUpdateFile $item.Source $item.Target;$applied.Add($item)
            if ((Get-PSUpdateHash $item.Target) -ne $item.After) { throw 'Updater runtime verification failed.' }
        }
    } catch {
        foreach ($item in $applied) { if ($item.Before) { [IO.File]::Copy($item.Backup,$item.Target,$true) } else { [IO.File]::Delete($item.Target) } }
        throw
    }
}
Export-ModuleMember -Function Invoke-PerditionUpdates,Install-PSUpdaterRuntime
