import argparse
import json
from datetime import datetime, timezone

from research_platform.db.session import SessionLocal
from research_platform.ingestion.backfill_planner import APPROVED_CATEGORIES, estimate_plan_summary, plan_backfill


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan-only mode: generate adaptive backfill windows. Does not fetch or insert papers.")
    parser.add_argument("--start-date", default="2016-01-01", help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD (exclusive)")
    parser.add_argument("--page-size", type=int, default=200)
    args = parser.parse_args()

    start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    session = SessionLocal()
    try:
        windows = plan_backfill(session, start, end, categories=APPROVED_CATEGORIES, page_size=args.page_size)
        summary = estimate_plan_summary(windows)
        print(json.dumps(summary, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
