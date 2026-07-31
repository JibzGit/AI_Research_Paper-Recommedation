import argparse
import json
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from research_platform.db.session import SessionLocal
from research_platform.ingestion.backfill_planner import (
    APPROVED_CATEGORIES,
    estimate_plan_summary,
    month_windows,
    plan_window,
)
from research_platform.db.models import BackfillWindow


def main() -> None:
    parser = argparse.ArgumentParser(description="Full plan-only pass, month by month, with progress logging.")
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--page-size", type=int, default=200)
    args = parser.parse_args()

    start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    session = SessionLocal()
    try:
        for month_start, month_end in month_windows(start, end):
            print(f"[{datetime.now(timezone.utc).isoformat()}] planning {month_start.date()}...", flush=True)
            try:
                windows = plan_window(session, APPROVED_CATEGORIES, month_start, month_end, "monthly", args.page_size)
            except Exception as exc:
                print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR planning {month_start.date()}: {exc}", flush=True)
                print("Stopping. Already-planned months are safely committed; re-run to resume (idempotent).", flush=True)
                sys.exit(1)
            for w in windows:
                print(
                    f"  -> {w.window_granularity:8s} {w.window_start.date()} - {w.window_end.date()} "
                    f"est={w.estimated_result_count} status={w.status}",
                    flush=True,
                )

        all_windows = session.execute(select(BackfillWindow)).scalars().all()
        summary = estimate_plan_summary(all_windows)
        summary["total_monthly_windows"] = sum(1 for w in all_windows if w.window_granularity == "monthly")
        summary["total_weekly_windows"] = sum(1 for w in all_windows if w.window_granularity == "weekly")
        summary["total_daily_windows"] = sum(1 for w in all_windows if w.window_granularity == "daily")
        print("=== FINAL PLAN SUMMARY ===", flush=True)
        print(json.dumps(summary, indent=2), flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
