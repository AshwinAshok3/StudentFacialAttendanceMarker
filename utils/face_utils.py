"""
FaceAnalyzer — InsightFace detection + embedding + matching pipeline.
Runs fully offline using locally cached buffalo_l model.
"""
import os
import numpy as np
import cv2
from typing import List, Optional, Tuple, Dict, Any

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_ROOT = os.path.join(BASE_DIR, "models", "insightface")

# Tunable thresholds (cosine similarity, higher = more strict)
SIMILARITY_THRESHOLD = 0.45   # primary match threshold
MIN_FACE_SIZE        = 60     # pixels (width or height)
MIN_DETECTION_CONF   = 0.85   # InsightFace det_score
MIN_VISIBILITY_RATIO = 0.60   # fraction of canonical 112×112 face that must be visible


class FaceAnalyzer:
    """
    Wraps InsightFace FaceAnalysis model.
    Lazy-loads on first call so Streamlit imports don't block.
    """

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = threshold
        self._model = None

    # ------------------------------------------------------------------ #
    # Model loading
    # ------------------------------------------------------------------ #

    def _load_model(self):
        """Load InsightFace buffalo_l model from local cache."""
        if self._model is not None:
            return
        try:
            import insightface
            from insightface.app import FaceAnalysis

            os.makedirs(MODEL_ROOT, exist_ok=True)
            self._model = FaceAnalysis(
                name="buffalo_l",
                root=MODEL_ROOT,
                providers=["CPUExecutionProvider"],   # CPU-only, no CUDA required
            )
            self._model.prepare(ctx_id=-1, det_size=(640, 640))
        except Exception as e:
            raise RuntimeError(f"Failed to load InsightFace model: {e}") from e

    # ------------------------------------------------------------------ #
    # Detection
    # ------------------------------------------------------------------ #

    def detect_faces(self, frame: np.ndarray) -> List[Any]:
        """
        Detect all faces in a BGR frame.
        Returns list of InsightFace Face objects that pass quality checks.
        """
        self._load_model()
        if frame is None or frame.size == 0:
            return []

        # Lighting normalisation: CLAHE on L-channel then convert back
        frame_normalized = self._normalize_lighting(frame)

        faces = self._model.get(frame_normalized)
        return [f for f in faces if self._passes_quality(f)]

    def _normalize_lighting(self, frame: np.ndarray) -> np.ndarray:
        """Apply CLAHE to reduce harsh lighting / shadows."""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_chan = clahe.apply(l_chan)
        lab = cv2.merge([l_chan, a_chan, b_chan])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _passes_quality(self, face: Any) -> bool:
        """Return True if a face meets minimum quality requirements."""
        # Detection confidence
        if hasattr(face, "det_score") and face.det_score < MIN_DETECTION_CONF:
            return False
        # Face size
        if face.bbox is not None:
            x1, y1, x2, y2 = face.bbox.astype(int)
            w, h = x2 - x1, y2 - y1
            if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
                return False
        # Embedding must be present
        if face.embedding is None:
            return False
        return True

    # ------------------------------------------------------------------ #
    # Embedding
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_embedding(face: Any) -> Optional[np.ndarray]:
        """Extract L2-normalised 512-dim embedding from a face object."""
        if face.embedding is None:
            return None
        emb = face.embedding.astype(np.float32)
        norm = np.linalg.norm(emb)
        if norm == 0:
            return None
        return emb / norm

    # ------------------------------------------------------------------ #
    # Similarity
    # ------------------------------------------------------------------ #

    @staticmethod
    def compare_embeddings(e1: np.ndarray, e2: np.ndarray) -> float:
        """Cosine similarity between two L2-normalised embeddings (0–1)."""
        return float(np.clip(np.dot(e1, e2), 0.0, 1.0))

    def find_best_match(
        self,
        query_embedding: np.ndarray,
        stored: List[Tuple[str, np.ndarray]],
    ) -> Tuple[Optional[str], float]:
        """
        Compare query against all stored (user_id, embedding) pairs.
        Returns (best_user_id, best_score) or (None, best_score).

        Averages scores across all embeddings for the same user to improve
        robustness across different face angles.
        """
        if not stored:
            return None, 0.0

        # Aggregate per user: take max similarity across their embeddings
        user_scores: Dict[str, float] = {}
        for uid, emb in stored:
            score = self.compare_embeddings(query_embedding, emb)
            if uid not in user_scores or score > user_scores[uid]:
                user_scores[uid] = score

        best_uid = max(user_scores, key=lambda k: user_scores[k])
        best_score = user_scores[best_uid]

        if best_score >= self.threshold:
            return best_uid, best_score
        return None, best_score

    # ------------------------------------------------------------------ #
    # Bounding box drawing
    # ------------------------------------------------------------------ #

    @staticmethod
    def draw_box(
        frame: np.ndarray,
        face: Any,
        label: str,
        color: Tuple[int, int, int],
        score: float = 0.0,
    ) -> np.ndarray:
        """
        Draw a bounding box and label on the frame.
        Colors: green=(0,200,50), red=(0,0,220), yellow=(0,200,200)
        """
        if face.bbox is None:
            return frame
        x1, y1, x2, y2 = face.bbox.astype(int)
        thickness = 2

        # Box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        # Label background
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)

        # Label text
        cv2.putText(
            frame, label, (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA,
        )

        # Confidence
        if score > 0:
            conf_label = f"{score:.2f}"
            cv2.putText(
                frame, conf_label, (x1 + 2, y2 + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
            )
        return frame

    # ------------------------------------------------------------------ #
    # Frame embedding for registration (multi-angle)
    # ------------------------------------------------------------------ #

    def extract_embedding_from_frame(
        self, frame: np.ndarray
    ) -> Optional[np.ndarray]:
        """
        Detect the largest / best face in a frame and return its embedding.
        Used during registration capture.
        """
        faces = self.detect_faces(frame)
        if not faces:
            return None
        # Pick face with highest detection score
        best = max(faces, key=lambda f: getattr(f, "det_score", 0))
        return self.get_embedding(best)
