@echo off
REM Claude Telegram Bridge Starter
REM This batch file runs the Claude Telegram Bridge

cd /d "%~dp0"

echo Starting Claude Telegram Bridge...
python claude_telegram_bridge.py

pause
