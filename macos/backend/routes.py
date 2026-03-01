"""
routes.py — Flask REST API routes for the Facial Attendance System.

All endpoints return JSON. No classes. Blueprint-based organization.
"""

from flask import Blueprint, request, jsonify

from auth import (
    hash_password, verify_password,
    create_session_token, require_auth, require_role
)
from database import (
    add_user, get_user_by_email, get_user_by_id, get_all_students,
    user_exists, store_embedding, get_all_embeddings,
    mark_attendance, get_attendance, get_attendance_stats,
    get_weekly_attendance, get_all_courses
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
# Auth Endpoints
# ---------------------------------------------------------------------------

@api.route("/auth/login", methods=["POST"])
def login():
    """Authenticate user and return a session token."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = get_user_by_email(email)
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    if not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_session_token(user["id"], user["role"])
    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "department": user["department"],
        },
    })


@api.route("/auth/register", methods=["POST"])
def register():
    """
    Register a new student with face embeddings.
    Expects JSON: {name, email, department, password, frames: [base64...]}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    department = data.get("department", "").strip()
    password = data.get("password", "")
    frames_b64 = data.get("frames", [])

    # Validation
    if not all([name, email, password]):
        return jsonify({"error": "Name, email and password are required"}), 400

    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400

    if user_exists(email):
        return jsonify({"error": "Email already registered"}), 409

    if not frames_b64 or len(frames_b64) < 3:
        return jsonify({"error": "At least 3 face frames required"}), 400

    # Decode frames
    frames = []
    for i, fb64 in enumerate(frames_b64):
        ok, msg = validate_frame_size(fb64)
        if not ok:
            return jsonify({"error": f"Frame {i+1}: {msg}"}), 400

        img = decode_base64_image(fb64)
        if img is None:
            return jsonify({"error": f"Frame {i+1}: could not decode image"}), 400
        frames.append(img)

    # Extract embeddings
    result = extract_registration_embeddings(frames)
    if not result["success"]:
        return jsonify({"error": result["message"]}), 400

    # Create user account
    pw_hash = hash_password(password)
    user_id = add_user(name, email, department, "student", pw_hash)

    # Store embedding
    store_embedding(user_id, result["embedding"])

    # Generate session token
    token = create_session_token(user_id, "student")

    return jsonify({
        "message": result["message"],
        "token": token,
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "role": "student",
            "department": department,
        },
    }), 201


# ---------------------------------------------------------------------------
# Recognition Endpoint
# ---------------------------------------------------------------------------

@api.route("/recognize", methods=["POST"])
@require_auth
def recognize():
    """
    Receive a base64 frame and return recognition results.
    Expects JSON: {frame: base64_string}
    """
    data = request.get_json(silent=True)
    if not data or "frame" not in data:
        return jsonify({"error": "Frame data required"}), 400

    ok, msg = validate_frame_size(data["frame"])
    if not ok:
        return jsonify({"error": msg}), 400

    image = decode_base64_image(data["frame"])
    if image is None:
        return jsonify({"error": "Could not decode frame"}), 400

    # Detect faces
    faces = detect_faces(image)

    if len(faces) == 0:
        return jsonify({"faces": [], "message": "No faces detected"})

    # Get all stored embeddings
    stored = get_all_embeddings()

    if len(stored) == 0:
        return jsonify({
            "faces": [{"bbox": f["bbox"], "det_score": f["det_score"]}
                      for f in faces],
            "message": "No registered faces in database",
        })

    # Handle recognition based on face count
    if len(faces) == 1:
        match = recognize_face(faces[0]["embedding"], stored)
        if match:
            user = get_user_by_id(match["user_id"])
            return jsonify({
                "faces": [{
                    "bbox": faces[0]["bbox"],
                    "matched": True,
                    "user_id": match["user_id"],
                    "name": user["name"] if user else "Unknown",
                    "similarity": match["similarity"],
                }],
                "message": "Face recognized",
            })
        else:
            return jsonify({
                "faces": [{
                    "bbox": faces[0]["bbox"],
                    "matched": False,
                }],
                "message": "Face not recognized",
            })

    # Multiple faces
    result = handle_multi_face(faces, stored)
    if result["error"]:
        return jsonify({
            "faces": [],
            "error": result["error"],
            "unknown_count": result["unknown_count"],
        }), 400

    # Build response for recognized faces
    face_results = []
    for rec in result["recognized"]:
        user = get_user_by_id(rec["user_id"])
        face_results.append({
            "bbox": rec["bbox"],
            "matched": True,
            "user_id": rec["user_id"],
            "name": user["name"] if user else "Unknown",
            "similarity": rec["similarity"],
        })

    return jsonify({
        "faces": face_results,
        "unknown_count": result["unknown_count"],
        "message": f"{len(face_results)} face(s) recognized",
    })


# ---------------------------------------------------------------------------
# Attendance Endpoints
# ---------------------------------------------------------------------------

@api.route("/attendance/mark", methods=["POST"])
@require_auth
def mark_attendance_route():
    """
    Mark attendance for a student.
    Expects JSON: {user_id, course_id (optional)}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    marked = mark_attendance(user_id, course_id)
    if marked:
        stats = get_attendance_stats(user_id)
        return jsonify({
            "message": f"Attendance marked for {user['name']}",
            "stats": stats,
        })
    else:
        return jsonify({
            "message": "Attendance already marked within the last hour",
        })


@api.route("/attendance/<int:user_id>", methods=["GET"])
@require_auth
def get_attendance_route(user_id):
    """Get attendance records for a student."""
    start = request.args.get("start")
    end = request.args.get("end")
    records = get_attendance(user_id, start, end)
    return jsonify({"records": records})


# ---------------------------------------------------------------------------
# Dashboard Endpoint
# ---------------------------------------------------------------------------

@api.route("/dashboard/<int:user_id>", methods=["GET"])
@require_auth
def dashboard(user_id):
    """Get dashboard data for a student."""
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    stats = get_attendance_stats(user_id)
    weekly = get_weekly_attendance(user_id)
    courses = get_all_courses()

    return jsonify({
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "department": user["department"],
        },
        "stats": stats,
        "weekly": weekly,
        "courses": courses,
    })


# ---------------------------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------------------------

@api.route("/students", methods=["GET"])
@require_auth
def list_students():
    """List all registered students (admin/staff only)."""
    students = get_all_students()

    # Attach attendance stats to each student
    for s in students:
        s["stats"] = get_attendance_stats(s["id"])

    return jsonify({"students": students})


@api.route("/system/info", methods=["GET"])
def system_info():
    """Return system information (GPU, model status, etc.)."""
    info = get_system_info()
    info["model_ready"] = is_model_ready()
    return jsonify(info)
