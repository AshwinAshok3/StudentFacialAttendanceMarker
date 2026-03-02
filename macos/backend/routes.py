"""
routes.py — Flask REST API routes for the Facial Attendance System.

v2: Identifier-based login (roll_no/reg_no/employee_code),
    separate student/staff register endpoints,
    unauthenticated kiosk recognize endpoint,
    staff dashboard endpoint.
"""

from flask import Blueprint, request, jsonify

from auth import (
    hash_password, verify_password,
    create_session_token, require_auth, require_role
)
from database import (
    add_user, get_user_by_email, get_user_by_id, get_user_by_identifier,
    get_all_students, get_all_staff,
    user_exists, user_exists_by_email, identifier_exists,
    store_embedding, get_all_embeddings,
    mark_attendance, get_attendance, get_attendance_stats,
    get_weekly_attendance, get_all_courses,
    get_students_attendance_today, get_attendance_by_date,
    get_last_attendance_time, delete_user as db_delete_user,
)
from recognition import (
    detect_faces, recognize_face, extract_registration_embeddings,
    handle_multi_face, is_model_ready
)
from utils import (
    decode_base64_image, validate_frame_size, get_system_info
)

api = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Auth — Login (identifier-based: roll_no / reg_no / employee_code / email)
# ---------------------------------------------------------------------------

@api.route("/auth/login", methods=["POST"])
def login():
    """
    Authenticate a user by role-specific identifier.
    Body: {identifier, password, role}
      role=student  → identifier matched against roll_no or reg_no
      role=staff    → identifier matched against employee_code
      role=admin    → identifier matched against email
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    identifier = data.get("identifier", "").strip()
    password   = data.get("password", "")
    role       = data.get("role", "student").strip().lower()

    if not identifier or not password:
        return jsonify({"error": "Identifier and password are required"}), 400

    if role not in ("student", "staff", "admin"):
        return jsonify({"error": "role must be student, staff, or admin"}), 400

    user = get_user_by_identifier(identifier, role)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    if not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_session_token(user["id"], user["role"])
    return jsonify({
        "token": token,
        "user": _user_payload(user),
    })


# ---------------------------------------------------------------------------
# Auth — Register Student
# ---------------------------------------------------------------------------

@api.route("/auth/register/student", methods=["POST"])
def register_student():
    """
    Register a new student with face embeddings.
    Body: {name, email, roll_no, reg_no, department, year, course_opted,
           password, frames: [base64, ...]}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    name         = data.get("name", "").strip()
    email        = data.get("email", "").strip().lower()
    roll_no      = data.get("roll_no", "").strip()
    reg_no       = data.get("reg_no", "").strip()
    department   = data.get("department", "").strip()
    year         = data.get("year", "").strip()
    course_opted = data.get("course_opted", "").strip()
    password     = data.get("password", "")
    frames_b64   = data.get("frames", [])

    # Required field validation
    if not all([name, email, roll_no, reg_no, password]):
        return jsonify({"error": "name, email, roll_no, reg_no and password are required"}), 400

    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400

    if user_exists_by_email(email):
        return jsonify({"error": "Email already registered"}), 409

    if identifier_exists(roll_no=roll_no, reg_no=reg_no):
        return jsonify({"error": "Roll number or registration number already in use"}), 409

    if not frames_b64 or len(frames_b64) < 3:
        return jsonify({"error": "At least 3 face frames required for registration"}), 400

    # Decode and validate frames
    frames = _decode_frames(frames_b64)
    if isinstance(frames, tuple):  # error response
        return frames

    # Extract face embedding
    result = extract_registration_embeddings(frames)
    if not result["success"]:
        return jsonify({"error": result["message"]}), 400

    pw_hash = hash_password(password)
    user_id = add_user(
        name, email, department, "student", pw_hash,
        roll_no=roll_no, reg_no=reg_no, year=year, course_opted=course_opted
    )
    store_embedding(user_id, result["embedding"])

    # P2: Immediately self-verify the embedding was stored and is recognizable
    fresh_stored = get_all_embeddings()
    verified = False
    try:
        test_match = recognize_face(result["embedding"], fresh_stored)
        verified = (test_match is not None and test_match["user_id"] == user_id)
    except Exception as ve:
        print(f"[Register/Student] Self-verify error: {ve}")

    if not verified:
        print(f"[Register/Student] WARNING: self-verify failed for user_id={user_id}")

    token = create_session_token(user_id, "student")
    user  = get_user_by_id(user_id)

    return jsonify({
        "message":        "Student registered successfully",
        "token":          token,
        "user":           _user_payload(user),
        "embedding_stored": True,
        "face_count":     result.get("face_count", 1),
        "frames_used":    len(frames_b64),
        "verified":       verified,
    }), 201


# ---------------------------------------------------------------------------
# Auth — Register Staff
# ---------------------------------------------------------------------------

@api.route("/auth/register/staff", methods=["POST"])
def register_staff():
    """
    Register a new staff member with face embeddings.
    Body: {name, email, employee_code, department, specialization,
           courses_teaching, password, frames: [base64, ...]}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    name             = data.get("name", "").strip()
    email            = data.get("email", "").strip().lower()
    employee_code    = data.get("employee_code", "").strip()
    department       = data.get("department", "").strip()
    specialization   = data.get("specialization", "").strip()
    courses_teaching = data.get("courses_teaching", "").strip()
    password         = data.get("password", "")
    frames_b64       = data.get("frames", [])

    if not all([name, email, employee_code, password]):
        return jsonify({"error": "name, email, employee_code and password are required"}), 400

    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400

    if user_exists_by_email(email):
        return jsonify({"error": "Email already registered"}), 409

    if identifier_exists(employee_code=employee_code):
        return jsonify({"error": "Employee code already in use"}), 409

    if not frames_b64 or len(frames_b64) < 3:
        return jsonify({"error": "At least 3 face frames required for registration"}), 400

    frames = _decode_frames(frames_b64)
    if isinstance(frames, tuple):
        return frames

    result = extract_registration_embeddings(frames)
    if not result["success"]:
        return jsonify({"error": result["message"]}), 400

    pw_hash = hash_password(password)
    user_id = add_user(
        name, email, department, "staff", pw_hash,
        employee_code=employee_code, specialization=specialization,
        courses_teaching=courses_teaching
    )
    store_embedding(user_id, result["embedding"])

    # P2: Immediately self-verify the embedding was stored and is recognizable
    fresh_stored = get_all_embeddings()
    verified = False
    try:
        test_match = recognize_face(result["embedding"], fresh_stored)
        verified = (test_match is not None and test_match["user_id"] == user_id)
    except Exception as ve:
        print(f"[Register/Staff] Self-verify error: {ve}")

    if not verified:
        print(f"[Register/Staff] WARNING: self-verify failed for user_id={user_id}, "
              f"stored_count={len(fresh_stored)}")

    token = create_session_token(user_id, "staff")
    user  = get_user_by_id(user_id)

    return jsonify({
        "message":          "Staff registered successfully",
        "token":            token,
        "user":             _user_payload(user),
        "embedding_stored": True,
        "face_count":       result.get("face_count", 1),
        "frames_used":      len(frames_b64),
        "verified":         verified,
    }), 201


# ---------------------------------------------------------------------------
# Kiosk Recognition (no auth — runs on landing page before login)
# ---------------------------------------------------------------------------

@api.route("/recognize/kiosk", methods=["POST"])
def kiosk_recognize():
    """
    Continuous kiosk recognition. No auth required.
    Receives a base64 frame, detects all faces, recognizes, auto-marks attendance.

    Returns:
      known:         [{user_id, name, similarity, bbox, attendance_marked}]
      unknown_count: int
      message:       string describing the result
    """
    data = request.get_json(silent=True)
    if not data or "frame" not in data:
        return jsonify({"error": "Frame required"}), 400

    ok, msg = validate_frame_size(data["frame"])
    if not ok:
        return jsonify({"error": msg}), 400

    image = decode_base64_image(data["frame"])
    if image is None:
        return jsonify({"error": "Could not decode frame"}), 400

    faces = detect_faces(image)
    if not faces:
        return jsonify({"known": [], "unknown_count": 0, "message": "no_face"})

    stored = get_all_embeddings()
    if not stored:
        return jsonify({
            "known":         [],
            "unknown_count": len(faces),
            "message":       "no_registered_faces",
        })

    known   = []
    unknown = 0

    for face in faces:
        match = recognize_face(face["embedding"], stored)
        if match:
            user    = get_user_by_id(match["user_id"])
            marked  = mark_attendance(match["user_id"])
            last_ts = get_last_attendance_time(match["user_id"])
            known.append({
                "user_id":           match["user_id"],
                "name":              user["name"] if user else "Unknown",
                "role":              user["role"] if user else "student",
                "similarity":        round(match["similarity"], 3),
                "bbox":              face["bbox"],
                "attendance_marked": marked,
                "last_marked_at":    last_ts,  # P1: for frontend cooldown info
            })
        else:
            unknown += 1

    # Determine message
    if len(faces) > 1 and unknown == len(faces):
        message = "multi_unknown"
    elif unknown > 0 and known:
        message = "mixed"
    elif unknown > 0:
        message = "unknown"
    else:
        message = "recognized"

    return jsonify({
        "known":         known,
        "unknown_count": unknown,
        "message":       message,
    })


# ---------------------------------------------------------------------------
# Authenticated recognize (for post-login pages)
# ---------------------------------------------------------------------------

@api.route("/recognize", methods=["POST"])
@require_auth
def recognize():
    """Standard authenticated recognition endpoint."""
    data = request.get_json(silent=True)
    if not data or "frame" not in data:
        return jsonify({"error": "Frame data required"}), 400

    ok, msg = validate_frame_size(data["frame"])
    if not ok:
        return jsonify({"error": msg}), 400

    image = decode_base64_image(data["frame"])
    if image is None:
        return jsonify({"error": "Could not decode frame"}), 400

    faces  = detect_faces(image)
    if not faces:
        return jsonify({"faces": [], "message": "No faces detected"})

    stored = get_all_embeddings()
    if not stored:
        return jsonify({
            "faces":   [{"bbox": f["bbox"]} for f in faces],
            "message": "No registered faces in database",
        })

    if len(faces) == 1:
        match = recognize_face(faces[0]["embedding"], stored)
        if match:
            user = get_user_by_id(match["user_id"])
            return jsonify({"faces": [{
                "bbox":       faces[0]["bbox"],
                "matched":    True,
                "user_id":    match["user_id"],
                "name":       user["name"] if user else "Unknown",
                "similarity": match["similarity"],
            }], "message": "Face recognized"})
        return jsonify({"faces": [{"bbox": faces[0]["bbox"], "matched": False}],
                        "message": "Face not recognized"})

    result = handle_multi_face(faces, stored)
    if result["error"]:
        return jsonify({"faces": [], "error": result["error"],
                        "unknown_count": result["unknown_count"]}), 400

    face_results = []
    for rec in result["recognized"]:
        user = get_user_by_id(rec["user_id"])
        face_results.append({
            "bbox":       rec["bbox"],
            "matched":    True,
            "user_id":    rec["user_id"],
            "name":       user["name"] if user else "Unknown",
            "similarity": rec["similarity"],
        })

    return jsonify({
        "faces":         face_results,
        "unknown_count": result["unknown_count"],
        "message":       f"{len(face_results)} face(s) recognized",
    })


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

@api.route("/attendance/mark", methods=["POST"])
@require_auth
def mark_attendance_route():
    """Mark attendance for a student."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    user_id   = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    marked = mark_attendance(user_id, course_id)
    if marked:
        return jsonify({
            "message": f"Attendance marked for {user['name']}",
            "stats":   get_attendance_stats(user_id),
        })
    return jsonify({"message": "Attendance already marked within the last 2.5 hours"})


@api.route("/attendance/<int:user_id>", methods=["GET"])
@require_auth
def get_attendance_route(user_id):
    """Get attendance records for a student."""
    start = request.args.get("start")
    end   = request.args.get("end")
    return jsonify({"records": get_attendance(user_id, start, end)})


# ---------------------------------------------------------------------------
# Student Dashboard
# ---------------------------------------------------------------------------

@api.route("/dashboard/<int:user_id>", methods=["GET"])
@require_auth
def dashboard(user_id):
    """Get full dashboard data for a student."""
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    stats  = get_attendance_stats(user_id)
    weekly = get_weekly_attendance(user_id)
    recent = get_attendance(user_id)[:10]

    return jsonify({
        "user": {
            "id":           user["id"],
            "name":         user["name"],
            "email":        user["email"],
            "department":   user["department"],
            "roll_no":      user.get("roll_no", ""),
            "reg_no":       user.get("reg_no", ""),
            "year":         user.get("year", ""),
            "course_opted": user.get("course_opted", ""),
        },
        "stats":   stats,
        "weekly":  weekly,
        "recent":  recent,
        "courses": get_all_courses(),
    })


# ---------------------------------------------------------------------------
# Staff Dashboard
# ---------------------------------------------------------------------------

@api.route("/dashboard/staff/<int:user_id>", methods=["GET"])
@require_auth
def staff_dashboard(user_id):
    """Get dashboard data for a staff member."""
    user = get_user_by_id(user_id)
    if not user or user["role"] not in ("staff", "admin"):
        return jsonify({"error": "Staff user not found"}), 404

    date_filter = request.args.get("date")  # YYYY-MM-DD, optional

    if date_filter:
        students_present = get_attendance_by_date(date_filter)
    else:
        students_present = get_students_attendance_today()

    all_students = get_all_students()

    # Attach attendance stats to each student
    for s in all_students:
        s["stats"] = get_attendance_stats(s["id"])

    return jsonify({
        "user": {
            "id":               user["id"],
            "name":             user["name"],
            "email":            user["email"],
            "department":       user["department"],
            "employee_code":    user.get("employee_code", ""),
            "specialization":   user.get("specialization", ""),
            "courses_teaching": user.get("courses_teaching", ""),
        },
        "students_present_today": len(students_present),
        "attendance_list":        students_present,
        "all_students":           all_students,
        "date_filter":            date_filter or "",
    })


# ---------------------------------------------------------------------------
# Admin / utility
# ---------------------------------------------------------------------------

@api.route("/students", methods=["GET"])
@require_auth
def list_students():
    """List all students with attendance stats."""
    students = get_all_students()
    for s in students:
        s["stats"] = get_attendance_stats(s["id"])
    return jsonify({"students": students})


@api.route("/system/info", methods=["GET"])
def system_info():
    """Return system information."""
    info = get_system_info()
    info["model_ready"] = is_model_ready()
    return jsonify(info)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _decode_frames(frames_b64):
    """Decode and validate a list of base64 frames. Returns list or error tuple."""
    frames = []
    for i, fb64 in enumerate(frames_b64):
        ok, msg = validate_frame_size(fb64)
        if not ok:
            return jsonify({"error": f"Frame {i+1}: {msg}"}), 400
        img = decode_base64_image(fb64)
        if img is None:
            return jsonify({"error": f"Frame {i+1}: could not decode image"}), 400
        frames.append(img)
    return frames


def _user_payload(user):
    """Build a consistent user dict for auth responses."""
    if not user:
        return {}
    return {
        "id":               user["id"],
        "name":             user["name"],
        "email":            user["email"],
        "role":             user["role"],
        "department":       user.get("department", ""),
        "roll_no":          user.get("roll_no", ""),
        "reg_no":           user.get("reg_no", ""),
        "year":             user.get("year", ""),
        "course_opted":     user.get("course_opted", ""),
        "employee_code":    user.get("employee_code", ""),
        "specialization":   user.get("specialization", ""),
        "courses_teaching": user.get("courses_teaching", ""),
    }


# ---------------------------------------------------------------------------
# Health check — P4: model loading lifecycle
# ---------------------------------------------------------------------------

@api.route("/health", methods=["GET"])
def health():
    """
    Lightweight readiness probe polled by the frontend loading screen.
    Returns {ready: bool, model_ready: bool, status: str}
    No auth required — called before login.
    """
    model_ready = is_model_ready()
    return jsonify({
        "ready":       model_ready,
        "model_ready": model_ready,
        "status":      "ready" if model_ready else "loading",
        "message":     "Face recognition engine ready" if model_ready
                       else "Loading AI model — please wait…",
    })


# ---------------------------------------------------------------------------
# Admin — user management (P1)
# ---------------------------------------------------------------------------

@api.route("/admin/users", methods=["GET"])
@require_auth
def admin_list_users():
    """
    List all users (students + staff).
    Query params: role=student|staff|all (default: all)
    """
    from database import get_connection
    role = request.args.get("role", "all")
    conn = get_connection()
    if role in ("student", "staff"):
        rows = conn.execute(
            "SELECT * FROM users WHERE role=? ORDER BY name", (role,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM users WHERE role != 'admin' ORDER BY role, name"
        ).fetchall()
    conn.close()

    users = [dict(r) for r in rows]
    # Attach attendance stats for students
    for u in users:
        u.pop("password_hash", None)   # Never expose hash
        if u["role"] == "student":
            u["stats"] = get_attendance_stats(u["id"])

    return jsonify({"users": users, "count": len(users)})


@api.route("/admin/users/<int:user_id>/delete", methods=["DELETE"])
@require_auth
def admin_delete_user(user_id):
    """Permanently delete a user and their embeddings/attendance (CASCADE)."""
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user["role"] == "admin":
        return jsonify({"error": "Cannot delete admin account"}), 403

    # Use the proper db_delete_user helper (handles CASCADE internally)
    success = db_delete_user(user_id)
    if success:
        return jsonify({"message": f"User '{user['name']}' deleted successfully"})
    return jsonify({"error": "Delete failed"}), 500


@api.route("/admin/users/<int:user_id>/edit", methods=["PATCH"])
@require_auth
def admin_edit_user(user_id):
    """
    Update editable user fields.
    Accepts any subset of: name, department, year, course_opted, specialization, courses_teaching
    """
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    allowed = ("name", "department", "year", "course_opted",
               "specialization", "courses_teaching")

    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values     = list(updates.values()) + [user_id]

    from database import get_connection
    conn = get_connection()
    conn.execute(f"UPDATE users SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()

    updated = get_user_by_id(user_id)
    return jsonify({"message": "User updated", "user": _user_payload(updated)})


# ---------------------------------------------------------------------------
# Admin — attendance logs (P1)
# ---------------------------------------------------------------------------

@api.route("/admin/attendance/logs", methods=["GET"])
@require_auth
def admin_attendance_logs():
    """
    Return paginated attendance logs with user info joined.
    P3 FIX: Wrapped in try/except so errors return JSON instead of 500 HTML.
    Query params: date (YYYY-MM-DD), limit (default 100), offset (default 0)
    """
    import traceback
    date_str = request.args.get("date")
    limit    = min(int(request.args.get("limit",  100)), 500)  # cap at 500
    offset   = int(request.args.get("offset", 0))

    try:
        from database import get_connection
        conn = get_connection()

        if date_str:
            rows = conn.execute(
                """SELECT a.id, a.timestamp, a.status, a.course_id,
                          u.id as user_id, u.name, u.role, u.department,
                          u.roll_no, u.employee_code
                   FROM attendance a
                   JOIN users u ON u.id = a.user_id
                   WHERE date(a.timestamp)=?
                   ORDER BY a.timestamp DESC LIMIT ? OFFSET ?""",
                (date_str, limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT a.id, a.timestamp, a.status, a.course_id,
                          u.id as user_id, u.name, u.role, u.department,
                          u.roll_no, u.employee_code
                   FROM attendance a
                   JOIN users u ON u.id = a.user_id
                   ORDER BY a.timestamp DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            ).fetchall()

        total = conn.execute("SELECT COUNT(*) as c FROM attendance").fetchone()["c"]
        conn.close()

        return jsonify({
            "logs":   [dict(r) for r in rows],
            "total":  total,
            "limit":  limit,
            "offset": offset,
        })

    except Exception as exc:
        print(f"[AdminLogs] ERROR: {exc}\n{traceback.format_exc()}")
        return jsonify({
            "error":  f"Failed to retrieve attendance logs: {str(exc)}",
            "logs":   [],
            "total":  0,
        }), 500


# ---------------------------------------------------------------------------
# Staff list (for admin panel)
# ---------------------------------------------------------------------------

@api.route("/staff", methods=["GET"])
@require_auth
def list_staff():
    """List all registered staff."""
    staff = get_all_staff()
    return jsonify({"staff": staff})
