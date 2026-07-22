import hashlib
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.change_log import ChangeLog
from app.models.external_access_token import ExternalAccessToken
from app.models.user import User
from app.utils.time_utils import to_db_datetime, utcnow


def _issue_external_token(client, username: str = "admin", scopes: list[str] | None = None) -> str:
    response = client.post(
        "/api/external/v1/auth/token",
        json={
            "username": username,
            "password": "admin" if username == "admin" else "password",
            "requested_scopes": scopes or ["network-plane:read"],
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _external_headers(raw_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_token}"}


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def test_external_token_can_be_issued_and_is_stored_as_hash(client, test_db):
    """签发外部 Token 时仅保存哈希，并以外部 API 方式记录审计日志。"""
    response = client.post(
        "/api/external/v1/auth/token",
        json={
            "username": "admin",
            "password": "admin",
            "requested_scopes": ["network-plane:read"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"].startswith("dcnp_ext_")
    assert body["expires_in"] == 30 * 60
    assert body["scope"] == ["network-plane:read"]

    session = Session(test_db)
    try:
        token = session.query(ExternalAccessToken).one()
        assert token.token_hash != body["access_token"]
        audit = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "external_access_token", ChangeLog.action == "create")
            .one()
        )
        assert audit.operator == "admin"
        assert audit.operation_method == "external_api"
    finally:
        session.close()


def test_external_token_reissue_revokes_previous_active_token(client, test_db):
    """同一用户重新签发令牌时，应自动撤销此前有效令牌并记录审计日志。"""
    request_body = {
        "username": "admin",
        "password": "admin",
        "requested_scopes": ["network-plane:read"],
    }
    first_response = client.post("/api/external/v1/auth/token", json=request_body)
    second_response = client.post("/api/external/v1/auth/token", json=request_body)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_token_hash = _token_hash(first_response.json()["access_token"])
    second_token_hash = _token_hash(second_response.json()["access_token"])
    session = Session(test_db)
    try:
        first_token = (
            session.query(ExternalAccessToken).filter(ExternalAccessToken.token_hash == first_token_hash).one()
        )
        second_token = (
            session.query(ExternalAccessToken).filter(ExternalAccessToken.token_hash == second_token_hash).one()
        )
        assert first_token.revoked_at is not None
        assert second_token.revoked_at is None
        assert session.query(ExternalAccessToken).filter(ExternalAccessToken.revoked_at.is_(None)).count() == 1

        revoke_audit = (
            session.query(ChangeLog)
            .filter(
                ChangeLog.entity_type == "external_access_token",
                ChangeLog.entity_id == first_token.id,
                ChangeLog.action == "revoke",
            )
            .one()
        )
        assert revoke_audit.operator == "admin"
        assert revoke_audit.operation_method == "external_api"
        assert revoke_audit.comment == "签发新外部 API 访问令牌时自动替换旧令牌"
    finally:
        session.close()


def test_external_token_creation_rejects_invalid_credentials(client):
    """错误的用户名或密码不能签发外部 API 访问令牌。"""
    for credentials in (
        {"username": "unknown", "password": "admin"},
        {"username": "admin", "password": "wrong-password"},
    ):
        response = client.post(
            "/api/external/v1/auth/token",
            json={**credentials, "requested_scopes": ["network-plane:read"]},
        )

        assert response.status_code == 401


def test_disabled_user_cannot_create_external_token(client, test_db):
    """被禁用的用户即使密码正确也不能签发外部 API 访问令牌。"""
    session = Session(test_db)
    try:
        admin = session.query(User).filter(User.username == "admin").one()
        admin.is_active = False
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/api/external/v1/auth/token",
        json={
            "username": "admin",
            "password": "admin",
            "requested_scopes": ["network-plane:read"],
        },
    )

    assert response.status_code == 401


def test_external_api_rejects_missing_bearer_token(client):
    """外部 API 未携带 Bearer token 时应返回 401。"""
    response = client.get("/api/external/v1/lookup?q=10.0.0.5")

    assert response.status_code == 401


def test_external_api_rejects_web_jwt(client, admin_headers):
    """Web JWT 不能越过外部 API 凭据边界调用 external API。"""
    response = client.get("/api/external/v1/lookup?q=10.0.0.5", headers=admin_headers)

    assert response.status_code == 401


def test_external_api_rejects_invalid_external_token(client):
    """不存在的外部 API 访问令牌应返回 401。"""
    response = client.get("/api/external/v1/lookup?q=10.0.0.5", headers=_external_headers("dcnp_ext_unknown"))

    assert response.status_code == 401


def test_external_api_rejects_revoked_token(client, test_db):
    """已撤销外部 API 访问令牌不能调用受保护的 external API。"""
    raw_token = _issue_external_token(client)
    session = Session(test_db)
    try:
        token = (
            session.query(ExternalAccessToken).filter(ExternalAccessToken.token_hash == _token_hash(raw_token)).one()
        )
        token.revoked_at = to_db_datetime(utcnow())
        session.commit()
    finally:
        session.close()

    response = client.get("/api/external/v1/lookup?q=10.0.0.5", headers=_external_headers(raw_token))

    assert response.status_code == 401


def test_external_api_rejects_expired_token(client, test_db):
    """已过期外部 API 访问令牌不能调用受保护的 external API。"""
    raw_token = _issue_external_token(client)
    session = Session(test_db)
    try:
        token = (
            session.query(ExternalAccessToken).filter(ExternalAccessToken.token_hash == _token_hash(raw_token)).one()
        )
        token.expires_at = to_db_datetime(utcnow() - timedelta(minutes=1))
        session.commit()
    finally:
        session.close()

    response = client.get("/api/external/v1/lookup?q=10.0.0.5", headers=_external_headers(raw_token))

    assert response.status_code == 401


def test_external_api_rejects_disabled_token_owner(client, test_db, user_headers_factory):
    """令牌所属用户被禁用后，外部 API 访问令牌应立即失效。"""
    user_headers_factory([], username="external-disabled-owner")
    raw_token = _issue_external_token(client, username="external-disabled-owner")
    session = Session(test_db)
    try:
        user = session.query(User).filter(User.username == "external-disabled-owner").one()
        user.is_active = False
        session.commit()
    finally:
        session.close()

    response = client.get("/api/external/v1/lookup?q=10.0.0.5", headers=_external_headers(raw_token))

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/external/v1/lookup?q=10.0.0.5",
        "/api/external/v1/network-plane-types",
    ],
)
def test_external_api_rejects_token_without_required_scope(client, user_headers_factory, test_db, path):
    """缺少接口所需 scope 的外部 API 访问令牌应返回 403。"""
    user_headers_factory([], username="external-no-read-scope")
    raw_token = "dcnp_ext_no_read_scope_token"
    session = Session(test_db)
    try:
        user = session.query(User).filter(User.username == "external-no-read-scope").one()
        session.add(
            ExternalAccessToken(
                token_hash=_token_hash(raw_token),
                user_id=user.id,
                scopes="[]",
                expires_at=to_db_datetime(utcnow() + timedelta(minutes=30)),
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(path, headers=_external_headers(raw_token))

    assert response.status_code == 403


def test_external_token_cannot_call_existing_web_api(client):
    """外部 API 访问令牌不能调用既有 Web 业务接口。"""
    raw_token = _issue_external_token(client)

    response = client.get("/api/lookup?q=10.0.0.5", headers=_external_headers(raw_token))

    assert response.status_code == 401
