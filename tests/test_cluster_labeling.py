"""Validates the LLM cluster-labeling feature: structured-output validation,
evidence anti-hallucination checks, retry/timeout/rate-limit handling,
escalation from the primary to the fallback model on validation-class
failures (never on transient ones), input-hash/prompt-version-driven
caching, safe failure recording, and noise exclusion. Fully mocked at the
provider-adapter boundary -- no real Anthropic API call is ever made.

Design note: label_one_cluster() needs a real clustering_runs row to
satisfy the FK on cluster_labels, but never touches papers/paper_embeddings/
paper_cluster_assignments itself -- so these tests use ONE synthetic
ClusteringRun row (cleaned up afterward) with hand-built cluster_summary
dicts, no synthetic Paper/Category rows needed at all. Two tests
(noise-exclusion, build_llm_cluster_summaries sanity) instead read the real,
already-completed clustering run from the prior session
(084a1215-53be-4644-86e5-6f8a84b5422f) -- read-only, no LLM call.

No pytest dependency. Requires the local dev database to be running. Does
NOT call the real Anthropic API. Run directly:

    python3 tests/test_cluster_labeling.py
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import delete, select

from research_platform import config
from research_platform.clustering import labeling, prompts
from research_platform.clustering.llm_providers import (
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from research_platform.db.models import ClusterLabel, ClusteringRun
from research_platform.db.session import SessionLocal

REAL_RUN_ID = "084a1215-53be-4644-86e5-6f8a84b5422f"  # the completed live clustering run


class _FakeAdapter:
    """side_effects: list of dicts (successful structured response) or
    Exception instances to raise, consumed in call order."""

    def __init__(self, side_effects):
        self.side_effects = list(side_effects)
        self.calls: list[str] = []

    def generate(self, system_prompt, user_prompt, model, capability, timeout):
        self.calls.append(model)
        if not self.side_effects:
            raise RuntimeError("FakeAdapter exhausted side_effects")
        effect = self.side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


def _valid_response(paper_id: str, confidence: float = 0.85) -> dict:
    return {
        "cluster_name": "Test Cluster Name",
        "short_description": "A test description tying the cluster together.",
        "keywords": ["test", "cluster", "keyword"],
        "confidence": confidence,
        "evidence": [{"paper_id": paper_id, "reason": "representative of the theme"}],
    }


def _make_cluster_summary(cluster_id: int = 0) -> tuple[dict, list[str]]:
    paper_ids = [str(uuid.uuid4()) for _ in range(3)]
    summary = {
        "cluster_id": cluster_id,
        "cluster_size": 7,
        "top_keywords": ["alpha", "beta", "gamma"],
        "category_distribution": [
            {"category": "cs.LG", "count": 5, "percent": 71.4},
            {"category": "cs.AI", "count": 2, "percent": 28.6},
        ],
        "representative_papers": [
            {"paper_id": paper_ids[0], "title": "Paper One", "abstract": "Abstract one."},
            {"paper_id": paper_ids[1], "title": "Paper Two", "abstract": "Abstract two."},
            {"paper_id": paper_ids[2], "title": "Paper Three", "abstract": "Abstract three."},
        ],
        "average_membership_probability": 0.9,
        "cluster_persistence": None,
        "coherence_notes": None,
    }
    return summary, paper_ids


def _make_run(session) -> ClusteringRun:
    run = ClusteringRun(
        embedding_model="test-model",
        embedding_model_version="test-version",
        algorithm_parameters={},
        random_seed=1,
        paper_count=0,
        cluster_count=0,
        noise_count=0,
        status="SUCCEEDED",
        created_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.commit()
    return run


def _cleanup_run(session, run_id) -> None:
    session.execute(delete(ClusterLabel).where(ClusterLabel.clustering_run_id == run_id))
    session.execute(delete(ClusteringRun).where(ClusteringRun.id == run_id))
    session.commit()


def _get_label(session, run_id, cluster_id, provider, model) -> ClusterLabel | None:
    session.expire_all()
    return session.execute(
        select(ClusterLabel).where(
            ClusterLabel.clustering_run_id == run_id,
            ClusterLabel.cluster_id == cluster_id,
            ClusterLabel.provider == provider,
            ClusterLabel.model == model,
        )
    ).scalar_one_or_none()


def _with_adapter(fake_adapter):
    return patch.object(labeling, "get_provider_adapter", lambda provider: fake_adapter)


def test_valid_structured_response_stored_succeeded():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, paper_ids = _make_cluster_summary()
        fake = _FakeAdapter([_valid_response(paper_ids[0])])
        with _with_adapter(fake):
            result = labeling.label_one_cluster(session, run.id, summary)

        assert result["outcome"] == "SUCCEEDED"
        assert fake.calls == [config.CLUSTER_LABEL_PRIMARY_MODEL]

        label = _get_label(session, run.id, 0, config.CLUSTER_LABEL_PRIMARY_PROVIDER, config.CLUSTER_LABEL_PRIMARY_MODEL)
        assert label is not None
        assert label.generation_status == "SUCCEEDED"
        assert label.cluster_name == "Test Cluster Name"
        assert label.confidence == 0.85
        assert label.review_status == "PENDING_REVIEW"
        assert label.evidence == [{"paper_id": paper_ids[0], "reason": "representative of the theme"}]
        assert label.model_version == config.CLUSTER_LABEL_PRIMARY_MODEL
        print("PASS: a valid structured response is validated and stored with generation_status=SUCCEEDED")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_invalid_json_both_models_fail():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, _ = _make_cluster_summary()
        fake = _FakeAdapter([LLMResponseError("no tool_use block"), LLMResponseError("no tool_use block")])
        with _with_adapter(fake):
            result = labeling.label_one_cluster(session, run.id, summary)

        assert result["outcome"] == "FAILED"
        assert len(fake.calls) == 2  # primary, then escalated fallback
        assert fake.calls[0] == config.CLUSTER_LABEL_PRIMARY_MODEL
        assert fake.calls[1] == config.CLUSTER_LABEL_FALLBACK_MODEL

        label = _get_label(session, run.id, 0, config.CLUSTER_LABEL_PRIMARY_PROVIDER, config.CLUSTER_LABEL_PRIMARY_MODEL)
        assert label.generation_status == "FAILED"
        assert label.cluster_name is None
        assert "primary failed" in label.failure_reason and "fallback failed" in label.failure_reason
        print("PASS: an unusable/invalid response escalates to the fallback model, then FAILS cleanly with no stored content")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_missing_required_fields_escalates_and_succeeds_on_fallback():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, paper_ids = _make_cluster_summary()
        bad_response = _valid_response(paper_ids[0])
        del bad_response["confidence"]  # missing required field -> pydantic ValidationError
        fake = _FakeAdapter([bad_response, _valid_response(paper_ids[1])])
        with _with_adapter(fake):
            result = labeling.label_one_cluster(session, run.id, summary)

        assert result["outcome"] == "SUCCEEDED_FALLBACK"
        assert fake.calls == [config.CLUSTER_LABEL_PRIMARY_MODEL, config.CLUSTER_LABEL_FALLBACK_MODEL]

        label = _get_label(session, run.id, 0, config.CLUSTER_LABEL_FALLBACK_PROVIDER, config.CLUSTER_LABEL_FALLBACK_MODEL)
        assert label.generation_status == "SUCCEEDED"
        print("PASS: a response missing a required field fails Pydantic validation and escalates to the fallback model, which succeeds")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_confidence_out_of_range_rejected():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, paper_ids = _make_cluster_summary()
        bad_response = _valid_response(paper_ids[0], confidence=1.5)
        fake = _FakeAdapter([bad_response, bad_response])
        with _with_adapter(fake):
            result = labeling.label_one_cluster(session, run.id, summary)
        assert result["outcome"] == "FAILED"
        print("PASS: confidence outside [0, 1] fails Pydantic validation on both models, recorded as FAILED")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_hallucinated_evidence_paper_id_rejected():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, paper_ids = _make_cluster_summary()
        hallucinated = _valid_response(str(uuid.uuid4()))  # not one of the 3 supplied paper_ids
        fake = _FakeAdapter([hallucinated, _valid_response(paper_ids[0])])
        with _with_adapter(fake):
            result = labeling.label_one_cluster(session, run.id, summary)

        assert result["outcome"] == "SUCCEEDED_FALLBACK"
        assert len(fake.calls) == 2
        print("PASS: a hallucinated evidence paper_id is rejected on the primary model and escalates to the fallback")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_provider_timeout_retried_then_fails_without_escalation():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, _ = _make_cluster_summary()
        fake = _FakeAdapter([LLMTimeoutError("t"), LLMTimeoutError("t"), LLMTimeoutError("t")])
        with _with_adapter(fake), patch.object(config, "CLUSTER_LABEL_BASE_BACKOFF_SECONDS", 0.01):
            result = labeling.label_one_cluster(session, run.id, summary)

        assert result["outcome"] == "FAILED"
        assert len(fake.calls) == config.CLUSTER_LABEL_MAX_RETRIES
        assert all(m == config.CLUSTER_LABEL_PRIMARY_MODEL for m in fake.calls), "transient errors must not escalate to the fallback model"
        print(f"PASS: a persistent timeout is retried {config.CLUSTER_LABEL_MAX_RETRIES}x on the primary model only, then FAILS")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_rate_limit_retried_then_succeeds():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, paper_ids = _make_cluster_summary()
        fake = _FakeAdapter([LLMRateLimitError("429", retry_after="0.01"), _valid_response(paper_ids[0])])
        with _with_adapter(fake), patch.object(config, "CLUSTER_LABEL_BASE_BACKOFF_SECONDS", 0.01):
            result = labeling.label_one_cluster(session, run.id, summary)

        assert result["outcome"] == "SUCCEEDED"
        assert len(fake.calls) == 2

        label = _get_label(session, run.id, 0, config.CLUSTER_LABEL_PRIMARY_PROVIDER, config.CLUSTER_LABEL_PRIMARY_MODEL)
        assert label.retry_count == 1
        print("PASS: a rate limit is retried honoring retry_after, succeeds on the second attempt, retry_count recorded")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_retry_count_is_bounded():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, _ = _make_cluster_summary()
        fake = _FakeAdapter([LLMTimeoutError("t")] * 10)  # far more than CLUSTER_LABEL_MAX_RETRIES
        with _with_adapter(fake), patch.object(config, "CLUSTER_LABEL_BASE_BACKOFF_SECONDS", 0.01):
            result = labeling.label_one_cluster(session, run.id, summary)
        assert result["outcome"] == "FAILED"
        assert len(fake.calls) == config.CLUSTER_LABEL_MAX_RETRIES, "retries must be bounded, never unbounded"
        print(f"PASS: retries are bounded to CLUSTER_LABEL_MAX_RETRIES ({config.CLUSTER_LABEL_MAX_RETRIES}), not unbounded")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_cached_label_reused_when_input_unchanged():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, paper_ids = _make_cluster_summary()
        fake1 = _FakeAdapter([_valid_response(paper_ids[0])])
        with _with_adapter(fake1):
            result1 = labeling.label_one_cluster(session, run.id, summary)
        assert result1["outcome"] == "SUCCEEDED"

        poison = _FakeAdapter([])  # any call raises RuntimeError("exhausted") -- proves it's never invoked
        with _with_adapter(poison):
            result2 = labeling.label_one_cluster(session, run.id, summary)

        assert result2["outcome"] == "CACHED"
        assert poison.calls == []
        print("PASS: an unchanged cluster_summary is served from cache, the model is never called again")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_input_hash_change_triggers_regeneration_same_row():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, paper_ids = _make_cluster_summary()
        fake1 = _FakeAdapter([_valid_response(paper_ids[0])])
        with _with_adapter(fake1):
            labeling.label_one_cluster(session, run.id, summary)

        changed_summary = dict(summary)
        changed_summary["top_keywords"] = ["completely", "different", "keywords"]
        fake2 = _FakeAdapter([_valid_response(paper_ids[1], confidence=0.6)])
        with _with_adapter(fake2):
            result = labeling.label_one_cluster(session, run.id, changed_summary)

        assert result["outcome"] == "SUCCEEDED"
        assert len(fake2.calls) == 1, "changed input must trigger a fresh model call, not a cache hit"

        session.expire_all()
        rows = session.execute(
            select(ClusterLabel).where(ClusterLabel.clustering_run_id == run.id, ClusterLabel.cluster_id == 0)
        ).scalars().all()
        assert len(rows) == 1, "regeneration must update the same row, never insert a duplicate"
        assert rows[0].confidence == 0.6
        print("PASS: a changed input_hash triggers regeneration, updating the same row (no duplicate)")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_prompt_version_change_creates_new_row():
    session = SessionLocal()
    run = _make_run(session)
    try:
        summary, paper_ids = _make_cluster_summary()
        fake1 = _FakeAdapter([_valid_response(paper_ids[0])])
        with _with_adapter(fake1):
            labeling.label_one_cluster(session, run.id, summary)

        fake2 = _FakeAdapter([_valid_response(paper_ids[1])])
        with _with_adapter(fake2), patch.object(prompts, "PROMPT_VERSION", "v2-test"):
            result = labeling.label_one_cluster(session, run.id, summary)

        assert result["outcome"] == "SUCCEEDED"
        assert len(fake2.calls) == 1, "a prompt_version bump is a different identity, not a cache hit"

        session.expire_all()
        rows = session.execute(
            select(ClusterLabel).where(ClusterLabel.clustering_run_id == run.id, ClusterLabel.cluster_id == 0)
        ).scalars().all()
        assert len(rows) == 2, "a prompt_version change must create a new row, not overwrite the old one"
        assert {r.prompt_version for r in rows} == {"v1", "v2-test"}
        print("PASS: a prompt_version change creates a new row (distinct identity), old row untouched")
    finally:
        _cleanup_run(session, run.id)
        session.close()


def test_failed_calls_do_not_modify_clustering_assignments():
    session = SessionLocal()

    def scalar(sql):
        from sqlalchemy import text
        return session.execute(text(sql)).scalar()

    before_assignments = scalar("SELECT COUNT(*) FROM paper_cluster_assignments")
    before_runs = scalar("SELECT COUNT(*) FROM clustering_runs")

    run = _make_run(session)
    try:
        summary, _ = _make_cluster_summary()
        fake = _FakeAdapter([LLMResponseError("bad"), LLMResponseError("bad")])
        with _with_adapter(fake):
            result = labeling.label_one_cluster(session, run.id, summary)
        assert result["outcome"] == "FAILED"

        after_assignments = scalar("SELECT COUNT(*) FROM paper_cluster_assignments")
        assert after_assignments == before_assignments, "paper_cluster_assignments must never be touched by labeling"
        print("PASS: a FAILED labeling attempt leaves paper_cluster_assignments completely unchanged")
    finally:
        _cleanup_run(session, run.id)
        after_runs = scalar("SELECT COUNT(*) FROM clustering_runs")
        assert after_runs == before_runs, "clustering_runs count must return to baseline after cleanup"
        session.close()


def test_no_labels_generated_for_noise_papers():
    summaries = labeling.build_llm_cluster_summaries(REAL_RUN_ID)

    session = SessionLocal()
    from sqlalchemy import text
    cluster_count = session.execute(
        text("SELECT cluster_count FROM clustering_runs WHERE id = :rid"), {"rid": REAL_RUN_ID}
    ).scalar_one()
    session.close()

    assert len(summaries) == cluster_count, "exactly one summary per real (non-noise) cluster, never one for noise"
    for s in summaries:
        assert s["cluster_id"] is not None and s["cluster_id"] >= 0
        assert len(s["representative_papers"]) > 0
        for rp in s["representative_papers"]:
            assert rp["paper_id"] is not None, "representative paper must resolve to a real paper UUID"
    print(f"PASS: build_llm_cluster_summaries() returns exactly {cluster_count} summaries, none for noise, all with resolved paper_ids")


if __name__ == "__main__":
    test_valid_structured_response_stored_succeeded()
    test_invalid_json_both_models_fail()
    test_missing_required_fields_escalates_and_succeeds_on_fallback()
    test_confidence_out_of_range_rejected()
    test_hallucinated_evidence_paper_id_rejected()
    test_provider_timeout_retried_then_fails_without_escalation()
    test_rate_limit_retried_then_succeeds()
    test_retry_count_is_bounded()
    test_cached_label_reused_when_input_unchanged()
    test_input_hash_change_triggers_regeneration_same_row()
    test_prompt_version_change_creates_new_row()
    test_failed_calls_do_not_modify_clustering_assignments()
    test_no_labels_generated_for_noise_papers()
    print("\nALL TESTS PASSED")
