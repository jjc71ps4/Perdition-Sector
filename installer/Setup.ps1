param([switch]$SmokeTest)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PerditionDisplay {
    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr context);
}
'@
[void][PerditionDisplay]::SetProcessDpiAwarenessContext([IntPtr](-4))
Import-Module (Join-Path $PSScriptRoot 'Core\Installer.psm1') -Force
[Windows.Forms.Application]::EnableVisualStyles()
$script:Worker=$null
$form=New-Object Windows.Forms.Form
$form.Text='Perdition Sector Setup 0.2.0-beta.1'
$form.ClientSize=New-Object Drawing.Size(760,590)
$form.StartPosition='CenterScreen'
$form.FormBorderStyle='FixedDialog'
$form.MaximizeBox=$false
$form.Font=New-Object Drawing.Font('Segoe UI',10)
$form.AutoScaleMode=[Windows.Forms.AutoScaleMode]::Dpi
$form.BackColor=[Drawing.Color]::FromArgb(25,27,30)
$form.ForeColor=[Drawing.Color]::Gainsboro

function Add-Label([string]$Text,[int]$X,[int]$Y,[int]$Width,[int]$Height) {
    $control=New-Object Windows.Forms.Label
    $control.Text=$Text;$control.SetBounds($X,$Y,$Width,$Height)
    $form.Controls.Add($control)
    return $control
}
function Add-TextBox([string]$Text,[int]$X,[int]$Y,[int]$Width) {
    $control=New-Object Windows.Forms.TextBox
    $control.Text=$Text;$control.SetBounds($X,$Y,$Width,28)
    $form.Controls.Add($control)
    return $control
}
function Add-Button([string]$Text,[int]$X,[int]$Y,[int]$Width) {
    $control=New-Object Windows.Forms.Button
    $control.Text=$Text;$control.SetBounds($X,$Y,$Width,30)
    $control.ForeColor=[Drawing.Color]::Black
    $control.UseVisualStyleBackColor=$true
    $form.Controls.Add($control)
    return $control
}

$title=Add-Label 'PERDITION SECTOR' 28 20 690 40
$title.Font=New-Object Drawing.Font('Segoe UI',21,[Drawing.FontStyle]::Bold)
$title.ForeColor=[Drawing.Color]::FromArgb(216,166,96)
[void](Add-Label 'Install Perdition Sector with its own compatible Fallout 4 instance.' 30 69 695 30)
[void](Add-Label 'Perdition package ZIP' 30 116 650 24)
$package=Add-TextBox '' 30 143 590
$browsePackage=Add-Button 'Browse...' 631 142 100
$online=New-Object Windows.Forms.CheckBox
$online.Text='Download the package automatically';$online.SetBounds(397,110,335,28)
$onlineAvailable=[IO.File]::Exists((Join-Path $PSScriptRoot 'package_source.json'))
$online.Visible=$onlineAvailable
$online.Checked=$onlineAvailable
$form.Controls.Add($online)
if ($online.Checked) { $package.Enabled=$false;$browsePackage.Enabled=$false }
$online.Add_CheckedChanged({$package.Enabled=-not $online.Checked;$browsePackage.Enabled=-not $online.Checked})
[void](Add-Label 'Install folder (new or setup-only; about 85 GB free, plus the ZIP)' 30 186 690 25)
$target=Add-TextBox ([IO.Path]::Combine([IO.Path]::GetPathRoot($PSScriptRoot),'Games\Perdition Sector')) 30 214 590
$browseTarget=Add-Button 'Browse...' 631 213 100
[void](Add-Label 'Steam login name' 30 260 355 24)
$username=Add-TextBox '' 30 288 340
$qr=New-Object Windows.Forms.CheckBox
$qr.Text='Use Steam mobile QR login';$qr.Checked=$false;$qr.SetBounds(397,289,330,28)
$form.Controls.Add($qr)
[void](Add-Label 'Resolution' 30 335 150 24)
$width=New-Object Windows.Forms.NumericUpDown
$height=New-Object Windows.Forms.NumericUpDown
$screen=[Windows.Forms.Screen]::PrimaryScreen.Bounds
$width.Minimum=800;$width.Maximum=16384;$width.Value=$screen.Width;$width.SetBounds(30,362,110,30)
$height.Minimum=600;$height.Maximum=16384;$height.Value=$screen.Height;$height.SetBounds(169,362,110,30)
$form.Controls.AddRange(@($width,$height))
[void](Add-Label 'x' 148 365 20 26)
$desktop=New-Object Windows.Forms.CheckBox
$desktop.Text='Create a desktop shortcut';$desktop.Checked=$true;$desktop.SetBounds(397,361,330,28)
$form.Controls.Add($desktop)
$enb=New-Object Windows.Forms.CheckBox
$enb.Text='Enable ENB (brightens the image; optional)';$enb.Checked=$false;$enb.SetBounds(30,397,700,28)
$form.Controls.Add($enb)
$note=Add-Label 'Use your Steam login name. Approve Steam Guard or scan a QR once; setup reuses that account for all packages.' 30 435 700 43
$note.ForeColor=[Drawing.Color]::Silver
$status=Add-Label 'Choose an installation folder, Steam account and resolution.' 30 490 700 40
$install=Add-Button 'Install / Resume' 30 538 180
$launch=Add-Button 'Launch Perdition Sector' 405 538 240
$launch.Enabled=$false
$close=Add-Button 'Close' 655 538 78

$browsePackage.Add_Click({
    $dialog=New-Object Windows.Forms.OpenFileDialog
    $dialog.Title='Select Perdition Sector ZIP';$dialog.Filter='Perdition ZIP package (*.zip)|*.zip'
    if ($dialog.ShowDialog($form) -eq [Windows.Forms.DialogResult]::OK) { $package.Text=$dialog.FileName }
    $dialog.Dispose()
})
$browseTarget.Add_Click({
    $dialog=New-Object Windows.Forms.FolderBrowserDialog
    $dialog.Description='Choose a new folder, or the folder containing only this Perdition setup bundle.'
    $dialog.SelectedPath=$target.Text;$dialog.ShowNewFolderButton=$true
    if ($dialog.ShowDialog($form) -eq [Windows.Forms.DialogResult]::OK) { $target.Text=$dialog.SelectedPath }
    $dialog.Dispose()
})
$install.Add_Click({
    try {
        if (-not $online.Checked -and -not [IO.File]::Exists($package.Text)) { throw 'Select an existing Perdition Sector ZIP.' }
        if ([string]::IsNullOrWhiteSpace($target.Text)) { throw 'Choose an installation folder.' }
        if ([string]::IsNullOrWhiteSpace($username.Text)) { throw 'Enter your Steam login name so setup can reuse the account after sign-in.' }
        $script:WorkerRoot=[IO.Path]::GetFullPath($target.Text)
        $args=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Core\Run-Install.ps1'),'-InstallRoot',$script:WorkerRoot,'-SteamUser',$username.Text,'-Width',[string]$width.Value,'-Height',[string]$height.Value)
        if ($online.Checked) { $args += '-DownloadPackage' } else { $args += @('-PackagePath',$package.Text) }
        if ($qr.Checked) { $args += '-UseQr' }
        if ($desktop.Checked) { $args += '-DesktopShortcut' }
        if ($enb.Checked) { $args += '-EnableEnb' }
        $start=New-Object Diagnostics.ProcessStartInfo
        $start.FileName=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $start.Arguments=($args | ForEach-Object { ConvertTo-WindowsArgument $_ }) -join ' '
        $start.UseShellExecute=$true;$start.WindowStyle=[Diagnostics.ProcessWindowStyle]::Normal
        $script:Worker=[Diagnostics.Process]::Start($start)
        $install.Enabled=$false;$package.Enabled=$false;$target.Enabled=$false
        $launch.Enabled=$false;$browsePackage.Enabled=$false;$browseTarget.Enabled=$false
        $online.Enabled=$false
        $status.Text='Setup started. Use the download window for Steam authentication and progress.'
        $timer.Start()
    } catch { [void][Windows.Forms.MessageBox]::Show($form,$_.Exception.Message,'Setup',[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Warning) }
})
$launch.Add_Click({
    $path=Join-Path $script:WorkerRoot 'Launch Perdition Sector.cmd'
    Start-Process -FilePath $path -WorkingDirectory $script:WorkerRoot -WindowStyle Hidden
})
$close.Add_Click({$form.Close()})
$form.Add_FormClosing({
    param($sender,$eventArgs)
    if ($script:Worker -and -not $script:Worker.HasExited) {
        $eventArgs.Cancel=$true
        [void][Windows.Forms.MessageBox]::Show($form,'Setup is still running. Finish or stop it in the download window before closing this window.','Setup is running')
    }
})
$timer=New-Object Windows.Forms.Timer
$timer.Interval=2000
$timer.Add_Tick({
    if (-not $script:Worker) { return }
    $statePath=Join-Path $script:WorkerRoot '_Installer\state.json'
    if ([IO.File]::Exists($statePath)) {
        try { $state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json;$status.Text=$state.stage } catch { }
    }
    if ($script:Worker.HasExited) {
        $timer.Stop();$install.Enabled=$true;$package.Enabled=-not $online.Checked;$target.Enabled=$true
        $browsePackage.Enabled=-not $online.Checked;$browseTarget.Enabled=$true;$online.Enabled=$true
        $result=Join-Path $script:WorkerRoot '_Installer\result.json'
        if ($script:Worker.ExitCode -eq 0 -and [IO.File]::Exists($result) -and (Get-Content -LiteralPath $result -Raw | ConvertFrom-Json).success) {
            $status.Text='Installation verified. Ready to play.';$launch.Enabled=$true
        } else { $status.Text='Setup stopped. Read the download window or install log, then retry to resume.' }
    }
})
if ($SmokeTest) {
    [pscustomobject]@{title=$form.Text;controls=$form.Controls.Count;width=$form.ClientSize.Width;height=$form.ClientSize.Height;nativeResolution=($screen.Width.ToString()+'x'+$screen.Height)} | ConvertTo-Json
    $timer.Dispose();$form.Dispose();exit 0
}
[void]$form.ShowDialog()
$timer.Dispose();$form.Dispose()
