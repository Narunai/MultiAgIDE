@echo off
title MultiAgIDE Studio Launcher
cd /d "%~dp0"
echo ========================================================
echo   Launching MultiAgIDE Studio (Multi-Account Workspace)
echo ========================================================
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred during execution.
    pause
)
