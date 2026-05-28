"""User management API tests."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.region import Region


def test_create_user_converts_username_integrity_error_to_conflict(client, admin_headers, monkeypatch):
    """创建用户遇到 username 唯一约束竞争时应转换为中文冲突错误。"""
    from sqlalchemy.orm import Session

    original_flush = Session.flush
    calls = {"count": 0}

    def flush_once_then_conflict(session, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise IntegrityError(
                "insert users",
                {},
                Exception("UNIQUE constraint failed: users.username"),
            )
        return original_flush(session, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", flush_once_then_conflict)

    response = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "race-user",
            "password": "password",
            "role": "user",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "用户名已存在"


def test_user_management_crud_with_region_permissions(client, admin_headers, test_db):
    """用户管理接口应支持创建、列表、更新授权、重置密码、登录和删除全流程。"""
    region_b = client.post("/api/regions", json={"name": "Region-B"}, headers=admin_headers).json()
    region_a = client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers).json()

    create_response = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "alice",
            "password": "initial-password",
            "role": "user",
            "permitted_region_ids": [region_b["id"], region_a["id"]],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["username"] == "alice"
    assert created["permitted_regions"] == [
        {"id": region_a["id"], "name": "Region-A"},
        {"id": region_b["id"], "name": "Region-B"},
    ]

    list_response = client.get("/api/users", headers=admin_headers)
    assert list_response.status_code == 200
    users = list_response.json()
    assert users["total"] == 2
    assert [item["username"] for item in users["items"]] == ["admin", "alice"]

    update_response = client.put(
        f"/api/users/{created['id']}",
        headers=admin_headers,
        json={
            "is_active": False,
            "permitted_region_ids": [region_b["id"]],
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["is_active"] is False
    assert updated["permitted_regions"] == [{"id": region_b["id"], "name": "Region-B"}]

    reset_response = client.post(
        f"/api/users/{created['id']}/reset-password",
        headers=admin_headers,
        json={"password": "new-password"},
    )
    assert reset_response.status_code == 200

    reactivate_response = client.put(
        f"/api/users/{created['id']}",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert reactivate_response.status_code == 200

    login_response = client.post("/api/auth/login", json={"username": "alice", "password": "new-password"})
    assert login_response.status_code == 200

    delete_response = client.delete(f"/api/users/{created['id']}", headers=admin_headers)
    assert delete_response.status_code == 204

    # 删除用户只应清理用户授权关系，不能级联删除被授权管理的 Region。
    session = Session(test_db)
    try:
        remaining_region_names = {region.name for region in session.query(Region).all()}
        assert remaining_region_names == {"Region-A", "Region-B"}
    finally:
        session.close()

    missing_response = client.get("/api/users", headers=admin_headers)
    assert missing_response.json()["total"] == 1


def test_create_user_rejects_duplicate_username(client, admin_headers):
    """创建重复用户名时应返回冲突错误。"""
    payload = {
        "username": "duplicate",
        "password": "password",
        "role": "user",
    }
    assert client.post("/api/users", headers=admin_headers, json=payload).status_code == 201

    response = client.post("/api/users", headers=admin_headers, json=payload)

    assert response.status_code == 409
    assert "用户名已存在" in response.json()["detail"]


def test_user_management_rejects_missing_region_permission(client, admin_headers):
    """为用户授权不存在的 Region 时应拒绝创建。"""
    response = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "missing-region-user",
            "password": "password",
            "role": "user",
            "permitted_region_ids": ["missing-region-id"],
        },
    )

    assert response.status_code == 409
    assert "Region 不存在" in response.json()["detail"]


def test_user_management_returns_404_for_missing_user(client, admin_headers):
    """更新、重置密码或删除不存在用户时都应返回 404。"""
    update_response = client.put(
        "/api/users/missing-user",
        headers=admin_headers,
        json={"is_active": False},
    )
    reset_response = client.post(
        "/api/users/missing-user/reset-password",
        headers=admin_headers,
        json={"password": "new-password"},
    )
    delete_response = client.delete("/api/users/missing-user", headers=admin_headers)

    assert update_response.status_code == 404
    assert reset_response.status_code == 404
    assert delete_response.status_code == 404


def test_administrator_cannot_delete_self(client, admin_headers):
    """administrator 不能删除当前登录的自己。"""
    me = client.get("/api/auth/me", headers=admin_headers).json()

    response = client.delete(f"/api/users/{me['id']}", headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "不能删除当前登录用户"


def test_last_administrator_cannot_be_disabled(client, admin_headers):
    """系统最后一个 administrator 不能被禁用。"""
    me = client.get("/api/auth/me", headers=admin_headers).json()

    response = client.put(f"/api/users/{me['id']}", json={"is_active": False}, headers=admin_headers)

    assert response.status_code == 409
