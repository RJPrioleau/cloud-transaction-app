@echo off
title Transaction App
cd /d "%~dp0"
pwsh.exe -NoProfile -File "%~dp0start_app.ps1" -Restart
if errorlevel 1 pause
