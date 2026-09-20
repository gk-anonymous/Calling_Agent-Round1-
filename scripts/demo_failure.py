"""Run a controlled failure/recovery demo against the deployed API."""

import argparse
import json
import time
import uuid
from datetime import datetime, timezone

import httpx


def event():
    return {
        "event_id": str(uuid.uuid4()),
        "campaign_id": "controlled-failure-demo",
        "borrower_bucket": "31-60 DPD",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome": "connected",
        "product_type": "personal_loan",
        "call_duration_s": 90,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    with httpx.Client(timeout=15) as client:
        results = [client.post(f"{args.base_url.rstrip('/')}/events/process", json=event()).json() for _ in range(args.count)]
        metrics = client.get(f"{args.base_url.rstrip('/')}/metrics").json()
        dlq = client.get(f"{args.base_url.rstrip('/')}/dlq?status=PENDING").json()
    print(json.dumps({"results": results, "metrics": metrics, "pending_dlq": dlq}, indent=2))


if __name__ == "__main__":
    main()