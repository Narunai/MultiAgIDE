@echo off
title MultiAgIDE Package Exporter
cd /d "%~dp0"
echo ========================================================
echo   MultiAgIDE Studio - Export Package
echo ========================================================
python export_package.py
pause
