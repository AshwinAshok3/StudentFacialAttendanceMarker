#!/bin/bash
# =========================================================================
#  setup.sh — Portable macOS Setup for Facial Attendance System
#
#  ISOLATION DESIGN:
#  - Installs Python 3.10.5 locally via pyenv into macos/.pyenv/
#  - Creates .venv inside macos/ using that local Python
#  - Installs ALL packages into .venv only
#  - ZERO system-wide changes
#  - MPS support for Apple Silicon, CPU fallback for Intel
#  - Entire setup is portable after first internet run
#
#  REQUIREMENTS:
#  - Internet connection (first run only)
#  - macOS 12.x+ (Monterey or later)
#  - Xcode command line tools (for building Python)
#  - ~2 GB disk space
# =========================================================================

set -e

# Resolve this script's directory (macos/)
MAC_DIR="$(cd "$(dirname "$0")" && pwd)"

PYENV_ROOT="$MAC_DIR/.pyenv"
PY_VERSION="3.10.5"
VENV_DIR="$MAC_DIR/.venv"
MODELS_DIR="$MAC_DIR/models"
REQ_FILE="$MAC_DIR/requirements.txt"

echo ""
echo " ====================================================="
echo "  FACIAL ATTENDANCE SYSTEM — PORTABLE macOS SETUP"
echo " ====================================================="
echo "  Target: Python $PY_VERSION (local only)"
echo "  Location: $MAC_DIR"
echo " ====================================================="
echo ""

# -----------------------------------------------------------------------
#  Step 1: Detect macOS version and architecture
# -----------------------------------------------------------------------
echo "[1/8] Detecting system..."

OS_VER=$(sw_vers -productVersion 2>/dev/null || echo "unknown")
ARCH=$(uname -m)
IS_ARM=0

if [ "$ARCH" = "arm64" ]; then
    IS_ARM=1
    echo "  Architecture: Apple Silicon (arm64)"
else
    echo "  Architecture: Intel ($ARCH)"
fi
echo "  macOS Version: $OS_VER"

# Check Xcode command line tools
if ! command -v xcode-select &>/dev/null || ! xcode-select -p &>/dev/null; then
    echo ""
    echo "  WARNING: Xcode command line tools not found."
    echo "  Install them with: xcode-select --install"
    echo "  Then re-run this script."
    exit 1
fi
echo "  Xcode CLI tools: Found"

# -----------------------------------------------------------------------
#  Step 2: Install Python 3.10.5 locally via pyenv
# -----------------------------------------------------------------------
echo ""
echo "[2/8] Setting up Python $PY_VERSION..."

# Check if we already have Python 3.10.5 installed locally
LOCAL_PYTHON="$PYENV_ROOT/versions/$PY_VERSION/bin/python3"

if [ -f "$LOCAL_PYTHON" ]; then
    FOUND_VER=$("$LOCAL_PYTHON" --version 2>&1 | awk '{print $2}')
    if [ "$FOUND_VER" = "$PY_VERSION" ]; then
        echo "  Found: Python $FOUND_VER (local)"
    else
        echo "  Version mismatch ($FOUND_VER). Reinstalling..."
        rm -rf "$PYENV_ROOT/versions/$PY_VERSION"
        LOCAL_PYTHON=""
    fi
fi

if [ ! -f "$LOCAL_PYTHON" ]; then
    echo "  Python $PY_VERSION not found locally."
    echo "  Installing via pyenv (local to this directory)..."

    # Install pyenv locally if not present
    if [ ! -d "$PYENV_ROOT" ]; then
        echo "  Downloading pyenv..."
        git clone https://github.com/pyenv/pyenv.git "$PYENV_ROOT" 2>/dev/null
    fi

    # Set pyenv environment (local only, no global shell changes)
    export PYENV_ROOT="$PYENV_ROOT"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$("$PYENV_ROOT/bin/pyenv" init --path 2>/dev/null)" || true

    echo "  Compiling Python $PY_VERSION (this may take 5-10 minutes)..."

    # Build flags for macOS
    if [ $IS_ARM -eq 1 ]; then
        PYTHON_CONFIGURE_OPTS="--enable-framework" \
        "$PYENV_ROOT/bin/pyenv" install "$PY_VERSION" -s 2>&1 | tail -5
    else
        PYTHON_CONFIGURE_OPTS="--enable-framework" \
        "$PYENV_ROOT/bin/pyenv" install "$PY_VERSION" -s 2>&1 | tail -5
    fi

    if [ ! -f "$LOCAL_PYTHON" ]; then
        echo "  ERROR: Python $PY_VERSION build failed."
        echo "  Make sure Xcode CLI tools and build dependencies are installed:"
        echo "    brew install openssl readline sqlite3 xz zlib tcl-tk"
        exit 1
    fi

    echo "  Python $PY_VERSION compiled and installed locally."
fi

echo "  Python path: $LOCAL_PYTHON"

# -----------------------------------------------------------------------
#  Step 3: Create virtual environment
# -----------------------------------------------------------------------
echo ""
echo "[3/8] Creating virtual environment..."

VENV_PYTHON="$VENV_DIR/bin/python3"

if [ -f "$VENV_PYTHON" ]; then
    VENV_VER=$("$VENV_PYTHON" --version 2>&1 | awk '{print $2}')
    if [ "$VENV_VER" = "$PY_VERSION" ]; then
        echo "  .venv already exists with Python $VENV_VER. Reusing."
    else
        echo "  .venv has wrong Python ($VENV_VER). Recreating..."
        rm -rf "$VENV_DIR"
        "$LOCAL_PYTHON" -m venv "$VENV_DIR"
    fi
else
    "$LOCAL_PYTHON" -m venv "$VENV_DIR"
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "  ERROR: Failed to create virtual environment."
    exit 1
fi

echo "  .venv ready at: $VENV_DIR"

# Activate (for this script only)
source "$VENV_DIR/bin/activate"

# -----------------------------------------------------------------------
#  Step 4: Upgrade pip
# -----------------------------------------------------------------------
echo ""
echo "[4/8] Upgrading pip..."
pip install --upgrade pip --quiet 2>/dev/null
echo "  pip upgraded."

# -----------------------------------------------------------------------
#  Step 5: Install base dependencies
# -----------------------------------------------------------------------
echo ""
echo "[5/8] Installing base dependencies..."
pip install -r "$REQ_FILE" --quiet 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  WARNING: Some packages may have failed. Retrying verbose..."
    pip install -r "$REQ_FILE"
fi
echo "  Base packages installed."

# -----------------------------------------------------------------------
#  Step 6: Install PyTorch (MPS or CPU)
# -----------------------------------------------------------------------
echo ""
echo "[6/8] Installing PyTorch..."

if [ $IS_ARM -eq 1 ]; then
    echo "  Installing PyTorch with MPS support (Apple Silicon)..."
    pip install torch==2.1.2 torchvision==0.16.2 --quiet 2>/dev/null

    # Verify MPS
    MPS_OK=$(python3 -c "
import torch
if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
    print('yes')
else:
    print('no')
" 2>/dev/null)

    if [ "$MPS_OK" = "yes" ]; then
        echo "  MPS (Metal) acceleration: AVAILABLE"
    else
        echo "  MPS not available. Using CPU fallback."
        echo "  (MPS requires macOS 12.3+ on Apple Silicon)"
    fi
else
    echo "  Installing CPU-only PyTorch (Intel Mac)..."
    pip install torch==2.1.2 torchvision==0.16.2 --quiet 2>/dev/null
fi

echo "  Installing ONNX Runtime..."
pip install onnxruntime==1.16.3 --quiet 2>/dev/null
if [ $? -ne 0 ]; then
    pip install onnxruntime --quiet 2>/dev/null
fi
echo "  Done."

# -----------------------------------------------------------------------
#  Step 7: Download InsightFace models
# -----------------------------------------------------------------------
echo ""
echo "[7/8] Checking InsightFace models..."

mkdir -p "$MODELS_DIR"

if [ -d "$MODELS_DIR/models/buffalo_l" ]; then
    echo "  Models already downloaded. Skipping."
else
    echo "  Downloading InsightFace buffalo_l model (~300MB)..."
    python3 -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_l', root='$MODELS_DIR')
print('  Models downloaded successfully.')
" 2>/dev/null || {
        echo "  WARNING: Model download failed."
        echo "  This requires internet access on first run."
        echo "  Retry by running ./setup.sh again."
    }
fi

# -----------------------------------------------------------------------
#  Step 8: System summary
# -----------------------------------------------------------------------
echo ""
echo "[8/8] System Summary"
echo ""
echo " ====================================================="
echo "  SETUP COMPLETE"
echo " ====================================================="
echo "  Python:       $PY_VERSION (local, portable)"
VENV_VER=$("$VENV_PYTHON" --version 2>&1 | awk '{print $2}')
echo "  Venv Python:  $VENV_VER"
echo "  Python Path:  $(dirname $LOCAL_PYTHON)"
echo "  Venv Path:    $VENV_DIR"
echo "  Models Path:  $MODELS_DIR"
echo "  Architecture: $ARCH"
echo "  macOS:        $OS_VER"

if [ $IS_ARM -eq 1 ]; then
    if [ "$MPS_OK" = "yes" ]; then
        echo "  Acceleration: MPS (Metal)"
    else
        echo "  Acceleration: CPU (MPS unavailable)"
    fi
else
    echo "  Acceleration: CPU (Intel)"
fi

# Validate torch
python3 -c "import torch; print('  Torch:        ' + torch.__version__)" 2>/dev/null || echo "  Torch:        NOT INSTALLED"
python3 -c "import insightface; print('  InsightFace:  ' + insightface.__version__)" 2>/dev/null || echo "  InsightFace:  NOT INSTALLED"

echo ""
echo " ====================================================="
echo "  Run './run.sh' to start the server."
echo " ====================================================="
echo ""
