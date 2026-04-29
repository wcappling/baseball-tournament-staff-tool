@echo off
REM ============================================================
REM Start the local Baseball Tournament Staff Tool web app.
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
echo.
python -m uvicorn baseball_aggregator.app:app --host 127.0.0.1 --port 8000
set EXITCODE=%errorlevel%
echo.

if %EXITCODE% neq 0 (
    echo.
    echo  App exited with error code %EXITCODE%.
)

pause
endlocal
