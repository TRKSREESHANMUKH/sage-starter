import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL not found. Did you copy .env.example to .env?"
    )

LIVE_DB_PATH = Path(__file__).resolve().parent.parent / "live" / "sage_live.db"
LIVE_DATABASE_URL = f"sqlite:///{LIVE_DB_PATH}"

Base = declarative_base()


def get_engine(source: Optional[str] = None):
    src = source or os.getenv("SAGE_SOURCE", "main")
    if src == "live":
        return create_engine(LIVE_DATABASE_URL, connect_args={"check_same_thread": False})
    if src == "ext":
        ext_url = os.getenv("EXT_DATABASE_URL", "postgresql+psycopg2://sage_user:sage_dev_password@localhost:5433/sage_ext")
        return create_engine(ext_url)
    return create_engine(DATABASE_URL)


def get_session_factory(source: Optional[str] = None):
    eng = get_engine(source)
    return sessionmaker(autocommit=False, autoflush=False, bind=eng)


class _DynamicSessionMaker:
    def __call__(self, *args, source: Optional[str] = None, **kwargs):
        factory = get_session_factory(source)
        return factory(*args, **kwargs)


SessionLocal = _DynamicSessionMaker()
engine = get_engine("main")

from app.models import suppliers, purchasing, inventory, production, sales, intelligence


def get_db(source: Optional[str] = None):
    db = SessionLocal(source=source)
    try:
        yield db
    finally:
        db.close()