@echo off
REM Setup videomakerauto - chay 1 lan sau khi pull/clone
cd /d "%~dp0"

echo === videomakerauto Setup ===

echo.
echo [1/2] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo [2/2] Creating .env if needed...
if not exist .env (
    copy .env.example .env
    echo Created .env. Open it and add your API keys.
    notepad .env
) else (
    echo .env already exists.
)

echo.
echo Done! Run: python main.py "your topic"
