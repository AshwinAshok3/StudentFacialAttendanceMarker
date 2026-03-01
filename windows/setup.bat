@echo off
REM =========================================================================
REM  setup.bat — Windows Setup for Facial Attendance System
REM
REM  1. Checks Python 3.10.x
REM  2. Creates virtual environment
REM  3. Installs base dependencies
REM  4. Detects NVIDIA GPU / CUDA
REM  5. Installs GPU or CPU PyTorch + ONNX Runtime
REM  6. Downloads InsightFace models
REM  7. Prints system summary
REM =========================================================================

setlocal enabledelayedexpansion

echo.
echo  ============================================
echo   FACIAL ATTENDANCE SYSTEM — WINDOWS SETUP
echo  ============================================
echo.

REM -----------------------------------------------------------------------
REM  Step 1: Check Python version
REM -----------------------------------------------------------------------
echo [1/7] Checking Python version...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo Please install Python 3.10.x from https://python.org
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   Found: %PYVER%

python -c "import sys; v=sys.version_info; exit(0 if v.major==3 and v.minor>=10 else 1)" 2>nul
if %errorlevel% neq 0 (
    echo WARNING: Python 3.10+ recommended. Found %PYVER%.
    echo Continuing anyway...
)

REM -----------------------------------------------------------------------
REM  Step 2: Create virtual environment
REM -----------------------------------------------------------------------
echo.
echo [2/7] Creating virtual environment...

if exist venv (
    echo   Virtual environment already exists. Reusing.
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo   Created: venv\
)

REM Activate venv
call venv\Scripts\activate.bat

REM Upgrade pip
echo   Upgrading pip...
python -m pip install --upgrade pip --quiet

REM -----------------------------------------------------------------------
REM  Step 3: Install base dependencies
REM -----------------------------------------------------------------------
echo.
echo [3/7] Installing base dependencies...

pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install base dependencies.
    pause
    exit /b 1
)
echo   Base packages installed.

REM -----------------------------------------------------------------------
REM  Step 4: Detect NVIDIA GPU
REM -----------------------------------------------------------------------
echo.
echo [4/7] Detecting GPU...

set GPU_FOUND=0
set GPU_NAME=None

where nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%g in ('nvidia-smi --query-gpu=name --format=csv,noheader 2^>nul') do (
        set GPU_NAME=%%g
        set GPU_FOUND=1
    )
)

if %GPU_FOUND% equ 1 (
    echo   NVIDIA GPU detected: %GPU_NAME%
) else (
    echo   No NVIDIA GPU detected. Will use CPU mode.
)

REM -----------------------------------------------------------------------
REM  Step 5: Install PyTorch (GPU or CPU)
REM -----------------------------------------------------------------------
echo.
echo [5/7] Installing PyTorch and ONNX Runtime...

if %GPU_FOUND% equ 1 (
    echo   Installing CUDA-enabled PyTorch...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 --quiet
    echo   Installing ONNX Runtime GPU...
    pip install onnxruntime-gpu --quiet
) else (
    echo   Installing CPU-only PyTorch...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --quiet
    echo   Installing ONNX Runtime CPU...
    pip install onnxruntime --quiet
)
echo   Done.

REM -----------------------------------------------------------------------
REM  Step 6: Download InsightFace models
REM -----------------------------------------------------------------------
echo.
echo [6/7] Downloading InsightFace models...

if exist models\buffalo_l (
    echo   Models already exist. Skipping download.
) else (
    python -c "from insightface.app import FaceAnalysis; app = FaceAnalysis(name='buffalo_l', root='models'); print('Models downloaded successfully.')"
    if %errorlevel% neq 0 (
        echo WARNING: Model download failed. You may need internet access.
        echo You can retry by running this script again.
    )
)

REM -----------------------------------------------------------------------
REM  Step 7: System Summary
REM -----------------------------------------------------------------------
echo.
echo [7/7] Generating system summary...
echo.

python -c "import sys; sys.path.insert(0,'backend'); from utils import format_system_summary; print(format_system_summary())"

echo.
echo  Setup complete! Run 'run.bat' to start the server.
echo.

pause
