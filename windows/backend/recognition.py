"""
recognition.py — InsightFace integration for the Facial Attendance System.

Face detection, embedding extraction, recognition matching.
No classes. All def-based functions.
"""

import os
import numpy as np

from config import (
    MODEL_DIR, INSIGHTFACE_MODEL, RECOGNITION_THRESHOLD,
    EMBEDDING_DIM, get_onnx_providers
)

# ---------------------------------------------------------------------------
# Module-level state (initialized once via init_model)
# ---------------------------------------------------------------------------
_face_app = None
_initialized = False


# ---------------------------------------------------------------------------
# Model Initialization
# ---------------------------------------------------------------------------

def init_model():
    """
    Load the InsightFace model. Call once at server startup.
    Uses GPU providers if available, falls back to CPU.
    """
    global _face_app, _initialized

    if _initialized:
        return True

    try:
        import insightface
        from insightface.app import FaceAnalysis

        providers = get_onnx_providers()
        print(f"[Recognition] Initializing InsightFace with providers: {providers}")

        _face_app = FaceAnalysis(
            name=INSIGHTFACE_MODEL,
            root=MODEL_DIR,
            providers=providers,
        )

        # det_size: detection input size, smaller = faster
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
        _initialized = True
        print("[Recognition] Model loaded successfully.")
        return True

    except Exception as e:
        print(f"[Recognition] ERROR loading model: {e}")
        _initialized = False
        return False


def is_model_ready():
    """Check if the recognition model is loaded."""
    return _initialized and _face_app is not None


# ---------------------------------------------------------------------------
# Face Detection
# ---------------------------------------------------------------------------

def detect_faces(image):
    """
    Detect faces in an image (BGR numpy array).
    Returns list of face dicts:
        [{bbox, embedding, det_score, ...}, ...]
    Returns empty list if no faces found or model not ready.
    """
    if not is_model_ready():
        print("[Recognition] Model not initialized!")
        return []

    try:
        faces = _face_app.get(image)
        results = []
        for face in faces:
            results.append({
                "bbox": face.bbox.tolist(),
                "embedding": face.normed_embedding,
                "det_score": float(face.det_score),
            })
        return results

    except Exception as e:
        print(f"[Recognition] Detection error: {e}")
        return []


# ---------------------------------------------------------------------------
# Face Recognition (Matching)
# ---------------------------------------------------------------------------

def compute_similarity(emb1, emb2):
    """Compute cosine similarity between two normalized embeddings."""
    return float(np.dot(emb1, emb2))


def recognize_face(embedding, stored_embeddings, threshold=None):
    """
    Compare a face embedding against stored embeddings.

    Args:
        embedding: numpy array (512,) — the probe face
        stored_embeddings: list of {user_id, embedding} dicts from DB
        threshold: float, minimum similarity to accept (default from config)

    Returns:
        dict or None: {user_id, similarity} if match found, else None
    """
    if threshold is None:
        threshold = RECOGNITION_THRESHOLD

    best_match = None
    best_score = -1.0

    for stored in stored_embeddings:
        sim = compute_similarity(embedding, stored["embedding"])
        if sim > best_score:
            best_score = sim
            best_match = stored["user_id"]

    if best_score >= threshold and best_match is not None:
        return {"user_id": best_match, "similarity": round(best_score, 4)}

    return None


# ---------------------------------------------------------------------------
# Registration Embeddings
# ---------------------------------------------------------------------------

def extract_registration_embeddings(frames):
    """
    Process multiple video frames to extract and average face embeddings.

    Args:
        frames: list of BGR numpy arrays (from video capture)

    Returns:
        dict: {success, embedding (np.array or None), face_count, message}
    """
    if not is_model_ready():
        return {"success": False, "embedding": None,
                "face_count": 0, "message": "Model not initialized"}

    embeddings = []

    for i, frame in enumerate(frames):
        faces = detect_faces(frame)

        if len(faces) == 0:
            # Skip frames with no face
            continue

        if len(faces) > 1:
            # Multiple faces in a registration frame is invalid
            return {
                "success": False,
                "embedding": None,
                "face_count": len(faces),
                "message": f"Multiple faces detected in frame {i+1}. "
                           "Please ensure only your face is visible.",
            }

        embeddings.append(faces[0]["embedding"])

    if len(embeddings) < 3:
        return {
            "success": False,
            "embedding": None,
            "face_count": 0,
            "message": f"Only {len(embeddings)} usable frames captured. "
                       "Need at least 3. Please try again with better lighting.",
        }

    # Average all embeddings for robustness
    avg_embedding = np.mean(embeddings, axis=0)
    # Normalize
    norm = np.linalg.norm(avg_embedding)
    if norm > 0:
        avg_embedding = avg_embedding / norm

    return {
        "success": True,
        "embedding": avg_embedding,
        "face_count": 1,
        "message": f"Registration successful. {len(embeddings)} frames processed.",
    }


# ---------------------------------------------------------------------------
# Multi-Face Handling
# ---------------------------------------------------------------------------

def handle_multi_face(faces, stored_embeddings):
    """
    Handle a frame with multiple faces during attendance.

    Rules:
        - If multiple unknown faces → return error
        - If known + unknown → return known people only
        - If all known → return all

    Args:
        faces: list of face dicts from detect_faces()
        stored_embeddings: all stored embeddings from DB

    Returns:
        dict: {recognized (list), unknown_count, error (str or None)}
    """
    recognized = []
    unknown_count = 0

    for face in faces:
        match = recognize_face(face["embedding"], stored_embeddings)
        if match:
            recognized.append({
                "user_id": match["user_id"],
                "similarity": match["similarity"],
                "bbox": face["bbox"],
            })
        else:
            unknown_count += 1

    # Multiple unknowns = ambiguous, reject
    if unknown_count > 1:
        return {
            "recognized": [],
            "unknown_count": unknown_count,
            "error": f"{unknown_count} unknown faces detected. "
                     "Cannot determine identity. Please ensure only "
                     "registered faces are in the frame.",
        }

    return {
        "recognized": recognized,
        "unknown_count": unknown_count,
        "error": None,
    }
