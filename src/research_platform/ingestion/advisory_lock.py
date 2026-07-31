import contextlib

from sqlalchemy import text

# Arbitrary fixed key identifying "the arXiv collector" as a single logical
# worker slot. Any two processes calling pg_try_advisory_lock with this same
# key contend for the same lock.
ARXIV_COLLECTOR_LOCK_KEY = 727501001


@contextlib.contextmanager
def try_acquire_arxiv_lock(engine):
    """Acquires a session-level Postgres advisory lock on a dedicated
    connection held open for the whole block. A session-level advisory lock
    is tied to the underlying DB connection, not to an ORM Session/transaction
    boundary -- if we used a pooled ORM session that commits/returns its
    connection mid-job (as our per-page checkpoint commits do), the lock
    could silently be released or reassigned. Holding our own dedicated
    connection open for the block's lifetime avoids that.

    Yields True if the lock was acquired, False if another worker already
    holds it (caller should exit without treating this as a failure).
    """
    conn = engine.connect()
    try:
        acquired = conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": ARXIV_COLLECTOR_LOCK_KEY}
        ).scalar()
        conn.commit()  # ends the implicit SQL transaction only; the session-level lock persists regardless
        try:
            yield bool(acquired)
        finally:
            if acquired:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ARXIV_COLLECTOR_LOCK_KEY})
                conn.commit()
    finally:
        conn.close()
