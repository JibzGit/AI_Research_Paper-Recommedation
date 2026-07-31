"""Ad hoc similar-paper recommendation runner against the existing
paper_embeddings table. Read-only: never generates or modifies embeddings.

    python3 scripts/run_similar_papers.py --arxiv-id 1601.01280 --top-k 5
    python3 scripts/run_similar_papers.py --paper-id <uuid> --category cs.CL
"""
import argparse
import json

from sqlalchemy import select

from research_platform.db.models import Paper
from research_platform.db.session import SessionLocal
from research_platform.embeddings.recommend import similar_papers


def _resolve_paper_id(arxiv_id: str | None, paper_id: str | None) -> str:
    if paper_id:
        return paper_id
    session = SessionLocal()
    try:
        resolved = session.execute(select(Paper.id).where(Paper.arxiv_id == arxiv_id)).scalar_one_or_none()
        if resolved is None:
            raise SystemExit(f"no paper found with arxiv_id={arxiv_id!r}")
        return str(resolved)
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--paper-id")
    group.add_argument("--arxiv-id")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--category", default=None)
    parser.add_argument("--year-from", type=int, default=None)
    parser.add_argument("--year-to", type=int, default=None)
    parser.add_argument("--min-similarity", type=float, default=None)
    args = parser.parse_args()

    paper_id = _resolve_paper_id(args.arxiv_id, args.paper_id)

    results = similar_papers(
        paper_id=paper_id,
        top_k=args.top_k,
        category=args.category,
        year_from=args.year_from,
        year_to=args.year_to,
        min_similarity=args.min_similarity,
    )

    print(json.dumps(results, default=str, indent=2))


if __name__ == "__main__":
    main()
