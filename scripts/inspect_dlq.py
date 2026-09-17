import argparse
from app.config import Settings
from app.dlq.repository import DLQRepository


parser = argparse.ArgumentParser()
parser.add_argument("--event-id")
parser.add_argument("--status")
args = parser.parse_args()
repo = DLQRepository(Settings().db_path)
print(repo.get(args.event_id) if args.event_id else repo.list(args.status))
