import hashlib
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


def test_unauthenticated_business_api_returns_401(client):
    """未登录访问业务接口时应返回 401。"""
    response = client.get("/api/regions")
    assert response.status_code == 401


def test_login_success_and_failure(client):
    """登录接口应支持正确密码登录，并拒绝错误密码。"""
    success = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert success.status_code == 200
    assert success.json()["user"]["role"] == "administrator"

    failure = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert failure.status_code == 401


def test_disabled_user_cannot_login(client, test_db):
    """被禁用用户即使密码正确也不能登录。"""
    session = Session(test_db)
    try:
        admin = session.query(User).filter(User.username == "admin").one()
        admin.is_active = False
        session.commit()
    finally:
        session.close()

    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 401


def test_invalid_token_returns_401(client):
    """携带无效 Bearer token 访问受保护接口时应返回 401。"""
    response = client.get("/api/regions", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


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

    first_token_hash = hashlib.sha256(first_response.json()["access_token"].encode("utf-8")).hexdigest()
    second_token_hash = hashlib.sha256(second_response.json()["access_token"].encode("utf-8")).hexdigest()
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


def test_external_token_cannot_call_existing_web_api(client):
    """外部 Token 不得越过认证边界调用既有 Web 业务接口。"""
    external_token_response = client.post(
        "/api/external/v1/auth/token",
        json={
            "username": "admin",
            "password": "admin",
            "requested_scopes": ["network-plane:read"],
        },
    ).json()

    response = client.get(
        "/api/regions", headers={"Authorization": f"Bearer {external_token_response['access_token']}"}
    )
    assert response.status_code == 401


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


def test_current_user_can_change_own_password(client, admin_headers):
    """当前登录用户可以修改自己的密码，并只能用新密码重新登录。"""
    response = client.put(
        "/api/auth/password",
        headers=admin_headers,
        json={"current_password": "admin", "new_password": "new-admin-password"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "admin"

    old_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"username": "admin", "password": "new-admin-password"})
    assert new_login.status_code == 200


def test_current_user_change_password_rejects_wrong_current_password(client, admin_headers):
    """修改当前用户密码时应拒绝错误的原密码。"""
    response = client.put(
        "/api/auth/password",
        headers=admin_headers,
        json={"current_password": "wrong", "new_password": "new-admin-password"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "原密码错误"


def test_user_can_read_all_but_only_write_assigned_region(client, admin_headers, user_headers_factory):
    """普通用户可读取全部 Region，但只能写入被授权的 Region 业务数据。"""
    region_a = client.post("/api/regions", json={"name": "A"}, headers=admin_headers).json()
    region_b = client.post("/api/regions", json={"name": "B"}, headers=admin_headers).json()
    pt = client.post("/api/network-plane-types", json={"name": "管理平面"}, headers=admin_headers).json()
    user_headers = user_headers_factory([region_a["id"]])

    read_response = client.get("/api/regions", headers=user_headers)
    assert read_response.status_code == 200
    assert read_response.json()["total"] == 2

    allowed = client.post(
        f"/api/regions/{region_a['id']}/planes",
        json={"plane_type_id": pt["id"], "cidr": "10.0.0.0/22"},
        headers=user_headers,
    )
    assert allowed.status_code == 201

    denied = client.post(
        f"/api/regions/{region_b['id']}/planes",
        json={"plane_type_id": pt["id"], "cidr": "10.1.0.0/22"},
        headers=user_headers,
    )
    assert denied.status_code == 403


def test_administrator_cannot_write_region_business_data(client, admin_headers):
    """administrator 角色不能直接写入 Region 网络平面等业务数据。"""
    region = client.post("/api/regions", json={"name": "A"}, headers=admin_headers).json()
    pt = client.post("/api/network-plane-types", json={"name": "管理平面"}, headers=admin_headers).json()

    response = client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": pt["id"], "cidr": "10.0.0.0/22"},
        headers=admin_headers,
    )

    assert response.status_code == 403


def test_audit_operator_comes_from_authenticated_user(client, admin_headers, test_db):
    """审计日志 operator 应来自认证用户，不能被请求头伪造。"""
    client.post("/api/regions", json={"name": "Audit"}, headers={**admin_headers, "X-Operator": "spoofed"})

    session = Session(test_db)
    try:
        entry = session.query(ChangeLog).filter(ChangeLog.entity_type == "region").one()
        assert entry.operator == "admin"
        assert entry.operation_method == "client"
    finally:
        session.close()
