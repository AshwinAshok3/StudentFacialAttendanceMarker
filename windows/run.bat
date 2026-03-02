@echo off
REM =========================================================================
REM  run.bat — Start the Facial Attendance System (Windows)
REM
REM  ISOLATION: Uses ONLY the local .venv inside windows/.
REM  Validates Python 3.10.5 before launching.
REM =========================================================================

setlocal enabledelayedexpansion

REM Resolve this script's directory (windows/)
set "WIN_DIR=%~dp0"
if "%WIN_DIR:~-1%"=="\" set "WIN_DIR=%WIN_DIR:~0,-1%"

set "VENV_DIR=%WIN_DIR%\venv"
set "VENV_PYTHON=%WIN_DIR%\venv\Scripts\python.exe"
set "BACKEND_DIR=%WIN_DIR%\backend"
set "REQUIRED_VERSION=3.10.5"

echo.
echo  =====================================================
echo   FACIAL ATTENDANCE SYSTEM — STARTING
echo  =====================================================
echo.

REM -----------------------------------------------------------------------
REM  Step 1: Verify .venv exists
REM -----------------------------------------------------------------------
if not exist "%VENV_PYTHON%" (
    echo   ERROR: Virtual environment not found at:
    echo     %VENV_DIR%
    echo.
    echo   Please run setup.bat first to create the environment.
    echo.
    pause
    exit /b 1
)

REM -----------------------------------------------------------------------
REM  Step 2: Validate Python version is exactly 3.10.5
REM -----------------------------------------------------------------------
echo [1/3] Validating Python version...

for /f "tokens=2 delims= " %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do set "FOUND_VER=%%v"

if not "!FOUND_VER!"=="%REQUIRED_VERSION%" (
    echo   ERROR: Python version mismatch!
    echo   Expected: %REQUIRED_VERSION%
    echo   Found:    !FOUND_VER!
    echo.
    echo   Please delete .venv and re-run setup.bat.
    pause
    exit /b 1
)

echo   Python !FOUND_VER! confirmed.

REM -----------------------------------------------------------------------
REM  Step 3: Validate backend/app.py exists
REM -----------------------------------------------------------------------
echo [2/3] Checking backend...

if not exist "%BACKEND_DIR%\app.py" (
    echo   ERROR: backend\app.py not found at:
    echo     %BACKEND_DIR%
    echo.
    echo   The backend code is missing. Please check your installation.
    pause
    exit /b 1
)

echo   Backend verified.

REM -----------------------------------------------------------------------
REM  Step 4: Start the server
REM -----------------------------------------------------------------------
echo [3/3] Starting server...
echo.
echo   Server:  http://localhost:5000
echo   Press Ctrl+C to stop.
echo.

REM Open browser after a short delay (non-blocking)
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5000" >nul 2>&1

REM Run the Flask server using venv Python
"%VENV_PYTHON%" "%BACKEND_DIR%\app.py"

if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Server exited with an error.
    echo   Check the output above for details.
    pause
)
