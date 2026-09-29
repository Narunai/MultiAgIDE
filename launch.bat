@echo off
title MultiAgIDE Control Deck
setlocal

:: ตรวจสอบตำแหน่งโฟลเดอร์ของโปรเจกต์
if exist "%~dp0main.py" (
    cd /d "%~dp0"
) else (
    cd /d "d:\ProJectNextLevel\MutiAgIDE"
)

echo ========================================================
echo   Launching MultiAgIDE Control Deck
echo   Directory: %CD%
echo ========================================================

python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] MultiAgIDE encountered an issue.
    pause
)
