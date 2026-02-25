"""
Landing page — role selector with three styled buttons.
Rendered as the default Streamlit page on first load.
"""
import streamlit as st


def show():
    st.markdown("""
    <style>
    .landing-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 70vh;
    }
    .landing-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1E88E5, #42A5F5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        text-align: center;
    }
    .landing-subtitle {
        font-size: 1.1rem;
        color: #78909C;
        margin-bottom: 3rem;
        text-align: center;
    }
    .role-row {
        display: flex;
        gap: 2rem;
        justify-content: center;
        flex-wrap: wrap;
    }
    .role-card {
        background: #1E293B;
        border-radius: 18px;
        padding: 2.5rem 2rem;
        text-align: center;
        cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s;
        border: 2px solid transparent;
        min-width: 180px;
    }
    .role-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 16px 40px rgba(0,0,0,0.4);
    }
    .role-icon { font-size: 3.5rem; margin-bottom: 0.8rem; }
    .role-label { font-size: 1.3rem; font-weight: 700; color: #E2E8F0; }
    .role-desc  { font-size: 0.85rem; color: #94A3B8; margin-top: 0.3rem; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="landing-title">🎓 StudentFacialAttendanceMarker</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="landing-subtitle">Select your role to continue</div>',
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1], gap="large")

    with col1:
        st.markdown("""
        <div class="role-card" style="border-color:#3B82F6;">
            <div class="role-icon">🎒</div>
            <div class="role-label">Student</div>
            <div class="role-desc">View your attendance history</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Enter as Student", key="btn_student",
                     use_container_width=True, type="primary"):
            st.session_state["role"] = "student"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="role-card" style="border-color:#10B981;">
            <div class="role-icon">👨‍🏫</div>
            <div class="role-label">Staff</div>
            <div class="role-desc">Manage student attendance</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Enter as Staff", key="btn_staff",
                     use_container_width=True):
            st.session_state["role"] = "staff"
            st.rerun()

    with col3:
        st.markdown("""
        <div class="role-card" style="border-color:#F59E0B;">
            <div class="role-icon">🛡️</div>
            <div class="role-label">Admin</div>
            <div class="role-desc">Full system control</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Enter as Admin", key="btn_admin",
                     use_container_width=True):
            st.session_state["role"] = "admin"
            st.rerun()
