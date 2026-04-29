@echo off
REM ============================================================
REM Baseball Tournament Aggregator - One-time Setup
REM ============================================================
REM Checks for Python, installs if missing, creates a virtual
REM environment, and installs all required Python packages.
REM
REM Run this ONCE. After it succeeds, use run.bat to fetch
REM tournaments and test.bat to verify the parser.
REM ============================================================

setlocal enabledelayedexpansion

REM Always run from the script's own directory
cd /d "%~dp0"

echo.
echo ============================================================
echo  Baseball Tournament Aggregator - Setup
echo ============================================================
echo.

REM --- Step 1: Find Python ----------------------------------------
echo [1/4] Checking for Python...

set PYTHON_CMD=
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    REM Try the py launcher (common when installed from python.org)
    py -3 --version >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=py -3
    )
)

if "!PYTHON_CMD!" == "" (
    echo   Python is not installed or not in PATH.
    echo.
    echo   Attempting to install Python 3.12 via winget...
    echo   ^(If this fails, install manually from https://www.python.org/downloads/^)
    echo.

    winget --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo   ERROR: winget is not available on this system.
        echo   Please install Python manually:
        echo     1. Go to https://www.python.org/downloads/
        echo     2. Download Python 3.12 or newer
        echo     3. During install, CHECK "Add Python to PATH"
        echo     4. Re-run this setup.bat after install completes
        echo.
        pause
        exit /b 1
    )

    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    if !errorlevel! neq 0 (
        echo.
        echo   Python install failed. Please install manually from:
        echo     https://www.python.org/downloads/
        pause
        exit /b 1
    )

    echo.
    echo   ============================================================
    echo   Python installed successfully!
    echo   ============================================================
    echo   IMPORTANT: Close this window, open a NEW Command Prompt or
    echo   PowerShell window, then run setup.bat again.
    echo   ^(The PATH change won't take effect in this session.^)
    echo.
    pause
    exit /b 0
)

for /f "tokens=*" %%i in ('!PYTHON_CMD! --version 2^>^&1') do set PYVER=%%i
echo   Found: !PYVER! ^(using "!PYTHON_CMD!"^)

REM --- Step 2: Verify Python version ------------------------------
echo.
echo [2/4] Checking Python version (need 3.10+)...
!PYTHON_CMD! -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if !errorlevel! neq 0 (
    echo   ERROR: Python 3.10 or newer is required.
    echo   Found: !PYVER!
    echo   Please install a newer version from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo   OK

!PYTHON_CMD! -c "import sys; sys.exit(0 if sys.version_info < (3, 14) else 1)" >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo   WARNING: Python 3.14 is very new and some binary packages may lag behind it.
    echo   If dependency installation fails, install Python 3.12 or 3.13 and rerun setup.bat.
)

REM --- Step 3: Create virtual environment -------------------------
echo.
echo [3/4] Setting up virtual environment in .venv ...
if exist ".venv\Scripts\activate.bat" (
    echo   .venv already exists, checking compatibility...
    call .venv\Scripts\activate.bat
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo   Existing .venv is broken or too old. Recreating it...
        call deactivate >nul 2>&1
        rmdir /s /q .venv
    ) else (
        python -c "import pydantic_core; import pathlib, sys; root = pathlib.Path(pydantic_core.__file__).parent; suffix = f'cp{sys.version_info.major}{sys.version_info.minor}'; files = list(root.glob('_pydantic_core*.pyd')); sys.exit(0 if not files or any(suffix in f.name for f in files) else 1)" >nul 2>&1
        if !errorlevel! neq 0 (
            echo   Existing .venv has binary packages for a different Python version. Recreating it...
            call deactivate >nul 2>&1
            rmdir /s /q .venv
        ) else (
            call deactivate >nul 2>&1
            echo   .venv is compatible
        )
    )
) 

if not exist ".venv\Scripts\activate.bat" (
    !PYTHON_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo.
        echo   ERROR: Failed to create virtual environment.
        echo   Close any running app windows, delete .venv if it exists, and rerun setup.bat.
        pause
        exit /b 1
    )
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo   ERROR: Virtual environment was not created correctly.
        echo   Missing .venv\Scripts\python.exe
        pause
        exit /b 1
    )
    echo   Created .venv
) else (
    echo   Reusing .venv
)

REM --- Step 4: Install dependencies -------------------------------
echo.
echo [4/4] Installing dependencies...
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo   Failed to activate virtual environment.
    pause
    exit /b 1
)

python -m pip install --upgrade pip --quiet
if !errorlevel! neq 0 (
    echo   WARNING: Could not upgrade pip. Continuing anyway...
)

python -m pip install --force-reinstall -r baseball_aggregator\requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo   Failed to install dependencies. Common causes:
    echo     - No internet connection
    echo     - Corporate firewall blocking pypi.org
    echo     - Antivirus blocking pip
    pause
    exit /b 1
)

python -c "import fastapi, pydantic_core, bs4, httpx; print('  Dependency import check OK')"
if !errorlevel! neq 0 (
    echo.
    echo   ERROR: Dependencies installed but failed to import.
    echo   If you are using Python 3.14, install Python 3.12 or 3.13 and rerun setup.bat.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Setup complete!
echo ============================================================
echo.
echo  Next steps:
echo    test.bat   - Verify the parser works ^(offline test, no network^)
echo    run.bat    - Start the local web app at http://127.0.0.1:8000
echo.
echo  App data will be saved to baseball_aggregator\data
echo.
pause
endlocal
