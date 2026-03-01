#!/bin/bash
# =========================================================================
#  run.sh — Start the Facial Attendance System (macOS)
# =========================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " Starting Facial Attendance System..."
echo ""

# Check if venv exists
if [ ! -f "venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found."
    echo "Please run ./setup.sh first."
    exit 1
fi

# Activate venv
source venv/bin/activate

echo " Server starting at http://localhost:5000"
echo " Press Ctrl+C to stop."
echo ""

# Open browser after a short delay
(sleep 3 && open http://localhost:5000) &

# Run the server
python3 backend/app.py
