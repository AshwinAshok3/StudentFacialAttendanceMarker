"""
config.py — Configuration constants for the Facial Attendance System.

All paths, secrets, and runtime settings centralized here.
No classes. Pure constants and detection functions.
"""

import os
import platform

# ---------------------------------------------------------------------------
# Paths  (resolved relative to this file → backend/)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)                 # windows/ or macos/
FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
MODEL_DIR = os.path.join(PROJECT_DIR, "models")
DB_PATH = os.path.join(PROJECT_DIR, "data", "attendance.db")

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SFAM_SECRET", "sfam-offline-secret-2026")
HOST = "0.0.0.0"
PORT = 5000
DEBUG = os.environ.get("SFAM_DEBUG", "1") == "1"

# ---------------------------------------------------------------------------
# Session / Auth
# ---------------------------------------------------------------------------
SESSION_LIFETIME_HOURS = 24
DEFAULT_ADMIN_EMAIL = "admin@system.local"
DEFAULT_ADMIN_PASSWORD = "admin123"

# ---------------------------------------------------------------------------
# Recognition
# ---------------------------------------------------------------------------
INSIGHTFACE_MODEL = "buffalo_l"
RECOGNITION_THRESHOLD = 0.45          # cosine similarity threshold
MAX_FRAME_BYTES = 5 * 1024 * 1024     # 5 MB per frame
REGISTRATION_FRAME_COUNT = 15         # target frames during 5-sec capture
EMBEDDING_DIM = 512

# ---------------------------------------------------------------------------
# GPU Detection
# ---------------------------------------------------------------------------

def detect_gpu():
    """
    Detect available GPU acceleration.
    Returns dict with keys: device, cuda_available, mps_available, gpu_name
    """
    info = {
        "device": "cpu",
        "cuda_available": False,
        "mps_available": False,
        "gpu_name": "None",
        "os": platform.system(),
    }

    # Try CUDA (Windows / Linux)
    try:
        import torch
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["device"] = "cuda"
            info["gpu_name"] = torch.cuda.get_device_name(0)
            return info
    except ImportError:
        pass

    # Try MPS (macOS Apple Silicon)
    try:
        import torch
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["mps_available"] = True
            info["device"] = "mps"
            info["gpu_name"] = "Apple Silicon (MPS)"
            return info
    except ImportError:
        pass

    return info


def get_onnx_providers():
    """
    Return the ONNX execution providers list for InsightFace.
    Prioritizes GPU providers when available.
    """
    gpu = detect_gpu()

    if gpu["cuda_available"]:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    # MPS doesn't use ONNX providers — InsightFace will use CPU on macOS
    return ["CPUExecutionProvider"]
