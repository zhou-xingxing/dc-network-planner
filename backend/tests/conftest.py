"""Test fixtures - each test gets an isolated in-memory SQLite database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.schemas.user import UserCreate
from app.services.backup import ensure_backup_config
from app.services.user import create_user, ensure_bootstrap_admin


@pytest.fixture
def test_db():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    bootstrap_db = TestSessionLocal()
    try:
        ensure_bootstrap_admin(bootstrap_db)
        ensure_backup_config(bootstrap_db)
        bootstrap_db.commit()
    except Exception:
        bootstrap_db.rollback()
        raise
    finally:
        bootstrap_db.close()

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield engine

    # Clean up
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    """FastAPI TestClient with isolated database."""
    return TestClient(app)


@pytest.fixture
def admin_headers(client):
    """Authorization headers for the bootstrap administrator."""
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def user_headers_factory(test_db, client):
    """Create a user permitted to write Region IDs and return Authorization headers."""

    def _factory(permitted_region_ids, username="region-user"):
        session = Session(test_db)
        try:
            create_user(
                session,
                UserCreate(
                    username=username,
                    password="password",
                    role="user",
                    permitted_region_ids=list(permitted_region_ids),
                ),
            )
            session.commit()
        finally:
            session.close()
        response = client.post("/api/auth/login", json={"username": username, "password": "password"})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _factory


@pytest.fixture
def operator():
    """Default audited operator after authentication."""
    return "admin"
