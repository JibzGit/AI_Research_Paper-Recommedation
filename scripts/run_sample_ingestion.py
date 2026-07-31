import argparse
import json

from research_platform.ingestion.arxiv_job import run_sample_ingestion

APPROVED_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.IR", "cs.CV", "cs.SI"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small, controlled arXiv sample ingestion (not a backfill).")
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--categories", nargs="+", default=APPROVED_CATEGORIES)
    args = parser.parse_args()

    if args.max_results > 25:
        raise SystemExit("Refusing to run: sample ingestion is capped at 25 papers.")

    summary = run_sample_ingestion(categories=args.categories, max_results=args.max_results)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
