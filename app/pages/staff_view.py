"""
Staff view — login with Emp ID + password, then see/manage student attendance.
Restricted: cannot see admin data, delete records, or modify system settings.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database.db_manager import DatabaseManager
from auth.auth_manager import AuthManager
import os


def show():
    db  = DatabaseManager()
    auth = AuthManager()

    # ── Login gate ────────────────────────────────────────────────────
    if "staff_logged_in" not in st.session_state:
        st.session_state["staff_logged_in"] = False
        st.session_state["staff_user_id"]   = None

    if not st.session_state["staff_logged_in"]:
        _show_login(db, auth)
        return

    _show_dashboard(db)


def _show_login(db: DatabaseManager, auth: AuthManager):
    st.markdown("## 👨‍🏫 Staff Login")
    with st.form("staff_login_form"):
        emp_id   = st.text_input("Employee ID").strip()
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary")

    if submitted:
        if not emp_id or not password:
            st.error("Please fill in all fields.")
            return

        # Verify user exists and is staff
        user = db.get_user(emp_id)
        if not user or user["role"] != "staff":
            st.error("❌ Employee ID not found.")
            return

        if auth.staff_login(emp_id, password):
            st.session_state["staff_logged_in"] = True
            st.session_state["staff_user_id"]   = emp_id
            st.session_state["staff_name"]       = user["name"]
            st.rerun()
        else:
            st.error("❌ Incorrect password.")

    st.markdown("---")
    if st.button("⬅ Back to Home", key="btn_staff_back_login"):
        del st.session_state["role"]
        st.rerun()


def _show_dashboard(db: DatabaseManager):
    staff_name = st.session_state.get("staff_name", "Staff")
    st.markdown(f"## 👨‍🏫 Welcome, {staff_name}")

    tab1, tab2 = st.tabs(["📋 Attendance Records", "⚙️ Account"])

    # ── Tab 1: Attendance ─────────────────────────────────────────────
    with tab1:
        st.subheader("Student Attendance")

        col1, col2 = st.columns(2)
        with col1:
            selected_date = st.date_input(
                "Select Date",
                value=date.today(),
                key="staff_date_picker",
            )
        with col2:
            search_name = st.text_input(
                "Search by Name / ID",
                placeholder="Leave blank to show all",
                key="staff_search",
            ).strip().lower()

        date_str = selected_date.strftime("%Y-%m-%d")
        records  = db.get_attendance_by_date(date_str, role="student")

        if not records:
            st.info(f"No student attendance records for {date_str}.")
        else:
            df = pd.DataFrame(records)

            if search_name:
                df = df[
                    df["name"].str.lower().str.contains(search_name) |
                    df["user_id"].str.lower().str.contains(search_name)
                ]

            # Display
            display_cols = ["user_id","name","course","department","time","status"]
            available = [c for c in display_cols if c in df.columns]
            st.dataframe(df[available], use_container_width=True)

            # Photo thumbnails
            if st.checkbox("Show Photos"):
                for _, row in df.iterrows():
                    ip = row.get("image_path", "")
                    if ip and os.path.exists(ip):
                        st.image(ip, caption=f"{row['name']} — {row['time']}",
                                 width=160)

            # Mark as Late
            st.markdown("#### Mark Student as Late")
            student_ids = df["user_id"].tolist()
            if student_ids:
                target_id = st.selectbox(
                    "Select Student",
                    options=student_ids,
                    format_func=lambda uid: f"{uid} — {df[df['user_id']==uid]['name'].values[0]}",
                    key="staff_late_select",
                )
                if st.button("Mark as Late", key="btn_mark_late", type="primary"):
                    db.update_attendance_status(target_id, date_str, "late")
                    st.success(f"✅ Marked {target_id} as 'Late' for {date_str}.")
                    st.rerun()

    # ── Tab 2: Account ────────────────────────────────────────────────
    with tab2:
        st.subheader("Change Password")
        auth = AuthManager()
        with st.form("staff_change_pw"):
            current_pw = st.text_input("Current Password", type="password")
            new_pw     = st.text_input("New Password",     type="password")
            confirm_pw = st.text_input("Confirm Password", type="password")
            submitted  = st.form_submit_button("Update Password")

        if submitted:
            emp_id = st.session_state["staff_user_id"]
            if not auth.staff_login(emp_id, current_pw):
                st.error("❌ Current password is incorrect.")
            elif new_pw != confirm_pw:
                st.error("❌ Passwords do not match.")
            else:
                strong, reason = AuthManager.is_strong_password(new_pw)
                if not strong:
                    st.error(f"❌ {reason}")
                else:
                    auth.change_staff_password(emp_id, new_pw)
                    st.success("✅ Password changed successfully.")

    # ── Logout ────────────────────────────────────────────────────────
    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🚪 Logout", key="btn_staff_logout"):
            st.session_state["staff_logged_in"] = False
            st.session_state["staff_user_id"]   = None
            st.rerun()
    with col_b:
        if st.button("⬅ Back to Home", key="btn_staff_home"):
            del st.session_state["role"]
            st.rerun()
