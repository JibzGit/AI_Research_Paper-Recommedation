import argparse
import json

from research_platform.ingestion.quota_orchestrator import DEFAULT_NEW_QUEUE_LOOKAHEAD, run_quota_ingestion

MAX_ALLOWED_QUOTA = 100  # controlled-validation guardrail; raise deliberately, not by accident


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute mode: quota-limited new+historical arXiv ingestion.")
    parser.add_argument("--quota", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--new-queue-lookahead", type=int, default=DEFAULT_NEW_QUEUE_LOOKAHEAD)
    args = parser.parse_args()

    if args.quota > MAX_ALLOWED_QUOTA:
        raise SystemExit(f"Refusing to run: quota is capped at {MAX_ALLOWED_QUOTA} for controlled validation.")

    summary = run_quota_ingestion(
        quota_limit=args.quota, page_size=args.page_size, new_queue_lookahead=args.new_queue_lookahead
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
