@echo off
title VBridge - Build Standalone Executable
echo ========================================================
echo       Building Standalone VBridge.exe Executable
echo ========================================================
echo.

cd /d "%~dp0"
python build_exe.py

echo.
pause
