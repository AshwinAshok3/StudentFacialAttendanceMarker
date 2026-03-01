#!/bin/bash
# =========================================================================
#  run.sh — Start the Facial Attendance System (macOS)
#
#  ISOLATION: Uses ONLY the local .venv inside macos/.
#  Validates Python 3.10.5 before launching.
# =========================================================================

# Resolve this script's directory (macos/)
MAC_DIR="$(cd "$(dirname "$0")" && pwd)"

VENV_DIR="$MAC_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
BACKEND_DIR="$MAC_DIR/backend"
REQUIRED_VERSION="3.10.5"

echo ""
echo " ====================================================="
echo "  FACIAL ATTENDANCE SYSTEM — STARTING"
echo " ====================================================="
echo ""

# -----------------------------------------------------------------------
#  Step 1: Verify .venv exists
# -----------------------------------------------------------------------
if [ ! -f "$VENV_PYTHON" ]; then
    echo "  ERROR: Virtual environment not found at:"
    echo "    $VENV_DIR"
    echo ""
    echo "  Please run ./setup.sh first to create the environment."
    exit 1
fi

# -----------------------------------------------------------------------
#  Step 2: Validate Python version is exactly 3.10.5
# -----------------------------------------------------------------------
echo "[1/3] Validating Python version..."

FOUND_VER=$("$VENV_PYTHON" --version 2>&1 | awk '{print $2}')

if [ "$FOUND_VER" != "$REQUIRED_VERSION" ]; then
    echo "  ERROR: Python version mismatch!"
    echo "  Expected: $REQUIRED_VERSION"
    echo "  Found:    $FOUND_VER"
    echo ""
    echo "  Please delete .venv and re-run ./setup.sh."
    exit 1
fi

echo "  Python $FOUND_VER confirmed."

# -----------------------------------------------------------------------
#  Step 3: Validate backend
# -----------------------------------------------------------------------
echo "[2/3] Checking backend..."

if [ ! -f "$BACKEND_DIR/app.py" ]; then
    echo "  ERROR: backend/app.py not found at:"
    echo "    $BACKEND_DIR"
    echo ""
    echo "  The backend code is missing."
    exit 1
fi

echo "  Backend verified."

# -----------------------------------------------------------------------
#  Step 4: Start the server
# -----------------------------------------------------------------------
echo "[3/3] Starting server..."
echo ""
echo "  Server:  http://localhost:5000"
echo "  Press Ctrl+C to stop."
echo ""

# Activate venv
source "$VENV_DIR/bin/activate"

# Open browser after a short delay (non-blocking)
(sleep 3 && open http://localhost:5000) &

# Run the Flask server
python3 "$BACKEND_DIR/app.py"
