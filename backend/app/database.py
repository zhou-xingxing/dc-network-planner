import uuid
from collections.abc import Generator
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import BACKEND_DIR, settings


def gen_uuid() -> str:
    return str(uuid.uuid4())


def _normalize_database_url(database_url: str) -> str:
    """把相对 SQLite 数据库路径固定到 backend 目录下。"""
    url = make_url(database_url)
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        return database_url

    database_path = Path(url.database)
    if database_path.is_absolute():
        return database_url

    resolved_path = (BACKEND_DIR / database_path).resolve()
    return str(url.set(database=str(resolved_path)))


def enable_sqlite_foreign_keys(target_engine: Engine) -> None:
    """为 SQLite engine 的每个连接启用外键约束。"""
    if target_engine.dialect.name != "sqlite":
        return

    @event.listens_for(target_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        if not isinstance(dbapi_connection, SQLiteConnection):
            return
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


engine = create_engine(
    _normalize_database_url(settings.DATABASE_URL),
    connect_args={"check_same_thread": False},
    echo=False,
)
enable_sqlite_foreign_keys(engine)

# 数据库会话工厂，每次请求通过 get_db() 获取独立会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
