@echo off
REM =========================================================================
REM  setup.bat — Portable Windows Setup for Facial Attendance System
REM
REM  ISOLATION DESIGN:
REM  - Downloads embedded Python 3.10.5 into windows\python\
REM  - Creates .venv inside windows\ using that portable Python
REM  - Installs ALL packages into .venv only
REM  - ZERO system-wide changes (no PATH, no registry, no C:\ pollution)
REM  - GPU packages (CUDA torch, onnxruntime-gpu) installed conditionally
REM  - Entire setup is USB-portable after first internet run
REM
REM  REQUIREMENTS:
REM  - Internet connection (first run only — to download Python + packages)
REM  - PowerShell 5+ (ships with Windows 10/11)
REM  - ~2 GB disk space
REM =========================================================================

setlocal enabledelayedexpansion

REM Resolve this script's directory (windows/)
set "WIN_DIR=%~dp0"
REM Remove trailing backslash for clean paths
if "%WIN_DIR:~-1%"=="\" set "WIN_DIR=%WIN_DIR:~0,-1%"

set "PYTHON_DIR=%WIN_DIR%\python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "VENV_DIR=%WIN_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "MODELS_DIR=%WIN_DIR%\models"
set "REQ_FILE=%WIN_DIR%\requirements.txt"

REM Python 3.10.5 embedded zip URL (official CPython release)
set "PY_VERSION=3.10.5"
set "PY_ZIP_URL=https://www.python.org/ftp/python/3.10.5/python-3.10.5-embed-amd64.zip"
set "PY_ZIP_FILE=%WIN_DIR%\python-3.10.5-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "GET_PIP_FILE=%WIN_DIR%\get-pip.py"

echo.
echo  =====================================================
echo   FACIAL ATTENDANCE SYSTEM — PORTABLE WINDOWS SETUP
echo  =====================================================
echo   Target: Python %PY_VERSION% (embedded, local only)
echo   Location: %WIN_DIR%
echo  =====================================================
echo.

REM -----------------------------------------------------------------------
REM  Step 1: Obtain Python 3.10.5 (embedded/portable)
REM -----------------------------------------------------------------------
echo [1/8] Checking for local Python %PY_VERSION%...

if exist "%PYTHON_EXE%" (
    REM Verify it's actually 3.10.5
    for /f "tokens=2 delims= " %%v in ('"%PYTHON_EXE%" --version 2^>^&1') do set "FOUND_VER=%%v"
    if "!FOUND_VER!"=="%PY_VERSION%" (
        echo   Found: Python !FOUND_VER! at %PYTHON_DIR%
        goto :python_ready
    ) else (
        echo   WARNING: Found Python !FOUND_VER! but need %PY_VERSION%.
        echo   Re-downloading correct version...
        rmdir /s /q "%PYTHON_DIR%" 2>nul
    )
)

echo   Python %PY_VERSION% not found locally. Downloading...
echo   URL: %PY_ZIP_URL%

REM Download the embedded zip using PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_ZIP_URL%' -OutFile '%PY_ZIP_FILE%'" 2>nul

if not exist "%PY_ZIP_FILE%" (
    echo   ERROR: Failed to download Python %PY_VERSION%.
    echo   Check your internet connection and try again.
    echo   Or manually download from: %PY_ZIP_URL%
    pause
    exit /b 1
)

REM Extract
echo   Extracting to %PYTHON_DIR%...
mkdir "%PYTHON_DIR%" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -Path '%PY_ZIP_FILE%' -DestinationPath '%PYTHON_DIR%' -Force" 2>nul

if not exist "%PYTHON_EXE%" (
    echo   ERROR: Extraction failed. Python executable not found.
    pause
    exit /b 1
)

REM Clean up zip
del "%PY_ZIP_FILE%" 2>nul

REM -----------------------------------------------------------------------
REM  Step 1b: Enable pip in embedded Python
REM
REM  The embedded distribution has pip disabled by default.
REM  We must:
REM    1. Uncomment "import site" in python310._pth
REM    2. Run get-pip.py to install pip locally
REM -----------------------------------------------------------------------
echo   Enabling pip in embedded Python...

REM Fix the ._pth file to enable site-packages
set "PTH_FILE=%PYTHON_DIR%\python310._pth"
if exist "%PTH_FILE%" (
    REM Rewrite the _pth file to uncomment "import site"
    (
        echo python310.zip
        echo .
        echo.
        echo import site
    ) > "%PTH_FILE%"
)

REM Download and run get-pip.py
if not exist "%PYTHON_DIR%\Scripts\pip.exe" (
    echo   Installing pip...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%GET_PIP_FILE%'" 2>nul

    if not exist "%GET_PIP_FILE%" (
        echo   ERROR: Failed to download get-pip.py.
        pause
        exit /b 1
    )

    "%PYTHON_EXE%" "%GET_PIP_FILE%" --no-warn-script-location 2>nul
    del "%GET_PIP_FILE%" 2>nul
)

echo   pip enabled.

:python_ready
echo   Python %PY_VERSION% ready at: %PYTHON_DIR%

REM -----------------------------------------------------------------------
REM  Step 2: Create virtual environment
REM -----------------------------------------------------------------------
echo.
echo [2/8] Creating virtual environment...

if exist "%VENV_DIR%\Scripts\python.exe" (
    REM Verify venv Python version
    for /f "tokens=2 delims= " %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do set "VENV_VER=%%v"
    if "!VENV_VER!"=="%PY_VERSION%" (
        echo   .venv already exists with Python !VENV_VER!. Reusing.
        goto :venv_ready
    ) else (
        echo   .venv has wrong Python version (!VENV_VER!). Recreating...
        rmdir /s /q "%VENV_DIR%" 2>nul
    )
)

REM The embedded Python does not ship with ensurepip/venv module.
REM We use pip to install virtualenv, then create the venv.
echo   Installing virtualenv...
"%PYTHON_EXE%" -m pip install virtualenv --no-warn-script-location --quiet 2>nul

echo   Creating .venv...
"%PYTHON_EXE%" -m virtualenv "%VENV_DIR%" --python="%PYTHON_EXE%" 2>nul

if not exist "%VENV_PYTHON%" (
    echo   ERROR: Failed to create virtual environment.
    echo   Attempting alternative method...
    REM Fallback: use pip's --target or manual venv structure
    "%PYTHON_DIR%\Scripts\virtualenv.exe" "%VENV_DIR%" 2>nul
)

if not exist "%VENV_PYTHON%" (
    echo   ERROR: Virtual environment creation failed completely.
    echo   Please ensure you have write permissions to: %WIN_DIR%
    pause
    exit /b 1
)

:venv_ready

REM Verify venv Python version one more time
for /f "tokens=2 delims= " %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do set "FINAL_VER=%%v"
echo   .venv ready: Python !FINAL_VER! at %VENV_DIR%

if not "!FINAL_VER!"=="%PY_VERSION%" (
    echo   WARNING: .venv Python is !FINAL_VER!, expected %PY_VERSION%.
    echo   This may cause compatibility issues.
)

REM -----------------------------------------------------------------------
REM  Step 3: Upgrade pip inside venv
REM -----------------------------------------------------------------------
echo.
echo [3/8] Upgrading pip inside .venv...
"%VENV_PYTHON%" -m pip install --upgrade pip --quiet 2>nul
echo   pip upgraded.

REM -----------------------------------------------------------------------
REM  Step 4: Install base dependencies
REM -----------------------------------------------------------------------
echo.
echo [4/8] Installing base dependencies...

"%VENV_PIP%" install -r "%REQ_FILE%" --quiet 2>nul
if %errorlevel% neq 0 (
    echo   WARNING: Some base packages may have failed.
    echo   Retrying without --quiet for diagnostics...
    "%VENV_PIP%" install -r "%REQ_FILE%"
)
echo   Base packages installed.

REM -----------------------------------------------------------------------
REM  Step 5: Detect NVIDIA GPU
REM -----------------------------------------------------------------------
echo.
echo [5/8] Detecting GPU...

set "GPU_FOUND=0"
set "GPU_NAME=None"

where nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%g in ('nvidia-smi --query-gpu=name --format^=csv^,noheader 2^>nul') do (
        set "GPU_NAME=%%g"
        set "GPU_FOUND=1"
    )
)

if %GPU_FOUND% equ 1 (
    echo   NVIDIA GPU detected: !GPU_NAME!
    echo   CUDA acceleration will be enabled.
) else (
    echo   No NVIDIA GPU detected.
    echo   System will use CPU mode (slower but fully functional).
)

REM -----------------------------------------------------------------------
REM  Step 6: Install PyTorch + ONNX Runtime (GPU or CPU)
REM -----------------------------------------------------------------------
echo.
echo [6/8] Installing PyTorch and ONNX Runtime...

if %GPU_FOUND% equ 1 (
    echo   Installing CUDA-enabled PyTorch (cu121)...
    "%VENV_PIP%" install torch==2.1.2+cu121 torchvision==0.16.2+cu121 --index-url https://download.pytorch.org/whl/cu121 --quiet 2>nul
    if %errorlevel% neq 0 (
        echo   WARNING: CUDA PyTorch install failed. Falling back to CPU...
        set "GPU_FOUND=0"
        goto :install_cpu_torch
    )
    echo   Installing ONNX Runtime GPU...
    "%VENV_PIP%" install onnxruntime-gpu==1.16.3 --quiet 2>nul
    if %errorlevel% neq 0 (
        echo   WARNING: onnxruntime-gpu failed. Installing CPU version...
        "%VENV_PIP%" install onnxruntime==1.16.3 --quiet 2>nul
    )
    goto :torch_done
)

:install_cpu_torch
echo   Installing CPU-only PyTorch...
"%VENV_PIP%" install torch==2.1.2+cpu torchvision==0.16.2+cpu --index-url https://download.pytorch.org/whl/cpu --quiet 2>nul
if %errorlevel% neq 0 (
    echo   WARNING: Pinned CPU torch failed. Trying latest compatible...
    "%VENV_PIP%" install torch torchvision --index-url https://download.pytorch.org/whl/cpu --quiet 2>nul
)
echo   Installing ONNX Runtime CPU...
"%VENV_PIP%" install onnxruntime==1.16.3 --quiet 2>nul
if %errorlevel% neq 0 (
    "%VENV_PIP%" install onnxruntime --quiet 2>nul
)

:torch_done
echo   PyTorch and ONNX Runtime installed.

REM -----------------------------------------------------------------------
REM  Step 7: Download InsightFace models
REM -----------------------------------------------------------------------
echo.
echo [7/8] Checking InsightFace models...

mkdir "%MODELS_DIR%" 2>nul
if exist "%MODELS_DIR%\models\buffalo_l" (
    echo   Models already downloaded. Skipping.
) else (
    echo   Downloading InsightFace buffalo_l model (~300MB)...
    echo   This may take a few minutes...
    "%VENV_PYTHON%" -c "from insightface.app import FaceAnalysis; app = FaceAnalysis(name='buffalo_l', root='%MODELS_DIR%'); print('  Models downloaded successfully.')" 2>nul
    if %errorlevel% neq 0 (
        echo   WARNING: Model download failed.
        echo   This requires internet access on first run.
        echo   You can retry by running setup.bat again.
    )
)

REM -----------------------------------------------------------------------
REM  Step 8: Validate and print system summary
REM -----------------------------------------------------------------------
echo.
echo [8/8] System Summary
echo.
echo  =====================================================
echo   SETUP COMPLETE
echo  =====================================================

echo   Python:       %PY_VERSION% (portable, local)

for /f "tokens=2 delims= " %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do echo   Venv Python:  %%v

echo   Python Path:  %PYTHON_DIR%
echo   Venv Path:    %VENV_DIR%
echo   Models Path:  %MODELS_DIR%

if %GPU_FOUND% equ 1 (
    echo   GPU:          !GPU_NAME!
    echo   Acceleration: CUDA (GPU)
) else (
    echo   GPU:          None detected
    echo   Acceleration: CPU (fallback)
)

REM Validate torch import
"%VENV_PYTHON%" -c "import torch; print('  Torch:        ' + torch.__version__); print('  CUDA:         ' + str(torch.cuda.is_available()))" 2>nul
if %errorlevel% neq 0 (
    echo   Torch:        NOT INSTALLED (may need retry)
)

REM Validate insightface
"%VENV_PYTHON%" -c "import insightface; print('  InsightFace:  ' + insightface.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo   InsightFace:  NOT INSTALLED (may need retry)
)

echo.
echo  =====================================================
echo   Run 'run.bat' to start the server.
echo  =====================================================
echo.

pause
