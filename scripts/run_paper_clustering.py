"""Runs the UMAP+HDBSCAN clustering pipeline once over all eligible papers
and prints the run summary plus a per-cluster report. Read-only with
respect to papers/paper_embeddings -- only ever writes to clustering_runs
and paper_cluster_assignments.

    python3 scripts/run_paper_clustering.py
    python3 scripts/run_paper_clustering.py --random-seed 7
"""
import argparse
import json

from research_platform.clustering.pipeline import describe_run, run_clustering


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()

    summary = run_clustering(random_seed=args.random_seed)
    print(json.dumps(summary, indent=2))

    report = describe_run(summary["run_id"])
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
