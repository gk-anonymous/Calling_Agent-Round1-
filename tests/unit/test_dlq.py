from app.dlq.repository import DLQRepository
from app.domain.models import CallEvent
from uuid import uuid4


def make_event():
    return CallEvent(event_id=uuid4(), campaign_id="C", borrower_bucket="90+ DPD", timestamp="2026-09-01T00:00:00Z", outcome="connected")


def test_dlq_survives_restart_and_replay_status(tmp_path):
    event = make_event(); path = str(tmp_path / "dlq.sqlite3")
    first = DLQRepository(path); first.enqueue(event, "downstream_timeout", 2)
    second = DLQRepository(path)
    row = second.begin_replay(str(event.event_id))
    assert row["status"] == "PENDING" and second.get(str(event.event_id))["replay_count"] == 1
    second.finish_replay(str(event.event_id), True)
    assert second.get(str(event.event_id))["status"] == "RESOLVED"
    assert second.begin_replay(str(event.event_id)) is None
