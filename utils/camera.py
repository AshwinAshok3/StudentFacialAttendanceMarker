"""
CameraThread — thread-safe OpenCV camera capture with auto-reconnect.
Access the latest frame via get_frame() from any thread.
"""
import cv2
import threading
import time
import numpy as np
from typing import Optional
from utils.logger import logger


class CameraThread(threading.Thread):
    """
    Captures frames from the camera in a background thread.
    Provides thread-safe access to the latest frame.
    Supports auto-reconnect on camera disconnect.
    """

    RECONNECT_DELAY   = 2.0   # seconds between reconnect attempts
    TARGET_FPS        = 30
    FRAME_INTERVAL    = 1.0 / TARGET_FPS

    def __init__(self, camera_index: int = 0):
        super().__init__(daemon=True)
        self.camera_index = camera_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._running = False
        self._fps_actual = 0.0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        self._running = True
        self._stop_event.clear()
        super().start()
        logger.info(f"CameraThread started on index={self.camera_index}")

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False
        if self._cap and self._cap.isOpened():
            self._cap.release()
        logger.info("CameraThread stopped")

    def get_frame(self) -> Optional[np.ndarray]:
        """Return the latest captured frame (thread-safe copy)."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    @property
    def is_running(self) -> bool:
        return self._running and not self._stop_event.is_set()

    @property
    def fps(self) -> float:
        return self._fps_actual

    # ------------------------------------------------------------------ #
    # Internal capture loop
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        while not self._stop_event.is_set():
            if not self._open_camera():
                logger.warning(
                    f"Camera {self.camera_index} unavailable, retrying in "
                    f"{self.RECONNECT_DELAY}s"
                )
                time.sleep(self.RECONNECT_DELAY)
                continue

            self._capture_loop()

            # Camera disconnected — try to reconnect
            if not self._stop_event.is_set():
                logger.warning("Camera disconnected, attempting reconnect...")
                if self._cap:
                    self._cap.release()
                    self._cap = None

    def _open_camera(self) -> bool:
        """Open the camera and set resolution."""
        try:
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                # Try without CAP_DSHOW on non-Windows
                cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                return False
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, self.TARGET_FPS)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # minimal latency
            self._cap = cap
            logger.info("Camera opened successfully")
            return True
        except Exception as e:
            logger.error(f"Camera open error: {e}")
            return False

    def _capture_loop(self) -> None:
        """Inner frame-grab loop."""
        frame_count = 0
        t_start = time.monotonic()

        while not self._stop_event.is_set():
            t0 = time.monotonic()

            if self._cap is None or not self._cap.isOpened():
                return   # trigger reconnect

            ret, frame = self._cap.read()
            if not ret or frame is None:
                return   # trigger reconnect

            with self._lock:
                self._frame = frame

            # FPS throttle
            elapsed = time.monotonic() - t0
            sleep_time = self.FRAME_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Update FPS counter every 60 frames
            frame_count += 1
            if frame_count % 60 == 0:
                self._fps_actual = 60.0 / (time.monotonic() - t_start)
                t_start = time.monotonic()
