import argparse
import json

from research_platform.enrichment.openalex_enrichment_job import run_openalex_enrichment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpenAlex enrichment on a fixed list of paper IDs (one per line, from stdin or a file).")
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    with open(args.file) as f:
        paper_ids = [line.strip() for line in f if line.strip()]

    print(f"Batch: {len(paper_ids)} papers from {args.file}")
    result = run_openalex_enrichment(paper_ids)
    summary = {k: v for k, v in result.items() if k != "per_paper"}
    print(json.dumps(summary, indent=2))
    print()
    for p in result["per_paper"]:
        print(json.dumps(p, default=str))


if __name__ == "__main__":
    main()
