import argparse
import json

from sqlalchemy import select

from research_platform.db.models import PaperEnrichmentMatch
from research_platform.db.session import SessionLocal
from research_platform.enrichment.semantic_scholar_enrichment_job import run_semantic_scholar_enrichment


def get_openalex_not_found_paper_ids() -> list:
    session = SessionLocal()
    try:
        rows = session.execute(
            select(PaperEnrichmentMatch.paper_id).where(
                PaperEnrichmentMatch.source == "openalex", PaperEnrichmentMatch.match_status == "NOT_FOUND"
            )
        ).scalars().all()
        return [str(r) for r in rows]
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled Semantic Scholar test on OpenAlex NOT_FOUND papers.")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    paper_ids = get_openalex_not_found_paper_ids()[: args.limit]
    print(f"Testing {len(paper_ids)} papers previously marked NOT_FOUND by OpenAlex")

    result = run_semantic_scholar_enrichment(paper_ids)
    summary = {k: v for k, v in result.items() if k != "per_paper"}
    print(json.dumps(summary, indent=2))
    print()
    for p in result["per_paper"]:
        print(json.dumps(p, default=str))


if __name__ == "__main__":
    main()
