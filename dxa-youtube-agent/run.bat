@echo off
rem ==========================================================
rem  DXA - Tro ly sua xe may. Bam dup vao file nay de chay.
rem  Lan dau: tu cai thu vien (vai phut), hoi Gemini API key.
rem  Nhung lan sau: mo trinh duyet sau vai giay.
rem ==========================================================
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
title DXA - Tro ly sua xe may

rem ---- 1. Tim Python (bo qua ban gia cua Microsoft Store) ----
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY (
    echo [DXA] May chua co Python. Dang cai Python 3.12...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo [DXA] Cai Python xong. Dong cua so nay, roi bam dup lai run.bat.
    pause
    exit /b 1
)

rem ---- 2. Moi truong rieng + thu vien (chi lam lan dau) ----
if not exist ".venv\Scripts\python.exe" (
    echo [DXA] Tao moi truong Python rieng cho DXA...
    %PY% -m venv .venv || goto :loi
)
set "VPY=.venv\Scripts\python.exe"
if not exist ".venv\da_cai.txt" (
    echo [DXA] Dang cai thu vien, lan dau mat vai phut...
    "%VPY%" -m pip install --upgrade pip -q
    "%VPY%" -m pip install -r requirements.txt -q || goto :loi
    echo ok> ".venv\da_cai.txt"
)

rem ---- 3. Gemini API key: con thieu key thi lan nao cung hoi ----
set "HASKEY="
if exist ".env" findstr /r /c:"^GEMINI_API_KEY=..*" ".env" >nul 2>nul && set "HASKEY=1"
if not defined HASKEY (
    echo.
    echo [DXA] Chua co Gemini API key. Dan key roi bam Enter.
    echo       Lay key mien phi tai https://aistudio.google.com/apikey
    echo       Bo trong roi bam Enter de chay ban offline, lan sau se hoi lai.
    set "KEY="
    set /p "KEY=Gemini API key: "
    call :ghi_env
)

rem ---- 4. Dung kho tri thuc ----
echo [DXA] Dung kho tri thuc...
"%VPY%" dxa.py build || goto :loi
"%VPY%" build_gemini.py 2>nul || echo [DXA] Chua dung Gemini: chay ban offline. Sua key trong file .env neu can.

rem ---- 5. Chay may chu va mo trinh duyet ----
echo.
echo [DXA] Dang chay tai http://localhost:8000
echo [DXA] Dong cua so nay de tat DXA.
start "" cmd /c "timeout /t 5 >nul & start http://localhost:8000"
"%VPY%" -m uvicorn api:app --port 8000
goto :eof

:ghi_env
if not defined KEY goto :eof
> ".env" echo GEMINI_API_KEY=%KEY%
goto :eof

:loi
echo.
echo [DXA] Co loi o buoc tren. Chup man hinh cua so nay gui cho nguoi ho tro.
pause
exit /b 1
