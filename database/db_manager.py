"""
StudentFacialAttendanceMarker
DatabaseManager — single interface for main.db and admin.db
"""
import sqlite3
import os
import numpy as np
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "database")
MAIN_DB = os.path.join(DB_DIR, "main.db")
ADMIN_DB = os.path.join(DB_DIR, "admin.db")

MAIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT    NOT NULL,
    user_id           TEXT    UNIQUE NOT NULL,
    role              TEXT    NOT NULL CHECK(role IN ('student', 'staff')),
    course            TEXT,
    department        TEXT,
    photo_path        TEXT,
    created_at        TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS embeddings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL,
    embedding   BLOB    NOT NULL,
    angle       TEXT    DEFAULT 'front',
    created_at  TEXT    DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    course      TEXT,
    department  TEXT,
    time        TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    status      TEXT    DEFAULT 'present' CHECK(status IN ('present','late','absent')),
    image_path  TEXT,
    UNIQUE(user_id, date)
);

CREATE TABLE IF NOT EXISTS system_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    level       TEXT    NOT NULL CHECK(level IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
    message     TEXT    NOT NULL,
    timestamp   TEXT    DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_attendance_date   ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_attendance_userid ON attendance(user_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_userid ON embeddings(user_id);
"""

ADMIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS admins (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    username              TEXT    UNIQUE NOT NULL,
    password_hash         TEXT    NOT NULL,
    salt                  TEXT    NOT NULL,
    must_change_password  INTEGER DEFAULT 1,
    created_at            TEXT    DEFAULT (datetime('now','localtime'))
);
"""

STAFF_AUTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff_credentials (
    user_id       TEXT    PRIMARY KEY,
    password_hash TEXT    NOT NULL,
    salt          TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""


class DatabaseManager:
    """Thread-safe SQLite manager for main.db and admin.db."""

    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.main_db_path = MAIN_DB
        self.admin_db_path = ADMIN_DB

    # ------------------------------------------------------------------ #
    # Connection helpers
    # ------------------------------------------------------------------ #

    @contextmanager
    def _main_conn(self):
        conn = sqlite3.connect(self.main_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _admin_conn(self):
        conn = sqlite3.connect(self.admin_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def initialize(self) -> None:
        """Create all tables and seed default admin if absent."""
        with self._main_conn() as conn:
            conn.executescript(MAIN_SCHEMA)
            conn.executescript(STAFF_AUTH_SCHEMA)

        with self._admin_conn() as conn:
            conn.executescript(ADMIN_SCHEMA)
            # Seed default admin: root / passwd
            row = conn.execute(
                "SELECT id FROM admins WHERE username = 'root'"
            ).fetchone()
            if not row:
                from auth.auth_manager import AuthManager
                am = AuthManager()
                h, s = am.hash_password("passwd")
                conn.execute(
                    "INSERT INTO admins(username, password_hash, salt, must_change_password) VALUES(?,?,?,1)",
                    ("root", h, s),
                )

    # ------------------------------------------------------------------ #
    # User CRUD
    # ------------------------------------------------------------------ #

    def add_user(self, name: str, user_id: str, role: str,
                 course: str = "", department: str = "",
                 photo_path: str = "") -> bool:
        try:
            with self._main_conn() as conn:
                conn.execute(
                    """INSERT INTO users(name, user_id, role, course, department, photo_path)
                       VALUES(?,?,?,?,?,?)""",
                    (name, user_id, role, course, department, photo_path),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user(self, user_id: str) -> Optional[Dict]:
        with self._main_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all_users(self, role: Optional[str] = None) -> List[Dict]:
        with self._main_conn() as conn:
            if role:
                rows = conn.execute(
                    "SELECT * FROM users WHERE role = ? ORDER BY name", (role,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM users ORDER BY role, name"
                ).fetchall()
        return [dict(r) for r in rows]

    def update_user(self, user_id: str, **kwargs) -> bool:
        allowed = {"name", "course", "department", "photo_path"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [user_id]
        with self._main_conn() as conn:
            conn.execute(
                f"UPDATE users SET {set_clause} WHERE user_id=?", values
            )
        return True

    def delete_user(self, user_id: str) -> bool:
        with self._main_conn() as conn:
            conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        return True

    # ------------------------------------------------------------------ #
    # Embedding CRUD
    # ------------------------------------------------------------------ #

    def add_embedding(self, user_id: str, embedding: np.ndarray,
                      angle: str = "front") -> bool:
        blob = embedding.astype(np.float32).tobytes()
        try:
            with self._main_conn() as conn:
                conn.execute(
                    "INSERT INTO embeddings(user_id, embedding, angle) VALUES(?,?,?)",
                    (user_id, blob, angle),
                )
            return True
        except Exception:
            return False

    def get_all_embeddings(self) -> List[Tuple[str, np.ndarray]]:
        """Return list of (user_id, embedding_array) for matcher."""
        with self._main_conn() as conn:
            rows = conn.execute(
                "SELECT user_id, embedding FROM embeddings"
            ).fetchall()
        result = []
        for row in rows:
            arr = np.frombuffer(row["embedding"], dtype=np.float32).copy()
            result.append((row["user_id"], arr))
        return result

    def delete_embeddings(self, user_id: str) -> bool:
        with self._main_conn() as conn:
            conn.execute("DELETE FROM embeddings WHERE user_id=?", (user_id,))
        return True

    # ------------------------------------------------------------------ #
    # Attendance CRUD
    # ------------------------------------------------------------------ #

    def mark_attendance(self, user_id: str, name: str, role: str,
                        course: str, department: str, time_str: str,
                        date_str: str, status: str = "present",
                        image_path: str = "") -> bool:
        """Returns True if newly marked, False if already exists (duplicate)."""
        try:
            with self._main_conn() as conn:
                conn.execute(
                    """INSERT INTO attendance
                       (user_id, name, role, course, department, time, date, status, image_path)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (user_id, name, role, course, department,
                     time_str, date_str, status, image_path),
                )
            return True
        except sqlite3.IntegrityError:
            return False  # duplicate

    def is_attendance_marked(self, user_id: str, date_str: str) -> bool:
        with self._main_conn() as conn:
            row = conn.execute(
                "SELECT id FROM attendance WHERE user_id=? AND date=?",
                (user_id, date_str),
            ).fetchone()
        return row is not None

    def get_attendance_by_date(self, date_str: str,
                               role: Optional[str] = None) -> List[Dict]:
        with self._main_conn() as conn:
            if role:
                rows = conn.execute(
                    "SELECT * FROM attendance WHERE date=? AND role=? ORDER BY time",
                    (date_str, role),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM attendance WHERE date=? ORDER BY role, time",
                    (date_str,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_attendance_by_user(self, user_id: str) -> List[Dict]:
        with self._main_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM attendance WHERE user_id=? ORDER BY date DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_attendance_status(self, user_id: str, date_str: str,
                                 new_status: str) -> bool:
        with self._main_conn() as conn:
            conn.execute(
                "UPDATE attendance SET status=? WHERE user_id=? AND date=?",
                (new_status, user_id, date_str),
            )
        return True

    def delete_attendance(self, attendance_id: int) -> bool:
        with self._main_conn() as conn:
            conn.execute("DELETE FROM attendance WHERE id=?", (attendance_id,))
        return True

    def get_all_attendance(self) -> List[Dict]:
        with self._main_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM attendance ORDER BY date DESC, time DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Staff credentials
    # ------------------------------------------------------------------ #

    def set_staff_credentials(self, user_id: str, password_hash: str,
                              salt: str) -> bool:
        try:
            with self._main_conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO staff_credentials(user_id, password_hash, salt)
                       VALUES(?,?,?)""",
                    (user_id, password_hash, salt),
                )
            return True
        except Exception:
            return False

    def get_staff_credentials(self, user_id: str) -> Optional[Dict]:
        with self._main_conn() as conn:
            row = conn.execute(
                "SELECT * FROM staff_credentials WHERE user_id=?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ #
    # Admin credentials
    # ------------------------------------------------------------------ #

    def get_admin(self, username: str) -> Optional[Dict]:
        with self._admin_conn() as conn:
            row = conn.execute(
                "SELECT * FROM admins WHERE username=?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def update_admin_password(self, username: str, password_hash: str,
                              salt: str) -> bool:
        with self._admin_conn() as conn:
            conn.execute(
                """UPDATE admins SET password_hash=?, salt=?, must_change_password=0
                   WHERE username=?""",
                (password_hash, salt, username),
            )
        return True

    def add_admin(self, username: str, password_hash: str, salt: str) -> bool:
        try:
            with self._admin_conn() as conn:
                conn.execute(
                    """INSERT INTO admins(username, password_hash, salt, must_change_password)
                       VALUES(?,?,?,0)""",
                    (username, password_hash, salt),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def list_admins(self) -> List[Dict]:
        with self._admin_conn() as conn:
            rows = conn.execute(
                "SELECT id, username, must_change_password, created_at FROM admins"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_admin(self, username: str) -> bool:
        if username == "root":
            return False  # protect root
        with self._admin_conn() as conn:
            conn.execute("DELETE FROM admins WHERE username=?", (username,))
        return True

    # ------------------------------------------------------------------ #
    # System Logs
    # ------------------------------------------------------------------ #

    def add_log(self, level: str, message: str) -> None:
        try:
            with self._main_conn() as conn:
                conn.execute(
                    "INSERT INTO system_logs(level, message) VALUES(?,?)",
                    (level, message),
                )
        except Exception:
            pass  # never let logging crash the app

    def get_logs(self, limit: int = 500) -> List[Dict]:
        with self._main_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_old_logs(self, keep_days: int = 30) -> None:
        with self._main_conn() as conn:
            conn.execute(
                """DELETE FROM system_logs
                   WHERE timestamp < datetime('now', ?, 'localtime')""",
                (f"-{keep_days} days",),
            )
