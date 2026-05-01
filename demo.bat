@echo off
REM ============================================================
REM Capture Playwright screenshots and videos for UI review.
REM ============================================================

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo  ERROR: Virtual environment not found.
    echo  Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python scripts\capture_ui_demo.py
echo.
pause
endlocal
