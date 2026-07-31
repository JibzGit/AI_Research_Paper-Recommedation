from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from research_platform.config import DATABASE_URL

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
