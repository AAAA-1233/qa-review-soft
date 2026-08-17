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
            project_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(projects)").fetchall()}
            if "owner_id" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN owner_id INTEGER")
            user_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
            if "username" not in user_columns:
                connection.exec_driver_sql("ALTER TABLE users ADD COLUMN username VARCHAR(80)")
            if "password_hash" not in user_columns:
                connection.exec_driver_sql("ALTER TABLE users ADD COLUMN password_hash VARCHAR(220) DEFAULT ''")
            connection.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users(username)")
    elif DATABASE_URL.startswith("postgresql"):
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE ai_configs ADD COLUMN IF NOT EXISTS proxy_url TEXT DEFAULT ''")
            connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(80)")
            connection.exec_driver_sql("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(220) DEFAULT ''")
            connection.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users(username)")

    from app.services.project_cleanup import cleanup_orphan_project_rows

    with SessionLocal() as db:
        cleanup_orphan_project_rows(db)
