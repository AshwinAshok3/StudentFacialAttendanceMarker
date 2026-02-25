"""
Admin dashboard — full CRUD, analytics, logs, user management, export.
Boots with root/passwd on first run; forces password change immediately.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from database.db_manager import DatabaseManager
from auth.auth_manager import AuthManager
from utils.excel_utils import export_date_range_to_excel
import os, io

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────────────────── #
# Entry point
# ─────────────────────────────────────────────────────────────────────────── #

def show():
    db   = DatabaseManager()
    auth = AuthManager()

    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"]       = False
        st.session_state["admin_must_change_pw"]  = False
        st.session_state["admin_username"]         = None

    if not st.session_state["admin_logged_in"]:
        _show_login(db, auth)
        return

    if st.session_state["admin_must_change_pw"]:
        _show_force_change(auth)
        return

    _show_dashboard(db, auth)


# ─────────────────────────────────────────────────────────────────────────── #
# Login
# ─────────────────────────────────────────────────────────────────────────── #

def _show_login(db: DatabaseManager, auth: AuthManager):
    st.markdown("## 🛡️ Admin Login")
    with st.form("admin_login_form"):
        username  = st.text_input("Username")
        password  = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary")

    if submitted:
        ok, must_change = auth.admin_login(username.strip(), password)
        if ok:
            st.session_state["admin_logged_in"]      = True
            st.session_state["admin_username"]        = username.strip()
            st.session_state["admin_must_change_pw"] = must_change
            st.rerun()
        else:
            st.error("❌ Invalid credentials.")

    st.markdown("---")
    if st.button("⬅ Back to Home", key="btn_admin_back_login"):
        del st.session_state["role"]
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────── #
# Force password change
# ─────────────────────────────────────────────────────────────────────────── #

def _show_force_change(auth: AuthManager):
    st.warning("⚠️ You must change your password before proceeding.")
    st.markdown("### 🔐 Set New Admin Password")
    with st.form("force_change_pw"):
        new_pw     = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm Password", type="password")
        submitted  = st.form_submit_button("Set Password", type="primary")

    if submitted:
        if new_pw != confirm_pw:
            st.error("❌ Passwords do not match.")
        else:
            strong, reason = AuthManager.is_strong_password(new_pw)
            if not strong:
                st.error(f"❌ {reason}")
            else:
                auth.change_admin_password(
                    st.session_state["admin_username"], new_pw
                )
                st.session_state["admin_must_change_pw"] = False
                st.success("✅ Password updated. Loading dashboard...")
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────── #
# Main dashboard
# ─────────────────────────────────────────────────────────────────────────── #

def _show_dashboard(db: DatabaseManager, auth: AuthManager):
    uname = st.session_state["admin_username"]
    st.markdown(f"## 🛡️ Admin Dashboard — {uname}")

    tabs = st.tabs([
        "📊 Analytics",
        "📋 Attendance",
        "👥 Users",
        "📤 Export",
        "📜 Logs",
        "⚙️ Settings",
    ])

    with tabs[0]: _tab_analytics(db)
    with tabs[1]: _tab_attendance(db)
    with tabs[2]: _tab_users(db, auth)
    with tabs[3]: _tab_export(db)
    with tabs[4]: _tab_logs(db)
    with tabs[5]: _tab_settings(db, auth)

    st.markdown("---")
    if st.button("🚪 Logout", key="btn_admin_logout"):
        st.session_state["admin_logged_in"] = False
        st.session_state["admin_username"]   = None
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────── #
# Analytics tab
# ─────────────────────────────────────────────────────────────────────────── #

def _tab_analytics(db: DatabaseManager):
    st.subheader("📊 Attendance Analytics")

    records = db.get_all_attendance()
    if not records:
        st.info("No attendance data yet.")
        return

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])

    # KPI row
    total_records = len(df)
    unique_people = df["user_id"].nunique()
    today_str     = datetime.now().strftime("%Y-%m-%d")
    today_count   = len(df[df["date"].dt.strftime("%Y-%m-%d") == today_str])

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records",  total_records)
    c2.metric("Unique Persons", unique_people)
    c3.metric("Today's Count",  today_count)

    # Daily trend
    daily = df.groupby(df["date"].dt.strftime("%Y-%m-%d"))["id"].count().reset_index()
    daily.columns = ["Date", "Count"]

    fig_trend = px.line(
        daily, x="Date", y="Count",
        title="Daily Attendance Trend",
        markers=True,
        template="plotly_dark",
        color_discrete_sequence=["#3B82F6"],
    )
    fig_trend.update_layout(
        plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
        font_color="#E2E8F0", title_font_size=16,
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    col_a, col_b = st.columns(2)

    # Role breakdown
    with col_a:
        role_counts = df["role"].value_counts().reset_index()
        role_counts.columns = ["Role", "Count"]
        fig_pie = px.pie(
            role_counts, names="Role", values="Count",
            title="Attendance by Role",
            template="plotly_dark",
            color_discrete_sequence=["#3B82F6", "#10B981", "#F59E0B"],
        )
        fig_pie.update_layout(
            plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
            font_color="#E2E8F0",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Department breakdown
    with col_b:
        dept_counts = df["department"].value_counts().head(10).reset_index()
        dept_counts.columns = ["Department", "Count"]
        fig_bar = px.bar(
            dept_counts, x="Count", y="Department",
            orientation="h",
            title="Top Departments by Attendance",
            template="plotly_dark",
            color="Count",
            color_continuous_scale="Blues",
        )
        fig_bar.update_layout(
            plot_bgcolor="#0F172A", paper_bgcolor="#0F172A",
            font_color="#E2E8F0",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Status breakdown
    status_df = df["status"].value_counts().reset_index()
    status_df.columns = ["Status", "Count"]
    fig_status = px.bar(
        status_df, x="Status", y="Count",
        title="Attendance Status Distribution",
        template="plotly_dark",
        color="Status",
        color_discrete_map={
            "present": "#10B981", "late": "#F59E0B", "absent": "#EF4444"
        },
    )
    fig_status.update_layout(
        plot_bgcolor="#0F172A", paper_bgcolor="#0F172A", font_color="#E2E8F0"
    )
    st.plotly_chart(fig_status, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────── #
# Attendance tab
# ─────────────────────────────────────────────────────────────────────────── #

def _tab_attendance(db: DatabaseManager):
    st.subheader("📋 Attendance Records")

    col1, col2 = st.columns(2)
    with col1:
        sel_date = st.date_input("Date", value=date.today(), key="admin_att_date")
    with col2:
        role_filter = st.selectbox("Role", ["all", "student", "staff"], key="admin_role_filter")

    date_str = sel_date.strftime("%Y-%m-%d")
    role_arg = None if role_filter == "all" else role_filter
    records  = db.get_attendance_by_date(date_str, role=role_arg)

    if not records:
        st.info(f"No records for {date_str}.")
        return

    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True)

    # Edit status
    st.markdown("#### Edit Status")
    colA, colB, colC = st.columns(3)
    with colA:
        att_id = st.number_input("Record ID", min_value=1, step=1, key="admin_att_id")
    with colB:
        new_status = st.selectbox("New Status", ["present", "late", "absent"], key="admin_new_status")
    with colC:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Update Status", type="primary", key="btn_update_status"):
            # look up user_id for this attendance id
            record_match = [r for r in records if r["id"] == att_id]
            if record_match:
                db.update_attendance_status(record_match[0]["user_id"], date_str, new_status)
                st.success("✅ Status updated.")
                st.rerun()
            else:
                st.error("Record ID not found in current view.")

    # Delete record
    st.markdown("#### Delete Record")
    del_id = st.number_input("Record ID to Delete", min_value=1, step=1, key="admin_del_id")
    if st.button("🗑️ Delete Record", type="secondary", key="btn_del_att"):
        db.delete_attendance(int(del_id))
        st.success("Record deleted.")
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────── #
# Users tab
# ─────────────────────────────────────────────────────────────────────────── #

def _tab_users(db: DatabaseManager, auth: AuthManager):
    st.subheader("👥 User Management")

    role_filter = st.selectbox("Filter Role", ["all", "student", "staff"], key="admin_user_role")
    role_arg    = None if role_filter == "all" else role_filter
    users       = db.get_all_users(role=role_arg)

    if users:
        df_users = pd.DataFrame(users)
        disp_cols = [c for c in ["user_id","name","role","course","department","created_at"] if c in df_users.columns]
        st.dataframe(df_users[disp_cols], use_container_width=True)
    else:
        st.info("No users found.")

    st.markdown("---")
    # Add new user manually
    with st.expander("➕ Register New User Manually"):
        with st.form("admin_add_user"):
            col1, col2 = st.columns(2)
            with col1:
                new_name   = st.text_input("Full Name")
                new_id     = st.text_input("ID (Roll No / Emp ID)")
                new_role   = st.selectbox("Role", ["student", "staff"])
            with col2:
                new_course = st.text_input("Course")
                new_dept   = st.text_input("Department")
                new_pw     = st.text_input(
                    "Password (Staff only)", type="password",
                    help="Required for Staff; ignored for Students"
                )
            add_submitted = st.form_submit_button("Register User", type="primary")

        if add_submitted:
            if not new_name or not new_id:
                st.error("Name and ID are required.")
            else:
                ok = db.add_user(new_name.strip(), new_id.strip().upper(),
                                  new_role, new_course.strip(), new_dept.strip())
                if ok:
                    if new_role == "staff" and new_pw:
                        h, s = auth.hash_password(new_pw)
                        db.set_staff_credentials(new_id.strip().upper(), h, s)
                    st.success(f"✅ User {new_name} registered.")
                else:
                    st.error("❌ User ID already exists.")

    # Delete user
    with st.expander("🗑️ Delete User"):
        del_uid = st.text_input("User ID to delete", key="admin_del_uid").strip().upper()
        if st.button("Delete User", type="secondary", key="btn_del_user"):
            if del_uid:
                db.delete_user(del_uid)
                db.delete_embeddings(del_uid)
                st.success(f"User {del_uid} deleted.")
                st.rerun()

    # Reset staff password
    with st.expander("🔑 Reset Staff Password"):
        rst_uid = st.text_input("Staff Emp ID", key="admin_rst_uid").strip().upper()
        rst_pw  = st.text_input("New Password", type="password", key="admin_rst_pw")
        if st.button("Reset Password", type="primary", key="btn_rst_pw"):
            strong, reason = AuthManager.is_strong_password(rst_pw)
            if not strong:
                st.error(f"❌ {reason}")
            else:
                auth.change_staff_password(rst_uid, rst_pw)
                st.success(f"✅ Password reset for {rst_uid}.")

    # Manage admin accounts
    with st.expander("👑 Manage Admin Accounts"):
        admins = db.list_admins()
        st.dataframe(pd.DataFrame(admins), use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            with st.form("add_admin_form"):
                new_admin_user = st.text_input("New Admin Username")
                new_admin_pw   = st.text_input("Password", type="password")
                if st.form_submit_button("Add Admin"):
                    h, s = auth.hash_password(new_admin_pw)
                    ok = db.add_admin(new_admin_user.strip(), h, s)
                    st.success("Admin added.") if ok else st.error("Username exists.")
        with col2:
            del_admin_u = st.text_input("Delete Admin Username", key="del_admin_u")
            if st.button("Delete Admin", type="secondary", key="btn_del_admin"):
                if db.delete_admin(del_admin_u.strip()):
                    st.success("Deleted.")
                    st.rerun()
                else:
                    st.error("Cannot delete root admin.")


# ─────────────────────────────────────────────────────────────────────────── #
# Export tab
# ─────────────────────────────────────────────────────────────────────────── #

def _tab_export(db: DatabaseManager):
    st.subheader("📤 Export Attendance")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=7), key="exp_start")
    with col2:
        end_date = st.date_input("To",   value=date.today(), key="exp_end")

    if st.button("Generate Excel Export", type="primary", key="btn_export"):
        start_str = start_date.strftime("%Y-%m-%d")
        end_str   = end_date.strftime("%Y-%m-%d")
        out_path  = os.path.join(
            BASE_DIR, "attendance_records",
            f"export_{start_str}_{end_str}.xlsx"
        )
        ok = export_date_range_to_excel(start_str, end_str, out_path)
        if ok and os.path.exists(out_path):
            with open(out_path, "rb") as f:
                data = f.read()
            st.download_button(
                label=f"⬇️ Download {os.path.basename(out_path)}",
                data=data,
                file_name=os.path.basename(out_path),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.error("Export failed. Check logs.")

    # Quick CSV download of all attendance
    st.markdown("---")
    if st.button("Download All Attendance as CSV", key="btn_csv"):
        all_records = db.get_all_attendance()
        if all_records:
            df = pd.DataFrame(all_records)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV", csv,
                file_name="all_attendance.csv", mime="text/csv"
            )
        else:
            st.info("No records to export.")


# ─────────────────────────────────────────────────────────────────────────── #
# Logs tab
# ─────────────────────────────────────────────────────────────────────────── #

def _tab_logs(db: DatabaseManager):
    st.subheader("📜 System Logs")
    level_filter = st.selectbox(
        "Level", ["ALL", "INFO", "WARNING", "ERROR", "CRITICAL"],
        key="admin_log_level"
    )
    logs = db.get_logs(limit=1000)
    if level_filter != "ALL":
        logs = [l for l in logs if l["level"] == level_filter]

    if not logs:
        st.info("No logs found.")
    else:
        log_df = pd.DataFrame(logs)
        def _row_style(row):
            color_map = {
                "ERROR":    "#FEE2E2", "CRITICAL": "#FCA5A5",
                "WARNING":  "#FEF9C3", "INFO":     "#F0FDF4",
            }
            bg = color_map.get(row["level"], "#FFFFFF")
            return [f"background-color:{bg}" for _ in row]

        st.dataframe(
            log_df[["timestamp","level","message"]].style.apply(_row_style, axis=1),
            use_container_width=True, height=450,
        )

    if st.button("🧹 Clear Logs Older Than 30 Days", key="btn_clear_logs"):
        db.clear_old_logs(30)
        st.success("Old logs cleared.")
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────── #
# Settings tab
# ─────────────────────────────────────────────────────────────────────────── #

def _tab_settings(db: DatabaseManager, auth: AuthManager):
    st.subheader("⚙️ System Settings")

    # Change own password
    st.markdown("#### Change Admin Password")
    with st.form("admin_change_pw_self"):
        cur_pw  = st.text_input("Current Password",  type="password")
        new_pw  = st.text_input("New Password",      type="password")
        conf_pw = st.text_input("Confirm Password",  type="password")
        if st.form_submit_button("Update Password", type="primary"):
            uname = st.session_state["admin_username"]
            ok, _ = auth.admin_login(uname, cur_pw)
            if not ok:
                st.error("❌ Current password wrong.")
            elif new_pw != conf_pw:
                st.error("❌ Passwords do not match.")
            else:
                strong, reason = AuthManager.is_strong_password(new_pw)
                if not strong:
                    st.error(f"❌ {reason}")
                else:
                    auth.change_admin_password(uname, new_pw)
                    st.success("✅ Password changed.")

    st.markdown("---")
    st.markdown("#### Database Paths")
    from database.db_manager import MAIN_DB, ADMIN_DB
    st.code(f"main.db  : {MAIN_DB}\nadmin.db : {ADMIN_DB}")

    st.markdown("#### Embedding Cache")
    with st.form("rebuild_cache"):
        if st.form_submit_button("🔄 Rebuild Embedding Cache"):
            # Triggers on next frame via attendance engine
            st.success("Cache will rebuild on next camera frame.")

    st.markdown("#### System Info")
    import platform, sys
    st.text(f"Python  : {sys.version.split()[0]}")
    st.text(f"OS      : {platform.system()} {platform.release()}")
    st.text(f"DB path : {os.path.dirname(MAIN_DB)}")
