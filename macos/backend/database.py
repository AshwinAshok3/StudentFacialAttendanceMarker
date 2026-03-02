"""
database.py — SQLite database operations for the Facial Attendance System.

Schema v2: Adds roll_no, reg_no, year, course_opted (students)
           and employee_code, specialization, courses_teaching (staff).
Migration-safe: uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS pattern.
"""

import sqlite3
import json
import os
import numpy as np
from datetime import datetime, timedelta

from config import DB_PATH


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection():
    """Get a SQLite connection with row_factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema initialization + migration
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables and run migrations. Called once on startup."""
    conn = get_connection()
    cursor = conn.cursor()

    # Core tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            department      TEXT DEFAULT '',
            role            TEXT NOT NULL CHECK(role IN ('admin','staff','student')),
            password_hash   TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now')),

            -- Student fields
            roll_no         TEXT UNIQUE,
            reg_no          TEXT UNIQUE,
            year            TEXT DEFAULT '',
            course_opted    TEXT DEFAULT '',

            -- Staff fields
            employee_code   TEXT UNIQUE,
            specialization  TEXT DEFAULT '',
            courses_teaching TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS embeddings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            embedding   BLOB NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS courses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            department  TEXT DEFAULT '',
            total_hours INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            course_id   INTEGER,
            timestamp   TEXT DEFAULT (datetime('now')),
            status      TEXT DEFAULT 'present',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_attendance_user
            ON attendance(user_id);
        CREATE INDEX IF NOT EXISTS idx_attendance_timestamp
            ON attendance(timestamp);
        CREATE INDEX IF NOT EXISTS idx_embeddings_user
            ON embeddings(user_id);
    """)

    # Migration: add new columns to existing databases (safe no-op if already present)
    _run_migrations(conn)

    conn.commit()
    conn.close()


def _run_migrations(conn):
    """Add new columns to existing databases without breaking existing data."""
    migrations = [
        ("users", "roll_no",          "TEXT UNIQUE"),
        ("users", "reg_no",           "TEXT UNIQUE"),
        ("users", "year",             "TEXT DEFAULT ''"),
        ("users", "course_opted",     "TEXT DEFAULT ''"),
        ("users", "employee_code",    "TEXT UNIQUE"),
        ("users", "specialization",   "TEXT DEFAULT ''"),
        ("users", "courses_teaching", "TEXT DEFAULT ''"),
    ]
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    for table, col, col_def in migrations:
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # Column already exists in some DB versions


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def add_user(name, email, department, role, password_hash,
             roll_no=None, reg_no=None, year=None, course_opted=None,
             employee_code=None, specialization=None, courses_teaching=None):
    """Insert a new user with optional role-specific fields. Returns user id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO users
           (name, email, department, role, password_hash,
            roll_no, reg_no, year, course_opted,
            employee_code, specialization, courses_teaching)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, email, department, role, password_hash,
         roll_no, reg_no, year or '', course_opted or '',
         employee_code, specialization or '', courses_teaching or '')
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def get_user_by_email(email):
    """Fetch a single user by email. Returns dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_identifier(identifier, role):
    """
    Fetch a user by role-specific login identifier.
      student: matches roll_no OR reg_no
      staff:   matches employee_code
      admin:   matches email
    Returns dict or None.
    """
    identifier = identifier.strip()
    conn = get_connection()

    if role == "student":
        row = conn.execute(
            "SELECT * FROM users WHERE role='student' AND (roll_no=? OR reg_no=?)",
            (identifier, identifier)
        ).fetchone()
    elif role == "staff":
        row = conn.execute(
            "SELECT * FROM users WHERE role='staff' AND employee_code=?",
            (identifier,)
        ).fetchone()
    else:  # admin fallback: email
        row = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (identifier,)
        ).fetchone()

    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    """Fetch a single user by id. Returns dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_students():
    """Return list of all student users."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, email, department, roll_no, reg_no, year, course_opted, created_at "
        "FROM users WHERE role = 'student' ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_staff():
    """Return list of all staff users."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, email, department, employee_code, specialization, courses_teaching, created_at "
        "FROM users WHERE role = 'staff' ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def user_exists_by_email(email):
    """Check if a user with this email already exists."""
    conn = get_connection()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row is not None


def user_exists(email):
    """Alias for backwards compatibility."""
    return user_exists_by_email(email)


def identifier_exists(roll_no=None, reg_no=None, employee_code=None):
    """Check uniqueness of role-specific identifiers before registration."""
    conn = get_connection()
    if roll_no:
        if conn.execute("SELECT id FROM users WHERE roll_no=?", (roll_no,)).fetchone():
            conn.close()
            return True
    if reg_no:
        if conn.execute("SELECT id FROM users WHERE reg_no=?", (reg_no,)).fetchone():
            conn.close()
            return True
    if employee_code:
        if conn.execute("SELECT id FROM users WHERE employee_code=?", (employee_code,)).fetchone():
            conn.close()
            return True
    conn.close()
    return False


# ---------------------------------------------------------------------------
# Embedding operations
# ---------------------------------------------------------------------------

def store_embedding(user_id, embedding_array):
    """
    Store a numpy embedding as BLOB.
    embedding_array: numpy array of shape (512,)
    """
    conn = get_connection()
    blob = embedding_array.astype(np.float32).tobytes()
    conn.execute(
        "INSERT INTO embeddings (user_id, embedding) VALUES (?, ?)",
        (user_id, blob)
    )
    conn.commit()
    conn.close()


def get_all_embeddings():
    """
    Load all embeddings from DB.
    Returns list of dicts: [{user_id, embedding (np.array)}, ...]
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id, embedding FROM embeddings"
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        emb = np.frombuffer(row["embedding"], dtype=np.float32)
        results.append({"user_id": row["user_id"], "embedding": emb})
    return results


# ---------------------------------------------------------------------------
# Attendance operations
# ---------------------------------------------------------------------------

def mark_attendance(user_id, course_id=None):
    """
    Mark attendance for a user right now.
    P1 FIX: Prevents duplicate marking within 2.5 hours (9000 seconds).
    Returns True if marked, False if already marked within the cooldown window.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 2.5 hours = 150 minutes = 9000 seconds
    cooldown_ago = (datetime.now() - timedelta(hours=2, minutes=30)).isoformat()
    existing = cursor.execute(
        "SELECT id FROM attendance WHERE user_id = ? AND timestamp > ?",
        (user_id, cooldown_ago)
    ).fetchone()

    if existing:
        conn.close()
        return False

    cursor.execute(
        "INSERT INTO attendance (user_id, course_id) VALUES (?, ?)",
        (user_id, course_id)
    )
    conn.commit()
    conn.close()
    return True


def get_last_attendance_time(user_id):
    """Return the ISO timestamp of the most recent attendance record, or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT timestamp FROM attendance WHERE user_id=? ORDER BY timestamp DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    return row["timestamp"] if row else None


def delete_user(user_id):
    """
    Delete a user and cascade-delete their embeddings and attendance records.
    Schema has ON DELETE CASCADE, so a single DELETE on users is sufficient.
    Returns True if deleted, False if user not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_attendance(user_id, start_date=None, end_date=None):
    """Get attendance records for a user within an optional date range."""
    conn = get_connection()
    query = "SELECT * FROM attendance WHERE user_id = ?"
    params = [user_id]

    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)

    query += " ORDER BY timestamp DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attendance_stats(user_id):
    """
    Calculate attendance statistics for a user.
    Returns dict: {total_days, present_days, percentage, total_hours}
    """
    conn = get_connection()

    present = conn.execute(
        "SELECT COUNT(DISTINCT date(timestamp)) as days "
        "FROM attendance WHERE user_id = ? AND status = 'present'",
        (user_id,)
    ).fetchone()
    present_days = present["days"] if present else 0

    total_records = conn.execute(
        "SELECT COUNT(*) as cnt FROM attendance WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    total_hours = total_records["cnt"] if total_records else 0

    user = conn.execute(
        "SELECT created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    total_days = 1
    if user and user["created_at"]:
        try:
            reg_date = datetime.fromisoformat(user["created_at"])
            delta = (datetime.now() - reg_date).days + 1
            total_days = max(1, int(delta * 5 / 7))
        except (ValueError, TypeError):
            total_days = 1

    percentage = round((present_days / total_days) * 100, 1) if total_days > 0 else 0
    percentage = min(percentage, 100.0)

    conn.close()
    return {
        "total_days":   total_days,
        "present_days": present_days,
        "percentage":   percentage,
        "total_hours":  total_hours,
    }


def get_weekly_attendance(user_id):
    """Get attendance count per day for the last 7 days."""
    conn = get_connection()
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

    rows = conn.execute(
        "SELECT date(timestamp) as dt, COUNT(*) as cnt "
        "FROM attendance WHERE user_id = ? AND timestamp >= ? "
        "GROUP BY date(timestamp) ORDER BY dt",
        (user_id, seven_days_ago)
    ).fetchall()

    conn.close()
    return [{"date": r["dt"], "count": r["cnt"]} for r in rows]


def get_students_attendance_today():
    """
    Return all students who have attendance marked today.
    Used by staff dashboard.
    """
    conn = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT u.id, u.name, u.department, u.roll_no, u.year, u.course_opted,
                  MIN(a.timestamp) as first_seen
           FROM attendance a
           JOIN users u ON u.id = a.user_id
           WHERE u.role = 'student' AND date(a.timestamp) = ?
           GROUP BY u.id
           ORDER BY first_seen DESC""",
        (today,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attendance_by_date(date_str):
    """
    Return attendance summary for a specific date (YYYY-MM-DD).
    Used by staff dashboard date filter.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT u.id, u.name, u.department, u.roll_no, u.year, u.course_opted,
                  MIN(a.timestamp) as time_in, COUNT(a.id) as sessions
           FROM attendance a
           JOIN users u ON u.id = a.user_id
           WHERE u.role = 'student' AND date(a.timestamp) = ?
           GROUP BY u.id
           ORDER BY u.name""",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Course operations
# ---------------------------------------------------------------------------

def add_course(code, name, department="", total_hours=0):
    """Create a new course. Returns course id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO courses (code, name, department, total_hours) VALUES (?, ?, ?, ?)",
        (code, name, department, total_hours)
    )
    course_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return course_id


def get_all_courses():
    """Return all courses."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM courses ORDER BY code").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seed_default_courses():
    """Insert default courses if table is empty."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) as cnt FROM courses").fetchone()["cnt"]
    conn.close()

    if count == 0:
        add_course("CS101", "Introduction to Computer Science", "CS", 40)
        add_course("CS201", "Data Structures & Algorithms", "CS", 45)
        add_course("CS301", "Machine Learning Fundamentals", "CS", 50)
        add_course("CS401", "Computer Vision", "CS", 40)
