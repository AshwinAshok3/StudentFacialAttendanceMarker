"""
AttendanceEngine — core pipeline that ties face recognition to attendance marking.
Designed to be called once per video frame from the Streamlit camera feed page.
"""
import os
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from utils.face_utils import FaceAnalyzer
from utils.excel_utils import append_to_excel
from utils.logger import logger
from database.db_manager import DatabaseManager

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTOS_DIR  = os.path.join(BASE_DIR, "attendance_records", "photos")

# Bounding box colours (BGR)
COLOR_SUCCESS  = (50,  200,  50)   # green
COLOR_UNKNOWN  = (0,   0,   220)   # red
COLOR_DUPLICATE = (0,  200, 200)   # yellow

STATUS_SUCCESS   = "success"
STATUS_DUPLICATE = "already_marked"
STATUS_UNKNOWN   = "unknown"


class AttendanceEngine:
    """
    Processes a single video frame:
    1. Detects all faces
    2. Matches each against stored embeddings
    3. Marks attendance (SQLite + Excel) if not already marked today
    4. Returns annotated frame + per-face result list
    """

    def __init__(self):
        self._analyzer = FaceAnalyzer()
        self._db       = DatabaseManager()
        self._embeddings_cache: Optional[List[Tuple[str, np.ndarray]]] = None
        self._cache_date: Optional[str] = None
        self._marked_today: set = set()   # in-memory duplicate guard

    # ------------------------------------------------------------------ #
    # Cache management
    # ------------------------------------------------------------------ #

    def _get_embeddings(self) -> List[Tuple[str, np.ndarray]]:
        """
        Return cached embeddings, refreshing cache when:
        - First call
        - Cache is from a previous day (midnight rollover)
        """
        today = datetime.now().strftime("%Y-%m-%d")
        if self._embeddings_cache is None or self._cache_date != today:
            self._embeddings_cache = self._db.get_all_embeddings()
            self._cache_date = today
            self._marked_today = set()   # reset duplicate cache at midnight
            logger.info(
                f"Embedding cache refreshed: {len(self._embeddings_cache)} entries"
            )
        return self._embeddings_cache

    def refresh_cache(self) -> None:
        """Force cache refresh (call after registering a new user)."""
        self._embeddings_cache = None

    # ------------------------------------------------------------------ #
    # Main processing entry point
    # ------------------------------------------------------------------ #

    def process_frame(
        self, frame: np.ndarray
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        Process a BGR frame.
        Returns:
            annotated_frame: frame with bounding boxes drawn
            results: list of per-face dicts:
                {
                  status: 'success'|'already_marked'|'unknown',
                  user_info: Dict | None,
                  score: float,
                  bbox: [x1,y1,x2,y2]
                }
        """
        annotated = frame.copy()
        results: List[Dict] = []

        try:
            faces = self._analyzer.detect_faces(frame)
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return annotated, results

        stored = self._get_embeddings()

        for face in faces:
            bbox = face.bbox.astype(int).tolist() if face.bbox is not None else [0, 0, 0, 0]
            result = self._process_single_face(face, stored, annotated, bbox)
            results.append(result)
            annotated = result.pop("_frame")  # extract modified frame

        return annotated, results

    # ------------------------------------------------------------------ #
    # Per-face processing
    # ------------------------------------------------------------------ #

    def _process_single_face(
        self,
        face,
        stored: List[Tuple[str, np.ndarray]],
        frame: np.ndarray,
        bbox: List[int],
    ) -> Dict:
        embedding = self._analyzer.get_embedding(face)
        if embedding is None:
            self._analyzer.draw_box(frame, face, "No Embed", COLOR_UNKNOWN)
            return {"_frame": frame, "status": STATUS_UNKNOWN,
                    "user_info": None, "score": 0.0, "bbox": bbox}

        user_id, score = self._analyzer.find_best_match(embedding, stored)

        # ── Unknown face ────────────────────────────────────────────────
        if user_id is None:
            self._analyzer.draw_box(frame, face, "Unknown", COLOR_UNKNOWN, score)
            return {"_frame": frame, "status": STATUS_UNKNOWN,
                    "user_info": None, "score": score, "bbox": bbox}

        today = datetime.now().strftime("%Y-%m-%d")

        # ── Duplicate guard (in-memory + DB) ────────────────────────────
        if user_id in self._marked_today or self._db.is_attendance_marked(user_id, today):
            self._marked_today.add(user_id)
            user_info = self._db.get_user(user_id)
            name = user_info.get("name", user_id) if user_info else user_id
            self._analyzer.draw_box(
                frame, face, f"✓ {name} (Marked)", COLOR_DUPLICATE, score
            )
            return {"_frame": frame, "status": STATUS_DUPLICATE,
                    "user_info": user_info, "score": score, "bbox": bbox}

        # ── Mark attendance ─────────────────────────────────────────────
        user_info = self._db.get_user(user_id)
        if not user_info:
            self._analyzer.draw_box(frame, face, "DB Error", COLOR_UNKNOWN)
            return {"_frame": frame, "status": STATUS_UNKNOWN,
                    "user_info": None, "score": score, "bbox": bbox}

        now       = datetime.now()
        time_str  = now.strftime("%H:%M:%S")
        date_str  = now.strftime("%Y-%m-%d")
        image_path = self._save_snapshot(frame, face, user_id, date_str, time_str)

        success = self._db.mark_attendance(
            user_id     = user_id,
            name        = user_info["name"],
            role        = user_info["role"],
            course      = user_info.get("course", ""),
            department  = user_info.get("department", ""),
            time_str    = time_str,
            date_str    = date_str,
            image_path  = image_path,
        )

        if success:
            self._marked_today.add(user_id)
            append_to_excel(date_str, {
                "name":       user_info["name"],
                "user_id":    user_id,
                "course":     user_info.get("course", ""),
                "department": user_info.get("department", ""),
                "time":       time_str,
                "date":       date_str,
                "status":     "present",
                "image_path": image_path,
            }, user_info["role"])
            logger.info(f"Attendance marked: {user_id} ({user_info['name']}) [{score:.3f}]")

        self._analyzer.draw_box(
            frame, face, user_info["name"], COLOR_SUCCESS, score
        )
        return {
            "_frame":    frame,
            "status":    STATUS_SUCCESS,
            "user_info": user_info,
            "score":     score,
            "bbox":      bbox,
            "time":      time_str,
            "date":      date_str,
        }

    # ------------------------------------------------------------------ #
    # Snapshot saving
    # ------------------------------------------------------------------ #

    def _save_snapshot(
        self, frame: np.ndarray, face, user_id: str,
        date_str: str, time_str: str
    ) -> str:
        """Crop and save the face region as a JPEG snapshot."""
        try:
            os.makedirs(PHOTOS_DIR, exist_ok=True)
            safe_time = time_str.replace(":", "-")
            filename  = f"{user_id}_{date_str}_{safe_time}.jpg"
            path      = os.path.join(PHOTOS_DIR, filename)

            if face.bbox is not None:
                x1, y1, x2, y2 = face.bbox.astype(int)
                # Add 20px padding
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1 - 20), max(0, y1 - 20)
                x2, y2 = min(w, x2 + 20), min(h, y2 + 20)
                crop = frame[y1:y2, x1:x2]
            else:
                crop = frame

            cv2.imwrite(path, crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return path
        except Exception as e:
            logger.error(f"Snapshot save error: {e}")
            return ""
