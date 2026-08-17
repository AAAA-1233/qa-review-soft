from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATA_DIR, DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if DATABASE_URL.startswith("sqlite"):
        with engine.begin() as connection:
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(ai_configs)").fetchall()}
            if "proxy_url" not in columns:
                connection.exec_driver_sql("ALTER TABLE ai_configs ADD COLUMN proxy_url TEXT DEFAULT ''")
    elif DATABASE_URL.startswith("postgresql"):
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE ai_configs ADD COLUMN IF NOT EXISTS proxy_url TEXT DEFAULT ''")
