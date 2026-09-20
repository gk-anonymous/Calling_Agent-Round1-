from uuid import uuid4

from app.dlq.repository import AwsDLQRepository
from app.domain.models import CallEvent


class Table:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, **kwargs):
        key = (Item["record_type"], Item["event_id"])
        if kwargs.get("ConditionExpression") and key in self.items:
            error = type("ConditionalCheckFailedException", (Exception,), {})
            raise error()
        self.items[key] = Item

    def get_item(self, Key):
        item = self.items.get((Key["record_type"], Key["event_id"]))
        return {"Item": item} if item else {}

    def update_item(self, Key, **kwargs):
        item = self.items[(Key["record_type"], Key["event_id"])]
        values = kwargs["ExpressionAttributeValues"]
        if ":replaying" in values:
            item["status"] = values[":replaying"]
            item["replay_count"] += values[":one"]
        elif ":processed_at" in values:
            item["status"] = values[":status"]
            item["processed_at"] = values[":processed_at"]
        else:
            item["status"] = values[":status"]
            item["last_error"] = values[":error"]
            item["last_failed_at"] = values[":updated"]
        return {"Attributes": item}

    def delete_item(self, Key):
        self.items.pop((Key["record_type"], Key["event_id"]), None)

    def scan(self):
        return {"Items": list(self.items.values())}


class Sqs:
    def __init__(self):
        self.messages = []

    def send_message(self, **kwargs):
        self.messages.append(kwargs)

    def receive_message(self, **kwargs):
        if not self.messages:
            return {}
        message = self.messages[0]
        return {"Messages": [{"Body": message["MessageBody"], "ReceiptHandle": "handle"}]}

    def delete_message(self, **kwargs):
        self.messages.clear()


def event():
    return CallEvent(event_id=uuid4(), campaign_id="C", borrower_bucket="0-30 DPD", timestamp="2026-09-01T00:00:00Z", outcome="connected")


def test_aws_dlq_persists_reference_and_replay_state():
    table, sqs = Table(), Sqs()
    repository = AwsDLQRepository("table", "queue", table=table, sqs=sqs)
    current = event()
    row = repository.enqueue(current, "downstream_timeout", 3)
    assert row["status"] == "PENDING"
    assert len(sqs.messages) == 1
    replay = repository.begin_replay(str(current.event_id))
    assert replay["status"] == "REPLAYING"
    repository.finish_replay(str(current.event_id), True)
    repository.acknowledge(str(current.event_id))
    assert repository.get(str(current.event_id))["status"] == "RESOLVED"
    assert not sqs.messages