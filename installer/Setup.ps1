param([switch]$SmokeTest,[string[]]$DetectionPaths)
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
$script:SelectedGameValid=$false
$requirement='Perdition Sector requires downgraded Fallout 4 version 1.10.163 with all six DLCs. Select the folder containing Fallout4.exe.'
$screen=[Windows.Forms.Screen]::PrimaryScreen
$form=New-Object Windows.Forms.Form
$form.Text='Perdition Sector Setup 0.2.3-beta.1'
$form.ClientSize=New-Object Drawing.Size(760,([Math]::Min(745,[Math]::Max(500,$screen.WorkingArea.Height-80))))
$form.AutoScroll=$true
$form.AutoScrollMinSize=New-Object Drawing.Size(740,735)
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
    $control.ForeColor=[Drawing.Color]::Black;$control.UseVisualStyleBackColor=$true
    $form.Controls.Add($control)
    return $control
}
$title=Add-Label 'PERDITION SECTOR' 28 20 690 40
$title.Font=New-Object Drawing.Font('Segoe UI',21,[Drawing.FontStyle]::Bold)
$title.ForeColor=[Drawing.Color]::FromArgb(216,166,96)
[void](Add-Label 'Requires Fallout 4 1.10.163 and all six DLCs.' 30 69 695 30)
[void](Add-Label 'Perdition package ZIP' 30 116 650 24)
$package=Add-TextBox '' 30 143 590
$browsePackage=Add-Button 'Browse...' 631 142 100
$online=New-Object Windows.Forms.CheckBox
$online.Text='Download the package from GitHub';$online.SetBounds(397,110,335,28)
$onlineAvailable=[IO.File]::Exists((Join-Path $PSScriptRoot 'package_source.json'))
$online.Visible=$onlineAvailable;$online.Checked=$onlineAvailable
$form.Controls.Add($online)
$online.Add_CheckedChanged({$package.Enabled=-not $online.Checked;$browsePackage.Enabled=-not $online.Checked})
[void](Add-Label 'Perdition install folder (separate from the Fallout 4 folder)' 30 186 690 25)
$target=Add-TextBox ([IO.Path]::Combine([IO.Path]::GetPathRoot($PSScriptRoot),'Games\Perdition Sector')) 30 214 590
$browseTarget=Add-Button 'Browse...' 631 213 100

$existing=New-Object Windows.Forms.RadioButton
$existing.Text='Use existing downgraded Fallout 4';$existing.SetBounds(30,260,350,28)
$downloadGame=New-Object Windows.Forms.RadioButton
$downloadGame.Text='Download compatible game from Steam';$downloadGame.SetBounds(397,260,340,28)
$form.Controls.AddRange(@($existing,$downloadGame))
[void](Add-Label 'Existing Fallout 4 folder' 30 301 690 24)
$existingPath=Add-TextBox '' 30 328 590
$browseGame=Add-Button 'Browse...' 631 327 100
$gameStatus=Add-Label '' 30 367 700 45
[void](Add-Label 'Steam login name (Steam download option only)' 30 423 690 24)
$username=Add-TextBox '' 30 451 340
$qr=New-Object Windows.Forms.CheckBox
$qr.Text='Use Steam mobile QR login';$qr.SetBounds(397,450,330,28)
$form.Controls.Add($qr)
[void](Add-Label 'Resolution' 30 494 150 24)
$width=New-Object Windows.Forms.NumericUpDown
$height=New-Object Windows.Forms.NumericUpDown
$width.Minimum=800;$width.Maximum=16384;$width.Value=$screen.Bounds.Width;$width.SetBounds(30,521,110,30)
$height.Minimum=600;$height.Maximum=16384;$height.Value=$screen.Bounds.Height;$height.SetBounds(169,521,110,30)
$form.Controls.AddRange(@($width,$height))
[void](Add-Label 'x' 148 524 20 26)
$desktop=New-Object Windows.Forms.CheckBox
$desktop.Text='Create a desktop shortcut';$desktop.Checked=$true;$desktop.SetBounds(397,520,330,28)
$form.Controls.Add($desktop)
$enb=New-Object Windows.Forms.CheckBox
$enb.Text='Enable ENB (brightens the image; optional)';$enb.SetBounds(30,561,700,28)
$form.Controls.Add($enb)
$note=Add-Label 'Uses the selected game folder directly. Setup adds F4SE and required game files; replaced files are backed up in the Perdition install folder.' 30 600 700 43
$note.ForeColor=[Drawing.Color]::Silver
$status=Add-Label 'Choose a compatible Fallout 4 folder to continue.' 30 650 700 32
$install=Add-Button 'Install / Resume' 30 694 180
$launch=Add-Button 'Launch Perdition Sector' 405 694 240
$launch.Enabled=$false
$close=Add-Button 'Close' 655 694 78

function Update-GameSelection {
    $busy=$script:Worker -and -not $script:Worker.HasExited
    $existingPath.Enabled=$existing.Checked -and -not $busy
    $browseGame.Enabled=$existingPath.Enabled
    $username.Enabled=$downloadGame.Checked -and -not $busy
    $qr.Enabled=$username.Enabled
    $script:SelectedGameValid=$false
    if ($existing.Checked) {
        try {
            [void](Assert-CompatibleGameFolder $existingPath.Text)
            $script:SelectedGameValid=$true
            $gameStatus.Text='Compatible Fallout 4 1.10.163 and all six DLCs found. Steam downloads and Steam sign-in will be skipped.'
            $gameStatus.ForeColor=[Drawing.Color]::LightGreen
        } catch {
            $gameStatus.Text=$requirement
            $gameStatus.ForeColor=[Drawing.Color]::Goldenrod
        }
        $note.Text='Uses the selected game folder directly. Setup adds F4SE and required game files; replaced files are backed up in the Perdition install folder.'
    } else {
        $gameStatus.Text='Setup will download Fallout 4 1.10.163 and all six DLCs into its own _Fallout4 folder using your Steam account.'
        $gameStatus.ForeColor=[Drawing.Color]::Gainsboro
        $note.Text='A Steam account owning Fallout 4 and all six DLCs is required. Your existing Steam installation is preserved.'
    }
    $install.Enabled=(-not $busy) -and ($downloadGame.Checked -or $script:SelectedGameValid)
}
$existing.Add_CheckedChanged({Update-GameSelection})
$downloadGame.Add_CheckedChanged({Update-GameSelection})
$existingPath.Add_TextChanged({Update-GameSelection})
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
$browseGame.Add_Click({
    $dialog=New-Object Windows.Forms.FolderBrowserDialog
    $dialog.Description='Select the downgraded Fallout 4 folder containing Fallout4.exe.'
    $dialog.ShowNewFolderButton=$false
    if ($existingPath.Text -and [IO.Directory]::Exists($existingPath.Text)) { $dialog.SelectedPath=$existingPath.Text }
    if ($dialog.ShowDialog($form) -eq [Windows.Forms.DialogResult]::OK) {
        $existingPath.Text=$dialog.SelectedPath
        try { [void](Assert-CompatibleGameFolder $existingPath.Text) }
        catch { [void][Windows.Forms.MessageBox]::Show($form,$_.Exception.Message,'Fallout 4 required',[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Warning) }
    }
    $dialog.Dispose()
})
$install.Add_Click({
    try {
        [void](Resolve-GameInstallPlan -InstallRoot $target.Text -UseExistingGame:$existing.Checked -ExistingGameRoot $existingPath.Text -SteamUser $username.Text)
        if (-not $online.Checked -and -not [IO.File]::Exists($package.Text)) { throw 'Select an existing Perdition Sector ZIP.' }
        if ([string]::IsNullOrWhiteSpace($target.Text)) { throw 'Choose an installation folder.' }
        $script:WorkerRoot=[IO.Path]::GetFullPath($target.Text)
        [void](Assert-InstallDestination $script:WorkerRoot $PSScriptRoot $package.Text)
        $arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Core\Run-Install.ps1'),'-InstallRoot',$script:WorkerRoot,'-Width',[string]$width.Value,'-Height',[string]$height.Value)
        if ($existing.Checked) { $arguments+=@('-UseExistingGame','-ExistingGameRoot',$existingPath.Text) }
        else {
            $arguments+=@('-SteamUser',$username.Text)
            if ($qr.Checked) { $arguments+='-UseQr' }
        }
        if ($online.Checked) { $arguments+='-DownloadPackage' } else { $arguments+=@('-PackagePath',$package.Text) }
        if ($desktop.Checked) { $arguments+='-DesktopShortcut' }
        if ($enb.Checked) { $arguments+='-EnableEnb' }
        $start=New-Object Diagnostics.ProcessStartInfo
        $start.FileName=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $start.Arguments=($arguments | ForEach-Object { ConvertTo-WindowsArgument $_ }) -join ' '
        $start.UseShellExecute=$true;$start.WindowStyle=[Diagnostics.ProcessWindowStyle]::Normal
        $script:Worker=[Diagnostics.Process]::Start($start)
        foreach ($control in @($install,$package,$target,$browsePackage,$browseTarget,$online,$existing,$downloadGame,$width,$height,$desktop,$enb)) { $control.Enabled=$false }
        $launch.Enabled=$false
        Update-GameSelection
        $status.Text='Setup started. Use the setup window for download progress.'
        $timer.Start()
    } catch { [void][Windows.Forms.MessageBox]::Show($form,$_.Exception.Message,'Setup',[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Warning) }
})
$launch.Add_Click({
    Start-Process -FilePath (Join-Path $script:WorkerRoot 'Launch Perdition Sector.cmd') -WorkingDirectory $script:WorkerRoot -WindowStyle Hidden
})
$close.Add_Click({$form.Close()})
$form.Add_FormClosing({
    param($sender,$eventArgs)
    if ($script:Worker -and -not $script:Worker.HasExited) {
        $eventArgs.Cancel=$true
        [void][Windows.Forms.MessageBox]::Show($form,'Setup is still running. Finish or stop it in the setup window before closing this window.','Setup is running')
    }
})
$timer=New-Object Windows.Forms.Timer
$timer.Interval=2000
$timer.Add_Tick({
    if (-not $script:Worker) { return }
    $statePath=Join-Path $script:WorkerRoot '_Installer\state.json'
    if ([IO.File]::Exists($statePath)) {
        try { $state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json;$status.Text=$state.stage } catch {}
    }
    if ($script:Worker.HasExited) {
        $timer.Stop()
        foreach ($control in @($target,$browseTarget,$online,$existing,$downloadGame,$width,$height,$desktop,$enb)) { $control.Enabled=$true }
        $package.Enabled=-not $online.Checked;$browsePackage.Enabled=$package.Enabled
        Update-GameSelection
        $result=Join-Path $script:WorkerRoot '_Installer\result.json'
        if ($script:Worker.ExitCode -eq 0 -and [IO.File]::Exists($result) -and (Get-Content -LiteralPath $result -Raw | ConvertFrom-Json).success) {
            $status.Text='Installation verified. Ready to play.';$launch.Enabled=$true
        } else { $status.Text='Setup stopped. Read the setup window or install log, then retry.' }
    }
})
$detected=if ($PSBoundParameters.ContainsKey('DetectionPaths')) { Get-DetectedGameFolder -CandidatePaths $DetectionPaths } else { Get-DetectedGameFolder -InstallerRoot $PSScriptRoot }
$existing.Checked=$true
$existingPath.Text=$detected
Update-GameSelection
$package.Enabled=-not $online.Checked;$browsePackage.Enabled=$package.Enabled
$form.Add_Shown({
    if ($existing.Checked -and -not $script:SelectedGameValid) {
        [void][Windows.Forms.MessageBox]::Show($form,$requirement,'Fallout 4 required',[Windows.Forms.MessageBoxButtons]::OK,[Windows.Forms.MessageBoxIcon]::Information)
        $browseGame.Focus()
    }
})
if ($SmokeTest) {
    $result=[ordered]@{title=$form.Text;controls=$form.Controls.Count;width=$form.ClientSize.Width;height=$form.ClientSize.Height;scrolling=$form.AutoScroll;defaultMode='existing';detectedGame=$detected;installEnabled=$install.Enabled;steamLoginEnabled=$username.Enabled;gameRequirement=$gameStatus.Text;githubPackageSelected=$online.Checked}
    if (-not $detected) {
        $missingBlocked=-not $install.Enabled
        $downloadGame.Checked=$true;Update-GameSelection
        $result['missingGameBlocked']=$missingBlocked
        $result['steamModeAvailable']=$install.Enabled -and $username.Enabled -and -not $existingPath.Enabled
        $existing.Checked=$true;Update-GameSelection
        $result['backToMissingBlocked']=-not $install.Enabled
    }
    $result | ConvertTo-Json
    $timer.Dispose();$form.Dispose();exit 0
}
[void]$form.ShowDialog()
$timer.Dispose();$form.Dispose()
