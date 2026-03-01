#!/bin/bash
# =========================================================================
#  setup.sh — macOS Setup for Facial Attendance System
#
#  1. Checks Python 3.10.x
#  2. Creates virtual environment
#  3. Installs base dependencies
#  4. Detects Apple Silicon vs Intel
#  5. Evaluates MPS support, installs appropriate PyTorch
#  6. Downloads InsightFace models
#  7. Prints system summary
# =========================================================================

set -e

echo ""
echo " ============================================"
echo "  FACIAL ATTENDANCE SYSTEM — macOS SETUP"
echo " ============================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# -----------------------------------------------------------------------
#  Step 1: Check Python version
# -----------------------------------------------------------------------
echo "[1/7] Checking Python version..."

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found."
    echo "Install Python 3.10+ via: brew install python@3.10"
    exit 1
fi

PYVER=$(python3 --version 2>&1)
echo "  Found: $PYVER"

python3 -c "
import sys
v = sys.version_info
if v.major != 3 or v.minor < 10:
    print('WARNING: Python 3.10+ recommended.')
" 2>/dev/null

# -----------------------------------------------------------------------
#  Step 2: Create virtual environment
# -----------------------------------------------------------------------
echo ""
echo "[2/7] Creating virtual environment..."

if [ -d "venv" ]; then
    echo "  Virtual environment already exists. Reusing."
else
    python3 -m venv venv
    echo "  Created: venv/"
fi

# Activate
source venv/bin/activate

# Upgrade pip
echo "  Upgrading pip..."
pip install --upgrade pip --quiet

# -----------------------------------------------------------------------
#  Step 3: Install base dependencies
# -----------------------------------------------------------------------
echo ""
echo "[3/7] Installing base dependencies..."
pip install -r requirements.txt --quiet
echo "  Base packages installed."

# -----------------------------------------------------------------------
#  Step 4: Detect hardware
# -----------------------------------------------------------------------
echo ""
echo "[4/7] Detecting hardware..."

ARCH=$(uname -m)
IS_ARM=0

if [ "$ARCH" = "arm64" ]; then
    echo "  Apple Silicon (arm64) detected."
    IS_ARM=1
else
    echo "  Intel ($ARCH) detected."
fi

# -----------------------------------------------------------------------
#  Step 5: Install PyTorch
# -----------------------------------------------------------------------
echo ""
echo "[5/7] Installing PyTorch and ONNX Runtime..."

if [ $IS_ARM -eq 1 ]; then
    echo "  Installing PyTorch with MPS support..."
    pip install torch torchvision --quiet
    
    # Check if MPS is actually available
    MPS_OK=$(python3 -c "
import torch
if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
    print('yes')
else:
    print('no')
" 2>/dev/null)

    if [ "$MPS_OK" = "yes" ]; then
        echo "  MPS (Metal) acceleration available!"
    else
        echo "  MPS not available on this system. Using CPU mode."
    fi
else
    echo "  Installing CPU-only PyTorch (Intel Mac)..."
    pip install torch torchvision --quiet
fi

echo "  Installing ONNX Runtime..."
pip install onnxruntime --quiet
echo "  Done."

# -----------------------------------------------------------------------
#  Step 6: Download InsightFace models
# -----------------------------------------------------------------------
echo ""
echo "[6/7] Downloading InsightFace models..."

if [ -d "models/buffalo_l" ]; then
    echo "  Models already exist. Skipping download."
else
    python3 -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_l', root='models')
print('Models downloaded successfully.')
" 2>/dev/null || {
        echo "WARNING: Model download failed. You may need internet access."
        echo "You can retry by running this script again."
    }
fi

# -----------------------------------------------------------------------
#  Step 7: System Summary
# -----------------------------------------------------------------------
echo ""
echo "[7/7] Generating system summary..."
echo ""

python3 -c "
import sys
sys.path.insert(0, 'backend')
from utils import format_system_summary
print(format_system_summary())
" 2>/dev/null || echo "  (Could not generate summary — run the server to see status)"

echo ""
echo " Setup complete! Run './run.sh' to start the server."
echo ""
