from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import BACKEND_DIR, settings


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


engine = create_engine(
    _normalize_database_url(settings.DATABASE_URL),
    connect_args={"check_same_thread": False},
    echo=False,
)

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
