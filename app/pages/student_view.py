"""
Student view — no login required.
Student enters Roll/Reg No and views their own attendance history.
Cannot edit anything.
"""
import streamlit as st
import pandas as pd
from database.db_manager import DatabaseManager


def show():
    st.markdown("## 🎒 Student Attendance Portal")
    st.markdown("Enter your Roll / Registration Number to view your attendance.")

    db = DatabaseManager()

    # ── Input ─────────────────────────────────────────────────────────
    roll_no = st.text_input(
        "Roll No / Reg No",
        placeholder="e.g. 22CS001",
        key="student_roll_input",
    ).strip().upper()

    if st.button("View Attendance", type="primary", key="btn_view_attendance"):
        if not roll_no:
            st.warning("Please enter your Roll No.")
            return

        user = db.get_user(roll_no)
        if not user or user["role"] != "student":
            st.error("❌ Student not found. Please check your Roll No.")
            return

        records = db.get_attendance_by_user(roll_no)

        # ── Profile card ─────────────────────────────────────────────
        st.markdown(f"""
        <div style="background:#1E293B;border-radius:14px;padding:1.2rem 1.5rem;
                    margin-bottom:1.5rem;border-left:5px solid #3B82F6;">
            <span style="font-size:1.5rem;font-weight:700;color:#E2E8F0;">
                👤 {user['name']}
            </span><br>
            <span style="color:#94A3B8;">
                {user['user_id']} &nbsp;|&nbsp;
                {user.get('course','—')} &nbsp;|&nbsp;
                {user.get('department','—')}
            </span>
        </div>
        """, unsafe_allow_html=True)

        if not records:
            st.info("No attendance records found.")
            return

        # ── Stats ─────────────────────────────────────────────────────
        df = pd.DataFrame(records)
        total   = len(df)
        present = len(df[df["status"] == "present"])
        late    = len(df[df["status"] == "late"])
        pct     = round((present + late) / total * 100, 1) if total > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Days", total)
        c2.metric("Present",    present)
        c3.metric("Late",       late)
        c4.metric("Attendance %", f"{pct}%",
                  delta_color="normal" if pct >= 75 else "inverse")

        if pct < 75:
            st.warning(f"⚠️ Your attendance is below 75%. Current: {pct}%")

        # ── Table ─────────────────────────────────────────────────────
        st.markdown("### 📋 Attendance History")
        display_df = df[["date", "time", "status"]].copy()
        display_df.columns = ["Date", "Time", "Status"]
        display_df = display_df.sort_values("Date", ascending=False)

        def _colour(row):
            color = (
                "#D1FAE5" if row["Status"] == "present" else
                "#FEF9C3" if row["Status"] == "late" else
                "#FEE2E2"
            )
            return [f"background-color:{color}" for _ in row]

        st.dataframe(
            display_df.style.apply(_colour, axis=1),
            use_container_width=True,
            height=400,
        )

    # Back button
    st.markdown("---")
    if st.button("⬅ Back to Home", key="btn_student_back"):
        del st.session_state["role"]
        st.rerun()
