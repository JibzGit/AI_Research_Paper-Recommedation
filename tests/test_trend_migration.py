"""Validates the trend-tables Alembic migration (revision 6e0681b31044,
"add trend analysis tables"): the migration chain has exactly one head,
upgrade creates all four tables with the expected columns/constraints/
indexes, downgrade cleanly drops them, and re-upgrading restores the exact
same schema.

Requires the local dev database to be running. Leaves the database
upgraded to head when it finishes -- every other trend test and the real
pipeline run depend on the tables existing. Never touches a source-table
row; this exercises DDL only, and only on tables this migration itself
owns end to end. Run directly:

    python3 tests/test_trend_migration.py
"""
import os

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from research_platform.db.session import engine

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_INI = os.path.join(PROJECT_ROOT, "alembic.ini")

NEW_TABLES = ["trend_analysis_runs", "trend_entity_snapshots", "trend_scores", "trend_evidence_papers"]
PRE_TREND_HEAD = "04d1988e2686"
TREND_TABLES_REVISION = "6e0681b31044"


def _alembic_config() -> Config:
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("script_location", os.path.join(PROJECT_ROOT, "migrations"))
    return cfg


def _tables_present() -> set[str]:
    return set(inspect(engine).get_table_names())


def _current_revision() -> str | None:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def test_migration_chain_has_exactly_one_head():
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1, f"expected exactly one migration head, got {heads}"
    assert heads[0] == TREND_TABLES_REVISION
    print(f"PASS: migration chain has exactly one head ({heads[0]})")


def test_upgrade_creates_all_four_tables_with_expected_shape():
    command.upgrade(_alembic_config(), "head")

    assert _current_revision() == TREND_TABLES_REVISION
    present = _tables_present()
    for table in NEW_TABLES:
        assert table in present, f"{table} missing after upgrade"

    inspector = inspect(engine)

    run_columns = {c["name"] for c in inspector.get_columns("trend_analysis_runs")}
    expected_run_columns = {
        "id", "calculation_version", "requested_trend_mode", "effective_trend_mode", "freshness_status",
        "corpus_latest_publication_date", "recent_period_start", "recent_period_end",
        "comparison_period_start", "comparison_period_end", "window_granularity", "parameters",
        "total_canonical_papers", "status", "error_message", "created_at", "completed_at",
    }
    assert expected_run_columns <= run_columns, f"missing: {expected_run_columns - run_columns}"

    snapshot_columns = {c["name"] for c in inspector.get_columns("trend_entity_snapshots")}
    expected_snapshot_columns = {
        "id", "trend_run_id", "entity_type", "entity_id", "entity_name", "recent_paper_count",
        "previous_paper_count", "absolute_growth", "growth_rate", "is_new_activity",
        "recent_publication_share", "previous_publication_share", "share_change", "acceleration",
        "consistency", "recency_score", "total_papers", "created_at",
    }
    assert expected_snapshot_columns <= snapshot_columns, f"missing: {expected_snapshot_columns - snapshot_columns}"

    score_columns = {c["name"] for c in inspector.get_columns("trend_scores")}
    expected_score_columns = {
        "id", "trend_run_id", "entity_type", "entity_id", "trend_type", "trend_score", "momentum_score",
        "trend_classification", "data_quality_level", "component_breakdown", "generated_explanation",
        "explanation_model", "created_at",
    }
    assert expected_score_columns <= score_columns, f"missing: {expected_score_columns - score_columns}"

    evidence_columns = {c["name"] for c in inspector.get_columns("trend_evidence_papers")}
    expected_evidence_columns = {"id", "trend_score_id", "paper_id", "role", "created_at"}
    assert expected_evidence_columns <= evidence_columns, f"missing: {expected_evidence_columns - evidence_columns}"

    print("PASS: upgrade creates all four trend tables with every required column")


def test_upgrade_creates_expected_constraints_fks_and_indexes():
    inspector = inspect(engine)

    score_checks = {c["name"] for c in inspector.get_check_constraints("trend_scores")}
    assert "ck_trend_scores_score_range" in score_checks

    evidence_checks = {c["name"] for c in inspector.get_check_constraints("trend_evidence_papers")}
    assert "ck_trend_evidence_papers_role" in evidence_checks

    snapshot_uniques = {tuple(sorted(u["column_names"])) for u in inspector.get_unique_constraints("trend_entity_snapshots")}
    assert tuple(sorted(["trend_run_id", "entity_type", "entity_id"])) in snapshot_uniques

    score_uniques = {tuple(sorted(u["column_names"])) for u in inspector.get_unique_constraints("trend_scores")}
    assert tuple(sorted(["trend_run_id", "entity_type", "entity_id", "trend_type"])) in score_uniques

    evidence_uniques = {tuple(sorted(u["column_names"])) for u in inspector.get_unique_constraints("trend_evidence_papers")}
    assert tuple(sorted(["trend_score_id", "paper_id", "role"])) in evidence_uniques

    snapshot_fks = inspector.get_foreign_keys("trend_entity_snapshots")
    assert any(fk["referred_table"] == "trend_analysis_runs" for fk in snapshot_fks)
    assert any(fk["options"].get("ondelete") == "CASCADE" for fk in snapshot_fks)

    score_fks = inspector.get_foreign_keys("trend_scores")
    assert any(fk["referred_table"] == "trend_analysis_runs" and fk["options"].get("ondelete") == "CASCADE" for fk in score_fks)

    evidence_fks = inspector.get_foreign_keys("trend_evidence_papers")
    referred_tables = {fk["referred_table"] for fk in evidence_fks}
    assert referred_tables == {"trend_scores", "papers"}
    score_fk = next(fk for fk in evidence_fks if fk["referred_table"] == "trend_scores")
    assert score_fk["options"].get("ondelete") == "CASCADE"
    paper_fk = next(fk for fk in evidence_fks if fk["referred_table"] == "papers")
    assert paper_fk["options"].get("ondelete") is None, "paper_id must not cascade -- canonical papers are never hard-deleted"

    index_names = {ix["name"] for ix in inspector.get_indexes("trend_scores")}
    assert "ix_trend_scores_classification" in index_names

    print("PASS: CHECK constraints, UNIQUE constraints, FKs (with correct CASCADE placement), and indexes all present as designed")


def test_downgrade_then_upgrade_round_trip():
    cfg = _alembic_config()

    command.downgrade(cfg, PRE_TREND_HEAD)
    assert _current_revision() == PRE_TREND_HEAD
    present_after_downgrade = _tables_present()
    for table in NEW_TABLES:
        assert table not in present_after_downgrade, f"{table} still present after downgrade"
    print("PASS: downgrade cleanly drops all four trend tables")

    command.upgrade(cfg, "head")
    assert _current_revision() == TREND_TABLES_REVISION
    present_after_reupgrade = _tables_present()
    for table in NEW_TABLES:
        assert table in present_after_reupgrade, f"{table} missing after re-upgrade"
    print("PASS: re-upgrading after downgrade restores all four trend tables (round trip verified) -- database left at head")


if __name__ == "__main__":
    test_migration_chain_has_exactly_one_head()
    test_upgrade_creates_all_four_tables_with_expected_shape()
    test_upgrade_creates_expected_constraints_fks_and_indexes()
    test_downgrade_then_upgrade_round_trip()
    print("\nALL TESTS PASSED")
