param(
    [switch]$VerifyOnly,
    [string]$PreviewPath,
    [ValidateRange(500,10000)][int]$SplashMilliseconds = 1800
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$mo2 = Join-Path $root 'ModOrganizer.exe'
$artPath = Join-Path $root 'splash.png'
$iniPath = Join-Path $root 'ModOrganizer.ini'
$logPath = Join-Path $PSScriptRoot 'launcher.log'

function Get-CompactSplashConfig {
    param([string]$Text)
    $newline = if ($Text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $section = [regex]::Match($Text,'(?im)^\[Settings\][^\r\n]*(?:\r?\n|$)')
    if (-not $section.Success) { return $Text.TrimEnd("`r","`n")+$newline+'[Settings]'+$newline+'use_splash=false'+$newline }
    $start = $section.Index+$section.Length
    $tail = $Text.Substring($start)
    $next = [regex]::Match($tail,'(?m)^\[')
    $length = if ($next.Success) { $next.Index } else { $tail.Length }
    $body = $tail.Substring(0,$length)
    $key = [regex]::Match($body,'(?im)^use_splash[ \t]*=[^\r\n]*')
    if ($key.Success) {
        $body = $body.Substring(0,$key.Index)+'use_splash=false'+$body.Substring($key.Index+$key.Length)
    } else { $body = 'use_splash=false'+$newline+$body }
    $prefix = $Text.Substring(0,$start)
    if (-not $prefix.EndsWith("`n")) { $prefix += $newline }
    return $prefix+$body+$tail.Substring($length)
}

function Get-SplashBounds {
    param([int]$ImageWidth,[int]$ImageHeight,[Drawing.Rectangle]$WorkArea)
    if ($ImageWidth -le 0 -or $ImageHeight -le 0) { throw 'Splash artwork has invalid dimensions.' }
    $limitW = [Math]::Max(1, [Math]::Min(800, $WorkArea.Width - 48))
    $limitH = [Math]::Max(1, [Math]::Min(600, $WorkArea.Height - 48))
    $scale = [Math]::Min($limitW / [double]$ImageWidth, $limitH / [double]$ImageHeight)
    $width = [Math]::Max(1, [int][Math]::Floor($ImageWidth * $scale))
    $height = [Math]::Max(1, [int][Math]::Floor($ImageHeight * $scale))
    $left = $WorkArea.Left + [int][Math]::Floor(($WorkArea.Width - $width) / 2.0)
    $top = $WorkArea.Top + [int][Math]::Floor(($WorkArea.Height - $height) / 2.0)
    return [Drawing.Rectangle]::new($left,$top,$width,$height)
}

function Show-PerditionSplash {
    param([switch]$Offscreen,[string]$SavePreview)
    $form = $null; $art = $null; $timer = $null; $picture = $null
    try {
        $art = [Drawing.Image]::FromFile($artPath)
        $area = [Windows.Forms.Screen]::FromPoint([Windows.Forms.Cursor]::Position).WorkingArea
        $bounds = Get-SplashBounds $art.Width $art.Height $area
        $form = New-Object Windows.Forms.Form
        $form.Text = 'Perdition Sector'
        $form.FormBorderStyle = [Windows.Forms.FormBorderStyle]::None
        $form.StartPosition = [Windows.Forms.FormStartPosition]::Manual
        $form.AutoScaleMode = [Windows.Forms.AutoScaleMode]::None
        $form.BackColor = [Drawing.Color]::Black
        $form.ShowInTaskbar = $false
        $form.TopMost = $false
        $form.Bounds = $bounds
        $picture = New-Object Windows.Forms.PictureBox
        $picture.Dock = [Windows.Forms.DockStyle]::Fill
        $picture.BackColor = [Drawing.Color]::Black
        $picture.SizeMode = [Windows.Forms.PictureBoxSizeMode]::Zoom
        $picture.Image = $art
        $form.Controls.Add($picture)

        if ($Offscreen) {
            [void]$form.CreateControl()
            [void]$picture.CreateControl()
            $picture.Bounds = [Drawing.Rectangle]::new(0,0,$bounds.Width,$bounds.Height)
            $form.PerformLayout()
            if ($SavePreview) {
                $bitmap = New-Object Drawing.Bitmap($bounds.Width,$bounds.Height)
                try {
                    $picture.DrawToBitmap($bitmap,[Drawing.Rectangle]::new(0,0,$bounds.Width,$bounds.Height))
                    $bitmap.Save($SavePreview,[Drawing.Imaging.ImageFormat]::Png)
                } finally { $bitmap.Dispose() }
            }
            return @{width=$bounds.Width;height=$bounds.Height;left=$bounds.Left;top=$bounds.Top;art_width=$art.Width;art_height=$art.Height}
        }

        $timer = New-Object Windows.Forms.Timer
        $timer.Interval = $SplashMilliseconds
        $timer.Add_Tick({ $timer.Stop(); $form.Close() }.GetNewClosure())
        $form.Add_Shown({ $timer.Start() }.GetNewClosure())
        [void]$form.ShowDialog()
    } finally {
        if ($timer) { $timer.Stop(); $timer.Dispose() }
        if ($picture) { $picture.Image = $null }
        if ($form) { $form.Dispose() }
        if ($art) { $art.Dispose() }
    }
}

try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PerditionLauncherDisplay {
    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
'@
    try { [void][PerditionLauncherDisplay]::SetProcessDpiAwarenessContext([IntPtr](-4)) }
    catch { try { [void][PerditionLauncherDisplay]::SetProcessDPIAware() } catch {} }
    [Windows.Forms.Application]::EnableVisualStyles()
    foreach ($p in @($mo2,$artPath,$iniPath,(Join-Path $root 'profiles\FO4ME'))) {
        if (-not (Test-Path -LiteralPath $p)) { throw "A required Perdition Sector file or folder is missing: $p" }
    }
    $config = [IO.File]::ReadAllText($iniPath)
    if ($config -notmatch '(?m)^\d+\\title=F4SE\s*$') { throw 'The F4SE entry is missing from Mod Organizer.' }

    if ($VerifyOnly) {
        $result = Show-PerditionSplash -Offscreen -SavePreview $PreviewPath
        $result['profile'] = 'FO4ME'; $result['executable'] = 'F4SE'
        $result['game_launched'] = $false; $result['steam_started'] = $false
        $result | ConvertTo-Json -Compress
        exit 0
    }

    # MO2 2.4.4 reads Settings/use_splash. Suppress its unscaled duplicate;
    # this launcher displays the original artwork at a monitor-fitted size.
    # When MO2 is already open it forwards the launch and shows no new splash.
    if (-not (Get-Process -Name ModOrganizer -ErrorAction SilentlyContinue)) {
        $updated = Get-CompactSplashConfig $config
        if ($updated -cne $config) {
            $iniBytes = [IO.File]::ReadAllBytes($iniPath)
            $hasBom = $iniBytes.Length -ge 3 -and $iniBytes[0] -eq 239 -and $iniBytes[1] -eq 187 -and $iniBytes[2] -eq 191
            [IO.File]::WriteAllText($iniPath,$updated,[Text.UTF8Encoding]::new($hasBom))
        }
    }

    $startedSteam = $false
    $startup = [Diagnostics.Stopwatch]::StartNew()
    if (-not (Get-Process -Name steam -ErrorAction SilentlyContinue)) {
        # Same Steam bootstrap as the installer launcher. Steam is interactive
        # when sign-in is needed; the helper itself is launched hidden by CMD.
        Start-Process -FilePath 'steam://open/main'
        $startedSteam = $true
    }
    try { Show-PerditionSplash }
    catch { [IO.File]::AppendAllText($logPath, ('Splash skipped: '+$_.Exception.Message+"`r`n")) }
    # All splash controls/timers are disposed before calling MO2/F4SE.
    if ($startedSteam -and $startup.ElapsedMilliseconds -lt 8000) {
        Start-Sleep -Milliseconds ([int](8000-$startup.ElapsedMilliseconds))
    }
    [IO.File]::AppendAllText($logPath, ([DateTime]::Now.ToString('s')+' Launching FO4ME / F4SE'+"`r`n"))
    Set-Location -LiteralPath $root
    & $mo2 -p 'FO4ME' 'moshortcut://:F4SE'
    if ($LASTEXITCODE) { throw "Mod Organizer returned exit code $LASTEXITCODE." }
} catch {
    $detail = $_.Exception.Message
    try { [IO.File]::AppendAllText($logPath, ([DateTime]::Now.ToString('s')+' '+$detail+"`r`n")) } catch {}
    try { [void][Windows.Forms.MessageBox]::Show($detail,'Perdition Sector',[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Error) } catch {}
    exit 1
}
