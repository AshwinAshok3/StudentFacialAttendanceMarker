#!/bin/bash
# =========================================================================
#  run.sh -- Start the Facial Attendance System (macOS Intel)
#
#  ISOLATION: Uses ONLY the local venv inside macos/.
#  Validates Python 3.10.5 exactly before launching.
# =========================================================================

MAC_DIR="$(cd "$(dirname "$0")" && pwd)"

VENV_DIR="$MAC_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
BACKEND_DIR="$MAC_DIR/backend"
REQUIRED_VERSION="3.10.5"

echo ""
echo " ====================================================="
echo "  FACIAL ATTENDANCE SYSTEM -- STARTING"
echo " ====================================================="
echo ""

# -----------------------------------------------------------------------
#  Check 1: venv exists
# -----------------------------------------------------------------------
if [ ! -f "$VENV_PYTHON" ]; then
    echo "  ERROR: Virtual environment not found:"
    echo "    $VENV_DIR"
    echo ""
    echo "  Run ./setup.sh first."
    exit 1
fi

# -----------------------------------------------------------------------
#  Check 2: Python version is exactly 3.10.5
# -----------------------------------------------------------------------
echo "[1/3] Validating Python version..."

FOUND_VER=$("$VENV_PYTHON" --version 2>&1 | awk '{print $2}')

if [ "$FOUND_VER" != "$REQUIRED_VERSION" ]; then
    echo "  ERROR: Python version mismatch."
    echo "  Expected: $REQUIRED_VERSION"
    echo "  Found:    $FOUND_VER"
    echo ""
    echo "  Delete venv/ and re-run ./setup.sh:"
    echo "    rm -rf $VENV_DIR && ./setup.sh"
    exit 1
fi
echo "  Python $FOUND_VER: OK"

# -----------------------------------------------------------------------
#  Check 3: backend exists
# -----------------------------------------------------------------------
echo "[2/3] Checking backend..."

if [ ! -f "$BACKEND_DIR/app.py" ]; then
    echo "  ERROR: backend/app.py not found at:"
    echo "    $BACKEND_DIR"
    exit 1
fi
echo "  Backend: OK"

# -----------------------------------------------------------------------
#  Check 4: models present (warn if not, but don't block startup)
# -----------------------------------------------------------------------
MODELS_DIR="$MAC_DIR/models"
if [ ! -d "$MODELS_DIR/models/buffalo_l" ]; then
    echo ""
    echo "  WARNING: InsightFace models not found at $MODELS_DIR"
    echo "  Face recognition will not work until models are downloaded."
    echo "  Run ./setup.sh with internet to download them."
    echo ""
fi

# -----------------------------------------------------------------------
#  Start
# -----------------------------------------------------------------------
echo "[3/3] Starting server..."
echo ""
echo "  URL:     http://localhost:5000"
echo "  Mode:    CPU (Intel Mac)"
echo "  Press Ctrl+C to stop."
echo ""

# Activate local venv for this session
source "$VENV_DIR/bin/activate"

# Open browser after 3 seconds (non-blocking)
(sleep 3 && open http://localhost:5000) &

# Run Flask server
python3 "$BACKEND_DIR/app.py"

FLASK_EXIT=$?
if [ $FLASK_EXIT -ne 0 ]; then
    echo ""
    echo "  Server exited with error code: $FLASK_EXIT"
    echo "  Check the output above for details."
fi
