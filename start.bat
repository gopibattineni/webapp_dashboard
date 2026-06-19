@echo off
REM Start SYNTH Data Audit web application
cd /d "%~dp0"
set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PYTHON%" set PYTHON=python
"%PYTHON%" -m pip install -r requirements.txt -q
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
