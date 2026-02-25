"""
Registration page — multi-angle face capture and embedding storage.
Triggered when an unknown face is detected in the camera feed.
"""
import streamlit as st
import cv2
import numpy as np
import os
from datetime import datetime
from database.db_manager import DatabaseManager
from auth.auth_manager import AuthManager
from utils.face_utils import FaceAnalyzer
from utils.logger import logger

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PHOTOS_DIR = os.path.join(BASE_DIR, "attendance_records", "photos")

ANGLES = ["Front", "Left", "Right", "Up", "Down"]


def show(camera_thread=None, initial_frame=None):
    """
    camera_thread: running CameraThread instance (for live capture)
    initial_frame: numpy BGR frame already captured (optional pre-fill)
    """
    st.markdown("## 📷 Register New User")

    db   = DatabaseManager()
    auth = AuthManager()
    fa   = FaceAnalyzer()

    # ── Role selector ─────────────────────────────────────────────────
    role = st.radio(
        "Registering as:",
        ["student", "staff"],
        horizontal=True,
        key="reg_role",
    )

    # ── User details form ─────────────────────────────────────────────
    with st.form("registration_form"):
        col1, col2 = st.columns(2)
        with col1:
            reg_name   = st.text_input("Full Name *")
            reg_id     = st.text_input(
                "Roll No (Student) / Emp ID (Staff) *",
                help="This is the unique identifier"
            )
        with col2:
            reg_course = st.text_input("Course (e.g. B.Tech CSE)")
            reg_dept   = st.text_input("Department (e.g. Computer Science)")

        staff_pw = ""
        if role == "staff":
            staff_pw = st.text_input(
                "Staff Password *", type="password",
                help="Required for staff login"
            )

        form_submitted = st.form_submit_button("Proceed to Face Capture", type="primary")

    if form_submitted:
        # Validation
        errors = []
        if not reg_name.strip():   errors.append("Name is required.")
        if not reg_id.strip():     errors.append("ID is required.")
        if role == "staff" and not staff_pw:
            errors.append("Password is required for Staff.")
        if role == "staff" and staff_pw:
            strong, reason = AuthManager.is_strong_password(staff_pw)
            if not strong:
                errors.append(reason)

        if errors:
            for e in errors:
                st.error(f"❌ {e}")
        else:
            clean_id = reg_id.strip().upper()
            if db.get_user(clean_id):
                st.error(f"❌ ID '{clean_id}' already exists.")
            else:
                st.session_state["reg_info"] = {
                    "name":     reg_name.strip(),
                    "user_id":  clean_id,
                    "role":     role,
                    "course":   reg_course.strip(),
                    "dept":     reg_dept.strip(),
                    "staff_pw": staff_pw,
                }
                st.session_state["reg_embeddings"] = []
                st.session_state["reg_angle_idx"]  = 0
                st.rerun()

    # ── Face capture stage ────────────────────────────────────────────
    if "reg_info" not in st.session_state:
        # back button
        st.markdown("---")
        if st.button("⬅ Back to Camera", key="btn_reg_back"):
            st.session_state["page"] = "camera"
            st.rerun()
        return

    info      = st.session_state["reg_info"]
    angle_idx = st.session_state.get("reg_angle_idx", 0)
    captured  = st.session_state.get("reg_embeddings", [])

    if angle_idx >= len(ANGLES):
        _finalise_registration(db, auth, info, captured, fa)
        return

    current_angle = ANGLES[angle_idx]

    st.markdown(f"""
    <div style="background:#1E293B;border-radius:12px;padding:1rem 1.5rem;margin-bottom:1rem;">
        <b style="color:#3B82F6;">Registering:</b>
        <span style="color:#E2E8F0;"> {info['name']} ({info['user_id']})</span>
    </div>
    """, unsafe_allow_html=True)

    st.info(
        f"📸 **Angle {angle_idx + 1}/{len(ANGLES)}: {current_angle}**  \n"
        f"Please look **{current_angle.lower()}** and click Capture."
    )

    # Progress
    st.progress((angle_idx) / len(ANGLES), text=f"Captured {angle_idx}/{len(ANGLES)} angles")

    # Show live frame if camera available
    frame_placeholder = st.empty()
    if camera_thread is not None:
        frame = camera_thread.get_frame()
    elif initial_frame is not None:
        frame = initial_frame.copy()
    else:
        frame = None

    if frame is not None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(rgb, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"📸 Capture — {current_angle}", type="primary",
                     key=f"btn_cap_{angle_idx}"):
            if frame is None:
                st.error("❌ No camera frame available. Check camera connection.")
            else:
                embedding = fa.extract_embedding_from_frame(frame)
                if embedding is None:
                    st.warning(
                        "⚠️ No face detected. Ensure your face is clearly visible "
                        "and well-lit, then try again."
                    )
                else:
                    captured.append((current_angle.lower(), embedding))
                    st.session_state["reg_embeddings"] = captured
                    st.session_state["reg_angle_idx"]  = angle_idx + 1
                    st.success(f"✅ Captured {current_angle} angle!")
                    st.rerun()

    with col2:
        if st.button("⏩ Skip this angle", key=f"btn_skip_{angle_idx}"):
            st.session_state["reg_angle_idx"] = angle_idx + 1
            st.rerun()

    st.markdown("---")
    if st.button("❌ Cancel Registration", key="btn_cancel_reg"):
        _clear_reg_state()
        st.session_state["page"] = "camera"
        st.rerun()


def _finalise_registration(
    db: DatabaseManager,
    auth: AuthManager,
    info: dict,
    captured: list,
    fa: FaceAnalyzer
):
    st.markdown("### ✅ Review & Confirm Registration")
    st.markdown(f"""
    | Field | Value |
    |-------|-------|
    | Name  | {info['name']} |
    | ID    | {info['user_id']} |
    | Role  | {info['role']} |
    | Course | {info['course']} |
    | Dept  | {info['dept']} |
    | Angles Captured | {len(captured)} / 5 |
    """)

    if len(captured) == 0:
        st.error("❌ No face embeddings captured. Cannot register.")
        if st.button("Restart", key="btn_restart_reg"):
            _clear_reg_state()
            st.rerun()
        return

    if st.button("✅ Confirm & Register", type="primary", key="btn_confirm_reg"):
        # Save profile photo (use first captured angle's frame placeholder)
        ok_user = db.add_user(
            name       = info["name"],
            user_id    = info["user_id"],
            role       = info["role"],
            course     = info["course"],
            department = info["dept"],
        )
        if not ok_user:
            st.error(f"❌ User ID {info['user_id']} already exists.")
            _clear_reg_state()
            return

        # Store embeddings
        for angle_name, emb in captured:
            db.add_embedding(info["user_id"], emb, angle=angle_name)

        # Staff credentials
        if info["role"] == "staff" and info.get("staff_pw"):
            h, s = auth.hash_password(info["staff_pw"])
            db.set_staff_credentials(info["user_id"], h, s)

        # Invalidate engine embedding cache
        if "attendance_engine" in st.session_state:
            st.session_state["attendance_engine"].refresh_cache()

        logger.info(
            f"New user registered: {info['user_id']} ({info['name']}) "
            f"role={info['role']} angles={len(captured)}"
        )

        st.success(
            f"🎉 **{info['name']}** registered successfully with "
            f"{len(captured)} face angle(s)!"
        )
        st.balloons()
        _clear_reg_state()

        if st.button("⬅ Back to Camera", key="btn_back_after_reg"):
            st.session_state["page"] = "camera"
            st.rerun()


def _clear_reg_state():
    for key in ["reg_info", "reg_embeddings", "reg_angle_idx"]:
        if key in st.session_state:
            del st.session_state[key]
