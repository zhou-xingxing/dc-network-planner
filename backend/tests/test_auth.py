from sqlalchemy.orm import Session

from app.models.change_log import ChangeLog
from app.models.user import User


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
