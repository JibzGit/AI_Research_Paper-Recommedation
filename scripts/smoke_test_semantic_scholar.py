"""Read-only Semantic Scholar connectivity smoke test.

Makes exactly one logical lookup (ARXIV:1706.03762) through the real
client/pacing/retry path. Never touches paper_enrichment_matches,
paper_source_records, paper_metric_snapshots, paper_references, or papers.
Never prints the API key or any request header.
"""
import json

from research_platform.config import semantic_scholar_api_key_status
from research_platform.db.session import SessionLocal
from research_platform.enrichment import semantic_scholar_client as s2_client

TEST_ARXIV_ID = "1706.03762"


def main() -> None:
    session = SessionLocal()
    try:
        call_count = 0
        saw_429 = False
        last_status = None
        real_http_get = s2_client._http_get

        def counting_http_get(url, params=None):
            nonlocal call_count, saw_429, last_status
            call_count += 1
            response = real_http_get(url, params)
            last_status = response.status_code
            if response.status_code == 429:
                saw_429 = True
            return response

        s2_client._http_get = counting_http_get
        try:
            paper = s2_client.get_paper_by_arxiv_id(session, TEST_ARXIV_ID)
        finally:
            s2_client._http_get = real_http_get  # always restore, even on failure

        report = {
            "api_key_mode": semantic_scholar_api_key_status(),
            "authenticated_mode_used": s2_client.api_key_configured(),
            "http_status": last_status,
            "s2_paper_id": paper.get("paperId") if paper else None,
            "external_ids": paper.get("externalIds") if paper else None,
            "title": paper.get("title") if paper else None,
            "year": paper.get("year") if paper else None,
            "saw_429": saw_429,
            "attempt_count": call_count,
        }
        print(json.dumps(report, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
