import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class DLQRepository:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS dead_letters (
                event_id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, original_payload TEXT NOT NULL,
                failure_reason TEXT NOT NULL, retry_count INTEGER NOT NULL, first_failed_at TEXT NOT NULL,
                last_failed_at TEXT NOT NULL, status TEXT NOT NULL, replay_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL)""")
            conn.execute("CREATE TABLE IF NOT EXISTS processed_events (event_id TEXT PRIMARY KEY, processed_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'COMPLETED')")

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def enqueue(self, event, reason: str, retry_count: int) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        payload = event.model_dump_json()
        with self._connect() as conn:
            conn.execute("""INSERT INTO dead_letters(event_id,campaign_id,original_payload,failure_reason,retry_count,
                first_failed_at,last_failed_at,status,replay_count,last_error) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(event_id) DO UPDATE SET last_failed_at=excluded.last_failed_at,
                retry_count=excluded.retry_count,last_error=excluded.last_error,status='FAILED'""",
                (str(event.event_id), event.campaign_id, payload, reason, retry_count, now, now, "PENDING", 0, reason))
        return self.get(str(event.event_id))

    def get(self, event_id: str):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM dead_letters WHERE event_id=?", (event_id,)).fetchone()
        return dict(row) if row else None

    def claim_event(self, event_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM processed_events WHERE event_id=?", (event_id,)).fetchone()
            if row:
                return False
            conn.execute("INSERT INTO processed_events(event_id, processed_at, status) VALUES(?, ?, 'PROCESSING')",
                         (event_id, datetime.now(timezone.utc).isoformat()))
            return True

    def mark_processed(self, event_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE processed_events SET processed_at=?, status='COMPLETED' WHERE event_id=?",
                         (datetime.now(timezone.utc).isoformat(), event_id))

    def release_event(self, event_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM processed_events WHERE event_id=? AND status='PROCESSING'", (event_id,))

    def list(self, status: str | None = None):
        with self._connect() as conn:
            query = "SELECT * FROM dead_letters"
            args = ()
            if status:
                query += " WHERE status=?"
                args = (status,)
            query += " ORDER BY last_failed_at DESC"
            return [dict(row) for row in conn.execute(query, args).fetchall()]

    def begin_replay(self, event_id: str):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM dead_letters WHERE event_id=?", (event_id,)).fetchone()
            if not row or row["status"] == "RESOLVED":
                return None
            conn.execute("UPDATE dead_letters SET status='REPLAYING', replay_count=replay_count+1 WHERE event_id=?", (event_id,))
            return dict(row)

    def finish_replay(self, event_id: str, success: bool, error: str = ""):
        with self._connect() as conn:
            conn.execute("UPDATE dead_letters SET status=?, last_error=?, last_failed_at=? WHERE event_id=?",
                         ("RESOLVED" if success else "FAILED", error, datetime.now(timezone.utc).isoformat(), event_id))

    @staticmethod
    def decode_event(row):
        from app.domain.models import CallEvent
        return CallEvent.model_validate(json.loads(row["original_payload"]))
