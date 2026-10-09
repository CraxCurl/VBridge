@echo off
title VBridge Audio Bridge
echo ========================================================
echo       Starting VBridge Windows Audio Relay Receiver
echo ========================================================
cd /d "%~dp0"
python -m pip install -r requirements.txt
python app.py
pause
