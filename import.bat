@echo off
title MultiAgIDE Package Importer
cd /d "%~dp0"
echo ========================================================
echo   MultiAgIDE Studio - Import Package
echo ========================================================
python import_package.py
pause
