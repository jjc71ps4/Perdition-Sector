@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Updater\Update-Perdition.ps1" -InstallRoot "%~dp0."
