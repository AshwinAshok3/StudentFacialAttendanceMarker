"""
database.py — SQLite database operations for the Facial Attendance System.

All functions are def-based. No classes. No ORM.
Handles: users, embeddings, attendance, courses.
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
# Schema initialization
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables if they don't exist. Called once on startup."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            department  TEXT DEFAULT '',
            role        TEXT NOT NULL CHECK(role IN ('admin','staff','student')),
            password_hash TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
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

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def add_user(name, email, department, role, password_hash):
    """Insert a new user. Returns user id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, department, role, password_hash) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, email, department, role, password_hash)
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
        "SELECT id, name, email, department, created_at "
        "FROM users WHERE role = 'student' ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def user_exists(email):
    """Check if a user with this email already exists."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row is not None


# ---------------------------------------------------------------------------
# Embedding operations
# ---------------------------------------------------------------------------

def store_embedding(user_id, embedding_array):
    """
    Store a numpy embedding as a BLOB.
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
    Prevents duplicate marking within the same hour.
    Returns True if marked, False if already marked.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Check if already marked within last hour
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    existing = cursor.execute(
        "SELECT id FROM attendance "
        "WHERE user_id = ? AND timestamp > ?",
        (user_id, one_hour_ago)
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


def get_attendance(user_id, start_date=None, end_date=None):
    """
    Get attendance records for a user within an optional date range.
    Returns list of dicts with timestamp and status.
    """
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

    # Count distinct days present
    present = conn.execute(
        "SELECT COUNT(DISTINCT date(timestamp)) as days "
        "FROM attendance WHERE user_id = ? AND status = 'present'",
        (user_id,)
    ).fetchone()

    present_days = present["days"] if present else 0

    # Count total records (each record ≈ 1 hour session)
    total_records = conn.execute(
        "SELECT COUNT(*) as cnt FROM attendance WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    total_hours = total_records["cnt"] if total_records else 0

    # Calculate percentage based on working days since registration
    user = conn.execute(
        "SELECT created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    total_days = 1
    if user and user["created_at"]:
        try:
            reg_date = datetime.fromisoformat(user["created_at"])
            delta = (datetime.now() - reg_date).days + 1
            # Exclude weekends (rough estimate)
            total_days = max(1, int(delta * 5 / 7))
        except (ValueError, TypeError):
            total_days = 1

    percentage = round((present_days / total_days) * 100, 1) if total_days > 0 else 0
    percentage = min(percentage, 100.0)

    conn.close()
    return {
        "total_days": total_days,
        "present_days": present_days,
        "percentage": percentage,
        "total_hours": total_hours,
    }


def get_weekly_attendance(user_id):
    """
    Get attendance count per day for the last 7 days.
    Returns list of {date, count} dicts.
    """
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


# ---------------------------------------------------------------------------
# Course operations
# ---------------------------------------------------------------------------

def add_course(code, name, department="", total_hours=0):
    """Create a new course. Returns course id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO courses (code, name, department, total_hours) "
        "VALUES (?, ?, ?, ?)",
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
    """Insert some default courses if table is empty."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) as cnt FROM courses").fetchone()["cnt"]
    conn.close()

    if count == 0:
        add_course("CS101", "Introduction to Computer Science", "CS", 40)
        add_course("CS201", "Data Structures & Algorithms", "CS", 45)
        add_course("CS301", "Machine Learning Fundamentals", "CS", 50)
        add_course("CS401", "Computer Vision", "CS", 40)
