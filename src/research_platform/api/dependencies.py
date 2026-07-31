from sqlalchemy import text

from research_platform.db.session import SessionLocal


def check_database_connected() -> bool:
    """Trivial connectivity check for /health. Lives here (not inline in
    routes/health.py) so the route file itself never contains SQL, even a
    one-liner. Opens and closes its own short-lived session -- consistent
    with how search_papers()/similar_papers() already manage sessions."""
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        session.close()
