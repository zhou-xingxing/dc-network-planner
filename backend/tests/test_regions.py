"""Region CRUD tests."""

from sqlalchemy.orm import Session

from app.models.change_log import ChangeLog
from app.models.region_network_plane import RegionNetworkPlane
from app.models.user import UserRegionPermission

REGION_DATA = {"name": "北京数据中心", "description": "Production region"}


def test_create_region(client, admin_headers):
    resp = client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == REGION_DATA["name"]
    assert data["description"] == REGION_DATA["description"]
    assert "id" in data


def test_create_duplicate_region(client, admin_headers):
    client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    resp = client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    assert resp.status_code == 409


def test_list_regions(client, admin_headers):
    client.post("/api/regions", json={"name": "Region-B", "description": ""}, headers=admin_headers)
    client.post("/api/regions", json={"name": "Region-A", "description": ""}, headers=admin_headers)
    resp = client.get("/api/regions?skip=0&limit=10", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert [item["name"] for item in data["items"]] == ["Region-A", "Region-B"]


def test_list_regions_includes_plane_count(client, admin_headers, user_headers_factory):
    """Region 列表中的 plane_count 由后端聚合查询返回。"""
    region = client.post("/api/regions", json={"name": "Region-A", "description": ""}, headers=admin_headers).json()
    plane_type = client.post("/api/network-plane-types", json={"name": "管理平面"}, headers=admin_headers).json()
    user_headers = user_headers_factory([region["id"]])
    client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": plane_type["id"], "cidr": "10.0.0.0/24"},
        headers=user_headers,
    )

    resp = client.get("/api/regions", headers=admin_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["name"] == "Region-A"
    assert data["items"][0]["plane_count"] == 1


def test_list_regions_search(client, admin_headers):
    client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    client.post(
        "/api/regions",
        json={"name": "上海数据中心", "description": ""},
        headers=admin_headers,
    )
    resp = client.get("/api/regions?search=北京", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "北京数据中心"


def test_update_region(client, admin_headers):
    resp = client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    region_id = resp.json()["id"]

    resp = client.put(
        f"/api/regions/{region_id}",
        json={"name": "北京数据中心-UPDATED", "description": "更新后的描述"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "北京数据中心-UPDATED"
    assert data["description"] == "更新后的描述"


def test_update_region_rejects_duplicate_name(client, admin_headers):
    client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers)
    region_b = client.post("/api/regions", json={"name": "Region-B"}, headers=admin_headers).json()

    resp = client.put(
        f"/api/regions/{region_b['id']}",
        json={"name": "Region-A"},
        headers=admin_headers,
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Region 名称已存在: Region-A"


def test_update_region_returns_404(client, admin_headers):
    resp = client.put(
        "/api/regions/missing-region",
        json={"name": "不存在"},
        headers=admin_headers,
    )

    assert resp.status_code == 404


def test_update_region_requires_administrator(client, admin_headers, user_headers_factory):
    """Region 元数据更新只允许 administrator 执行。"""
    region = client.post("/api/regions", json=REGION_DATA, headers=admin_headers).json()
    user_headers = user_headers_factory([])

    resp = client.put(
        f"/api/regions/{region['id']}",
        json={"name": "普通用户不可更新"},
        headers=user_headers,
    )

    assert resp.status_code == 403


def test_delete_region(client, admin_headers, test_db):
    resp = client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    region_id = resp.json()["id"]

    resp = client.delete(f"/api/regions/{region_id}", headers=admin_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/regions/{region_id}", headers=admin_headers)
    assert resp.status_code == 404
    session = Session(test_db)
    try:
        delete_log = (
            session.query(ChangeLog).filter_by(entity_type="region", entity_id=region_id, action="delete").one()
        )
        assert delete_log.old_value == "name=北京数据中心, region_planes=0, user_region_permissions=0"
    finally:
        session.close()


def test_delete_region_cleans_user_region_permissions(client, admin_headers, user_headers_factory, test_db):
    """删除 Region 时同步清理普通用户的 Region 授权。"""
    region = client.post("/api/regions", json=REGION_DATA, headers=admin_headers).json()
    user_headers_factory([region["id"]])

    resp = client.delete(f"/api/regions/{region['id']}", headers=admin_headers)

    assert resp.status_code == 204
    session = Session(test_db)
    try:
        remaining_permissions = session.query(UserRegionPermission).filter_by(region_id=region["id"]).all()
        assert remaining_permissions == []
    finally:
        session.close()


def test_delete_region_cascades_region_planes(client, admin_headers, user_headers_factory, test_db):
    """删除 Region 时清理关联数据，并在审计日志记录影响范围。"""
    region = client.post("/api/regions", json=REGION_DATA, headers=admin_headers).json()
    plane_type = client.post("/api/network-plane-types", json={"name": "管理平面"}, headers=admin_headers).json()
    user_headers = user_headers_factory([region["id"]])
    plane_response = client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": plane_type["id"], "cidr": "10.0.0.0/24"},
        headers=user_headers,
    )
    assert plane_response.status_code == 201

    resp = client.delete(f"/api/regions/{region['id']}", headers=admin_headers)

    assert resp.status_code == 204
    session = Session(test_db)
    try:
        remaining_planes = session.query(RegionNetworkPlane).filter_by(region_id=region["id"]).all()
        assert remaining_planes == []
        remaining_permissions = session.query(UserRegionPermission).filter_by(region_id=region["id"]).all()
        assert remaining_permissions == []
        delete_log = (
            session.query(ChangeLog).filter_by(entity_type="region", entity_id=region["id"], action="delete").one()
        )
        assert delete_log.old_value == "name=北京数据中心, region_planes=1, user_region_permissions=1"
    finally:
        session.close()


def test_get_nonexistent_region(client, admin_headers):
    resp = client.get("/api/regions/nonexistent-id", headers=admin_headers)
    assert resp.status_code == 404
