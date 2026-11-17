@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-CTRx.ps1" -Action Start
if errorlevel 1 pause
