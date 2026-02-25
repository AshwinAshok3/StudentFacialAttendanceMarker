"""
camera_feed.py — live attendance camera feed rendered inside Streamlit.
Auto-refreshes the image every ~100ms using st_autorefresh or manual rerun.
Shows attendance status card on recognition event.
"""
import streamlit as st
import cv2
import numpy as np
from datetime import datetime
import time

from utils.camera import CameraThread
from app.attendance_engine import AttendanceEngine, STATUS_SUCCESS, STATUS_DUPLICATE, STATUS_UNKNOWN
from app.pages import register as register_page


def show():
    st.markdown("## 📹 Live Attendance Feed")

    # ── Session state init ─────────────────────────────────────────────
    if "camera_thread" not in st.session_state:
        ct = CameraThread(camera_index=0)
        ct.start()
        st.session_state["camera_thread"] = ct

    if "attendance_engine" not in st.session_state:
        st.session_state["attendance_engine"] = AttendanceEngine()

    camera   = st.session_state["camera_thread"]
    engine   = st.session_state["attendance_engine"]

    # ── Controls row ───────────────────────────────────────────────────
    col_l, col_m, col_r = st.columns([2, 1, 1])
    with col_l:
        st.markdown(
            f"<span style='color:#94A3B8;font-size:0.85rem;'>"
            f"🕐 {datetime.now().strftime('%A, %d %B %Y  %H:%M:%S')}</span>",
            unsafe_allow_html=True
        )
    with col_m:
        fps_val = f"{camera.fps:.1f} FPS" if camera.fps > 0 else "—"
        st.markdown(
            f"<span style='color:#3B82F6;'>{fps_val}</span>",
            unsafe_allow_html=True
        )
    with col_r:
        if st.button("⏹ Stop Camera", key="btn_stop_cam"):
            camera.stop()
            del st.session_state["camera_thread"]
            st.rerun()

    # ── Registration redirect ──────────────────────────────────────────
    if st.session_state.get("page") == "register":
        register_page.show(camera_thread=camera)
        return

    # ── Frame container ────────────────────────────────────────────────
    feed_placeholder   = st.empty()
    status_placeholder = st.empty()

    if not camera.is_running:
        feed_placeholder.warning("⚠️ Camera not running.")
        return

    frame = camera.get_frame()
    if frame is None:
        feed_placeholder.info("🔴 Waiting for camera frame...")
        time.sleep(0.2)
        st.rerun()
        return

    # ── Process frame ──────────────────────────────────────────────────
    annotated, results = engine.process_frame(frame)

    # Convert to RGB for Streamlit display
    rgb_frame = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
    feed_placeholder.image(rgb_frame, use_container_width=True)

    # ── Status cards ───────────────────────────────────────────────────
    for res in results:
        status    = res["status"]
        user_info = res.get("user_info")
        score     = res.get("score", 0.0)

        if status == STATUS_SUCCESS and user_info:
            status_placeholder.success(
                f"""✅ **Attendance Marked**\n
| Field | Value |
|-------|-------|
| 👤 Name | **{user_info.get('name', '—')}** |
| 🆔 ID | {user_info.get('user_id', '—')} |
| 📚 Course | {user_info.get('course', '—')} |
| 🏢 Dept | {user_info.get('department', '—')} |
| 🕐 Time | {res.get('time', '—')} |
| 📅 Date | {res.get('date', '—')} |
| 📊 Confidence | {score:.1%} |"""
            )

        elif status == STATUS_DUPLICATE and user_info:
            status_placeholder.warning(
                f"🟡 **Attendance Already Marked** for "
                f"**{user_info.get('name', '—')}** today."
            )

        elif status == STATUS_UNKNOWN:
            with status_placeholder.container():
                st.error("🔴 **Unknown Face Detected**")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📝 Register as Student", key=f"reg_stu_{time.time_ns()}"):
                        st.session_state["page"] = "register"
                        st.session_state["reg_role_hint"] = "student"
                        st.rerun()
                with col2:
                    if st.button("🏢 Register as Staff", key=f"reg_sta_{time.time_ns()}"):
                        st.session_state["page"] = "register"
                        st.session_state["reg_role_hint"] = "staff"
                        st.rerun()

    # ── Auto-refresh every 150ms ───────────────────────────────────────
    time.sleep(0.15)
    st.rerun()
