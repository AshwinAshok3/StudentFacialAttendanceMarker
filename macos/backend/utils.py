"""
utils.py — Utility functions for the Facial Attendance System.

Image encoding/decoding, GPU detection summaries, frame validation.
No classes. All def-based.
"""

import base64
import platform
import sys
import os

import cv2
import numpy as np

from config import MAX_FRAME_BYTES, MODEL_DIR, INSIGHTFACE_MODEL, detect_gpu


# ---------------------------------------------------------------------------
# Image Encoding / Decoding
# ---------------------------------------------------------------------------

def decode_base64_image(data):
    """
    Decode a base64-encoded image string to a numpy array (BGR).
    Handles optional 'data:image/...;base64,' prefix.
    Returns numpy array or None on failure.
    """
    try:
        # Strip data URI prefix if present
        if "," in data:
            data = data.split(",", 1)[1]

        img_bytes = base64.b64decode(data)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return image

    except Exception:
        return None


def encode_image_base64(image):
    """
    Encode a numpy array (BGR) to a base64 JPEG string.
    Returns base64 string or None on failure.
    """
    try:
        _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        b64 = base64.b64encode(buffer).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_frame_size(data):
    """
    Check that a base64 frame doesn't exceed the max allowed size.
    Returns (ok: bool, message: str).
    """
    if not data:
        return False, "No frame data provided"

    # Estimate decoded size (base64 is ~4/3 of original)
    estimated_size = len(data) * 3 // 4
    if estimated_size > MAX_FRAME_BYTES:
        return False, f"Frame too large: {estimated_size} bytes (max {MAX_FRAME_BYTES})"

    return True, "OK"


# ---------------------------------------------------------------------------
# System Information
# ---------------------------------------------------------------------------

def get_system_info():
    """
    Gather system information for the admin dashboard.
    Returns dict with OS, Python, GPU, and model details.
    """
    gpu = detect_gpu()

    # Check if InsightFace models are downloaded
    model_path = os.path.join(MODEL_DIR, INSIGHTFACE_MODEL)
    models_ready = os.path.isdir(model_path) and len(os.listdir(model_path)) > 0

    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": sys.version.split()[0],
        "architecture": platform.machine(),
        "gpu_device": gpu["device"],
        "gpu_name": gpu["gpu_name"],
        "cuda_available": gpu["cuda_available"],
        "mps_available": gpu["mps_available"],
        "models_ready": models_ready,
        "model_name": INSIGHTFACE_MODEL,
        "model_path": model_path,
    }


def format_system_summary():
    """
    Create a human-readable system summary string.
    Used by setup scripts and admin panel.
    """
    info = get_system_info()
    lines = [
        "=" * 50,
        "  FACIAL ATTENDANCE SYSTEM — STATUS",
        "=" * 50,
        f"  OS:           {info['os']} {info['os_version'][:30]}",
        f"  Python:       {info['python_version']}",
        f"  Architecture: {info['architecture']}",
        f"  GPU Device:   {info['gpu_device'].upper()}",
        f"  GPU Name:     {info['gpu_name']}",
        f"  CUDA:         {'Yes' if info['cuda_available'] else 'No'}",
        f"  MPS:          {'Yes' if info['mps_available'] else 'No'}",
        f"  Models Ready: {'Yes' if info['models_ready'] else 'No'}",
        f"  Model:        {info['model_name']}",
        "=" * 50,
    ]
    return "\n".join(lines)
