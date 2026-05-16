"""IP Lookup tests."""

import pytest

from app.exceptions import BusinessError
from app.services.lookup import lookup_region_planes


class _NoQueryDB:
    """用于确认非法查询在进入数据库前就被拒绝。"""

    def query(self, *args, **kwargs):
        raise AssertionError("invalid lookup query should not touch database")


def _setup_data(client, admin_headers, user_headers_factory):
    """Create a region with an enabled network plane for lookup tests."""
    r = client.post("/api/regions", json={"name": "TestRegion"}, headers=admin_headers).json()
    pt = client.post("/api/network-plane-types", json={"name": "管理平面"}, headers=admin_headers).json()
    user_headers = user_headers_factory([r["id"]])
    client.post(
        f"/api/regions/{r['id']}/planes",
        json={"plane_type_id": pt["id"], "cidr": "10.0.0.0/24"},
        headers=user_headers,
    )
    return r, pt, user_headers


def _setup_tree_data(client, admin_headers, user_headers_factory):
    """创建父子网络平面，用于验证查询结果保留树形上下文。"""
    region = client.post("/api/regions", json={"name": "TreeRegion"}, headers=admin_headers).json()
    root_type = client.post("/api/network-plane-types", json={"name": "父平面"}, headers=admin_headers).json()
    child_type = client.post(
        "/api/network-plane-types",
        json={"name": "子平面", "parent_id": root_type["id"]},
        headers=admin_headers,
    ).json()
    user_headers = user_headers_factory([region["id"]])
    client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": root_type["id"], "cidr": "10.0.0.0/22"},
        headers=user_headers,
    )
    client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": child_type["id"], "cidr": "10.0.1.0/24"},
        headers=user_headers,
    )
    return user_headers


def test_lookup_by_ip(client, admin_headers, user_headers_factory):
    _, _, user_headers = _setup_data(client, admin_headers, user_headers_factory)
    resp = client.get("/api/lookup?q=10.0.0.5", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["results"][0]["cidr"] == "10.0.0.0/24"


def test_lookup_exact_cidr(client, admin_headers, user_headers_factory):
    _, _, user_headers = _setup_data(client, admin_headers, user_headers_factory)
    resp = client.get("/api/lookup?q=10.0.0.0/24", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


def test_lookup_exact_child_cidr_includes_parent_context(client, admin_headers, user_headers_factory):
    """精确命中子平面时，响应树应带出父平面上下文但不计入命中总数。"""
    user_headers = _setup_tree_data(client, admin_headers, user_headers_factory)

    resp = client.get("/api/lookup?q=10.0.1.0/24", headers=user_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["results"]) == 1
    parent = data["results"][0]
    assert parent["cidr"] == "10.0.0.0/22"
    assert parent["is_match"] is False
    assert len(parent["children"]) == 1
    child = parent["children"][0]
    assert child["cidr"] == "10.0.1.0/24"
    assert child["parent_id"] == parent["id"]
    assert child["is_match"] is True


def test_lookup_ip_marks_parent_and_child_as_matches(client, admin_headers, user_headers_factory):
    """IP 同时落入父子 CIDR 时，父子节点都是真正命中项。"""
    user_headers = _setup_tree_data(client, admin_headers, user_headers_factory)

    resp = client.get("/api/lookup?q=10.0.1.5", headers=user_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    parent = data["results"][0]
    assert parent["cidr"] == "10.0.0.0/22"
    assert parent["is_match"] is True
    child = parent["children"][0]
    assert child["cidr"] == "10.0.1.0/24"
    assert child["is_match"] is True


def test_lookup_overlap_cidr(client, admin_headers, user_headers_factory):
    _, _, user_headers = _setup_data(client, admin_headers, user_headers_factory)
    resp = client.get("/api/lookup?q=10.0.0.0/25&exact=false", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


def test_lookup_results_order_by_region_and_plane_name(client, admin_headers, user_headers_factory):
    """lookup 多条结果按 Region 名称、网络平面名称、scope、CIDR 升序返回。"""
    region = client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers).json()
    pt_z = client.post("/api/network-plane-types", json={"name": "Z平面"}, headers=admin_headers).json()
    pt_a = client.post("/api/network-plane-types", json={"name": "A平面"}, headers=admin_headers).json()
    user_headers = user_headers_factory([region["id"]])
    client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": pt_z["id"], "cidr": "10.0.1.0/24"},
        headers=user_headers,
    )
    client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": pt_a["id"], "cidr": "10.0.2.0/24"},
        headers=user_headers,
    )

    resp = client.get("/api/lookup?q=10.0.0.0/8&exact=false", headers=user_headers)

    assert resp.status_code == 200
    assert [item["plane_type_name"] for item in resp.json()["results"]] == ["A平面", "Z平面"]


def test_lookup_no_match(client, admin_headers, user_headers_factory):
    _, _, user_headers = _setup_data(client, admin_headers, user_headers_factory)
    resp = client.get("/api/lookup?q=192.168.1.1", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_lookup_invalid_query(client, admin_headers):
    resp = client.get("/api/lookup?q=not-an-ip", headers=admin_headers)
    assert resp.status_code == 400


def test_lookup_invalid_query_is_rejected_before_database_query():
    """非法 IP/CIDR 输入应先被校验拦截，避免无意义全表扫描。"""
    with pytest.raises(BusinessError):
        lookup_region_planes(_NoQueryDB(), "not-an-ip")
