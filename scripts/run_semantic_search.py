"""Ad hoc semantic-search runner against the existing paper_embeddings
table. Read-only: never generates or modifies embeddings.

    python3 scripts/run_semantic_search.py --query "graph neural networks" --top-k 5
    python3 scripts/run_semantic_search.py --query "..." --category cs.LG --year-from 2020
"""
import argparse
import json

from research_platform.embeddings.search import search_papers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--category", default=None)
    parser.add_argument("--year-from", type=int, default=None)
    parser.add_argument("--year-to", type=int, default=None)
    parser.add_argument("--min-similarity", type=float, default=None)
    args = parser.parse_args()

    results = search_papers(
        query=args.query,
        top_k=args.top_k,
        category=args.category,
        year_from=args.year_from,
        year_to=args.year_to,
        min_similarity=args.min_similarity,
    )

    print(json.dumps(results, default=str, indent=2))


if __name__ == "__main__":
    main()
