@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo TradingView Alerts - End to End
echo 1. Lu session  2. Chup alerts + Gui Telegram
echo ========================================
echo.

echo [Buoc 1/2] Lu session TradingView...
echo Dang nhap neu can, roi nhan ENTER de luu.
echo.
python save_session.py

echo.
echo [Buoc 2/2] Mo alerts, chup man hinh, gui Telegram...
echo.
python run_alerts_screenshot.py

pause
