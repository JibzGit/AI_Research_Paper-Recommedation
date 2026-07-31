import argparse
import json

from research_platform.trends.metrics import DEFAULT_MIN_SUPPORT_PERIOD, DEFAULT_MIN_SUPPORT_TOTAL
from research_platform.trends.pipeline import (
    CALCULATION_VERSION,
    DEFAULT_COHORT_GAP_DAYS,
    DEFAULT_EVIDENCE_LIMIT,
    run_historical_cohort_pipeline,
)


def _serialize_result(result: dict) -> dict:
    entity = result["entity"]
    return {
        "entity_type": entity.entity_type,
        "entity_id": entity.entity_id,
        "entity_name": entity.entity_name,
        "recent_count": entity.recent_count,
        "previous_count": entity.previous_count,
        "total_papers": result["total_papers"],
        "absolute_growth": result["absolute_growth"],
        "growth_rate": result["growth_rate"],
        "is_new_activity": result["is_new_activity"],
        "recent_share": result["recent_share"],
        "previous_share": result["previous_share"],
        "share_change": result["share_change"],
        "trend_score": result["trend_score"],
        "momentum_score": result["momentum"],
        "trend_classification": result["trend_classification"],
        "data_quality_level": result["data_quality_level"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Historical Cohort Comparison trend pipeline (compares the corpus's two "
            "ingestion batches; not a continuous trend, and never a Current Trend Mode result)."
        )
    )
    parser.add_argument("--calculation-version", default=CALCULATION_VERSION)
    parser.add_argument("--min-support-total", type=int, default=DEFAULT_MIN_SUPPORT_TOTAL)
    parser.add_argument("--min-support-period", type=int, default=DEFAULT_MIN_SUPPORT_PERIOD)
    parser.add_argument("--evidence-limit", type=int, default=DEFAULT_EVIDENCE_LIMIT)
    parser.add_argument("--cohort-gap-days", type=int, default=DEFAULT_COHORT_GAP_DAYS)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and print a summary only -- persists no TrendAnalysisRun, snapshot, score, or evidence rows.",
    )
    args = parser.parse_args()

    summary = run_historical_cohort_pipeline(
        calculation_version=args.calculation_version,
        min_support_total=args.min_support_total,
        min_support_period=args.min_support_period,
        evidence_limit=args.evidence_limit,
        cohort_gap_days=args.cohort_gap_days,
        dry_run=args.dry_run,
    )

    cohorts = summary["cohorts"]
    output = {
        "run_id": summary["run_id"],
        "status": summary["status"],
        "dry_run": summary["dry_run"],
        "trend_mode_label": "Historical Cohort Comparison",
        "freshness_status": summary["freshness_status"],
        "comparison_period": {
            "start": cohorts.comparison_start.isoformat(),
            "end": cohorts.comparison_end.isoformat(),
        },
        "recent_period": {
            "start": cohorts.recent_start.isoformat(),
            "end": cohorts.recent_end.isoformat(),
        },
        "cluster_count": len(summary["cluster_results"]),
        "category_count": len(summary["category_results"]),
        "clusters": [_serialize_result(r) for r in summary["cluster_results"]],
        "categories": [_serialize_result(r) for r in summary["category_results"]],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
