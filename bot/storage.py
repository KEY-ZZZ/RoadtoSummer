import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                profile_json TEXT DEFAULT '{}',
                memory_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                pre_survey_json TEXT,
                decision_json TEXT,
                plan_json TEXT,
                feedback_json TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS exercise_stats (
                telegram_id INTEGER NOT NULL,
                exercise_id TEXT NOT NULL,
                times_done INTEGER DEFAULT 0,
                feel_better_count INTEGER DEFAULT 0,
                feel_worse_count INTEGER DEFAULT 0,
                last_done TEXT,
                PRIMARY KEY (telegram_id, exercise_id)
            );
        """)


def save_user_profile(telegram_id: int, profile: dict):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET profile_json = ? WHERE telegram_id = ?",
            (json.dumps(profile), telegram_id),
        )


def get_or_create_user(telegram_id: int, username: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (telegram_id, username) VALUES (?, ?)",
                (telegram_id, username),
            )
            return {"profile": {}, "memory": {}, "is_new": True}
        return {
            "profile": json.loads(row["profile_json"]),
            "memory": json.loads(row["memory_json"]),
            "is_new": False,
        }


def save_session(telegram_id: int, pre_survey: dict, decision: dict, plan: list) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO sessions (telegram_id, pre_survey_json, decision_json, plan_json) VALUES (?, ?, ?, ?)",
            (telegram_id, json.dumps(pre_survey), json.dumps(decision), json.dumps(plan)),
        )
        return cursor.lastrowid


def save_feedback(session_id: int, feedback: dict, telegram_id: int):
    plan_row = None
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET feedback_json = ?, completed_at = datetime('now') WHERE id = ?",
            (json.dumps(feedback), session_id),
        )
        plan_row = conn.execute(
            "SELECT plan_json FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

    if plan_row and feedback.get("body_response"):
        plan = json.loads(plan_row["plan_json"])
        feel = feedback["body_response"]
        with get_conn() as conn:
            for ex in plan:
                eid = ex.get("exercise_id")
                if not eid:
                    continue
                conn.execute("""
                    INSERT INTO exercise_stats (telegram_id, exercise_id, times_done, feel_better_count, feel_worse_count, last_done)
                    VALUES (?, ?, 1, ?, ?, date('now'))
                    ON CONFLICT(telegram_id, exercise_id) DO UPDATE SET
                        times_done = times_done + 1,
                        feel_better_count = feel_better_count + excluded.feel_better_count,
                        feel_worse_count = feel_worse_count + excluded.feel_worse_count,
                        last_done = excluded.last_done
                """, (
                    telegram_id, eid,
                    1 if feel == "feel_better" else 0,
                    1 if feel == "feel_worse" else 0,
                ))


def get_user_memory(telegram_id: int) -> dict:
    with get_conn() as conn:
        user_row = conn.execute(
            "SELECT memory_json FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        memory = json.loads(user_row["memory_json"]) if user_row else {}

        recent = conn.execute("""
            SELECT pre_survey_json, decision_json, feedback_json, created_at
            FROM sessions
            WHERE telegram_id = ? AND completed_at IS NOT NULL
            ORDER BY created_at DESC LIMIT 5
        """, (telegram_id,)).fetchall()

        stats = conn.execute("""
            SELECT exercise_id, times_done, feel_better_count, feel_worse_count, last_done
            FROM exercise_stats WHERE telegram_id = ?
        """, (telegram_id,)).fetchall()

    memory["session_history"] = [
        {
            "date": r["created_at"][:10],
            "energy": json.loads(r["pre_survey_json"]).get("energy"),
            "intensity": json.loads(r["decision_json"]).get("intensity"),
            "mood_after": json.loads(r["feedback_json"] or "{}").get("mood_after"),
        }
        for r in recent
    ]

    memory["exercise_stats"] = {
        r["exercise_id"]: {
            "times_done": r["times_done"],
            "feel_better_rate": round(r["feel_better_count"] / r["times_done"], 2) if r["times_done"] else 0,
            "feel_worse_rate": round(r["feel_worse_count"] / r["times_done"], 2) if r["times_done"] else 0,
            "last_done": r["last_done"],
        }
        for r in stats
    }

    recently_used = sorted(
        [(r["exercise_id"], r["last_done"]) for r in stats if r["last_done"]],
        key=lambda x: x[1], reverse=True
    )[:5]
    memory["recently_used"] = [e for e, _ in recently_used]

    return memory
