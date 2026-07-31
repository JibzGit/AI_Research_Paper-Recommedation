import hashlib
import json
import time
from datetime import datetime, timezone

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from research_platform import config
from research_platform.clustering import prompts
from research_platform.clustering.label_schemas import ClusterLabelResult
from research_platform.clustering.llm_providers import (
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    LLMTransientError,
    get_model_capability,
    get_provider_adapter,
)
from research_platform.clustering.pipeline import describe_run
from research_platform.db.models import ClusterLabel, Paper
from research_platform.db.session import SessionLocal

LOW_PROBABILITY_THRESHOLD = 0.8
SCATTERED_CATEGORY_MIN_CATEGORIES = 3
SCATTERED_CATEGORY_MAX_TOP_PERCENT = 60.0
MAX_ABSTRACT_CHARS = 500


class EvidenceHallucinationError(ValueError):
    """Raised when a generated evidence[].paper_id is not one of the
    paper_ids actually supplied in the cluster summary -- the concrete
    enforcement mechanism behind "no invented papers" (prompts.SYSTEM_PROMPT
    rule 7), not just an instruction the model is trusted to follow."""


def _truncate_abstract(abstract: str, max_chars: int = MAX_ABSTRACT_CHARS) -> str:
    """Truncates at the nearest sentence boundary within max_chars, falling
    back to a word boundary, never mid-word. Always marks truncation with
    a trailing '...' so it's visible to a human reviewer."""
    if len(abstract) <= max_chars:
        return abstract
    truncated = abstract[:max_chars]
    last_period = truncated.rfind(". ")
    if last_period > max_chars * 0.5:
        return truncated[: last_period + 1] + ".."
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."


def _derive_coherence_notes(average_membership_probability: float, category_distribution: list[dict]) -> str | None:
    """Cheap, deterministic pre-interpretation of stats already in the
    payload -- not free-text commentary the model invents. Flags weak
    signals explicitly so the model doesn't have to re-derive "0.70 is
    low" itself."""
    notes = []
    if average_membership_probability < LOW_PROBABILITY_THRESHOLD:
        notes.append(
            f"average membership probability is {average_membership_probability:.2f}, below "
            f"{LOW_PROBABILITY_THRESHOLD} -- treat this cluster's boundary as fuzzy"
        )
    if category_distribution:
        top_percent = category_distribution[0]["percent"]
        if len(category_distribution) >= SCATTERED_CATEGORY_MIN_CATEGORIES and top_percent < SCATTERED_CATEGORY_MAX_TOP_PERCENT:
            notes.append(
                f"category distribution is scattered across {len(category_distribution)} categories "
                f"(largest is only {top_percent}%)"
            )
    return "; ".join(notes) if notes else None


def build_llm_cluster_summaries(clustering_run_id: str) -> list[dict]:
    """Builds the LLM-ready input (design §1) for every non-noise cluster in
    a run, by enriching pipeline.describe_run()'s report with each
    representative paper's real paper_id (UUID) and a safely-truncated
    abstract -- describe_run() doesn't expose either (it's built for human/
    report reading). Read-only; never modifies clustering tables or papers.

    cluster_persistence is intentionally always None: HDBSCAN's per-cluster
    persistence values are not currently persisted anywhere in the schema
    (pipeline.run_clustering() only returns them transiently in its return
    value) -- a known, deliberate gap, out of scope for this labeling
    feature to fix; flagged here rather than silently worked around.
    """
    report = describe_run(clustering_run_id)

    all_arxiv_ids = {rp["arxiv_id"] for cluster in report["clusters"] for rp in cluster["representative_papers"]}

    session = SessionLocal()
    try:
        rows = session.execute(
            select(Paper.id, Paper.arxiv_id, Paper.abstract).where(Paper.arxiv_id.in_(all_arxiv_ids))
        ).all()
        lookup = {row.arxiv_id: (str(row.id), row.abstract) for row in rows}
    finally:
        session.close()

    summaries = []
    for cluster in report["clusters"]:
        representative_papers = []
        for rp in cluster["representative_papers"]:
            paper_id, abstract = lookup.get(rp["arxiv_id"], (None, ""))
            representative_papers.append(
                {"paper_id": paper_id, "title": rp["title"], "abstract": _truncate_abstract(abstract or "")}
            )
        summaries.append(
            {
                "cluster_id": cluster["cluster_id"],
                "cluster_size": cluster["size"],
                "top_keywords": cluster["top_keywords"],
                "category_distribution": cluster["category_distribution"],
                "representative_papers": representative_papers,
                "average_membership_probability": cluster["average_membership_probability"],
                "cluster_persistence": None,
                "coherence_notes": _derive_coherence_notes(
                    cluster["average_membership_probability"], cluster["category_distribution"]
                ),
            }
        )
    return summaries


def _compute_input_hash(cluster_summary: dict) -> str:
    canonical = json.dumps(cluster_summary, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _call_with_retries(adapter, system_prompt: str, user_prompt: str, model: str, capability) -> tuple[dict, int]:
    """Retries only transient failures (timeout/rate-limit/5xx) with
    exponential backoff, honoring a rate-limit's retry_after hint when
    present. A schema/evidence validation failure is a different class of
    problem, handled by label_one_cluster's escalation-to-fallback-model
    logic, not retried here."""
    attempts = 0
    last_exc: Exception | None = None
    while attempts < config.CLUSTER_LABEL_MAX_RETRIES:
        attempts += 1
        try:
            raw = adapter.generate(
                system_prompt, user_prompt, model, capability, timeout=config.CLUSTER_LABEL_TIMEOUT_SECONDS
            )
            return raw, attempts - 1
        except (LLMTimeoutError, LLMTransientError, LLMRateLimitError) as exc:
            last_exc = exc
            if attempts >= config.CLUSTER_LABEL_MAX_RETRIES:
                raise
            delay = config.CLUSTER_LABEL_BASE_BACKOFF_SECONDS * (2 ** (attempts - 1))
            retry_after = getattr(exc, "retry_after", None)
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except (TypeError, ValueError):
                    pass
            time.sleep(delay)
    raise last_exc  # pragma: no cover -- loop always returns or raises above


def generate_cluster_label(
    cluster_summary: dict, provider: str | None = None, model: str | None = None
) -> tuple[ClusterLabelResult, int]:
    """Pure: no DB access, no caching decision. Raises LLMProviderError /
    pydantic.ValidationError / EvidenceHallucinationError on failure --
    callers (label_one_cluster) decide fallback/escalation/storage. This is
    the provider-independent entry point: swapping provider/model changes
    nothing about the calling contract."""
    provider = provider or config.CLUSTER_LABEL_PRIMARY_PROVIDER
    model = model or config.CLUSTER_LABEL_PRIMARY_MODEL
    capability = get_model_capability(provider, model)
    adapter = get_provider_adapter(provider)

    allowed_paper_ids = {
        rp["paper_id"] for rp in cluster_summary.get("representative_papers", []) if rp.get("paper_id")
    }

    system_prompt = prompts.SYSTEM_PROMPT
    user_prompt = prompts.build_user_prompt(cluster_summary)

    raw, retry_count = _call_with_retries(adapter, system_prompt, user_prompt, model, capability)
    result = ClusterLabelResult.model_validate(raw)

    for item in result.evidence:
        if item.paper_id not in allowed_paper_ids:
            raise EvidenceHallucinationError(
                f"evidence references paper_id {item.paper_id!r}, not present in the "
                f"{len(allowed_paper_ids)} representative papers supplied for this cluster"
            )

    return result, retry_count


def _existing_label(session, clustering_run_id, cluster_id, provider, model, model_version, prompt_version):
    return session.execute(
        select(ClusterLabel).where(
            ClusterLabel.clustering_run_id == clustering_run_id,
            ClusterLabel.cluster_id == cluster_id,
            ClusterLabel.provider == provider,
            ClusterLabel.model == model,
            ClusterLabel.model_version == model_version,
            ClusterLabel.prompt_version == prompt_version,
        )
    ).scalar_one_or_none()


def _upsert_label(
    session,
    clustering_run_id,
    cluster_id: int,
    provider: str,
    model: str,
    model_version: str,
    input_hash: str,
    temperature: float | None,
    retry_count: int,
    status: str,
    failure_reason: str | None,
    result: ClusterLabelResult | None,
) -> None:
    """Upserts on the (run, cluster, provider, model, model_version,
    prompt_version) identity -- a regenerated label updates the same row
    in place (like PaperEmbedding's source_text_hash pattern), never
    duplicates. review_status resets to PENDING_REVIEW on every
    (re)generation: a previously-approved label must be re-reviewed if its
    content changes, never silently carried forward as still-approved."""
    now = datetime.now(timezone.utc)
    values = dict(
        clustering_run_id=clustering_run_id,
        cluster_id=cluster_id,
        provider=provider,
        model=model,
        model_version=model_version,
        prompt_version=prompts.PROMPT_VERSION,
        input_hash=input_hash,
        temperature=temperature,
        generation_status=status,
        failure_reason=failure_reason,
        retry_count=retry_count,
        review_status="PENDING_REVIEW",
        generated_at=now if status == "SUCCEEDED" else None,
        cluster_name=result.cluster_name if result else None,
        short_description=result.short_description if result else None,
        keywords=result.keywords if result else None,
        confidence=result.confidence if result else None,
        evidence=[item.model_dump() for item in result.evidence] if result else None,
    )
    stmt = pg_insert(ClusterLabel).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["clustering_run_id", "cluster_id", "provider", "model", "model_version", "prompt_version"],
        set_={
            "input_hash": stmt.excluded.input_hash,
            "temperature": stmt.excluded.temperature,
            "generation_status": stmt.excluded.generation_status,
            "failure_reason": stmt.excluded.failure_reason,
            "retry_count": stmt.excluded.retry_count,
            "review_status": "PENDING_REVIEW",
            "generated_at": stmt.excluded.generated_at,
            "cluster_name": stmt.excluded.cluster_name,
            "short_description": stmt.excluded.short_description,
            "keywords": stmt.excluded.keywords,
            "confidence": stmt.excluded.confidence,
            "evidence": stmt.excluded.evidence,
            "updated_at": now,
        },
    )
    session.execute(stmt)


def label_one_cluster(session, clustering_run_id: str, cluster_summary: dict) -> dict:
    """Caching (skip if unchanged) -> primary model -> on a validation-class
    failure, escalate to the fallback model once -> on any remaining
    failure, record FAILED (never store unvalidated output) and move on.
    Never raises -- always returns an outcome dict, so a batch over all
    clusters isolates one cluster's failure from the rest, and never
    touches papers/paper_embeddings/clustering_runs/paper_cluster_assignments."""
    cluster_id = cluster_summary["cluster_id"]
    input_hash = _compute_input_hash(cluster_summary)

    primary_provider = config.CLUSTER_LABEL_PRIMARY_PROVIDER
    primary_model = config.CLUSTER_LABEL_PRIMARY_MODEL
    primary_capability = get_model_capability(primary_provider, primary_model)

    existing = _existing_label(
        session, clustering_run_id, cluster_id, primary_provider, primary_model, primary_model, prompts.PROMPT_VERSION
    )
    if existing is not None and existing.generation_status == "SUCCEEDED" and existing.input_hash == input_hash:
        return {"cluster_id": cluster_id, "outcome": "CACHED", "label_id": str(existing.id)}

    try:
        result, retry_count = generate_cluster_label(cluster_summary, provider=primary_provider, model=primary_model)
        with session.begin_nested():
            _upsert_label(
                session, clustering_run_id, cluster_id, primary_provider, primary_model, primary_model,
                input_hash, primary_capability.temperature, retry_count, "SUCCEEDED", None, result,
            )
        session.commit()
        return {"cluster_id": cluster_id, "outcome": "SUCCEEDED", "provider": primary_provider, "model": primary_model}

    except (PydanticValidationError, EvidenceHallucinationError, LLMResponseError) as primary_exc:
        fallback_provider = config.CLUSTER_LABEL_FALLBACK_PROVIDER
        fallback_model = config.CLUSTER_LABEL_FALLBACK_MODEL
        fallback_capability = get_model_capability(fallback_provider, fallback_model)
        try:
            result, retry_count = generate_cluster_label(
                cluster_summary, provider=fallback_provider, model=fallback_model
            )
            with session.begin_nested():
                _upsert_label(
                    session, clustering_run_id, cluster_id, fallback_provider, fallback_model, fallback_model,
                    input_hash, fallback_capability.temperature, retry_count, "SUCCEEDED", None, result,
                )
            session.commit()
            return {
                "cluster_id": cluster_id, "outcome": "SUCCEEDED_FALLBACK",
                "provider": fallback_provider, "model": fallback_model,
            }
        except Exception as fallback_exc:
            with session.begin_nested():
                _upsert_label(
                    session, clustering_run_id, cluster_id, primary_provider, primary_model, primary_model,
                    input_hash, primary_capability.temperature, 0, "FAILED",
                    f"primary failed: {primary_exc}; fallback failed: {fallback_exc}", None,
                )
            session.commit()
            return {"cluster_id": cluster_id, "outcome": "FAILED", "error": str(fallback_exc)}

    except LLMProviderError as primary_exc:
        # Transient error, already retried and exhausted inside
        # generate_cluster_label -- no model escalation for transient
        # failures (escalation is for validation-class problems only).
        with session.begin_nested():
            _upsert_label(
                session, clustering_run_id, cluster_id, primary_provider, primary_model, primary_model,
                input_hash, primary_capability.temperature, config.CLUSTER_LABEL_MAX_RETRIES, "FAILED",
                str(primary_exc), None,
            )
        session.commit()
        return {"cluster_id": cluster_id, "outcome": "FAILED", "error": str(primary_exc)}


def label_clustering_run(clustering_run_id: str) -> dict:
    """Labels every non-noise cluster in a run. Only ever writes to
    cluster_labels -- never papers, paper_embeddings, clustering_runs, or
    paper_cluster_assignments."""
    summaries = build_llm_cluster_summaries(clustering_run_id)
    session = SessionLocal()
    try:
        results = [label_one_cluster(session, clustering_run_id, summary) for summary in summaries]
        return {
            "clustering_run_id": clustering_run_id,
            "attempted": len(results),
            "succeeded": sum(1 for r in results if r["outcome"] in ("SUCCEEDED", "SUCCEEDED_FALLBACK")),
            "cached": sum(1 for r in results if r["outcome"] == "CACHED"),
            "failed": sum(1 for r in results if r["outcome"] == "FAILED"),
            "results": results,
        }
    finally:
        session.close()
