"""
main.py — Entry point for StudentFacialAttendanceMarker.

Run with:  streamlit run main.py
"""
import os
import sys
import streamlit as st

# ── Ensure project root is in sys.path ────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Page config (must be first Streamlit call) ─────────────────────────
st.set_page_config(
    page_title="StudentFacialAttendanceMarker",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Base dark theme */
[data-testid="stAppViewContainer"] {
    background: #0F172A;
    color: #E2E8F0;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #1E293B; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #1E293B;
    border-radius: 12px;
    padding: 1rem;
    border: 1px solid #334155;
}

/* Buttons */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(59,130,246,0.4);
}

/* Streamlit default overrides */
h1, h2, h3, h4 { color: #F1F5F9 !important; }
.stTabs [data-baseweb="tab"] { color: #94A3B8; font-weight: 600; }
.stTabs [aria-selected="true"] { color: #3B82F6 !important; }
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Database initialisation (runs once per session) ────────────────────
@st.cache_resource
def _init_db():
    from database.db_manager import DatabaseManager
    db = DatabaseManager()
    db.initialize()
    return db


_init_db()


# ── Sidebar navigation ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎓 SFAM")
    st.markdown("---")
    st.markdown(
        "<span style='color:#94A3B8;font-size:0.8rem;'>"
        "StudentFacialAttendanceMarker<br>v1.0 — Fully Offline"
        "</span>",
        unsafe_allow_html=True
    )
    st.markdown("---")

    nav_page = st.radio(
        "Navigation",
        ["🏠 Home", "📹 Live Camera", "🎒 Student", "👨‍🏫 Staff", "🛡️ Admin"],
        key="nav_radio",
        label_visibility="collapsed",
    )

    st.markdown("---")
    from datetime import datetime
    st.markdown(
        f"<span style='color:#64748B;font-size:0.75rem;'>"
        f"🕐 {datetime.now().strftime('%H:%M:%S')}</span>",
        unsafe_allow_html=True
    )


# ── Page routing ────────────────────────────────────────────────────────
def _route(nav_choice: str):
    # Session-state driven role (from landing page buttons)
    role = st.session_state.get("role")
    page = st.session_state.get("page")

    # Registration sub-page (triggered from camera feed)
    if page == "register":
        from app.pages import register as reg_mod

        cam = st.session_state.get("camera_thread")
        reg_mod.show(camera_thread=cam)
        return

    # Sidebar nav takes priority when role not set
    if nav_choice == "📹 Live Camera" or (role is None and nav_choice == "📹 Live Camera"):
        from app import camera_feed
        camera_feed.show()
        return

    if nav_choice == "🎒 Student" or role == "student":
        from app.pages import student_view
        student_view.show()
        return

    if nav_choice == "👨‍🏫 Staff" or role == "staff":
        from app.pages import staff_view
        staff_view.show()
        return

    if nav_choice == "🛡️ Admin" or role == "admin":
        from app.pages import admin_view
        admin_view.show()
        return

    # Default: landing
    from app.pages import landing
    landing.show()


_route(nav_page)
