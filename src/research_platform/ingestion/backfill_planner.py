import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from research_platform.config import (
    ARXIV_BASE_DELAY_SECONDS,
    ARXIV_DEFAULT_PAGE_SIZE,
    ARXIV_JITTER_MAX_SECONDS,
)
from research_platform.db.models import BackfillWindow
from research_platform.ingestion.arxiv_client import build_date_range_query, preflight_count

APPROVED_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.IR", "cs.CV", "cs.SI"]

EMPTY_RESULT_THRESHOLD = 0
SINGLE_PAGE_MAX = 200
WINDOW_SPLIT_THRESHOLD = 1000


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    return dt.replace(year=year, month=month)


def month_windows(start: datetime, end: datetime):
    cursor = start
    while cursor < end:
        nxt = min(_add_months(cursor, 1), end)
        yield cursor, nxt - timedelta(seconds=1)
        cursor = nxt


def week_windows(start: datetime, end: datetime):
    cursor = start
    while cursor < end:
        nxt = min(cursor + timedelta(days=7), end)
        yield cursor, nxt - timedelta(seconds=1)
        cursor = nxt


def day_windows(start: datetime, end: datetime):
    cursor = start
    while cursor < end:
        nxt = min(cursor + timedelta(days=1), end)
        yield cursor, nxt - timedelta(seconds=1)
        cursor = nxt


def plan_window(
    session,
    categories: list[str],
    window_start: datetime,
    window_end: datetime,
    granularity: str,
    page_size: int = ARXIV_DEFAULT_PAGE_SIZE,
    split_from_id=None,
) -> list[BackfillWindow]:
    """Preflights one date window and either stores it as a terminal
    (executable) window or splits it into smaller windows per the approved
    rules, recursing as needed. Returns every BackfillWindow row created by
    this call, including any parent SPLIT row and all of its descendants.

    Idempotent: if a window with this exact (window_start, window_end,
    granularity) already exists, it (and, if it was split, its full
    descendant tree) is returned as-is with zero preflight requests and zero
    new rows -- re-running the planner must never re-plan, duplicate, or
    touch the checkpoint of an already-planned window."""
    existing = session.execute(
        select(BackfillWindow).where(
            BackfillWindow.window_start == window_start,
            BackfillWindow.window_end == window_end,
            BackfillWindow.window_granularity == granularity,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status != "SPLIT":
            return [existing]
        children = (
            session.execute(select(BackfillWindow).where(BackfillWindow.split_from_window_id == existing.id))
            .scalars()
            .all()
        )
        results = [existing]
        for child in children:
            results.extend(
                plan_window(
                    session, categories, child.window_start, child.window_end, child.window_granularity,
                    page_size, split_from_id=existing.id,
                )
            )
        return results

    query = build_date_range_query(categories, window_start, window_end)
    total = preflight_count(session, query)

    if total <= EMPTY_RESULT_THRESHOLD:
        window = BackfillWindow(
            window_start=window_start,
            window_end=window_end,
            window_granularity=granularity,
            estimated_result_count=0,
            page_size=page_size,
            status="SKIPPED_EMPTY",
            split_from_window_id=split_from_id,
        )
        session.add(window)
        session.commit()
        return [window]

    # daily is the floor granularity: even if still above the split
    # threshold, we do not split further (documented limitation, not
    # expected to occur for these categories in practice).
    if total <= WINDOW_SPLIT_THRESHOLD or granularity == "daily":
        window = BackfillWindow(
            window_start=window_start,
            window_end=window_end,
            window_granularity=granularity,
            estimated_result_count=total,
            page_size=page_size,
            status="PLANNED",
            split_from_window_id=split_from_id,
        )
        session.add(window)
        session.commit()
        return [window]

    # total > WINDOW_SPLIT_THRESHOLD: split into finer windows
    if granularity == "monthly":
        sub_windows, sub_granularity = list(week_windows(window_start, window_end)), "weekly"
    else:  # weekly, still too large
        sub_windows, sub_granularity = list(day_windows(window_start, window_end)), "daily"

    parent = BackfillWindow(
        window_start=window_start,
        window_end=window_end,
        window_granularity=granularity,
        estimated_result_count=total,
        page_size=page_size,
        status="SPLIT",
        split_from_window_id=split_from_id,
    )
    session.add(parent)
    session.commit()

    results = [parent]
    for sub_start, sub_end in sub_windows:
        results.extend(
            plan_window(session, categories, sub_start, sub_end, sub_granularity, page_size, split_from_id=parent.id)
        )
    return results


def plan_backfill(
    session,
    start_date: datetime,
    end_date: datetime,
    categories: list[str] = APPROVED_CATEGORIES,
    page_size: int = ARXIV_DEFAULT_PAGE_SIZE,
) -> list[BackfillWindow]:
    """Plan-only mode: generates monthly windows across [start_date, end_date),
    preflighting each and splitting per the approved rules. Does not fetch
    or insert any papers."""
    all_windows: list[BackfillWindow] = []
    for month_start, month_end in month_windows(start_date, end_date):
        all_windows.extend(plan_window(session, categories, month_start, month_end, "monthly", page_size))
    return all_windows


def estimate_plan_summary(windows: list[BackfillWindow]) -> dict:
    terminal = [w for w in windows if w.status == "PLANNED"]
    estimated_papers = sum(w.estimated_result_count or 0 for w in terminal)
    estimated_pages = sum(math.ceil((w.estimated_result_count or 0) / w.page_size) for w in terminal)
    preflight_requests = len(windows)  # one preflight per window row created, including SPLIT parents
    estimated_requests = preflight_requests + estimated_pages
    avg_delay = ARXIV_BASE_DELAY_SECONDS + (ARXIV_JITTER_MAX_SECONDS / 2)
    estimated_minimum_seconds = estimated_requests * avg_delay

    return {
        "estimated_papers": estimated_papers,
        "estimated_pages": estimated_pages,
        "preflight_requests_used": preflight_requests,
        "estimated_total_requests": estimated_requests,
        "estimated_minimum_execution_seconds": round(estimated_minimum_seconds, 1),
        "windows_split": sum(1 for w in windows if w.status == "SPLIT"),
        "windows_skipped_empty": sum(1 for w in windows if w.status == "SKIPPED_EMPTY"),
        "windows_planned": len(terminal),
    }
