@echo off
REM =========================================================================
REM  setup.bat -- Portable Windows Setup for Facial Attendance System
REM
REM  ISOLATION DESIGN:
REM  - Downloads embedded Python 3.10.5 into windows\python\
REM  - Creates venv inside windows\ using that portable Python
REM  - Installs ALL packages into venv only
REM  - ZERO system-wide changes (no PATH, no registry, no C:\ pollution)
REM  - GPU packages (CUDA torch, onnxruntime-gpu) installed conditionally
REM  - Entire setup is USB-portable after first internet run
REM =========================================================================

setlocal enabledelayedexpansion

REM Resolve this script's directory (windows/)
set "WIN_DIR=%~dp0"
REM Remove trailing backslash
if "%WIN_DIR:~-1%"=="\" set "WIN_DIR=%WIN_DIR:~0,-1%"

REM All paths sandboxed inside WIN_DIR
set "PYTHON_DIR=%WIN_DIR%\python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "VENV_DIR=%WIN_DIR%\venv"
set "VENV_PYTHON=%WIN_DIR%\venv\Scripts\python.exe"
set "VENV_PIP=%WIN_DIR%\venv\Scripts\pip.exe"
set "MODELS_DIR=%WIN_DIR%\models"
set "REQ_FILE=%WIN_DIR%\requirements.txt"

set "PY_VERSION=3.10.5"
set "PY_ZIP_URL=https://www.python.org/ftp/python/3.10.5/python-3.10.5-embed-amd64.zip"
set "PY_ZIP_FILE=%WIN_DIR%\py3105.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "GET_PIP_FILE=%WIN_DIR%\get-pip.py"

echo.
echo  =====================================================
echo   FACIAL ATTENDANCE SYSTEM - PORTABLE WINDOWS SETUP
echo  =====================================================
echo   Target:   Python %PY_VERSION% (embedded, local)
echo   Location: %WIN_DIR%
echo  =====================================================
echo.

REM -----------------------------------------------------------------------
REM  Step 1: Obtain Python 3.10.5 (embedded/portable)
REM -----------------------------------------------------------------------
echo [1/8] Checking for local Python %PY_VERSION%...

if exist "%PYTHON_EXE%" (
    for /f "tokens=2 delims= " %%v in ('"%PYTHON_EXE%" --version 2^>^&1') do set "FOUND_VER=%%v"
    if "!FOUND_VER!"=="%PY_VERSION%" (
        echo   OK: Python !FOUND_VER! found at %PYTHON_DIR%
        goto :ensure_pip
    )
    echo   Wrong version found ^(!FOUND_VER!^). Re-downloading %PY_VERSION%...
    rmdir /s /q "%PYTHON_DIR%" 2>nul
)

echo   Python %PY_VERSION% not found locally. Downloading portable build...
echo   Source: %PY_ZIP_URL%
echo   Please wait...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_ZIP_URL%' -OutFile '%PY_ZIP_FILE%'"

if not exist "%PY_ZIP_FILE%" (
    echo.
    echo   ERROR: Download failed. Check internet connection.
    echo   Manual download: %PY_ZIP_URL%
    echo   Place extracted folder at: %PYTHON_DIR%
    pause & exit /b 1
)

echo   Extracting Python...
mkdir "%PYTHON_DIR%" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -Path '%PY_ZIP_FILE%' -DestinationPath '%PYTHON_DIR%' -Force"
del "%PY_ZIP_FILE%" 2>nul

if not exist "%PYTHON_EXE%" (
    echo   ERROR: Extraction failed. %PYTHON_EXE% not found.
    pause & exit /b 1
)
echo   Python %PY_VERSION% extracted.

REM -----------------------------------------------------------------------
REM  Step 1b: Enable pip in embedded Python
REM
REM  The embedded zip has pip disabled. Must patch python310._pth and
REM  run get-pip.py to enable it. Written as individual statements
REM  (NOT inside a paren-redirect block) to avoid CMD parse errors.
REM -----------------------------------------------------------------------
:ensure_pip

echo   Checking pip in embedded Python...

set "PTH_FILE=%PYTHON_DIR%\python310._pth"

REM Only patch if pip not yet installed
if exist "%PYTHON_DIR%\Scripts\pip.exe" goto :pip_ready

echo   Patching python310._pth to enable site-packages...

REM Write each line separately using individual echo+redirect
REM Do NOT use parenthesized blocks -- that causes the "." parse error
echo python310.zip>"%PTH_FILE%"
echo .>>"%PTH_FILE%"
echo.>>"%PTH_FILE%"
echo import site>>"%PTH_FILE%"

echo   Downloading get-pip.py...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%GET_PIP_FILE%'"

if not exist "%GET_PIP_FILE%" (
    echo   ERROR: Failed to download get-pip.py.
    pause & exit /b 1
)

echo   Installing pip into embedded Python...
"%PYTHON_EXE%" "%GET_PIP_FILE%" --no-warn-script-location
del "%GET_PIP_FILE%" 2>nul

:pip_ready
echo   pip: OK

REM -----------------------------------------------------------------------
REM  Step 2: Install virtualenv into the embedded Python
REM -----------------------------------------------------------------------
echo.
echo [2/8] Preparing virtualenv...

REM Always ensure virtualenv is installed (runs even on re-runs)
"%PYTHON_EXE%" -m pip install virtualenv --no-warn-script-location --quiet
if %errorlevel% neq 0 (
    echo   ERROR: Could not install virtualenv.
    echo   Make sure internet is available or pip works correctly.
    pause & exit /b 1
)
echo   virtualenv: OK

REM -----------------------------------------------------------------------
REM  Step 3: Create virtual environment
REM -----------------------------------------------------------------------
echo.
echo [3/8] Creating virtual environment...

if exist "%VENV_PYTHON%" (
    for /f "tokens=2 delims= " %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do set "VENV_VER=%%v"
    if "!VENV_VER!"=="%PY_VERSION%" (
        echo   venv already exists with Python !VENV_VER!. Reusing.
        goto :venv_ready
    )
    echo   venv has wrong Python ^(!VENV_VER!^). Recreating...
    rmdir /s /q "%VENV_DIR%" 2>nul
)

echo   Creating venv at %VENV_DIR%...
"%PYTHON_EXE%" -m virtualenv "%VENV_DIR%"

if not exist "%VENV_PYTHON%" (
    echo   ERROR: Virtual environment creation failed.
    echo   Path attempted: %VENV_DIR%
    echo   Check write permissions for this folder.
    pause & exit /b 1
)

:venv_ready
for /f "tokens=2 delims= " %%v in ('"%VENV_PYTHON%" --version 2^>^&1') do set "FINAL_VER=%%v"
echo   venv ready: Python !FINAL_VER!

if not "!FINAL_VER!"=="%PY_VERSION%" (
    echo   WARNING: venv Python is !FINAL_VER!, expected !PY_VERSION!.
)

REM -----------------------------------------------------------------------
REM  Step 4: Upgrade pip inside venv
REM -----------------------------------------------------------------------
echo.
echo [4/8] Upgrading pip inside venv...
"%VENV_PYTHON%" -m pip install --upgrade pip --quiet
echo   pip upgraded.

REM -----------------------------------------------------------------------
REM  Step 5: Install base dependencies
REM -----------------------------------------------------------------------
echo.
echo [5/8] Installing base dependencies...
echo   This may take several minutes...

"%VENV_PIP%" install -r "%REQ_FILE%"
if %errorlevel% neq 0 (
    echo   ERROR: Some base packages failed to install.
    echo   Review the output above for details.
    pause & exit /b 1
)
echo   Base dependencies installed.

REM -----------------------------------------------------------------------
REM  Step 6: Detect NVIDIA GPU
REM -----------------------------------------------------------------------
echo.
echo [6/8] Detecting GPU...

set "GPU_FOUND=0"
set "GPU_NAME=None"

where nvidia-smi >nul 2>&1
if %errorlevel% equ 0 (
    REM Use --query-gpu without --format=csv,noheader (older drivers don't support it)
    REM Instead, capture gpu name via a simpler query and validate it's not an error
    for /f "skip=1 tokens=*" %%g in ('nvidia-smi --query-gpu=name --format=csv 2^>nul') do (
        if not "%%g"=="" (
            REM Reject lines that look like errors
            echo %%g | findstr /i /c:"error" /c:"option" /c:"recognized" >nul 2>&1
            if !errorlevel! neq 0 (
                set "GPU_NAME=%%g"
                set "GPU_FOUND=1"
            )
        )
    )
)

if "%GPU_FOUND%"=="1" (
    echo   NVIDIA GPU detected: !GPU_NAME!
    echo   CUDA acceleration will be enabled.
) else (
    echo   No NVIDIA GPU detected.
    echo   Running in CPU mode.
)

REM -----------------------------------------------------------------------
REM  Step 7: Install PyTorch + ONNX Runtime (GPU or CPU)
REM -----------------------------------------------------------------------
echo.
echo [7/8] Installing PyTorch and ONNX Runtime...

if "%GPU_FOUND%"=="1" (
    echo   Installing CUDA PyTorch ^(torch 2.1.2 + cu121^)...
    "%VENV_PIP%" install torch==2.1.2+cu121 torchvision==0.16.2+cu121 ^
        --index-url https://download.pytorch.org/whl/cu121
    if %errorlevel% neq 0 (
        echo   WARNING: CUDA PyTorch install failed. Falling back to CPU...
        set "GPU_FOUND=0"
    ) else (
        echo   Installing ONNX Runtime GPU...
        "%VENV_PIP%" install onnxruntime-gpu==1.16.3
        if %errorlevel% neq 0 (
            echo   WARNING: onnxruntime-gpu failed. Using CPU version...
            "%VENV_PIP%" install onnxruntime==1.16.3
        )
        goto :torch_done
    )
)

echo   Installing CPU PyTorch ^(torch 2.1.2+cpu^)...
"%VENV_PIP%" install torch==2.1.2+cpu torchvision==0.16.2+cpu ^
    --index-url https://download.pytorch.org/whl/cpu
if %errorlevel% neq 0 (
    echo   WARNING: Pinned CPU torch failed. Trying unpinned...
    "%VENV_PIP%" install torch torchvision --index-url https://download.pytorch.org/whl/cpu
)

echo   Installing ONNX Runtime CPU...
"%VENV_PIP%" install onnxruntime==1.16.3
if %errorlevel% neq 0 (
    "%VENV_PIP%" install onnxruntime
)

:torch_done
echo   PyTorch and ONNX Runtime installed.

REM -----------------------------------------------------------------------
REM  Step 8: Download InsightFace models
REM -----------------------------------------------------------------------
echo.
echo [8/8] Checking InsightFace models...

mkdir "%MODELS_DIR%" 2>nul

if exist "%MODELS_DIR%\models\buffalo_l" (
    echo   Models already downloaded. Skipping.
) else (
    echo   Downloading InsightFace buffalo_l model ^(~300MB^)...
    echo   Requires internet. Please wait...
    "%VENV_PYTHON%" -c "from insightface.app import FaceAnalysis; app = FaceAnalysis(name='buffalo_l', root='%MODELS_DIR%'); print('OK')"
    if !errorlevel! neq 0 (
        echo   WARNING: Model download failed. Re-run setup.bat when online.
    ) else (
        echo   Models downloaded.
    )
)

REM -----------------------------------------------------------------------
REM  Summary
REM -----------------------------------------------------------------------
echo.
echo  =====================================================
echo   SETUP COMPLETE
echo  =====================================================
echo   Python:    %PY_VERSION% (portable, isolated)
echo   Location:  %WIN_DIR%
echo   venv:      %VENV_DIR%
echo   Models:    %MODELS_DIR%

if "%GPU_FOUND%"=="1" (
    echo   GPU:       !GPU_NAME!
    echo   Mode:      CUDA (GPU Accelerated)
) else (
    echo   GPU:       Not detected
    echo   Mode:      CPU
)

echo.
"%VENV_PYTHON%" -c "import torch; print('  torch        ' + torch.__version__); print('  CUDA         ' + str(torch.cuda.is_available()))" 2>nul
"%VENV_PYTHON%" -c "import insightface; print('  insightface  ' + insightface.__version__)" 2>nul
"%VENV_PYTHON%" -c "import flask; print('  flask        ' + flask.__version__)" 2>nul
echo.
echo   Run 'run.bat' to start the server.
echo  =====================================================
echo.
pause
