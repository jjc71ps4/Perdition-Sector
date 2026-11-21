@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
title Perdition Sector
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0Launcher\Start-Perdition.ps1"
if errorlevel 1 (
  echo Perdition Sector could not start. See Launcher\launcher.log for details.
  pause
  exit /b 1
)
endlocal
