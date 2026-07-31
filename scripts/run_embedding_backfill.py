"""Controlled batch runner for paper embedding generation. Selects eligible
canonical papers, builds canonical text, and generates/updates embeddings
via the idempotent embedding job. No --limit means "use the configured
batch size" (config.EMBEDDING_BATCH_SIZE), not "process everything" -- an
unbounded default would risk silently running the full corpus.

    python3 scripts/run_embedding_backfill.py --arxiv-id 1601.00738 1601.01157
    python3 scripts/run_embedding_backfill.py --limit 5
"""
import argparse
import json

from research_platform import config
from research_platform.embeddings.embedding_job import run_embedding_backfill


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help=f"default: {config.EMBEDDING_BATCH_SIZE} (from EMBEDDING_BATCH_SIZE)")
    parser.add_argument("--paper-id", nargs="+", default=None, help="restrict to specific paper UUIDs")
    parser.add_argument("--arxiv-id", nargs="+", default=None, help="restrict to specific arXiv IDs")
    args = parser.parse_args()

    limit = args.limit if args.limit is not None else config.EMBEDDING_BATCH_SIZE

    result = run_embedding_backfill(paper_ids=args.paper_id, arxiv_ids=args.arxiv_id, limit=limit)

    for paper_result in result["per_paper"]:
        print(json.dumps(paper_result, default=str))

    summary = {
        "run_id": result["run_id"],
        "status": result["status"],
        "attempted": result["attempted"],
        "created": result["created"],
        "updated": result["updated"],
        "skipped": result["skipped"],
        "failed": result["failed"],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
