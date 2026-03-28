@echo off
REM ========================================
REM  DOUBLE-CLICK FILE NAY = mo cua so scan
REM  Khong can go lenh, khong can main.py
REM ========================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%.venv\Scripts\pythonw.exe" (
    start "" /D "%ROOT%" "%ROOT%.venv\Scripts\pythonw.exe" "%ROOT%app\scan_gui.py"
    exit /b 0
)

where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" /D "%ROOT%" pythonw "%ROOT%app\scan_gui.py"
    exit /b 0
)

if exist "%ROOT%.venv\Scripts\python.exe" (
    start "" /D "%ROOT%" "%ROOT%.venv\Scripts\python.exe" "%ROOT%app\scan_gui.py"
    exit /b 0
)

where python >nul 2>&1
if %errorlevel%==0 (
    start "" /D "%ROOT%" python "%ROOT%app\scan_gui.py"
    exit /b 0
)

msg * Cai Python 3.8+ (python.org) va dat vao PATH, hoac tao .venv trong thu muc nay.
