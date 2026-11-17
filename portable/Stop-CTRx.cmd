@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-CTRx.ps1" -Action Stop
if errorlevel 1 pause
