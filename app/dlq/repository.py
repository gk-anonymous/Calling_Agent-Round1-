import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


class AwsDLQRepository:
    """DynamoDB-backed DLQ records with SQS event references."""

    def __init__(self, table_name: str, queue_url: str, *, table: Any = None, sqs: Any = None):
        if not table_name or not queue_url:
            raise ValueError("AWS DLQ requires AWS_DLQ_TABLE and AWS_DLQ_QUEUE_URL")
        if table is None or sqs is None:
            import boto3
            table = table or boto3.resource("dynamodb").Table(table_name)
            sqs = sqs or boto3.client("sqs")
        self.table = table
        self.sqs = sqs
        self.queue_url = queue_url

    @staticmethod
    def _key(record_type: str, event_id: str) -> dict:
        return {"record_type": record_type, "event_id": event_id}

    def enqueue(self, event, reason: str, retry_count: int) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        event_id = str(event.event_id)
        item = {
            **self._key("DLQ", event_id),
            "campaign_id": event.campaign_id,
            "original_payload": event.model_dump_json(),
            "failure_reason": reason,
            "retry_count": retry_count,
            "first_failed_at": now,
            "last_failed_at": now,
            "status": "PENDING",
            "replay_count": 0,
            "last_error": reason,
        }
        self.table.put_item(Item=item)
        self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=json.dumps({"event_id": event_id}))
        return item

    def get(self, event_id: str):
        response = self.table.get_item(Key=self._key("DLQ", event_id))
        return response.get("Item")

    def claim_event(self, event_id: str) -> bool:
        try:
            self.table.put_item(
                Item={**self._key("PROCESSED", event_id), "status": "PROCESSING", "processed_at": datetime.now(timezone.utc).isoformat()},
                ConditionExpression="attribute_not_exists(record_type)",
            )
            return True
        except Exception as exc:
            if exc.__class__.__name__ != "ConditionalCheckFailedException":
                raise
            return False

    def mark_processed(self, event_id: str) -> None:
        self.table.update_item(
            Key=self._key("PROCESSED", event_id),
            UpdateExpression="SET #status = :status, processed_at = :processed_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "COMPLETED", ":processed_at": datetime.now(timezone.utc).isoformat()},
        )

    def release_event(self, event_id: str) -> None:
        self.table.delete_item(Key=self._key("PROCESSED", event_id))

    def list(self, status: str | None = None):
        response = self.table.scan()
        rows = [item for item in response.get("Items", []) if item.get("record_type") == "DLQ"]
        if status:
            rows = [item for item in rows if item.get("status") == status]
        return sorted(rows, key=lambda item: item.get("last_failed_at", ""), reverse=True)

    def begin_replay(self, event_id: str):
        row = self.get(event_id)
        if not row or row.get("status") == "RESOLVED":
            return None
        try:
            response = self.table.update_item(
                Key=self._key("DLQ", event_id),
                UpdateExpression="SET #status = :replaying ADD replay_count :one",
                ConditionExpression="#status IN (:pending, :failed)",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":replaying": "REPLAYING", ":pending": "PENDING", ":failed": "FAILED", ":one": 1},
                ReturnValues="ALL_NEW",
            )
            return response.get("Attributes")
        except Exception as exc:
            if exc.__class__.__name__ == "ConditionalCheckFailedException":
                return None
            raise

    def finish_replay(self, event_id: str, success: bool, error: str = ""):
        self.table.update_item(
            Key=self._key("DLQ", event_id),
            UpdateExpression="SET #status = :status, last_error = :error, last_failed_at = :updated",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "RESOLVED" if success else "FAILED", ":error": error, ":updated": datetime.now(timezone.utc).isoformat()},
        )

    def acknowledge(self, event_id: str) -> None:
        response = self.sqs.receive_message(QueueUrl=self.queue_url, MaxNumberOfMessages=10, VisibilityTimeout=0)
        for message in response.get("Messages", []):
            try:
                reference = json.loads(message["Body"])
            except (KeyError, json.JSONDecodeError):
                continue
            if reference.get("event_id") == event_id:
                self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"])
                return

    @staticmethod
    def decode_event(row):
        from app.domain.models import CallEvent
        return CallEvent.model_validate(json.loads(row["original_payload"]))


def create_repository(settings):
    if settings.dlq_backend.lower() == "aws":
        return AwsDLQRepository(settings.aws_dlq_table, settings.aws_dlq_queue_url)
    return DLQRepository(settings.db_path)
