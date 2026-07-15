@echo off
rem One-time setup for the stall laptop (Windows).
rem Needs Python 3.9-3.12 (MediaPipe does not support 3.13+).
rem Get it from https://www.python.org/downloads/ or: winget install Python.Python.3.12

py -3.12 -m venv .venv || (echo Python 3.12 not found - install it first & exit /b 1)
.venv\Scripts\python -m pip install -r requirements.txt
echo.
echo Done. Start the game with run.bat
