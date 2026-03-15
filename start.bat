@echo off
title Plex Suggester
cd /d "%~dp0"
echo Starting Plex Suggester...
echo.
python -m uvicorn plex_suggester.web.app:app --host localhost --port 8000 --app-dir src --reload
pause
