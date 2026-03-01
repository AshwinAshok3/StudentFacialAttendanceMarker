@echo off
REM =========================================================================
REM  run.bat — Start the Facial Attendance System (Windows)
REM =========================================================================

setlocal

echo.
echo  Starting Facial Attendance System...
echo.

REM Check if venv exists
if not exist venv\Scripts\activate.bat (
    echo ERROR: Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM Activate venv
call venv\Scripts\activate.bat

REM Start the Flask server
echo  Server starting at http://localhost:5000
echo  Press Ctrl+C to stop.
echo.

REM Open browser after a short delay
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5000"

REM Run the server
python backend\app.py

pause
