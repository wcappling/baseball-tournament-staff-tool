@echo off
REM ============================================================
REM Run offline parser, storage, and API tests.
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
python -m pytest baseball_aggregator\tests -p no:cacheprovider --basetemp=.tmp\pytest-run
echo.
pause
endlocal
