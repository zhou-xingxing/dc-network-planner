"""系统统计接口测试。"""

from app.models.change_log import ChangeLog
from app.services.stats import _build_summary


def test_stats_scope_distribution_orders_public_before_private(client, admin_headers, user_headers_factory):
    """公网/私网分布固定按非私网、私网顺序返回。"""
    region = client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers).json()
    private_type = client.post(
        "/api/network-plane-types",
        json={"name": "私网平面", "is_private": True},
        headers=admin_headers,
    ).json()
    public_type = client.post(
        "/api/network-plane-types",
        json={"name": "公网平面", "is_private": False},
        headers=admin_headers,
    ).json()
    user_headers = user_headers_factory([region["id"]])
    client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": private_type["id"], "cidr": "10.0.1.0/24"},
        headers=user_headers,
    )
    client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": public_type["id"], "cidr": "10.0.2.0/24"},
        headers=user_headers,
    )

    response = client.get("/api/stats", headers=admin_headers)

    assert response.status_code == 200
    assert list(response.json()["plane_by_scope"].keys()) == ["非私网", "私网"]


def test_stats_region_distribution_orders_by_region_name(client, admin_headers):
    """按 Region 分布默认按 Region 名称升序返回。"""
    client.post("/api/regions", json={"name": "Region-B"}, headers=admin_headers)
    client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers)

    response = client.get("/api/stats", headers=admin_headers)

    assert response.status_code == 200
    names = [item["region_name"] for item in response.json()["plane_by_region"]]
    assert names == ["Region-A", "Region-B"]


def test_build_summary_fallback_includes_entity_name():
    """未知操作摘要回退时仍应展示具体变更对象。"""
    change_log = ChangeLog(
        entity_type="network_plane_type",
        entity_id="plane-type-1",
        entity_name="业务平面",
        action="backup",
        operator="admin",
    )

    assert _build_summary(change_log) == "backup network_plane_type 业务平面"
