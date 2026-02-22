"""
Freelance Time Tracker – a Streamlit application.
Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta

from database import (
    init_db,
    create_task,
    get_tasks,
    update_task,
    delete_task,
    start_entry,
    pause_entry,
    resume_entry,
    stop_entry,
    get_active_entry,
    elapsed_seconds,
    add_manual_entry,
    get_entries,
    get_today_entries,
    get_daily_stats,
    get_range_stats,
    get_task_distribution,
    delete_entry,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Freelance Time Tracker",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ── Helpers ───────────────────────────────────────────────────────────────────


def fmt_dur(seconds):
    """Seconds → HH:MM:SS."""
    if not seconds or seconds < 0:
        return "00:00:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_hrs(seconds):
    """Seconds → X.Xh."""
    if not seconds or seconds <= 0:
        return "0.0 h"
    return f"{seconds / 3600:.1f} h"


def parse_dt(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown(
    """
<style>
    .timer-box {
        text-align: center; padding: 2rem 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 1rem; margin: 1rem 0;
    }
    .timer-box h1 { color: #fff; font-size: 4rem; font-family: monospace; margin: 0; }
    .timer-box p  { color: rgba(255,255,255,.8); margin: .25rem 0 0; }
    div[data-testid="stMetric"] {
        background: #f8f9fa; border-radius: .5rem; padding: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⏱️ Time Tracker")
    st.divider()
    page = st.radio(
        "Go to",
        ["⏱️ Timer", "📋 History", "📊 Dashboard", "⚙️ Tasks"],
        label_visibility="collapsed",
    )
    st.divider()

    # Mini active-timer widget
    active = get_active_entry()
    if active:
        el = elapsed_seconds(active)
        icon = "▶️" if active["status"] == "active" else "⏸️"
        st.markdown(f"### {icon} {active['task_name']}")
        st.markdown(f"### `{fmt_dur(el)}`")
        c1, c2 = st.columns(2)
        with c1:
            if active["status"] == "active":
                if st.button("⏸️ Pause", key="sb_p", use_container_width=True):
                    pause_entry(active["id"])
                    st.rerun()
            else:
                if st.button("▶️ Resume", key="sb_r", use_container_width=True):
                    resume_entry(active["id"])
                    st.rerun()
        with c2:
            if st.button("⏹️ Stop", key="sb_s", use_container_width=True):
                stop_entry(active["id"])
                st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
#  TIMER PAGE
# ═════════════════════════════════════════════════════════════════════════════
if page == "⏱️ Timer":
    st.header("⏱️ Timer")
    active = get_active_entry()

    if active:
        el = elapsed_seconds(active)
        status_label = "🟢 Running" if active["status"] == "active" else "🟡 Paused"

        st.markdown(
            f'<div class="timer-box"><h1>{fmt_dur(el)}</h1>'
            f"<p>{status_label} — {active['task_name']}</p></div>",
            unsafe_allow_html=True,
        )
        if active.get("notes"):
            st.caption(f"📝 {active['notes']}")

        col1, col2, col3 = st.columns(3)
        with col1:
            if active["status"] == "active":
                if st.button("⏸️  Pause", use_container_width=True, type="secondary"):
                    pause_entry(active["id"])
                    st.rerun()
            else:
                if st.button("▶️  Resume", use_container_width=True, type="primary"):
                    resume_entry(active["id"])
                    st.rerun()
        with col2:
            if st.button("⏹️  Stop", use_container_width=True, type="primary"):
                stop_entry(active["id"])
                st.balloons()
                st.rerun()
        with col3:
            if st.button("🔄  Refresh", use_container_width=True):
                st.rerun()

        # Auto-refresh while running (every ~2 s)
        if active["status"] == "active":
            try:
                from streamlit_autorefresh import st_autorefresh

                st_autorefresh(interval=2000, limit=None, key="timer_auto")
            except ImportError:
                pass  # fall back to manual refresh button
    else:
        # ── Start new timer ──────────────────────────────────────────────
        st.subheader("Start a new timer")
        tasks = get_tasks()

        if not tasks:
            st.info("No tasks yet — create one below and start tracking!")
            with st.form("quick_task"):
                new_name = st.text_input("Task name")
                if st.form_submit_button("Create & Start"):
                    if new_name.strip():
                        tid = create_task(new_name)
                        start_entry(tid)
                        st.rerun()
        else:
            task_map = {t["name"]: t["id"] for t in tasks}
            sel = st.selectbox("Task", list(task_map.keys()))
            notes = st.text_input("Notes (optional)", placeholder="What are you working on?")
            if st.button("▶️  Start Timer", type="primary", use_container_width=True):
                try:
                    start_entry(task_map[sel], notes)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

            with st.expander("➕ Quick-add a new task"):
                with st.form("new_task_inline"):
                    n = st.text_input("Name")
                    c = st.color_picker("Color", "#4CAF50")
                    if st.form_submit_button("Create"):
                        if n.strip():
                            try:
                                create_task(n, c)
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

    # ── Today's log ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📅 Today's Log")

    today_entries = get_today_entries()
    if today_entries:
        total_today = sum(e["total_seconds"] for e in today_entries)
        st.metric("Total today", fmt_hrs(total_today))
        for entry in today_entries:
            s = parse_dt(entry["start_time"])
            e = parse_dt(entry["end_time"])
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.markdown(f"**{entry['task_name']}**")
            if entry.get("notes"):
                c1.caption(entry["notes"])
            c2.text(f"{s.strftime('%I:%M %p')} → {e.strftime('%I:%M %p') if e else '…'}")
            c3.text(fmt_dur(entry["total_seconds"]))
            if c4.button("🗑️", key=f"td_{entry['id']}"):
                delete_entry(entry["id"])
                st.rerun()
    else:
        st.caption("No entries yet today.")

# ═════════════════════════════════════════════════════════════════════════════
#  HISTORY PAGE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📋 History":
    st.header("📋 History")

    hc1, hc2 = st.columns(2)
    start_d = hc1.date_input("From", date.today() - timedelta(days=30))
    end_d = hc2.date_input("To", date.today())

    entries = get_entries(start_d, end_d)
    if entries:
        total = sum(e["total_seconds"] for e in entries)
        days_span = max((end_d - start_d).days, 1)
        m1, m2, m3 = st.columns(3)
        m1.metric("Entries", len(entries))
        m2.metric("Total hours", fmt_hrs(total))
        m3.metric("Avg / day", fmt_hrs(total / days_span))

        # CSV export
        df_export = pd.DataFrame(
            [
                {
                    "Task": e["task_name"],
                    "Start": e["start_time"],
                    "End": e["end_time"],
                    "Hours": round(e["total_seconds"] / 3600, 2),
                    "Notes": e.get("notes", ""),
                }
                for e in entries
            ]
        )
        st.download_button(
            "⬇️ Export CSV",
            df_export.to_csv(index=False),
            "time_entries.csv",
            "text/csv",
        )

        st.divider()

        # Group by date
        by_date: dict[date, list] = {}
        for entry in entries:
            d = parse_dt(entry["start_time"]).date()
            by_date.setdefault(d, []).append(entry)

        for day in sorted(by_date, reverse=True):
            day_entries = by_date[day]
            day_total = sum(e["total_seconds"] for e in day_entries)
            with st.expander(
                f"📅 {day.strftime('%A, %b %d %Y')} — {fmt_hrs(day_total)}",
                expanded=(day == date.today()),
            ):
                for entry in day_entries:
                    s = parse_dt(entry["start_time"])
                    e = parse_dt(entry["end_time"])
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    c1.markdown(f"**{entry['task_name']}**")
                    if entry.get("notes"):
                        c1.caption(entry["notes"])
                    c2.text(
                        f"{s.strftime('%I:%M %p')} → {e.strftime('%I:%M %p') if e else '…'}"
                    )
                    c3.text(fmt_dur(entry["total_seconds"]))
                    if c4.button("🗑️", key=f"h_{entry['id']}"):
                        delete_entry(entry["id"])
                        st.rerun()
    else:
        st.info("No entries for this period.")

    # ── Manual entry form ────────────────────────────────────────────────
    st.divider()
    st.subheader("➕ Add Manual Entry")
    tasks = get_tasks()
    if tasks:
        with st.form("manual"):
            mc1, mc2 = st.columns(2)
            task_map = {t["name"]: t["id"] for t in tasks}
            m_task = mc1.selectbox("Task", list(task_map.keys()))
            m_date = mc2.date_input("Date", date.today())
            mc3, mc4 = st.columns(2)
            m_start = mc3.time_input("Start time", datetime.now().replace(hour=9, minute=0))
            m_end = mc4.time_input("End time", datetime.now().replace(hour=17, minute=0))
            m_notes = st.text_input("Notes")
            if st.form_submit_button("Add entry", use_container_width=True):
                try:
                    add_manual_entry(
                        task_map[m_task],
                        datetime.combine(m_date, m_start),
                        datetime.combine(m_date, m_end),
                        m_notes,
                    )
                    st.success("Entry added!")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    else:
        st.warning("Create a task first in ⚙️ Tasks.")

# ═════════════════════════════════════════════════════════════════════════════
#  DASHBOARD PAGE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📊 Dashboard":
    st.header("📊 Dashboard")

    period = st.radio(
        "Period",
        ["Today", "This Week", "This Month", "This Year", "Custom"],
        horizontal=True,
    )

    today = date.today()
    if period == "Today":
        sd, ed = today, today
    elif period == "This Week":
        sd = today - timedelta(days=today.weekday())
        ed = sd + timedelta(days=6)
    elif period == "This Month":
        sd = today.replace(day=1)
        nxt = today.replace(day=28) + timedelta(days=4)
        ed = nxt - timedelta(days=nxt.day)
    elif period == "This Year":
        sd = today.replace(month=1, day=1)
        ed = today.replace(month=12, day=31)
    else:
        dc1, dc2 = st.columns(2)
        sd = dc1.date_input("From", today - timedelta(days=30), key="ds")
        ed = dc2.date_input("To", today, key="de")

    entries = get_entries(sd, ed)
    daily_data = get_range_stats(sd, ed)
    task_data = get_task_distribution(sd, ed)

    total_sec = sum(e["total_seconds"] for e in entries) if entries else 0
    days_in_range = max((ed - sd).days + 1, 1)
    days_worked = len(daily_data)
    avg_day = total_sec / max(days_worked, 1)
    top_task = task_data[0]["name"] if task_data else "—"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Hours", fmt_hrs(total_sec))
    k2.metric("Days Worked", f"{days_worked} / {days_in_range}")
    k3.metric("Avg / Day", fmt_hrs(avg_day))
    k4.metric("Top Task", top_task)

    if not entries:
        st.info("No data for this period. Start tracking to see charts!")
    else:
        st.divider()

        # ── Row 1: hours-per-day bar + task pie ──────────────────────────
        ch1, ch2 = st.columns(2)
        with ch1:
            st.subheader("Hours by Day")
            if daily_data:
                df_d = pd.DataFrame(daily_data)
                df_d["hours"] = df_d["total_seconds"] / 3600
                df_d["day"] = pd.to_datetime(df_d["day"])
                all_days = pd.date_range(sd, min(ed, today))
                df_all = pd.DataFrame({"day": all_days})
                df_all = df_all.merge(df_d[["day", "hours"]], on="day", how="left").fillna(0)
                fig = px.bar(
                    df_all,
                    x="day",
                    y="hours",
                    labels={"day": "", "hours": "Hours"},
                    color_discrete_sequence=["#667eea"],
                )
                fig.add_hline(y=8, line_dash="dash", line_color="red", annotation_text="8 h target")
                fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), xaxis_tickformat="%b %d")
                st.plotly_chart(fig, use_container_width=True, key="hours_by_day")

        with ch2:
            st.subheader("Task Distribution")
            if task_data:
                df_t = pd.DataFrame(task_data)
                df_t["hours"] = df_t["total_seconds"] / 3600
                fig = px.pie(
                    df_t,
                    values="hours",
                    names="name",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig, use_container_width=True, key="task_distribution")

        # ── Today detail: login / logout / break ─────────────────────────
        if period == "Today":
            st.divider()
            st.subheader("Today's Details")
            stats = get_daily_stats(today)
            if stats["first_start"]:
                first = parse_dt(stats["first_start"])
                last = parse_dt(stats["last_end"])
                d1, d2, d3 = st.columns(3)
                d1.metric("Login (first start)", first.strftime("%I:%M %p"))
                d2.metric("Logout (last stop)", last.strftime("%I:%M %p") if last else "Active")
                if last:
                    span = (last - first).total_seconds()
                    brk = max(span - stats["total_seconds"], 0)
                    d3.metric("Break time", fmt_hrs(brk))

        # ── Task breakdown bars ──────────────────────────────────────────
        st.divider()
        st.subheader("Task Breakdown")
        for t in task_data:
            hrs = t["total_seconds"] / 3600
            pct = t["total_seconds"] / total_sec * 100 if total_sec else 0
            tc1, tc2, tc3 = st.columns([3, 3, 1])
            tc1.markdown(f"**{t['name']}**")
            tc2.progress(min(pct / 100, 1.0))
            tc3.text(f"{hrs:.1f} h ({pct:.0f}%)")

        # ── Weekly pattern (month / year / custom) ───────────────────────
        if period in ("This Month", "This Year", "Custom") and daily_data:
            st.divider()
            st.subheader("Weekly Pattern (avg hours)")
            df_d = pd.DataFrame(daily_data)
            df_d["day"] = pd.to_datetime(df_d["day"])
            df_d["weekday"] = df_d["day"].dt.day_name()
            df_d["hours"] = df_d["total_seconds"] / 3600
            order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            wk = df_d.groupby("weekday")["hours"].mean().reindex(order).fillna(0)
            fig = px.bar(x=wk.index, y=wk.values, labels={"x": "", "y": "Avg hours"}, color_discrete_sequence=["#764ba2"])
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True, key="weekly_pattern")

        # ── Monthly summary (year view) ──────────────────────────────────
        if period == "This Year" and daily_data:
            st.divider()
            st.subheader("Monthly Summary")
            df_d = pd.DataFrame(daily_data)
            df_d["day"] = pd.to_datetime(df_d["day"])
            df_d["month"] = df_d["day"].dt.strftime("%B")
            df_d["month_num"] = df_d["day"].dt.month
            df_d["hours"] = df_d["total_seconds"] / 3600
            df_m = (
                df_d.groupby(["month", "month_num"])
                .agg(total_hours=("hours", "sum"), days_worked=("day", "count"))
                .reset_index()
                .sort_values("month_num")
            )
            fig = px.bar(
                df_m,
                x="month",
                y="total_hours",
                text="total_hours",
                labels={"month": "", "total_hours": "Hours"},
                color_discrete_sequence=["#667eea"],
            )
            fig.update_traces(texttemplate="%{text:.1f} h", textposition="outside")
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True, key="monthly_summary")

# ═════════════════════════════════════════════════════════════════════════════
#  TASKS PAGE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Tasks":
    st.header("⚙️ Manage Tasks")

    with st.form("add_task"):
        ac1, ac2, ac3 = st.columns([4, 1, 1])
        name = ac1.text_input("Task name", placeholder="e.g. Client Project, Meetings …")
        color = ac2.color_picker("Color", "#4CAF50")
        ac3.write("")
        ac3.write("")
        submitted = ac3.form_submit_button("➕ Add")
    if submitted and name.strip():
        try:
            create_task(name, color)
            st.success(f"Task **{name}** created!")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.divider()
    tasks = get_tasks(active_only=False)
    if tasks:
        for t in tasks:
            tc1, tc2, tc3, tc4 = st.columns([5, 1, 1, 1])
            status = "🟢" if t["is_active"] else "🔴"
            tc1.markdown(f"{status} **{t['name']}**")
            tc2.markdown(
                f'<div style="width:24px;height:24px;background:{t["color"]};'
                f'border-radius:4px;margin-top:6px"></div>',
                unsafe_allow_html=True,
            )
            if t["is_active"]:
                if tc3.button("Archive", key=f"arch_{t['id']}"):
                    update_task(t["id"], is_active=False)
                    st.rerun()
            else:
                if tc3.button("Restore", key=f"rest_{t['id']}"):
                    update_task(t["id"], is_active=True)
                    st.rerun()
            if tc4.button("🗑️", key=f"del_{t['id']}"):
                delete_task(t["id"])
                st.rerun()
    else:
        st.info("No tasks yet. Create one above!")
