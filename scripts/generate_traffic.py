import argparse
import asyncio
import time
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from statistics import mean

BUCKETS = ["0-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"]
PRODUCTS = ["credit_card", "bnpl", "personal_loan"]


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def target_rate(simulated_minutes: float, start_hour: float = 0) -> float:
    hour = (start_hour + simulated_minutes / 60) % 24
    for start, end in ((8, 10), (14, 16)):
        if start <= hour < end:
            return 10 + 40 * min(1, (hour - start) / 0.25)
    return 10


async def run(base_url: str, duration: float, speed: float, start_hour: float = 0, interval: float = 1.0):
    sent = 0; carried = 0.0; results = []
    started = time.monotonic()
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        while time.monotonic() - started < duration:
            simulated_minutes = (time.monotonic() - started) * speed
            rate = target_rate(simulated_minutes, start_hour)
            exact_count = rate * interval / 60 + carried
            count = int(exact_count)
            carried = exact_count - count
            if count == 0:
                await asyncio.sleep(interval)
                continue
            events = [{"event_id": str(uuid4()), "campaign_id": "CAMP-2026-09-A", "borrower_bucket": BUCKETS[sent % 4], "product_type": PRODUCTS[sent % 3], "timestamp": datetime.now(timezone.utc).isoformat(), "outcome": "connected", "call_duration_s": 30} for _ in range(count)]
            responses = await asyncio.gather(*(client.post("/events/process", json=event) for event in events))
            results.extend([response.json() for response in responses])
            sent += len(responses)
            print(f"simulated_minute={simulated_minutes:.1f} target_rate={rate:.1f} sent={sent}")
            await asyncio.sleep(interval)
    latencies = [item["total_latency_ms"] for item in results]
    successes = sum(item["success"] for item in results)
    retries = sum(item["retry_count"] for item in results)
    dlq_events = sum(1 for item in results if item.get("dlq_status"))
    print(f"summary total={sent} successful={successes} failed={sent-successes} retry_attempts={retries} dlq_events={dlq_events} average_latency_ms={mean(latencies) if latencies else 0:.2f} p50={percentile(latencies,.5) if latencies else 0:.2f} p90={percentile(latencies,.9) if latencies else 0:.2f} p99={percentile(latencies,.99) if latencies else 0:.2f}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--duration-seconds", type=float, default=60)
    parser.add_argument("--speed", type=float, default=60, help="simulated minutes per real minute")
    parser.add_argument("--start-hour", type=float, default=0, help="simulated hour at the start of the run")
    args = parser.parse_args()
    print(asyncio.run(run(args.base_url, args.duration_seconds, args.speed, args.start_hour)))


if __name__ == "__main__":
    main()
