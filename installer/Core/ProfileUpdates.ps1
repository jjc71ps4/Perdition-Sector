# Declarative, targeted profile migrations. No save or arbitrary profile paths.
function Get-PSProfileTextHash([string]$Text) {
    $hash=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-','').ToLowerInvariant() }
    finally { $hash.Dispose() }
}

function Set-PSProfileListEntry([string]$Text,[string]$Name,[string]$Mode,[bool]$Enabled) {
    if ($Name -notmatch '^[^\\/:*?"<>|\r\n]{1,180}$') { throw 'Invalid profile entry name.' }
    $newline=if ($Text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $lines=New-Object 'Collections.Generic.List[string]'
    foreach ($line in ($Text.TrimEnd("`r","`n") -split '\r?\n')) { $lines.Add($line) }
    $found=-1
    for ($i=0;$i -lt $lines.Count;$i++) {
        $line=$lines[$i]
        if ($line.StartsWith('#') -or -not $line) { continue }
        $value=if ($Mode -eq 'mod') { $line.Substring(1) } elseif ($Mode -eq 'plugin') { $line.TrimStart('*') } else { $line }
        if ($value -ieq $Name) { if ($found -ge 0) { throw "Duplicate profile entry: $Name" };$found=$i }
    }
    $replacement=if ($Mode -eq 'mod') { $(if ($Enabled) {'+'} else {'-'})+$Name } elseif ($Mode -eq 'plugin') { $(if ($Enabled) {'*'} else {''})+$Name } else { $Name }
    if ($found -ge 0) { $lines[$found]=$replacement }
    elseif ($Mode -eq 'mod' -and $Enabled) { $lines.Insert($(if($lines.Count -gt 0 -and $lines[0].StartsWith('#')){1}else{0}),$replacement) }
    else { $lines.Add($replacement) }
    return ($lines -join $newline)+$newline
}

function Set-PSProfileDistance([string]$Text,$Setting) {
    $allowed=@{
        'Display/fMeshLODLevel1FadeDist'='3500';'Display/fMeshLODLevel2FadeDist'='2000'
        'Display/fInteriorMeshLODLevel1FadeDist'='2600';'Display/fInteriorMeshLODLevel2FadeDist'='1950'
        'Display/fMeshLODFadeScalar'='1';'LOD/fLODFadeOutMultObjects'='15'
    }
    $identity=([string]$Setting.section)+'/'+([string]$Setting.key)
    if (-not $allowed.ContainsKey($identity) -or [string]$Setting.value -ne $allowed[$identity]) { throw 'Unsupported profile setting migration.' }
    $newline=if ($Text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $lines=$Text.TrimEnd("`r","`n") -split '\r?\n';$section='';$found=-1
    for ($i=0;$i -lt $lines.Count;$i++) {
        $line=$lines[$i]
        if ($line -match '^\s*\[([^\]]+)\]\s*$') { $section=$Matches[1];continue }
        if ($section -ieq $Setting.section -and $line -match ('^(\s*'+[regex]::Escape($Setting.key)+'\s*=\s*)([^;#]*)(.*)$')) {
            if ($found -ge 0) { throw "Duplicate INI setting: $identity" };$found=$i
            $prefix=$Matches[1];$current=$Matches[2].Trim();$suffix=$Matches[3]
            $number=[double]::Parse($current,[Globalization.CultureInfo]::InvariantCulture)
            $permitted=@([string]$Setting.value)+@($Setting.previous_values)
            $match=@($permitted | Where-Object { [double]::Parse([string]$_,[Globalization.CultureInfo]::InvariantCulture) -eq $number }).Count -gt 0
            if (-not $match) { throw "A custom distance setting was preserved: $identity=$current" }
            if ($number -ne [double]$Setting.value) { $lines[$i]=$prefix+([string]$Setting.value)+'.0000'+$suffix }
        }
    }
    if ($found -lt 0) { throw "Required profile setting missing: $identity" }
    return ($lines -join $newline)+$newline
}

function Get-PSUpdateProfileChanges($Update,[string]$Root) {
    $property=$Update.PSObject.Properties['profile_changes']
    if (-not $property) { return @() }
    $definition=$property.Value
    if ($definition.schema_version -ne 1) { throw 'Unsupported profile migration.' }
    $names=@('schema_version','enable_mods','disable_mods','enable_plugins','settings')
    foreach ($p in $definition.PSObject.Properties.Name) { if ($names -notcontains $p) { throw 'Unsupported profile action.' } }
    foreach ($p in $names) { if (-not $definition.PSObject.Properties[$p]) { throw 'Incomplete profile migration.' } }
    $content=@{};$paths=@{}
    foreach ($name in @('modlist.txt','plugins.txt','loadorder.txt','fallout4prefs.ini')) {
        $path=Join-Path $Root ('profiles\FO4ME\'+$name);Assert-PSUpdateUnlinked $path
        if (-not [IO.File]::Exists($path)) { throw "Missing Perdition profile file: $name" }
        $paths[$name]=$path;$content[$name]=[IO.File]::ReadAllText($path)
    }
    foreach ($name in $definition.enable_mods) { $content['modlist.txt']=Set-PSProfileListEntry $content['modlist.txt'] $name 'mod' $true }
    foreach ($name in $definition.disable_mods) { $content['modlist.txt']=Set-PSProfileListEntry $content['modlist.txt'] $name 'mod' $false }
    foreach ($name in $definition.enable_plugins) {
        if ($name -notmatch '\.(esp|esm|esl)$') { throw 'Invalid plugin name.' }
        $content['plugins.txt']=Set-PSProfileListEntry $content['plugins.txt'] $name 'plugin' $true
        $content['loadorder.txt']=Set-PSProfileListEntry $content['loadorder.txt'] $name 'order' $true
    }
    foreach ($setting in $definition.settings) { $content['fallout4prefs.ini']=Set-PSProfileDistance $content['fallout4prefs.ini'] $setting }
    foreach ($name in @('modlist.txt','plugins.txt','loadorder.txt','fallout4prefs.ini')) {
        $before=Get-PSUpdateHash $paths[$name];$after=Get-PSProfileTextHash $content[$name]
        [pscustomobject]@{Target=$paths[$name];Relative=('profiles/FO4ME/'+$name);Before=$before;After=$after;Content=$content[$name]}
    }
}
