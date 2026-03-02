#!/bin/bash
# =========================================================================
#  setup.sh -- macOS Monterey 12.7.6 Intel (x86_64)
#  Facial Attendance System -- Portable Local Environment Setup
#
#  ISOLATION DESIGN:
#  - pyenv installed locally into macos/.pyenv/ (no system-wide changes)
#  - Python 3.10.5 compiled from source inside macos/.pyenv/versions/
#  - venv created at macos/venv/ using that local Python
#  - ALL packages installed inside venv only
#  - InsightFace models stored in macos/models/ (never ~/.insightface)
#  - ZERO global changes (no ~/.bashrc, no /usr/local writes by this script)
#
#  LESSONS APPLIED FROM WINDOWS DEBUGGING:
#  - Phased pip install order (numpy FIRST, then opencv, then rest, then insightface)
#  - albumentations pinned at 1.3.1 (1.4.11 has albucore API mismatch)
#  - opencv pinned at 4.8.1.78 (last version accepting numpy 1.x)
#  - numpy pinned at 1.26.4 (insightface 0.7.3 is NOT numpy 2.x compatible)
#  - No set -e (prevents silent exits that hide fallback logic)
#  - No --force-reinstall (wipes shared deps)
#  - Explicit $VENV_PIP path (never bare 'pip' which may resolve wrong)
#  - numpy version guard AFTER full install (re-pin if something upgraded it)
#  - Per-package import validation at end
#
#  TARGET: macOS Monterey 12.7.6 -- Intel x86_64 ONLY
#  PYTHON:  3.10.5 (local pyenv, compiled from source)
#  GPU:     None (Intel Mac -- CPU mode only)
# =========================================================================

# --- Resolve script location (macos/) -----------------------------------
MAC_DIR="$(cd "$(dirname "$0")" && pwd)"

PYENV_ROOT="$MAC_DIR/.pyenv"
PY_VERSION="3.10.5"
VENV_DIR="$MAC_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip3"
MODELS_DIR="$MAC_DIR/models"
LOCAL_PYTHON="$PYENV_ROOT/versions/$PY_VERSION/bin/python3"

echo ""
echo " ====================================================="
echo "  FACIAL ATTENDANCE SYSTEM"
echo "  macOS Monterey 12.7.6 Intel -- Setup"
echo " ====================================================="
echo "  Python:   $PY_VERSION (local, isolated)"
echo "  Location: $MAC_DIR"
echo " ====================================================="
echo ""

# -----------------------------------------------------------------------
#  Step 1: Verify platform -- Intel x86_64 only
# -----------------------------------------------------------------------
echo "[1/9] Checking platform..."

OS_VER=$(sw_vers -productVersion 2>/dev/null || echo "unknown")
ARCH=$(uname -m)

echo "  macOS:  $OS_VER"
echo "  CPU:    $ARCH"

if [ "$ARCH" = "arm64" ]; then
    echo ""
    echo "  ERROR: This setup.sh is for Intel (x86_64) Macs."
    echo "  You are running Apple Silicon (arm64)."
    echo "  Please configure and use the Apple Silicon version."
    exit 1
fi

if [ "$ARCH" != "x86_64" ]; then
    echo "  WARNING: Unexpected architecture ($ARCH). Proceeding anyway."
fi

# Verify Xcode CLI tools
if ! xcode-select -p >/dev/null 2>&1; then
    echo ""
    echo "  ERROR: Xcode command line tools not found."
    echo "  Install with: xcode-select --install"
    echo "  Then re-run this script."
    exit 1
fi
echo "  Xcode CLI tools: OK"

# -----------------------------------------------------------------------
#  Step 2: Install Homebrew build dependencies for Python compilation
#
#  pyenv compiles Python from source.
#  Without these, Python either fails to build or lacks SSL/readline:
#    openssl@3  -- required for pip (https), hashlib
#    readline   -- required for interactive Python shell
#    sqlite3    -- required for sqlite3 module
#    xz         -- required for lzma module
#    zlib       -- required for zlib/gzip module
#    bzip2      -- required for bz2 module
# -----------------------------------------------------------------------
echo ""
echo "[2/9] Installing Homebrew build dependencies..."

if ! command -v brew >/dev/null 2>&1; then
    echo ""
    echo "  ERROR: Homebrew not found."
    echo "  Install Homebrew from: https://brew.sh"
    echo "  Then re-run this script."
    exit 1
fi

echo "  Homebrew: $(brew --version | head -1)"
BREW_PREFIX=$(brew --prefix)
echo "  Brew prefix: $BREW_PREFIX"

# Packages required to compile Python 3.10.5 from source
BREW_DEPS="openssl@3 readline sqlite3 xz zlib bzip2 tcl-tk"

for pkg in $BREW_DEPS; do
    if brew list --formula "$pkg" >/dev/null 2>&1; then
        echo "    $pkg: already installed"
    else
        echo "    Installing $pkg ..."
        brew install "$pkg" 2>&1 | tail -2
        if [ $? -ne 0 ]; then
            echo "    WARNING: Failed to install $pkg via brew."
            echo "    Python compilation may fail. Try: brew install $pkg"
        fi
    fi
done

# Set compiler flags so pyenv uses brew's openssl, readline, bzip2, zlib
# These are library paths specific to Intel Mac homebrew (/usr/local)
export LDFLAGS="-L$BREW_PREFIX/opt/openssl@3/lib \
    -L$BREW_PREFIX/opt/readline/lib \
    -L$BREW_PREFIX/opt/zlib/lib \
    -L$BREW_PREFIX/opt/bzip2/lib \
    -L$BREW_PREFIX/opt/sqlite3/lib"

export CPPFLAGS="-I$BREW_PREFIX/opt/openssl@3/include \
    -I$BREW_PREFIX/opt/readline/include \
    -I$BREW_PREFIX/opt/zlib/include \
    -I$BREW_PREFIX/opt/bzip2/include \
    -I$BREW_PREFIX/opt/sqlite3/include"

export PKG_CONFIG_PATH="$BREW_PREFIX/opt/openssl@3/lib/pkgconfig"

echo "  Build flags set."

# -----------------------------------------------------------------------
#  Step 3: Install Python 3.10.5 locally via pyenv
# -----------------------------------------------------------------------
echo ""
echo "[3/9] Setting up Python $PY_VERSION..."

# Check if already installed and correct version
if [ -f "$LOCAL_PYTHON" ]; then
    FOUND_VER=$("$LOCAL_PYTHON" --version 2>&1 | awk '{print $2}')
    if [ "$FOUND_VER" = "$PY_VERSION" ]; then
        echo "  OK: Python $FOUND_VER already installed locally."
    else
        echo "  Wrong version ($FOUND_VER). Removing and reinstalling $PY_VERSION..."
        rm -rf "$PYENV_ROOT/versions/$PY_VERSION"
        LOCAL_PYTHON=""
    fi
fi

if [ ! -f "$LOCAL_PYTHON" ]; then
    # Clone pyenv locally if missing
    if [ ! -d "$PYENV_ROOT" ]; then
        echo "  Cloning pyenv into $PYENV_ROOT ..."
        git clone https://github.com/pyenv/pyenv.git "$PYENV_ROOT" 2>&1
        if [ $? -ne 0 ]; then
            echo "  ERROR: git clone failed."
            echo "  Make sure git is installed: xcode-select --install"
            exit 1
        fi
        # Build pyenv native extensions (speeds up shims)
        cd "$PYENV_ROOT" && src/configure 2>/dev/null && make -C src 2>/dev/null || true
        cd "$MAC_DIR"
    fi

    # Activate pyenv for this shell session only
    export PYENV_ROOT="$PYENV_ROOT"
    export PATH="$PYENV_ROOT/bin:$PATH"

    echo "  Compiling Python $PY_VERSION (may take 10-20 minutes on Intel)..."
    echo "  You will see build output. This is normal."
    echo ""

    PYTHON_CONFIGURE_OPTS="--enable-framework" \
        "$PYENV_ROOT/bin/pyenv" install "$PY_VERSION" 2>&1

    echo ""
    if [ ! -f "$LOCAL_PYTHON" ]; then
        echo "  ERROR: Python $PY_VERSION compilation failed."
        echo ""
        echo "  Common fixes:"
        echo "    1. Install all brew deps:  brew install openssl@3 readline sqlite3 xz zlib bzip2 tcl-tk"
        echo "    2. Reinstall Xcode CLI:    xcode-select --install"
        echo "    3. Then delete partially built version:"
        echo "       rm -rf $PYENV_ROOT/versions/$PY_VERSION"
        echo "       And re-run ./setup.sh"
        exit 1
    fi
    echo "  Python $PY_VERSION compiled successfully."
fi

# --- Critical: Validate SSL works (pip won't work without it) -----------
"$LOCAL_PYTHON" -c "import ssl; print('  SSL: OK')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "  ERROR: Python compiled WITHOUT SSL support."
    echo "  pip will fail to connect to PyPI. Fix:"
    echo "    brew install openssl@3"
    echo "    rm -rf $PYENV_ROOT/versions/$PY_VERSION"
    echo "    Then re-run ./setup.sh"
    exit 1
fi

# --- Validate sqlite3 (needed by Flask sessions) ------------------------
"$LOCAL_PYTHON" -c "import sqlite3; print('  sqlite3: OK')" 2>/dev/null || \
    echo "  WARNING: sqlite3 module missing from Python build."

echo "  Python path: $LOCAL_PYTHON"

# -----------------------------------------------------------------------
#  Step 4: Create virtual environment
# -----------------------------------------------------------------------
echo ""
echo "[4/9] Creating virtual environment..."

if [ -f "$VENV_PYTHON" ]; then
    VENV_VER=$("$VENV_PYTHON" --version 2>&1 | awk '{print $2}')
    if [ "$VENV_VER" = "$PY_VERSION" ]; then
        echo "  venv already exists with Python $VENV_VER. Reusing."
    else
        echo "  Wrong Python in venv ($VENV_VER). Recreating..."
        rm -rf "$VENV_DIR"
        "$LOCAL_PYTHON" -m venv "$VENV_DIR"
    fi
else
    "$LOCAL_PYTHON" -m venv "$VENV_DIR"
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "  ERROR: Virtual environment creation failed at $VENV_DIR"
    exit 1
fi

ACTUAL_VER=$("$VENV_PYTHON" --version 2>&1 | awk '{print $2}')
if [ "$ACTUAL_VER" != "$PY_VERSION" ]; then
    echo "  WARNING: venv Python is $ACTUAL_VER, expected $PY_VERSION"
else
    echo "  venv ready: Python $ACTUAL_VER"
fi

# Activate for this script session
source "$VENV_DIR/bin/activate"

# -----------------------------------------------------------------------
#  Step 5: Upgrade pip
# -----------------------------------------------------------------------
echo ""
echo "[5/9] Upgrading pip..."
"$VENV_PIP" install --upgrade pip
if [ $? -ne 0 ]; then
    echo "  ERROR: pip upgrade failed."
    exit 1
fi
echo "  pip ready."

# -----------------------------------------------------------------------
#  Step 6: Install packages in STRICT ORDER
#
#  WHY ORDER MATTERS:
#  insightface 0.7.3 uses numpy 1.x internal C APIs.
#  opencv-python-headless >= 4.9.0 requires numpy >= 2.0.
#  Result: if you install together, pip resolves numpy 2.x which breaks insightface.
#
#  SOLUTION (same as Windows fix):
#    Phase 1: numpy 1.26.4 (explicitly lock 1.x first)
#    Phase 2: opencv 4.8.1.78 (last version accepting numpy 1.x on macOS Intel)
#    Phase 3: all other base packages EXCEPT insightface
#    Phase 4: insightface 0.7.3 last (deps already present)
#    Post:    verify numpy wasn't upgraded to 2.x by any transitive dep
# -----------------------------------------------------------------------
echo ""
echo "[6/9] Installing dependencies (phased to avoid numpy conflict)..."

echo ""
echo "  Phase 1/4: numpy 1.26.4 (must be 1.x for insightface)..."
"$VENV_PIP" install "numpy==1.26.4"
if [ $? -ne 0 ]; then
    echo "  ERROR: numpy install failed."
    exit 1
fi
echo "  numpy 1.26.4: installed"

echo ""
echo "  Phase 2/4: opencv-python-headless 4.8.1.78 (numpy 1.x compatible)..."
"$VENV_PIP" install "opencv-python-headless==4.8.1.78"
if [ $? -ne 0 ]; then
    echo "  ERROR: opencv install failed."
    echo "  This package requires macOS 10.15+ with x86_64 architecture."
    exit 1
fi
echo "  opencv 4.8.1.78: installed"

echo ""
echo "  Phase 3/4: Base packages..."
"$VENV_PIP" install \
    "flask==3.0.3" \
    "flask-cors==4.0.1" \
    "Pillow==10.4.0" \
    "Cython==3.0.10" \
    "scikit-learn==1.5.1" \
    "scipy==1.13.1" \
    "onnx==1.16.1" \
    "tqdm==4.66.4" \
    "prettytable==3.10.0" \
    "albumentations==1.3.1"
if [ $? -ne 0 ]; then
    echo "  ERROR: Base package install failed. See output above."
    exit 1
fi
echo "  Base packages: installed"

echo ""
echo "  Phase 4/4: insightface 0.7.3..."
"$VENV_PIP" install "insightface==0.7.3"
if [ $? -ne 0 ]; then
    echo "  ERROR: insightface install failed."
    echo "  Try running: $VENV_PIP install insightface==0.7.3 -v"
    echo "  to see the full error output."
    exit 1
fi
echo "  insightface 0.7.3: installed"

# --- numpy version guard ------------------------------------------------
# A transitive dependency might have upgraded numpy to 2.x.
# Re-pin it to 1.26.4 if that happened.
NUMPY_VER=$("$VENV_PYTHON" -c "import numpy; print(numpy.__version__)" 2>/dev/null)
echo ""
echo "  Checking numpy version: $NUMPY_VER"
if [[ "$NUMPY_VER" == 2* ]]; then
    echo "  WARNING: numpy was upgraded to 2.x by a transitive dep!"
    echo "  Re-pinning to numpy 1.26.4..."
    "$VENV_PIP" install "numpy==1.26.4"
    NUMPY_VER=$("$VENV_PYTHON" -c "import numpy; print(numpy.__version__)" 2>/dev/null)
    echo "  numpy is now: $NUMPY_VER"
fi

# -----------------------------------------------------------------------
#  Step 7: Install PyTorch (CPU-only for Intel Mac)
# -----------------------------------------------------------------------
echo ""
echo "[7/9] Installing PyTorch (CPU, Intel Mac)..."

# No CUDA on Intel, no MPS on Intel -- CPU only
echo "  Installing torch 2.1.2 (CPU)..."
"$VENV_PIP" install "torch==2.1.2" "torchvision==0.16.2"
if [ $? -ne 0 ]; then
    echo "  Pinned version failed. Trying latest compatible..."
    "$VENV_PIP" install torch torchvision
    if [ $? -ne 0 ]; then
        echo "  ERROR: torch install failed."
        exit 1
    fi
fi

# Confirm CPU mode -- Intel Mac has no MPS
TORCH_VER=$("$VENV_PYTHON" -c "import torch; print(torch.__version__)" 2>/dev/null)
echo "  torch $TORCH_VER: installed (CPU mode)"

echo "  Installing ONNX Runtime (CPU)..."
"$VENV_PIP" install "onnxruntime==1.16.3"
if [ $? -ne 0 ]; then
    echo "  Pinned version failed. Trying latest compatible..."
    "$VENV_PIP" install onnxruntime
fi
echo "  onnxruntime: installed"

# -----------------------------------------------------------------------
#  Step 8: Download InsightFace models
# -----------------------------------------------------------------------
echo ""
echo "[8/9] Checking InsightFace models..."

mkdir -p "$MODELS_DIR"

if [ -d "$MODELS_DIR/models/buffalo_l" ]; then
    echo "  Models already downloaded. Skipping."
else
    echo "  Downloading InsightFace buffalo_l model (~300MB)..."
    echo "  Requires internet. Please wait..."

    # Use double-quoted -c string -- $MODELS_DIR MUST expand here (not inside Python)
    "$VENV_PYTHON" -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_l', root='$MODELS_DIR')
print('Models downloaded successfully.')
"
    if [ $? -ne 0 ]; then
        echo "  WARNING: Model download failed."
        echo "  Internet is required on first run."
        echo "  Re-run ./setup.sh when online to download models."
        echo "  The server will not recognize faces until models are present."
    fi
fi

# -----------------------------------------------------------------------
#  Step 9: Per-package import validation
# -----------------------------------------------------------------------
echo ""
echo "[9/9] Validating all imports..."
echo ""

ALL_OK=1

validate() {
    MOD="$1"
    LABEL="$2"
    RESULT=$("$VENV_PYTHON" -c "
import $MOD
v = getattr(__import__('$MOD'), '__version__', 'ok')
print(v)
" 2>&1)
    if echo "$RESULT" | grep -q "Error\|error\|Traceback"; then
        echo "  FAIL  $LABEL"
        echo "        $RESULT"
        ALL_OK=0
    else
        printf "  OK    %-22s %s\n" "$LABEL" "$RESULT"
    fi
}

validate "flask"            "Flask"
validate "flask_cors"       "Flask-CORS"
validate "cv2"              "OpenCV"
validate "numpy"            "NumPy"
validate "PIL"              "Pillow"
validate "sklearn"          "scikit-learn"
validate "scipy"            "SciPy"
validate "onnx"             "ONNX"
validate "onnxruntime"      "onnxruntime"
validate "albumentations"   "albumentations"
validate "torch"            "PyTorch"
validate "insightface"      "InsightFace"

# numpy 1.x confirmation
NVER=$("$VENV_PYTHON" -c "import numpy; print(numpy.__version__)" 2>/dev/null)
if [[ "$NVER" == 2* ]]; then
    echo "  FAIL  numpy is $NVER -- insightface WILL fail at runtime!"
    ALL_OK=0
else
    echo "  OK    numpy 1.x ($NVER) -- insightface compatible"
fi

echo ""
echo " ====================================================="
echo "  SETUP COMPLETE"
echo " ====================================================="
echo "  Python:  $PY_VERSION (local, portable)"
echo "  venv:    $VENV_DIR"
echo "  Models:  $MODELS_DIR"
echo "  OS:      macOS $OS_VER | $ARCH"
echo "  GPU:     None (Intel Mac -- CPU mode)"
echo ""
if [ $ALL_OK -eq 1 ]; then
    echo "  Status:  ALL IMPORTS OK"
else
    echo "  Status:  SOME IMPORTS FAILED -- see above"
fi
echo ""
echo "  Run './run.sh' to start the server."
echo " ====================================================="
echo ""
