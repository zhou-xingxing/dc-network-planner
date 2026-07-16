from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.change_log import ChangeLog
from app.models.external_access_token import ExternalAccessToken
from app.models.user import User
from app.utils.time_utils import to_db_datetime, utcnow


def _new_external_access_token(user_id: str, token_hash: str, expires_in_minutes: int) -> ExternalAccessToken:
    """构造用于管理员访问令牌管理测试的令牌记录。"""
    return ExternalAccessToken(
        token_hash=token_hash,
        user_id=user_id,
        scopes='["network-plane:read"]',
        expires_at=to_db_datetime(utcnow() + timedelta(minutes=expires_in_minutes)),
    )


def test_administrator_lists_unrevoked_unexpired_external_access_tokens(client, admin_headers, test_db):
    """管理员列表返回未撤销、未过期令牌，并标记所属用户状态。"""
    session = Session(test_db)
    try:
        admin = session.query(User).filter(User.username == "admin").one()
        active = _new_external_access_token(admin.id, "active-token", 30)
        expired = _new_external_access_token(admin.id, "expired-token", -1)
        revoked = _new_external_access_token(admin.id, "revoked-token", 30)
        revoked.revoked_at = to_db_datetime(utcnow())
        disabled_user = User(
            username="disabled-token-owner",
            password_hash="not-used-in-this-test",
            role="user",
            is_active=False,
        )
        session.add(disabled_user)
        session.flush()
        disabled_user_token = _new_external_access_token(disabled_user.id, "disabled-owner-token", 30)
        session.add_all([active, expired, revoked, disabled_user_token])
        session.commit()

        response = client.get("/api/external-access-tokens", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        items_by_id = {item["id"]: item for item in body["items"]}
        assert set(items_by_id) == {active.id, disabled_user_token.id}
        assert items_by_id[active.id]["username"] == "admin"
        assert items_by_id[active.id]["owner_is_active"] is True
        assert items_by_id[disabled_user_token.id]["owner_is_active"] is False
        assert "token_hash" not in items_by_id[active.id]
        assert "access_token" not in items_by_id[active.id]
    finally:
        session.close()


def test_regular_user_cannot_manage_external_access_tokens(client, user_headers_factory):
    """普通用户不能查看或撤销外部 API 访问令牌。"""
    user_headers = user_headers_factory([], username="token-manager-user")

    list_response = client.get("/api/external-access-tokens", headers=user_headers)
    revoke_response = client.delete("/api/external-access-tokens/nonexistent-token", headers=user_headers)

    assert list_response.status_code == 403
    assert revoke_response.status_code == 403


def test_administrator_can_revoke_active_external_access_token(client, admin_headers, test_db):
    """管理员撤销有效令牌后应更新状态并记录客户端操作审计日志。"""
    session = Session(test_db)
    try:
        admin = session.query(User).filter(User.username == "admin").one()
        token = _new_external_access_token(admin.id, "token-to-revoke", 30)
        session.add(token)
        session.commit()

        response = client.delete(f"/api/external-access-tokens/{token.id}", headers=admin_headers)
        assert response.status_code == 204

        session.expire_all()
        revoked_token = session.get(ExternalAccessToken, token.id)
        assert revoked_token is not None
        assert revoked_token.revoked_at is not None
        audit = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "external_access_token", ChangeLog.entity_id == token.id)
            .one()
        )
        assert audit.action == "revoke"
        assert audit.operator == "admin"
        assert audit.operation_method == "client"
    finally:
        session.close()


def test_administrator_can_revoke_expired_external_access_token(client, admin_headers, test_db):
    """管理员可以撤销已过期但尚未撤销的令牌。"""
    session = Session(test_db)
    try:
        admin = session.query(User).filter(User.username == "admin").one()
        token = _new_external_access_token(admin.id, "expired-token-to-revoke", -1)
        session.add(token)
        session.commit()

        response = client.delete(f"/api/external-access-tokens/{token.id}", headers=admin_headers)
        assert response.status_code == 204
        session.expire_all()
        revoked_token = session.get(ExternalAccessToken, token.id)
        assert revoked_token is not None
        assert revoked_token.revoked_at is not None
    finally:
        session.close()


def test_administrator_gets_not_found_for_unknown_external_access_token(client, admin_headers):
    """管理员撤销不存在的令牌时应收到 404。"""
    response = client.delete("/api/external-access-tokens/unknown-token-id", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "外部 API 访问令牌不存在"


def test_administrator_cannot_revoke_already_revoked_external_access_token(client, admin_headers, test_db):
    """管理员重复撤销令牌时应收到已撤销提示。"""
    session = Session(test_db)
    try:
        admin = session.query(User).filter(User.username == "admin").one()
        token = _new_external_access_token(admin.id, "already-revoked-token", 30)
        token.revoked_at = to_db_datetime(utcnow())
        session.add(token)
        session.commit()

        response = client.delete(f"/api/external-access-tokens/{token.id}", headers=admin_headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "外部 API 访问令牌已撤销，无法重复撤销"
    finally:
        session.close()


def test_administrator_can_revoke_external_token_owned_by_disabled_user(client, admin_headers, test_db):
    """令牌所属用户被停用后，管理员仍可撤销该令牌。"""
    session = Session(test_db)
    try:
        disabled_user = User(
            username="disabled-token-owner-to-revoke",
            password_hash="not-used-in-this-test",
            role="user",
            is_active=False,
        )
        session.add(disabled_user)
        session.flush()
        token = _new_external_access_token(disabled_user.id, "disabled-owner-token-to-revoke", 30)
        session.add(token)
        session.commit()

        response = client.delete(f"/api/external-access-tokens/{token.id}", headers=admin_headers)
        assert response.status_code == 204
        session.expire_all()
        revoked_token = session.get(ExternalAccessToken, token.id)
        assert revoked_token is not None
        assert revoked_token.revoked_at is not None
    finally:
        session.close()
