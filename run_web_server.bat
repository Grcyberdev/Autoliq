@echo off
title Liquor Bond Automation Server
echo ===================================================
echo 🚀 Starting Liquor Bond Automation Web Server...
echo ===================================================

cd /d "%~dp0"

REM Check if virtual env exists and activate it
if exist "env\Scripts\activate.bat" (
    echo 📦 Activating virtual environment 'env'...
    call env\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo 📦 Activating virtual environment 'venv'...
    call venv\Scripts\activate.bat
) else (
    echo ⚠️ Virtual environment not found in root. Using system global Python...
)

echo ⏳ Installing/Verifying dependencies (FastAPI, Uvicorn, WebSockets)...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo 🔍 Discovering your Local IP address...
set local_ip=
for /f "tokens=4 delims= " %%i in ('route print ^| find " 0.0.0.0 "') do set local_ip=%%i

echo ===================================================
echo 🌐 Web Dashboard is ready!
echo.
echo 👉 To access from THIS PC: http://localhost:8000
if not "%local_ip%"=="" (
    echo 👉 To access from OTHER PCs on local network: http://%local_ip%:8000
)
echo ===================================================
echo.

python app.py
pause
