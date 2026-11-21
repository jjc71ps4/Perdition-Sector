Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$script:Utf8 = New-Object System.Text.UTF8Encoding($false)
$script:LogPath = $null
$script:RuntimeFolders = @('dlls','explorer++','licenses','loot','NCC','platforms','plugins','pythoncore','QtQml','QtQuick.2','resources','styles','stylesheets','translations','tutorials')
$script:RootFiles = @('ModOrganizer.exe','helper.exe','nxmhandler.exe','QtWebEngineProcess.exe','boost_python38-vc142-mt-x64-1_75.dll','libcrypto-1_1-x64.dll','libffi-7.dll','libssl-1_1-x64.dll','python38.dll','pythoncore.zip','uibase.dll','usvfs_proxy_x64.exe','usvfs_proxy_x86.exe','usvfs_x64.dll','usvfs_x86.dll','splash.png','portable.txt')
$script:ProfileFiles = @('archives.txt','fallout4.ini','fallout4custom.ini','fallout4prefs.ini','initweaks.ini','loadorder.txt','lockedorder.txt','modlist.txt','plugins.txt','settings.ini')

function Write-InstallerLog {
    param([string]$Message)
    Write-Host $Message
    if ($script:LogPath) { [IO.File]::AppendAllText($script:LogPath, ('[{0}] {1}' -f [DateTime]::UtcNow.ToString('o'),$Message)+"`r`n",$script:Utf8) }
}

function Save-JsonFile {
    param([string]$Path, $Value)
    $temp = $Path + '.new'
    [IO.File]::WriteAllText($temp, ($Value | ConvertTo-Json -Depth 20),$script:Utf8)
    if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temp,$Path,[System.Management.Automation.Language.NullString]::Value) } else { [IO.File]::Move($temp,$Path) }
}

function Get-SafeChildPath {
    param([string]$Root,[string]$Relative)
    $parts = $Relative.Replace('\','/').Split('/')
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':') -or $parts -contains '..') { throw "Unsafe package path: $Relative" }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $path = [IO.Path]::GetFullPath([IO.Path]::Combine($base,$Relative.Replace('/','\')))
    if (-not $path.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)) { throw "Package path escapes destination: $Relative" }
    return $path
}

function Assert-NoLinkedAncestors {
    param([string]$Path)
    $item = [IO.Path]::GetFullPath($Path)
    while ($item) {
        if (Test-Path -LiteralPath $item) {
            $attributes = (Get-Item -LiteralPath $item -Force).Attributes
            if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Choose an installation path outside linked folders: $item" }
        }
        $parent = [IO.Path]::GetDirectoryName($item)
        if ($parent -eq $item) { break }
        $item = $parent
    }
}

function Read-ZipText {
    param($Archive,[string]$Name)
    $entry = $Archive.GetEntry($Name)
    if (-not $entry) { throw "Package is missing $Name" }
    $reader = New-Object IO.StreamReader($entry.Open(),[Text.Encoding]::UTF8,$true)
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}

function Get-PackageInformation {
    param([string]$PackagePath)
    $zip = [IO.Compression.ZipFile]::OpenRead($PackagePath)
    try {
        $matches = @($zip.Entries | Where-Object { $_.FullName -match '(^|/)ModOrganizer\.exe$' })
        if ($matches.Count -ne 1) { throw 'Select a Perdition Sector package containing one ModOrganizer.exe.' }
        $prefix = $matches[0].FullName.Substring(0,$matches[0].FullName.Length-'ModOrganizer.exe'.Length)
        $mods = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        foreach ($line in ((Read-ZipText $zip ($prefix+'profiles/FO4ME/modlist.txt')) -split '\r?\n')) {
            if ($line.StartsWith('+')) { [void]$mods.Add($line.Substring(1)) }
        }
        if (-not $mods.Count -or -not $zip.GetEntry($prefix+'overwrite/Perdition Sector World.esp')) { throw 'The selected archive is not the expected Perdition build.' }
        $bytes = [long]0
        $count = 0
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        foreach ($entry in $zip.Entries) {
            if (-not $entry.FullName.StartsWith($prefix,[StringComparison]::Ordinal)) { continue }
            $relative = $entry.FullName.Substring($prefix.Length)
            if (Test-PayloadEntry $relative $mods) {
                [void](Get-SafeChildPath ([IO.Path]::GetTempPath()) $relative)
                if (-not $seen.Add($relative)) { throw "Duplicate package destination: $relative" }
                $bytes += $entry.Length
                $count++
            }
        }
        $world = $zip.GetEntry($prefix+'overwrite/Perdition Sector World.esp')
        $stream = $world.Open(); $algorithm = [Security.Cryptography.SHA256]::Create()
        try { $worldHash = ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
        finally { $stream.Dispose(); $algorithm.Dispose() }
        return [pscustomobject]@{Prefix=$prefix;Mods=$mods;Bytes=$bytes;Files=$count;WorldHash=$worldHash}
    } finally { $zip.Dispose() }
}

function Test-PayloadEntry {
    param([string]$Relative,$Mods)
    if (-not $Relative -or $Relative.EndsWith('/')) { return $false }
    if ($Relative -match '(^|/)(\.git|__pycache__|FO4Edit Backups|FO4Edit Cache|crashDumps|SteamSession)(/|$)' -or $Relative -match '\.(bak|broken|log|fos|f4se|dmp|pdb|psd)$' -or $Relative -match '(^|/)(desktop\.ini|Thumbs\.db)$') { return $false }
    $parts = $Relative.Split('/')
    if ($Relative -eq 'Launch Perdition Sector.cmd' -or $Relative -eq 'Launcher/Start-Perdition.ps1') { return $true }
    if ($parts.Count -eq 1) { return $script:RootFiles -contains $Relative }
    if ($script:RuntimeFolders -contains $parts[0]) { return $true }
    if ($parts[0] -eq 'mods' -and $parts.Count -ge 3) {
        if (-not $Mods.Contains($parts[1])) { return $false }
        if ($Relative -match '/(src|\.git)/' -or $Relative -match '\.(broken|bak|log)$') { return $false }
        if ($Relative.StartsWith('mods/F4SE/f4se_0_06_23/',[StringComparison]::OrdinalIgnoreCase)) { return $false }
        return $true
    }
    if ($parts[0] -eq 'overwrite') {
        return $Relative -notmatch '(^|/)(Source|Backups?|Logs)(/|$)|\.(psc|bak|log)$'
    }
    return $parts.Count -eq 3 -and $parts[0] -eq 'profiles' -and $parts[1] -eq 'FO4ME' -and $script:ProfileFiles -contains $parts[2]
}

function Expand-PerditionPackage {
    param([string]$PackagePath,[string]$InstallRoot,$Information)
    $zip = [IO.Compression.ZipFile]::OpenRead($PackagePath)
    $count = 0
    try {
        foreach ($entry in $zip.Entries) {
            if (-not $entry.FullName.StartsWith($Information.Prefix,[StringComparison]::Ordinal)) { continue }
            $relative = $entry.FullName.Substring($Information.Prefix.Length)
            if (-not (Test-PayloadEntry $relative $Information.Mods)) { continue }
            $target = Get-SafeChildPath $InstallRoot $relative
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
            Assert-NoLinkedAncestors ([IO.Path]::GetDirectoryName($target))
            if ((Test-Path -LiteralPath $target) -and ((Get-Item -LiteralPath $target -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Linked destination file is not allowed.' }
            $inputStream = $entry.Open()
            $temp = $target + '.installing'
            try {
                $output = [IO.File]::Open($temp,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None)
                try { $inputStream.CopyTo($output) } finally { $output.Dispose() }
            } finally { $inputStream.Dispose() }
            if ((Get-Item -LiteralPath $temp).Length -ne $entry.Length) { throw "Incomplete extraction: $relative" }
            if ([IO.File]::Exists($target)) { [IO.File]::Replace($temp,$target,[System.Management.Automation.Language.NullString]::Value) } else { [IO.File]::Move($temp,$target) }
            $count++
            if ($count % 250 -eq 0) { Write-Progress -Activity 'Installing Perdition Sector' -Status "$count of $($Information.Files) files" -PercentComplete ([Math]::Min(100,100*$count/$Information.Files)) }
        }
    } finally { $zip.Dispose(); Write-Progress -Activity 'Installing Perdition Sector' -Completed }
    $world = Join-Path $InstallRoot 'overwrite\Perdition Sector World.esp'
    if ((Get-FileHash -LiteralPath $world -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Information.WorldHash) { throw 'The main world plugin failed verification.' }
}

function Get-VerifiedDownload {
    param($Dependency,[string]$CacheRoot)
    $path = Get-SafeChildPath $CacheRoot $Dependency.filename
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))
    if ([IO.File]::Exists($path)) {
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $Dependency.sha256) { return $path }
        if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'A linked cache file cannot be replaced.' }
        Write-InstallerLog "Replacing corrupt cached download: $($Dependency.filename)"
        [IO.File]::Delete($path)
    }
    $uri = [Uri]$Dependency.url
    if ($uri.Scheme -ne 'https') { throw 'Dependency downloads require HTTPS.' }
    Write-InstallerLog "Downloading $($Dependency.filename)"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $client = New-Object Net.WebClient
    try { $client.Headers['User-Agent']='PerditionSectorInstaller/0.2.0-beta.1'; $client.DownloadFile($uri,$path+'.download') }
    finally { $client.Dispose() }
    if ((Get-FileHash -LiteralPath ($path+'.download') -Algorithm SHA256).Hash -ne $Dependency.sha256) { throw "Downloaded dependency failed verification: $($Dependency.filename)" }
    [IO.File]::Move($path+'.download',$path)
    return $path
}

function Resolve-OnlinePackage {
    param([string]$SourceManifest,[string]$CacheRoot)
    $source=Get-Content -LiteralPath $SourceManifest -Raw | ConvertFrom-Json
    if ($source.archive_name -notmatch '^[A-Za-z0-9_.-]+\.zip$' -or $source.archive_sha256 -notmatch '^[0-9a-fA-F]{64}$' -or [long]$source.archive_bytes -le 0 -or -not @($source.parts).Count) { throw 'Invalid package download manifest.' }
    $sum=[long]0
    $names=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($part in $source.parts) {
        if ($part.filename -notmatch '^[A-Za-z0-9_.-]+$' -or $part.filename -ieq $source.archive_name -or -not $names.Add($part.filename) -or $part.sha256 -notmatch '^[0-9a-fA-F]{64}$' -or ([Uri]$part.url).Scheme -ne 'https' -or [long]$part.bytes -le 0) { throw 'Invalid package part record.' }
        $sum += [long]$part.bytes
    }
    if ($sum -ne [long]$source.archive_bytes) { throw 'Package part sizes do not match the final archive.' }
    $cache=[IO.Path]::GetFullPath($CacheRoot)
    Assert-NoLinkedAncestors $cache
    $marker=Join-Path $cache 'perdition_download_cache.json'
    if (Test-Path -LiteralPath $marker) {
        $owner=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        if ($owner.product -ne 'PerditionPackageCache' -or $owner.archive_sha256 -ne $source.archive_sha256) { throw 'A different package already owns this cache folder.' }
    } elseif ((Test-Path -LiteralPath $cache) -and @(Get-ChildItem -LiteralPath $cache -Force).Count) { throw 'Choose an empty download cache folder.' }
    [void][IO.Directory]::CreateDirectory($cache)
    Save-JsonFile $marker @{product='PerditionPackageCache';archive_sha256=$source.archive_sha256}
    $output=Get-SafeChildPath $cache $source.archive_name
    if ([IO.File]::Exists($output) -and (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash -eq $source.archive_sha256) { return $output }
    $drive=New-Object IO.DriveInfo([IO.Path]::GetPathRoot($cache))
    if ($drive.AvailableFreeSpace -lt (2*$sum+1GB)) { throw 'Not enough space to download and assemble the package on this drive.' }
    $paths=@()
    foreach ($part in $source.parts) {
        Write-InstallerLog ('Downloading package part '+($paths.Count+1)+' of '+@($source.parts).Count)
        $path=Get-VerifiedDownload $part $cache
        if ((Get-Item -LiteralPath $path).Length -ne [long]$part.bytes) { throw 'Package part size is incorrect.' }
        $paths += $path
    }
    $temporary=$output+'.assembling'
    $stream=[IO.File]::Open($temporary,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { foreach ($path in $paths) { $inputStream=[IO.File]::OpenRead($path);try {$inputStream.CopyTo($stream)} finally {$inputStream.Dispose()} } } finally {$stream.Dispose()}
    if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $source.archive_sha256) { throw 'The assembled package failed verification.' }
    if ([IO.File]::Exists($output)) { [IO.File]::Replace($temporary,$output,[System.Management.Automation.Language.NullString]::Value) } else { [IO.File]::Move($temporary,$output) }
    # These exact checksum-verified part files belong to this cache. The verified
    # complete archive is retained for offline reinstall and resume.
    foreach ($path in $paths) { [IO.File]::Delete($path) }
    return $output
}

function Install-VisualCppRuntimeIfNeeded {
    param([string]$CacheRoot)
    $system=Join-Path $env:WINDIR 'System32'
    $missing=@(@('msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll') | Where-Object { -not [IO.File]::Exists((Join-Path $system $_)) })
    if (-not $missing.Count) { return }
    Write-InstallerLog 'Installing the Microsoft Visual C++ x64 runtime required by MO2 and native plugins.'
    [void][IO.Directory]::CreateDirectory($CacheRoot)
    $file=Join-Path $CacheRoot 'vc_redist.x64.exe'
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    $client=New-Object Net.WebClient
    try { $client.DownloadFile('https://aka.ms/vc14/vc_redist.x64.exe',$file) } finally { $client.Dispose() }
    $signature=Get-AuthenticodeSignature -LiteralPath $file
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|,\s*)CN=Microsoft Corporation(,|$)') { throw 'Microsoft runtime signature could not be verified.' }
    $process=Start-Process -FilePath $file -ArgumentList '/install /quiet /norestart' -Verb RunAs -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -notin @(0,1638,3010)) { throw "Microsoft runtime installation failed: $($process.ExitCode)" }
}

function Expand-CheckedZip {
    param([string]$ArchivePath,[string]$Destination)
    $zip = [IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        foreach ($entry in $zip.Entries) {
            if ($entry.FullName.EndsWith('/')) { continue }
            $target = Get-SafeChildPath $Destination $entry.FullName
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
            Assert-NoLinkedAncestors ([IO.Path]::GetDirectoryName($target))
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$target,$true)
        }
    } finally { $zip.Dispose() }
}

function Install-GameRootOverlay {
    param([string]$ArchivePath,[string]$GameRoot,[bool]$EnableEnb)
    $zip=[IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        foreach ($entry in $zip.Entries) {
            if ($entry.FullName.EndsWith('/')) { continue }
            $parts=$entry.FullName.Split('/',2)
            if ($parts.Count -ne 2 -or $parts[0] -notin @('Shared','ENB')) { throw 'Unexpected gameplay overlay entry.' }
            $relative=$parts[1]
            $target=Get-SafeChildPath $GameRoot $relative
            if ($parts[0] -eq 'ENB' -and -not $EnableEnb) {
                # A resumed installation may previously have enabled ENB. Deactivate
                # only the exact bundled hook; leave unrelated/custom DLLs alone.
                if ($relative -ieq 'd3d11.dll' -and [IO.File]::Exists($target)) {
                    $algorithm=[Security.Cryptography.SHA256]::Create();$stream=$entry.Open()
                    try { $expected=([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','') }
                    finally { $stream.Dispose();$algorithm.Dispose() }
                    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expected) { throw 'An unrecognized d3d11.dll exists in this installer-owned game folder. It will not be removed.' }
                    $disabled=Join-Path (Split-Path -Parent $GameRoot) 'Optional\ENB\d3d11.dll'
                    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($disabled))
                    [IO.File]::Copy($target,$disabled,$true)
                    [IO.File]::Delete($target)
                }
                continue
            }
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
            Assert-NoLinkedAncestors ([IO.Path]::GetDirectoryName($target))
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$target,$true)
        }
    } finally { $zip.Dispose() }
}

function Set-IniValue {
    param([string]$Path,[string]$Section,[string]$Key,[AllowEmptyString()][string]$Value)
    $text = [IO.File]::ReadAllText($Path)
    $lines = [Collections.Generic.List[string]]::new()
    $inSection=$false; $foundSection=$false; $written=$false
    foreach ($line in ($text -split '\r?\n')) {
        if ($line -match '^\s*\[([^\]]+)\]\s*$') {
            if ($inSection -and -not $written) { $lines.Add("$Key=$Value");$written=$true }
            $inSection=$Matches[1] -ieq $Section
            if ($inSection) { $foundSection=$true }
        }
        if ($inSection -and $line -match ('^\s*'+[regex]::Escape($Key)+'\s*=')) {
            if (-not $written) { $lines.Add("$Key=$Value");$written=$true }
        } else { $lines.Add($line) }
    }
    if (-not $foundSection) { $lines.Add("[$Section]") }
    if (-not $written) { $lines.Add("$Key=$Value") }
    [IO.File]::WriteAllText($Path,($lines -join "`r`n").TrimEnd()+"`r`n",$script:Utf8)
}

function ConvertTo-WindowsArgument {
    param([AllowEmptyString()][string]$Value)
    if ($Value.Length -and $Value -notmatch '[\s"]') { return $Value }
    $escaped = [regex]::Replace($Value,'(\\*)"','$1$1\"')
    $escaped = [regex]::Replace($escaped,'(\\+)$','$1$1')
    return '"'+$escaped+'"'
}

function New-MO2Configuration {
    param([string]$InstallRoot,[int]$Width,[int]$Height)
    foreach ($name in @('Launch Perdition Sector.cmd','Start-Perdition.ps1')) {
        if (-not [IO.File]::Exists((Join-Path $PSScriptRoot $name))) { throw "The setup bundle is missing its launcher template: $name" }
    }
    $game = Join-Path $InstallRoot '_Fallout4'
    $qtGame = -join ([Text.Encoding]::UTF8.GetBytes($game) | ForEach-Object { '\x'+$_.ToString('x2') })
    $base = $InstallRoot.Replace('\','/')
    $g = $game.Replace('\','/')
    $lines = @('[General]','gameName=Fallout 4','selected_profile=@ByteArray(FO4ME)',"gamePath=@ByteArray($qtGame)",'version=2.4.4','first_start=false','backup_install=false','','[Settings]',"base_directory=$base", "mod_directory=$base/mods", "profiles_directory=$base/profiles", "overwrite_directory=$base/overwrite", "download_directory=$base/downloads",'check_for_updates=false','offline_mode=true','lock_gui=true','use_splash=false','','[customExecutables]','size=3')
    $executables = @(@('F4SE','f4se_loader.exe'),@('Fallout 4','Fallout4.exe'),@('Fallout Launcher','Fallout4Launcher.exe'))
    for ($i=1;$i -le 3;$i++) {
        $lines += @("$i\title=$($executables[$i-1][0])", "$i\binary=$g/$($executables[$i-1][1])", "$i\workingDirectory=$g", "$i\arguments=", "$i\steamAppID=377160", "$i\hide=false", "$i\ownicon=true", "$i\toolbar=true")
    }
    [IO.File]::WriteAllText((Join-Path $InstallRoot 'ModOrganizer.ini'),($lines -join "`r`n")+"`r`n",$script:Utf8)
    [IO.File]::WriteAllText((Join-Path $InstallRoot 'portable.txt'),'',$script:Utf8)
    foreach ($name in @('downloads','overwrite')) { [void][IO.Directory]::CreateDirectory((Join-Path $InstallRoot $name)) }
    $profile = Join-Path $InstallRoot 'profiles\FO4ME'
    [void][IO.Directory]::CreateDirectory((Join-Path $profile 'saves'))
    foreach ($name in @('fallout4.ini','fallout4custom.ini')) {
        $path=Join-Path $profile $name
        Set-IniValue $path 'General' 'sIntroSequence' 'GameIntro_V3_B.bk2'
        Set-IniValue $path 'General' 'fChancesToPlayAlternateIntro' '0.0000'
    }
    $prefs=Join-Path $profile 'fallout4prefs.ini'
    Set-IniValue $prefs 'Display' 'iSize W' $Width.ToString()
    Set-IniValue $prefs 'Display' 'iSize H' $Height.ToString()
    Set-IniValue $prefs 'Display' 'bBorderless' '1'
    Set-IniValue $prefs 'Display' 'bFull Screen' '0'
    Set-IniValue $prefs 'Display' 'iAdapter' '0'
    # Pin True Grass visibility independently of the incoming package prefs.
    # LocalSettings below makes this the active INI for the FO4ME MO2 profile.
    Set-IniValue $prefs 'Grass' 'fGrassStartFadeDistance' '7000'
    Set-IniValue $prefs 'Grass' 'fGrassMaxStartFadeDistance' '7000.0000'
    Set-IniValue $prefs 'Grass' 'fGrassMinStartFadeDistance' '7000.0000'
    $content=[IO.File]::ReadAllText($prefs) -replace '(?im)^\s*sD3DDevice\s*=.*\r?\n?',''
    [IO.File]::WriteAllText($prefs,$content,$script:Utf8)
    foreach ($pair in @(@('LocalSaves','true'),@('LocalSettings','true'),@('AutomaticArchiveInvalidation','false'))) { Set-IniValue (Join-Path $profile 'settings.ini') 'General' $pair[0] $pair[1] }
    Assert-NoLinkedAncestors (Join-Path $InstallRoot 'Launcher')
    [void][IO.Directory]::CreateDirectory((Join-Path $InstallRoot 'Launcher'))
    [IO.File]::Copy((Join-Path $PSScriptRoot 'Launch Perdition Sector.cmd'),(Join-Path $InstallRoot 'Launch Perdition Sector.cmd'),$true)
    [IO.File]::Copy((Join-Path $PSScriptRoot 'Start-Perdition.ps1'),(Join-Path $InstallRoot 'Launcher\Start-Perdition.ps1'),$true)
}

function Assert-InstalledBuild {
    param([string]$InstallRoot,$Information,$Manifest)
    foreach ($name in @('Launch Perdition Sector.cmd','Launcher\Start-Perdition.ps1','splash.png')) {
        if (-not [IO.File]::Exists((Join-Path $InstallRoot $name))) { throw "Required launcher file is missing: $name" }
    }
    $game = Join-Path $InstallRoot '_Fallout4'
    $exe = Join-Path $game 'Fallout4.exe'
    if (-not [IO.File]::Exists($exe)) { throw 'The game executable is missing after Steam downloads.' }
    $version = [Diagnostics.FileVersionInfo]::GetVersionInfo($exe).FileVersion
    if (-not $version.StartsWith('1.10.163')) { throw "Unsupported game runtime after installation: $version" }
    if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne $Manifest.game_exe_sha256) { throw 'Fallout4.exe does not match the pinned runtime.' }
    foreach ($name in @('f4se_loader.exe','f4se_1_10_163.dll','f4se_steam_loader.dll','Fallout4Launcher.exe','Data\Fallout4.esm','Data\DLCCoast.esm','Data\DLCNukaWorld.esm','Data\DLCRobot.esm','Data\DLCworkshop01.esm','Data\DLCworkshop02.esm','Data\DLCworkshop03.esm')) {
        if (-not [IO.File]::Exists((Join-Path $game $name))) { throw "Required runtime file is missing: $name" }
    }
    $providers = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($directory in @((Join-Path $game 'Data'),(Join-Path $InstallRoot 'overwrite')) + @($Information.Mods | ForEach-Object { Join-Path $InstallRoot ('mods\'+$_) })) {
        if (Test-Path -LiteralPath $directory) { foreach ($path in [IO.Directory]::EnumerateFiles($directory)) { [void]$providers.Add([IO.Path]::GetFileName($path)) } }
    }
    $missing = @()
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $InstallRoot 'profiles\FO4ME\plugins.txt'))) {
        if ($line.StartsWith('*')) { $name=$line.Substring(1);if (-not $providers.Contains($name)) { $missing += $name } }
    }
    if ($missing.Count) { throw ('Missing active plugins: '+($missing -join ', ')) }
    if ((Get-FileHash -LiteralPath (Join-Path $InstallRoot 'overwrite\Perdition Sector World.esp')).Hash.ToLowerInvariant() -ne $Information.WorldHash) { throw 'Installed world plugin failed verification.' }
}

function Assert-InstallPathPolicy {
    param([string]$InstallRoot)
    if ([string]::IsNullOrWhiteSpace($InstallRoot) -or -not [IO.Path]::IsPathRooted($InstallRoot)) { throw 'Choose an absolute installation path, such as C:\Perdition Sector.' }
    $root=[IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
    if ($root -eq [IO.Path]::GetPathRoot($root+'\').TrimEnd('\')) { throw 'Select a dedicated installation folder, not the root of a drive.' }
    $protected=@([Environment]::GetFolderPath('Windows'),[Environment]::GetFolderPath('ProgramFiles'),[Environment]::GetFolderPath('ProgramFilesX86'))
    foreach ($blocked in $protected) {
        if ($blocked -and ($root+'\').StartsWith(([IO.Path]::GetFullPath($blocked).TrimEnd('\')+'\'),[StringComparison]::OrdinalIgnoreCase)) {
            throw "The destination '$root' is inside the protected folder '$blocked'. Choose a folder such as C:\Perdition Sector."
        }
    }
    Assert-NoLinkedAncestors $root
    return $root
}

function Assert-InstallDestination {
    param([string]$InstallRoot,[string]$DistributionRoot,[string]$PackagePath='')
    $root=Assert-InstallPathPolicy $InstallRoot
    $marker=Join-Path $root '_Installer\ownership.json'
    Assert-NoLinkedAncestors (Split-Path -Parent $marker)
    $owned=$false
    if (Test-Path -LiteralPath $marker) {
        $owner=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        if ($owner.product -ne 'PerditionSectorInstaller' -or $owner.root -ne $root) { throw 'Installation ownership does not match this folder.' }
        $owned=$true
    }
    if ((Test-Path -LiteralPath $root) -and -not $owned) {
        $children=@(Get-ChildItem -LiteralPath $root -Force)
        if ($children.Count) {
            # GAMMA-style deployment commonly keeps setup beside the installed
            # game. Only the known setup bundle may pre-exist in that case;
            # existing MO2/game files still require our ownership marker.
            $setupHere=$DistributionRoot -and $root -eq [IO.Path]::GetFullPath($DistributionRoot).TrimEnd('\')
            foreach ($required in @('PerditionSetup.exe','Setup.ps1','release.json','Core\Installer.psm1')) {
                if (-not [IO.File]::Exists((Join-Path $root $required))) { $setupHere=$false }
            }
            if (-not $setupHere) { throw "The destination '$root' already contains files. Choose a new folder, or the folder containing only this Perdition setup bundle. Existing games and mod builds are preserved." }
            $setupFiles=@('PerditionSetup.exe','Setup.ps1','SetupBootstrap.cs','Build-Payload.ps1','build_release.py','README.md','release.json','RootOverlay.zip','package_source.json','package_source.pending.json')
            $setupFolders=@('Core','Tools','Documentation','Tests')
            $packageFull='';if ($PackagePath) {$packageFull=[IO.Path]::GetFullPath($PackagePath)}
            foreach ($child in $children) {
                Assert-NoLinkedAncestors $child.FullName
                $allowed=$false
                if ($child.PSIsContainer) { $allowed=$setupFolders -contains $child.Name }
                else {
                    $allowed=$setupFiles -contains $child.Name -or $child.FullName -eq $packageFull -or $child.Name -match '^Perdition_Sector_Installer_v[0-9][A-Za-z0-9.-]*_(Test_Candidate|Beta)\.(zip|receipt\.json)$'
                }
                if (-not $allowed) { throw "The destination contains '$($child.Name)', which is not part of this setup bundle. Choose a new folder to protect the existing files." }
            }
        }
    }
    return [pscustomobject]@{Root=$root;Owned=$owned;Marker=$marker}
}

function Test-FullPackageVerificationEnabled {
    param($Manifest)
    $setting=$Manifest.PSObject.Properties['full_package_verification']
    if (-not $setting) { return $true }
    if ($setting.Value -isnot [bool]) { throw 'full_package_verification must be a JSON boolean.' }
    return $setting.Value
}

function Invoke-PackageArchiveCheck {
    param([string]$PackagePath,[string]$DistributionRoot,$Manifest)
    if (-not (Test-FullPackageVerificationEnabled $Manifest)) {
        Write-InstallerLog 'Debug build: skipping the long full-package archive test. Quick package checks remain enabled.'
        return
    }
    Write-InstallerLog 'Testing every ZIP entry before installation. This can take several minutes.'
    & (Join-Path $DistributionRoot 'Tools\7z.exe') t $PackagePath -bb0 -bsp1
    if ($LASTEXITCODE -ne 0) { throw 'The Perdition ZIP failed its full archive integrity test.' }
}

function New-SteamDepotArguments {
    param([string]$DepotId,[string]$ManifestId,[string]$GameRoot,[int]$LoginId,[string]$SteamUser='',[switch]$UseQr)
    $arguments=@('-app','377160','-depot',$DepotId,'-manifest',$ManifestId,'-dir',$GameRoot,'-remember-password','-loginid',$LoginId.ToString(),'-validate')
    if ($UseQr) {
        # DepotDownloader 3.4.0 rejects -qr together with -username.
        $arguments += '-qr'
    } else {
        if ([string]::IsNullOrWhiteSpace($SteamUser)) { throw 'Enter the Steam account name for password login, or choose QR login.' }
        $arguments += @('-username',$SteamUser)
    }
    return $arguments
}

function Get-SteamSessionContext {
    $text=[Environment]::MachineName+'|'+[Environment]::UserDomainName+'|'+[Environment]::UserName
    $hash=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($text)))).Replace('-','').ToLowerInvariant() }
    finally { $hash.Dispose() }
}

function Invoke-SteamDepotDownloads {
    param([string]$Downloader,$Manifest,[string]$GameRoot,[string]$SessionRoot,[string]$SteamUser,[switch]$UseQr,$State,[string]$StatePath)
    if ([string]::IsNullOrWhiteSpace($SteamUser)) { throw 'Enter your Steam login name so setup can reuse the authenticated account after the first sign-in.' }
    [void][IO.Directory]::CreateDirectory($GameRoot)
    [void][IO.Directory]::CreateDirectory($SessionRoot)
    $accountPath=Join-Path $SessionRoot 'remembered_account.json'
    $context=Get-SteamSessionContext
    $remembered=$false
    if (Test-Path -LiteralPath $accountPath) {
        try {
            $account=Get-Content -LiteralPath $accountPath -Raw | ConvertFrom-Json
            $remembered=$account.product -eq 'PerditionSteamSession' -and $account.account_name -eq $SteamUser -and $account.user_context -eq $context
        } catch { $remembered=$false }
    }
    $requestQr=[bool]$UseQr -and -not $remembered
    if ($remembered) { Write-InstallerLog 'Reusing the saved Steam sign-in for this installation.' }
    $loginId=Get-Random -Minimum 10000 -Maximum 2147483000
    foreach ($depot in $Manifest.depots) {
        $State.stage='Steam download: '+$depot.name
        Save-JsonFile $StatePath $State
        Write-InstallerLog ('Downloading and verifying '+$depot.name)
        if ($requestQr) { Write-Host 'Scan once using the Steam account matching the login name entered in setup. Later packages will reuse that sign-in.' }
        else { Write-Host 'Using the remembered account session. Steam may request authentication if the session is unavailable or expired.' }
        $arguments=@(New-SteamDepotArguments -DepotId ([string]$depot.depot) -ManifestId ([string]$depot.manifest) -GameRoot $GameRoot -LoginId $loginId -SteamUser $SteamUser -UseQr:$requestQr)
        Push-Location $SessionRoot
        try { & $Downloader @arguments; $exitCode=$LASTEXITCODE } finally { Pop-Location }
        if ($exitCode -ne 0) {
            # Do not trust our account-name hint after a failed authentication or
            # download. The downloader's own account token store is not altered.
            if ([IO.File]::Exists($accountPath)) { [IO.File]::Delete($accountPath) }
            throw "Steam download stopped for $($depot.name) (exit code $exitCode). The downloader's error is shown above. Retry setup to resume; completed game data is retained."
        }
        if ($requestQr) { Write-InstallerLog 'Steam sign-in completed. Remaining packages will reuse the saved session.' }
        $requestQr=$false
        Save-JsonFile $accountPath @{product='PerditionSteamSession';account_name=$SteamUser;user_context=$context;updated_utc=[DateTime]::UtcNow.ToString('o')}
        $State.completed_depots += [string]$depot.depot
        Save-JsonFile $StatePath $State
    }
}

function Get-RequiredInstallBytes {
    param([long]$PayloadBytes,[long]$ExistingBytes=0)
    if ($PayloadBytes -lt 0 -or $ExistingBytes -lt 0) { throw 'Installation byte counts cannot be negative.' }
    [long]$planned=$PayloadBytes+[long](44GB)+[long](1GB)
    [long]$remaining=$planned-$ExistingBytes
    # Both arguments must be Int64. An untyped zero selects Math.Max(Int32,
    # Int32) in Windows PowerShell 5.1 and overflows for this ~90 GB build.
    return [Math]::Max([long]0,$remaining)
}

function Invoke-PerditionInstallation {
    param([string]$InstallRoot,[string]$PackagePath,[string]$SteamUser,[int]$Width=1920,[int]$Height=1080,[switch]$UseQr,[string]$DistributionRoot,[switch]$DesktopShortcut,[switch]$EnableEnb)
    $destination=Assert-InstallDestination $InstallRoot $DistributionRoot $PackagePath
    $root=$destination.Root;$owned=$destination.Owned;$marker=$destination.Marker
    if ([string]::IsNullOrWhiteSpace($SteamUser)) { throw 'Enter your Steam login name so setup can reuse the signed-in account for all packages.' }
    if ($Width -lt 800 -or $Height -lt 600 -or $Width -gt 16384 -or $Height -gt 16384) { throw 'Choose a valid display resolution.' }
    Write-InstallerLog 'Reading the Perdition package...'
    $information=Get-PackageInformation $PackagePath
    $manifest=Get-Content -LiteralPath (Join-Path $DistributionRoot 'release.json') -Raw | ConvertFrom-Json
    if ($information.WorldHash -ne $manifest.world_plugin_sha256) { throw 'This setup release requires its matching Perdition package.' }
    $drive=New-Object IO.DriveInfo([IO.Path]::GetPathRoot($root))
    $existing=[long]0
    if ($owned) { foreach ($item in Get-ChildItem -LiteralPath $root -Recurse -File -Force) { $existing += $item.Length } }
    $required=Get-RequiredInstallBytes -PayloadBytes $information.Bytes -ExistingBytes $existing
    if ($drive.AvailableFreeSpace -lt $required) { throw ('Not enough free space. Setup needs about '+[Math]::Ceiling($required/1GB)+' GB more on this drive.') }
    $stateRoot=Join-Path $root '_Installer'
    [void][IO.Directory]::CreateDirectory($stateRoot)
    $script:LogPath=Join-Path $stateRoot 'install.log'
    if (-not $owned) { Save-JsonFile $marker @{product='PerditionSectorInstaller';root=$root;created_utc=[DateTime]::UtcNow.ToString('o')} }
    $state=@{status='running';stage='Preparing downloads';version=$manifest.version;root=$root;package=[IO.Path]::GetFullPath($PackagePath);completed_depots=@();enb_enabled=[bool]$EnableEnb}
    $statePath=Join-Path $stateRoot 'state.json'
    Save-JsonFile $statePath $state
    try {
        $cache=Join-Path $stateRoot 'Cache'
        if (Test-FullPackageVerificationEnabled $manifest) { $state.stage='Verifying the Perdition package' }
        else { $state.stage='Preparing downloads (debug: full archive test skipped)' }
        Save-JsonFile $statePath $state
        Invoke-PackageArchiveCheck -PackagePath $PackagePath -DistributionRoot $DistributionRoot -Manifest $manifest
        Install-VisualCppRuntimeIfNeeded $cache
        $depotZip=Get-VerifiedDownload $manifest.dependencies.depot_downloader $cache
        $depotRoot=Join-Path $stateRoot 'DepotDownloader'
        Expand-CheckedZip $depotZip $depotRoot
        $downloader=Join-Path $depotRoot 'DepotDownloader.exe'
        if (-not [IO.File]::Exists($downloader)) { throw 'DepotDownloader executable was not found in its official archive.' }
        $game=Join-Path $root '_Fallout4'
        $session=Join-Path $stateRoot 'SteamSession'
        Invoke-SteamDepotDownloads -Downloader $downloader -Manifest $manifest -GameRoot $game -SessionRoot $session -SteamUser $SteamUser -UseQr:$UseQr -State $state -StatePath $statePath
        $state.stage='Installing F4SE 0.6.23';Save-JsonFile $statePath $state
        $f4seArchive=Get-VerifiedDownload $manifest.dependencies.f4se $cache
        $f4seRoot=Join-Path $cache 'F4SE'
        [void][IO.Directory]::CreateDirectory($f4seRoot)
        & (Join-Path $DistributionRoot 'Tools\7z.exe') x $f4seArchive ('-o'+$f4seRoot) -y -bsp0 -bb0
        if ($LASTEXITCODE -ne 0) { throw 'F4SE extraction failed.' }
        $filesRoot=Join-Path $f4seRoot 'f4se_0_06_23'
        foreach ($name in @('f4se_loader.exe','f4se_1_10_163.dll','f4se_steam_loader.dll','f4se_readme.txt','f4se_whatsnew.txt')) { [IO.File]::Copy((Join-Path $filesRoot $name),(Join-Path $game $name),$true) }
        if (Test-Path -LiteralPath (Join-Path $filesRoot 'Data')) {
            foreach ($file in Get-ChildItem -LiteralPath (Join-Path $filesRoot 'Data') -Recurse -File) {
                $relative=$file.FullName.Substring($filesRoot.Length+1)
                $target=Get-SafeChildPath $game $relative
                [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target));[IO.File]::Copy($file.FullName,$target,$true)
            }
        }
        $state.stage='Installing Perdition Sector';Save-JsonFile $statePath $state
        Expand-PerditionPackage $PackagePath $root $information
        $overlay=Join-Path $DistributionRoot 'RootOverlay.zip'
        if ((Get-FileHash -LiteralPath $overlay -Algorithm SHA256).Hash -ne $manifest.root_overlay_sha256) { throw 'Gameplay root overlay failed verification.' }
        Install-GameRootOverlay $overlay $game ([bool]$EnableEnb)
        $state.stage='Configuring paths and display';Save-JsonFile $statePath $state
        New-MO2Configuration $root $Width $Height
        $state.stage='Verifying the installation';Save-JsonFile $statePath $state
        Assert-InstalledBuild $root $information $manifest
        if ($DesktopShortcut) {
            $shell=New-Object -ComObject WScript.Shell
            $shortcut=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Perdition Sector.lnk'))
            $shortcut.TargetPath=Join-Path $root 'Launch Perdition Sector.cmd';$shortcut.WorkingDirectory=$root
            $shortcut.IconLocation=(Join-Path $root 'ModOrganizer.exe')+',0';$shortcut.Save()
        }
        $state.status='complete';$state.stage='Ready to play';$state.completed_utc=[DateTime]::UtcNow.ToString('o')
        Save-JsonFile $statePath $state
        Save-JsonFile (Join-Path $stateRoot 'result.json') @{success=$true;root=$root;launcher=(Join-Path $root 'Launch Perdition Sector.cmd');runtime='1.10.163';f4se='0.6.23';enb_enabled=[bool]$EnableEnb}
        Write-InstallerLog 'Installation completed. Launch Perdition Sector.cmd starts the game through MO2 and F4SE.'
        Write-Host 'Start a New Game and choose your name and gender. Jug''s preset and Side Aim initialize automatically.'
    } catch {
        $state.status='failed';$state.error=$_.Exception.Message;Save-JsonFile $statePath $state
        Save-JsonFile (Join-Path $stateRoot 'result.json') @{success=$false;error=$_.Exception.Message}
        Write-InstallerLog ('Installation stopped: '+$_.Exception.Message)
        throw
    } finally { $script:LogPath=$null }
}

Export-ModuleMember -Function Get-SafeChildPath,Assert-NoLinkedAncestors,Get-PackageInformation,Test-PayloadEntry,Expand-PerditionPackage,Expand-CheckedZip,Install-GameRootOverlay,Set-IniValue,ConvertTo-WindowsArgument,New-MO2Configuration,Get-VerifiedDownload,Resolve-OnlinePackage,Assert-InstallPathPolicy,Assert-InstallDestination,Test-FullPackageVerificationEnabled,Invoke-PackageArchiveCheck,New-SteamDepotArguments,Invoke-SteamDepotDownloads,Get-RequiredInstallBytes,Invoke-PerditionInstallation
