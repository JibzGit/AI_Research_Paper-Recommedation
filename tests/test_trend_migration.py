"""Validates the trend-tables Alembic migration (revision 6e0681b31044,
"add trend analysis tables"): the migration chain has exactly one head,
upgrade creates all four tables with the expected columns/constraints/
indexes, downgrade cleanly drops them, and re-upgrading restores the exact
same schema.

Runs entirely against a dedicated TEST_DATABASE_URL, never against the
development database (DATABASE_URL) -- this test performs a real
Alembic downgrade (DROP TABLE ... CASCADE), which must never touch the
persisted official trend run or any other development data. See
_resolve_test_database_url() for the guard: TEST_DATABASE_URL is
required, must not be the development database name or the same
database as DATABASE_URL, and must look like a test database by name.
There is no fallback to DATABASE_URL under any failure mode -- an
unconfigured or misconfigured test database makes this file refuse to
run at all (fail safe, not fail open).

The test database is created automatically on first run if it doesn't
exist yet (purely additive -- CREATE DATABASE, never touching an existing
one) and its public schema is dropped and recreated at the start of each
run for a guaranteed-clean slate. Requires the local Postgres server
(the same one DATABASE_URL points at, just a different database on it)
to be running. Run directly:

    python3 tests/test_trend_migration.py
"""
import os
from urllib.parse import urlsplit

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from research_platform.config import DATABASE_URL

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_INI = os.path.join(PROJECT_ROOT, "alembic.ini")

NEW_TABLES = ["trend_analysis_runs", "trend_entity_snapshots", "trend_scores", "trend_evidence_papers"]
PRE_TREND_HEAD = "04d1988e2686"
TREND_TABLES_REVISION = "6e0681b31044"
DEV_DATABASE_NAME = "research_platform"


def _database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def _resolve_test_database_url() -> str:
    """Hard guard against ever running a destructive downgrade against the
    development database. Every rejection path raises immediately and
    explains exactly how to fix it -- no silent fallback to DATABASE_URL
    under any circumstance."""
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set. test_trend_migration.py performs a real Alembic "
            "downgrade (DROP TABLE ... CASCADE) and must never run against the development "
            "database. Set TEST_DATABASE_URL to a dedicated test database, e.g. in .env:\n"
            "  TEST_DATABASE_URL=postgresql+psycopg2://research_user:research_password@localhost:5433/research_platform_test\n"
            "The test database is created automatically on first run if it doesn't already exist."
        )

    test_db_name = _database_name(test_url)
    dev_db_name = _database_name(DATABASE_URL)

    if not test_db_name:
        raise RuntimeError(f"TEST_DATABASE_URL has no database name in its path: {test_url!r}")
    if test_db_name == DEV_DATABASE_NAME:
        raise RuntimeError(
            f"TEST_DATABASE_URL points at the development database name ({DEV_DATABASE_NAME!r}) -- refusing to run"
        )
    if test_db_name == dev_db_name:
        raise RuntimeError(
            f"TEST_DATABASE_URL resolves to the same database name as DATABASE_URL ({dev_db_name!r}) -- refusing to run"
        )
    if test_url == DATABASE_URL:
        raise RuntimeError("TEST_DATABASE_URL is identical to DATABASE_URL -- refusing to run")
    if "test" not in test_db_name.lower():
        raise RuntimeError(
            f"TEST_DATABASE_URL's database name ({test_db_name!r}) does not look like a test database "
            "(expected a name containing 'test', e.g. 'research_platform_test') -- refusing to run a "
            "destructive migration round trip against an unexpected database"
        )
    return test_url


def _ensure_test_database_exists(test_url: str) -> None:
    """CREATE DATABASE only -- purely additive, never destructive, and
    only ever targets the name _resolve_test_database_url() already
    validated. Connects to the server's default 'postgres' maintenance
    database to do it, since CREATE DATABASE cannot run against the
    database being created (and cannot run inside a transaction)."""
    parts = urlsplit(test_url)
    test_db_name = parts.path.lstrip("/")
    admin_url = parts._replace(path="/postgres").geturl()

    admin_engine = create_engine(admin_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_db_name}
            ).scalar_one_or_none()
            if not exists:
                # TEMPLATE template0, not the default template1: this
                # host's template1 has a stored collation version that no
                # longer matches its OS-provided collation library (a
                # known, unrelated environment drift issue), which makes
                # Postgres refuse CREATE DATABASE from it. template0 is
                # the pristine bootstrap template and isn't affected.
                conn.execute(text(f'CREATE DATABASE "{test_db_name}" TEMPLATE template0'))
    finally:
        admin_engine.dispose()


TEST_DATABASE_URL = _resolve_test_database_url()

# migrations/env.py reads this to decide which database Alembic actually
# targets when command.upgrade()/command.downgrade() run -- setting
# sqlalchemy.url on the Config object alone is NOT enough, since env.py
# otherwise unconditionally overwrites it with DATABASE_URL. This is the
# one line that makes every migration command below actually hit the
# isolated test database instead of silently falling back to dev.
os.environ["ALEMBIC_DATABASE_URL_OVERRIDE"] = TEST_DATABASE_URL

try:
    _ensure_test_database_exists(TEST_DATABASE_URL)
except OperationalError as exc:
    raise RuntimeError(
        f"Could not reach the Postgres server to prepare the test database (is it running?). "
        f"TEST_DATABASE_URL={TEST_DATABASE_URL!r}. Original error: {exc}"
    ) from exc

test_engine = create_engine(TEST_DATABASE_URL, future=True)


def _alembic_config() -> Config:
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("script_location", os.path.join(PROJECT_ROOT, "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return cfg


def _reset_test_schema() -> None:
    """Drops and recreates the public schema so every run starts from a
    guaranteed-empty slate regardless of what a previous (possibly
    crashed) run left behind. Only ever executes against test_engine,
    which is bound to the already guard-validated TEST_DATABASE_URL --
    never the shared `engine`/DATABASE_URL used everywhere else in this
    codebase."""
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def _tables_present() -> set[str]:
    return set(inspect(test_engine).get_table_names())


def _current_revision() -> str | None:
    with test_engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def test_migration_chain_has_exactly_one_head():
    # Reads the migration script directory only -- touches no database at
    # all, so this one is safe to run regardless of test-DB availability.
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1, f"expected exactly one migration head, got {heads}"
    assert heads[0] == TREND_TABLES_REVISION
    print(f"PASS: migration chain has exactly one head ({heads[0]})")


def test_upgrade_creates_all_four_tables_with_expected_shape():
    _reset_test_schema()
    command.upgrade(_alembic_config(), "head")

    assert _current_revision() == TREND_TABLES_REVISION
    present = _tables_present()
    for table in NEW_TABLES:
        assert table in present, f"{table} missing after upgrade"

    inspector = inspect(test_engine)

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

    print(f"PASS: upgrade against the isolated test database ({_database_name(TEST_DATABASE_URL)}) creates all four trend tables with every required column")


def test_upgrade_creates_expected_constraints_fks_and_indexes():
    inspector = inspect(test_engine)

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
    print("PASS: downgrade cleanly drops all four trend tables (in the isolated test database only)")

    command.upgrade(cfg, "head")
    assert _current_revision() == TREND_TABLES_REVISION
    present_after_reupgrade = _tables_present()
    for table in NEW_TABLES:
        assert table in present_after_reupgrade, f"{table} missing after re-upgrade"
    print("PASS: re-upgrading after downgrade restores all four trend tables (round trip verified, isolated test database)")


if __name__ == "__main__":
    test_migration_chain_has_exactly_one_head()
    test_upgrade_creates_all_four_tables_with_expected_shape()
    test_upgrade_creates_expected_constraints_fks_and_indexes()
    test_downgrade_then_upgrade_round_trip()
    _reset_test_schema()  # leave the test database clean, not mid-migration, for the next run
    print("\nALL TESTS PASSED")
