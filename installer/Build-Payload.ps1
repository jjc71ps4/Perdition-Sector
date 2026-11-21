param(
    [Parameter(Mandatory=$true)][string]$SourceZip,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$BaseDownloadUrl='',
    [long]$PartBytes=1900000000
)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'Core\Installer.psm1') -Force
if ($PartBytes -lt 1024 -or $PartBytes -ge 2147483648) { throw 'Release parts must be at least 1 KB and smaller than 2 GiB.' }
if ($BaseDownloadUrl -and ([Uri]$BaseDownloadUrl).Scheme -ne 'https') { throw 'Use an HTTPS release download URL.' }
$info=Get-PackageInformation $SourceZip
$release=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'release.json') -Raw | ConvertFrom-Json
if ($info.WorldHash -ne $release.world_plugin_sha256) { throw 'The source archive does not match this setup release.' }
$output=[IO.Path]::GetFullPath($OutputDirectory)
Assert-NoLinkedAncestors $output
if ((Test-Path -LiteralPath $output) -and @(Get-ChildItem -LiteralPath $output -Force).Count) { throw 'Select an empty output folder; existing releases will not be overwritten.' }
$drive=New-Object IO.DriveInfo([IO.Path]::GetPathRoot($output))
if ($drive.AvailableFreeSpace -lt (2*$info.Bytes+1GB)) { throw 'The output drive needs room for the clean ZIP and its release parts.' }
[void][IO.Directory]::CreateDirectory($output)
$name='Perdition_Payload_v'+$release.version+'.zip'
$archivePath=Join-Path $output $name
$partial=$archivePath+'.partial'
$source=[IO.Compression.ZipFile]::OpenRead($SourceZip)
$destination=[IO.Compression.ZipFile]::Open($partial,[IO.Compression.ZipArchiveMode]::Create)
$count=0
try {
    foreach ($entry in $source.Entries) {
        if (-not $entry.FullName.StartsWith($info.Prefix,[StringComparison]::Ordinal)) { continue }
        $relative=$entry.FullName.Substring($info.Prefix.Length)
        if (-not (Test-PayloadEntry $relative $info.Mods)) { continue }
        $target=$destination.CreateEntry('Perdition Sector/'+$relative,[IO.Compression.CompressionLevel]::Fastest)
        $inputStream=$entry.Open();$outputStream=$target.Open()
        try {$inputStream.CopyTo($outputStream)} finally {$inputStream.Dispose();$outputStream.Dispose()}
        $count++
        if ($count % 250 -eq 0) { Write-Progress -Activity 'Preparing player package' -Status "$count of $($info.Files) files" -PercentComplete ([Math]::Min(100,100*$count/$info.Files)) }
    }
} finally {$source.Dispose();$destination.Dispose();Write-Progress -Activity 'Preparing player package' -Completed}
& (Join-Path $PSScriptRoot 'Tools\7z.exe') t $partial -tzip -bb0 -bsp0
if ($LASTEXITCODE -ne 0) { throw 'The clean player package failed its archive test.' }
[IO.File]::Move($partial,$archivePath)
$archiveHash=(Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
$parts=@();$inputStream=[IO.File]::OpenRead($archivePath);$buffer=New-Object byte[] (8MB)
try {
    while ($inputStream.Position -lt $inputStream.Length) {
        $partName=$name+'.'+($parts.Count+1).ToString('000')
        $partPath=Join-Path $output $partName
        $stream=[IO.File]::Open($partPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
        $hash=[Security.Cryptography.SHA256]::Create();$written=[long]0
        try {
            while ($written -lt $PartBytes -and $inputStream.Position -lt $inputStream.Length) {
                $amount=[int][Math]::Min($buffer.Length,$PartBytes-$written)
                $read=$inputStream.Read($buffer,0,$amount)
                if (-not $read) { break }
                $stream.Write($buffer,0,$read);[void]$hash.TransformBlock($buffer,0,$read,$buffer,0);$written+=$read
            }
            [void]$hash.TransformFinalBlock([byte[]]@(),0,0)
            $partHash=([BitConverter]::ToString($hash.Hash)).Replace('-','').ToLowerInvariant()
        } finally {$stream.Dispose();$hash.Dispose()}
        $url='';if ($BaseDownloadUrl) {$url=$BaseDownloadUrl.TrimEnd('/')+'/'+$partName}
        $parts+=@{filename=$partName;bytes=$written;sha256=$partHash;url=$url}
        Write-Host ('Prepared '+$partName)
    }
} finally {$inputStream.Dispose()}
$manifest=@{version=$release.version;archive_name=$name;archive_bytes=(Get-Item -LiteralPath $archivePath).Length;archive_sha256=$archiveHash;installed_payload_bytes=$info.Bytes;parts=$parts}
$manifestName='package_source.pending.json';if ($BaseDownloadUrl) {$manifestName='package_source.json'}
[IO.File]::WriteAllText((Join-Path $output $manifestName),($manifest | ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText((Join-Path $output ($name+'.sha256.txt')),$archiveHash+'  '+$name+"`n",[Text.Encoding]::ASCII)
Write-Host ('Created a player package with '+$count+' files. Personal saves, original account settings, disabled mods and development tools were excluded.')
if ($BaseDownloadUrl) { Write-Host 'Upload the numbered parts as release assets, and include package_source.json in the setup distribution.' }
else { Write-Host 'Hosting is not configured. The pending source manifest needs HTTPS URLs for the uploaded numbered parts before use.' }
