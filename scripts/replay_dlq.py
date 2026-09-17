import argparse
import asyncio
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:8000")
parser.add_argument("--event-id")
parser.add_argument("--pending", action="store_true")
args = parser.parse_args()


async def main():
    async with httpx.AsyncClient(base_url=args.base_url, timeout=120) as client:
        if args.pending:
            response = await client.post("/dlq/replay-pending")
        elif args.event_id:
            response = await client.post(f"/dlq/{args.event_id}/replay")
        else:
            parser.error("provide --event-id or --pending")
        response.raise_for_status()
        print(response.json())


if __name__ == "__main__":
    asyncio.run(main())
