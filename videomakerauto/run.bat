@echo off
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://www.python.org/downloads/
    echo Then run this file again.
    pause
    exit /b 1
)

echo === videomakerauto ===
echo.
echo Installing dependencies... (first run only)
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Try: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

python run.py

pause
