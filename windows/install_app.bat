@echo off
title VBridge - Windows App Setup
echo ========================================================
echo          Installing VBridge as a Windows App
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Installing required Python libraries...
python -m pip install -r requirements.txt --quiet

echo [2/3] Generating app icon assets...
python generate_icon.py

echo [3/3] Creating Windows Start Menu & Desktop Shortcuts...
python install_shortcuts.py

echo.
echo ========================================================
echo  SUCCESS! VBridge is installed like a native Windows App!
echo  - You can now find VBridge in your Windows Start Menu
echo  - You can launch it from the Desktop shortcut
echo  - Runs in background with System Tray & Auto-Startup
echo ========================================================
pause
