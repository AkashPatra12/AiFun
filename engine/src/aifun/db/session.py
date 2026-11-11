import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from aifun.db.models import Base

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
    # create_all() only creates missing *tables* — it won't add a column to
    # a `media` table that already exists from before `stage` was added.
    # Still no Alembic (docs/phase1-data-ingestion.md §1): for one ad-hoc
    # column, ADD COLUMN IF NOT EXISTS is simpler than standing up a
    # migrations tool, and — unlike Base.metadata.create_all() — doesn't
    # require wiping local dev data to add it.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE media ADD COLUMN IF NOT EXISTS stage VARCHAR"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
