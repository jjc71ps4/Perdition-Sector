@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
title Perdition Sector - Publish Beta
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0publisher\Start-Publish.ps1"
if errorlevel 1 (
  echo Publishing stopped. Completed uploads remain available for resume.
)
pause

