"""
Database module for Time Tracker.
Uses SQLite to store tasks, time entries, and time segments.
"""

import sqlite3
import os
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "time_tracker.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _parse_dt(val):
    """Parse a datetime value from the DB (may be str or None)."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            color       TEXT DEFAULT '#4CAF50',
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS time_entries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id       INTEGER NOT NULL,
            start_time    TEXT NOT NULL,
            end_time      TEXT,
            status        TEXT NOT NULL DEFAULT 'active'
                          CHECK(status IN ('active','paused','completed')),
            total_seconds REAL DEFAULT 0,
            notes         TEXT DEFAULT '',
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS time_segments (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id      INTEGER NOT NULL,
            segment_start TEXT NOT NULL,
            segment_end   TEXT,
            FOREIGN KEY (entry_id) REFERENCES time_entries(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


# ── Task CRUD ─────────────────────────────────────────────────────────────────

def create_task(name, color="#4CAF50"):
    conn = _get_conn()
    cur = conn.execute("INSERT INTO tasks (name, color) VALUES (?, ?)", (name.strip(), color))
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid


def get_tasks(active_only=True):
    conn = _get_conn()
    if active_only:
        rows = conn.execute("SELECT * FROM tasks WHERE is_active=1 ORDER BY name").fetchall()
    else:
        rows = conn.execute("SELECT * FROM tasks ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_task(task_id, *, name=None, color=None, is_active=None):
    conn = _get_conn()
    if name is not None:
        conn.execute("UPDATE tasks SET name=? WHERE id=?", (name.strip(), task_id))
    if color is not None:
        conn.execute("UPDATE tasks SET color=? WHERE id=?", (color, task_id))
    if is_active is not None:
        conn.execute("UPDATE tasks SET is_active=? WHERE id=?", (int(is_active), task_id))
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = _get_conn()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


# ── Timer Operations ──────────────────────────────────────────────────────────

def get_active_entry():
    """Return the currently active or paused entry, or None."""
    conn = _get_conn()
    row = conn.execute("""
        SELECT te.*, t.name AS task_name, t.color AS task_color
        FROM time_entries te JOIN tasks t ON te.task_id = t.id
        WHERE te.status IN ('active','paused')
        ORDER BY te.start_time DESC LIMIT 1
    """).fetchone()
    if row:
        entry = dict(row)
        segs = conn.execute(
            "SELECT * FROM time_segments WHERE entry_id=? ORDER BY segment_start",
            (entry["id"],),
        ).fetchall()
        entry["segments"] = [dict(s) for s in segs]
        conn.close()
        return entry
    conn.close()
    return None


def start_entry(task_id, notes=""):
    now = datetime.now().isoformat()
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM time_entries WHERE status IN ('active','paused')"
    ).fetchone()
    if existing:
        conn.close()
        raise ValueError("An active timer already exists. Stop it first.")
    cur = conn.execute(
        "INSERT INTO time_entries (task_id, start_time, status, notes) VALUES (?,?,'active',?)",
        (task_id, now, notes),
    )
    entry_id = cur.lastrowid
    conn.execute(
        "INSERT INTO time_segments (entry_id, segment_start) VALUES (?,?)",
        (entry_id, now),
    )
    conn.commit()
    conn.close()
    return entry_id


def pause_entry(entry_id):
    now = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "UPDATE time_segments SET segment_end=? WHERE entry_id=? AND segment_end IS NULL",
        (now, entry_id),
    )
    conn.execute("UPDATE time_entries SET status='paused' WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()


def resume_entry(entry_id):
    now = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO time_segments (entry_id, segment_start) VALUES (?,?)",
        (entry_id, now),
    )
    conn.execute("UPDATE time_entries SET status='active' WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()


def stop_entry(entry_id):
    now_str = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "UPDATE time_segments SET segment_end=? WHERE entry_id=? AND segment_end IS NULL",
        (now_str, entry_id),
    )
    segs = conn.execute(
        "SELECT segment_start, segment_end FROM time_segments WHERE entry_id=?",
        (entry_id,),
    ).fetchall()
    total = 0.0
    for s in segs:
        st = _parse_dt(s["segment_start"])
        en = _parse_dt(s["segment_end"])
        if st and en:
            total += (en - st).total_seconds()
    conn.execute(
        "UPDATE time_entries SET status='completed', end_time=?, total_seconds=? WHERE id=?",
        (now_str, total, entry_id),
    )
    conn.commit()
    conn.close()


def elapsed_seconds(entry):
    """Calculate elapsed seconds for an entry dict (handles live segments)."""
    total = 0.0
    for seg in entry.get("segments", []):
        st = _parse_dt(seg["segment_start"])
        en = _parse_dt(seg["segment_end"])
        if st and en:
            total += (en - st).total_seconds()
        elif st and entry["status"] == "active":
            total += (datetime.now() - st).total_seconds()
    return total


# ── Manual Entry ──────────────────────────────────────────────────────────────

def add_manual_entry(task_id, start_time, end_time, notes=""):
    total = (end_time - start_time).total_seconds()
    if total <= 0:
        raise ValueError("End time must be after start time.")
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO time_entries (task_id,start_time,end_time,status,total_seconds,notes) "
        "VALUES (?,?,?,'completed',?,?)",
        (task_id, start_time.isoformat(), end_time.isoformat(), total, notes),
    )
    eid = cur.lastrowid
    conn.execute(
        "INSERT INTO time_segments (entry_id,segment_start,segment_end) VALUES (?,?,?)",
        (eid, start_time.isoformat(), end_time.isoformat()),
    )
    conn.commit()
    conn.close()
    return eid


# ── Queries ───────────────────────────────────────────────────────────────────

def get_entries(start_date, end_date):
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT te.*, t.name AS task_name, t.color AS task_color
        FROM time_entries te JOIN tasks t ON te.task_id=t.id
        WHERE te.status='completed'
          AND DATE(te.start_time) >= ? AND DATE(te.start_time) <= ?
        ORDER BY te.start_time DESC
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_entries():
    return get_entries(date.today(), date.today())


def get_daily_stats(target_date):
    conn = _get_conn()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(total_seconds),0) AS total_seconds,
               COUNT(*) AS entry_count,
               MIN(start_time) AS first_start,
               MAX(end_time) AS last_end
        FROM time_entries
        WHERE status='completed' AND DATE(start_time)=?
        """,
        (target_date.isoformat(),),
    ).fetchone()
    stats = dict(row)
    tasks = conn.execute(
        """
        SELECT t.name, t.color, SUM(te.total_seconds) AS total_seconds, COUNT(*) AS entry_count
        FROM time_entries te JOIN tasks t ON te.task_id=t.id
        WHERE te.status='completed' AND DATE(te.start_time)=?
        GROUP BY t.id ORDER BY total_seconds DESC
        """,
        (target_date.isoformat(),),
    ).fetchall()
    stats["tasks"] = [dict(t) for t in tasks]
    conn.close()
    return stats


def get_range_stats(start_date, end_date):
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT DATE(start_time) AS day,
               SUM(total_seconds) AS total_seconds,
               COUNT(*) AS entry_count
        FROM time_entries
        WHERE status='completed'
          AND DATE(start_time) >= ? AND DATE(start_time) <= ?
        GROUP BY DATE(start_time) ORDER BY day
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_task_distribution(start_date, end_date):
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT t.name, t.color, SUM(te.total_seconds) AS total_seconds, COUNT(*) AS entry_count
        FROM time_entries te JOIN tasks t ON te.task_id=t.id
        WHERE te.status='completed'
          AND DATE(te.start_time) >= ? AND DATE(te.start_time) <= ?
        GROUP BY t.id ORDER BY total_seconds DESC
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_entry(entry_id):
    conn = _get_conn()
    conn.execute("DELETE FROM time_segments WHERE entry_id=?", (entry_id,))
    conn.execute("DELETE FROM time_entries WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()


def update_entry_notes(entry_id, notes):
    conn = _get_conn()
    conn.execute("UPDATE time_entries SET notes=? WHERE id=?", (notes, entry_id))
    conn.commit()
    conn.close()
