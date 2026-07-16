"""SQLite persistence — stores triage results."""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class Database:
    def __init__(self, config):
        raw_path = config.get("database.path", "~/.local/share/inboxguard/emails.db")
        db_path = Path(raw_path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS emails (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id    TEXT    UNIQUE,
                    sender        TEXT,
                    subject       TEXT,
                    date          TEXT,
                    action        TEXT,
                    priority      TEXT,
                    summary       TEXT,
                    reason        TEXT,
                    processed_at  TEXT,
                    raw_snippet   TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_msg_id  ON emails(message_id);
                CREATE INDEX IF NOT EXISTS idx_proc_at ON emails(processed_at);
                CREATE INDEX IF NOT EXISTS idx_action  ON emails(action);
            """)
            self.conn.commit()

    def is_processed(self, message_id: str) -> bool:
        with self._lock:
            cur = self.conn.execute(
                "SELECT 1 FROM emails WHERE message_id = ?", (message_id,)
            )
            return cur.fetchone() is not None

    def save_result(self, email: dict, result: dict):
        with self._lock:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO emails
                    (message_id, sender, subject, date,
                     action, priority, summary, reason,
                     processed_at, raw_snippet)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    email["message_id"],
                    email.get("sender", ""),
                    email.get("subject", ""),
                    email.get("date", ""),
                    result.get("action", "summary"),
                    result.get("priority", "normal"),
                    result.get("summary", ""),
                    result.get("reason", ""),
                    datetime.now().isoformat(timespec="seconds"),
                    email.get("snippet", "")[:500],
                ),
            )
            self.conn.commit()

    def get_recent(self, limit: int = 50, action: str = None) -> List[Dict]:
        with self._lock:
            if action and action != "all":
                cur = self.conn.execute(
                    "SELECT * FROM emails WHERE action=? ORDER BY processed_at DESC LIMIT ?",
                    (action, limit),
                )
            else:
                cur = self.conn.execute(
                    "SELECT * FROM emails ORDER BY processed_at DESC LIMIT ?", (limit,)
                )
            return [dict(row) for row in cur.fetchall()]

    def get_stats(self) -> Dict:
        with self._lock:
            cur = self.conn.execute(
                "SELECT action, COUNT(*) AS cnt FROM emails GROUP BY action"
            )
            stats = {row["action"]: row["cnt"] for row in cur.fetchall()}
        total = sum(stats.values())
        return {"total": total, **stats}

    def clear_old(self, keep_days: int = 30):
        """Delete records older than keep_days."""
        with self._lock:
            self.conn.execute(
                "DELETE FROM emails WHERE processed_at < datetime('now', ?)",
                (f"-{keep_days} days",),
            )
            self.conn.commit()
