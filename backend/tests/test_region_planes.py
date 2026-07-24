"""Region 网络平面实例测试。

覆盖：Region 创建平面、CIDR/VLAN/网关约束校验、树形结构查询和删除保护。
"""

from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.services import region_plane as region_plane_service


class _NoQueryDB:
    """用于确认纯输入错误会在访问数据库前被拦截。"""

    def query(self, *args, **kwargs):
        raise AssertionError("invalid plane assignment should not touch database")


def _create_plane_type(client, admin_headers, name, parent_id=None, **kwargs):
    """创建网络平面类型。"""
    payload = {"name": name}
    if parent_id:
        payload["parent_id"] = parent_id
    payload.update(kwargs)
    response = client.post("/api/network-plane-types", json=payload, headers=admin_headers)
    return response


def _setup(client, admin_headers, user_headers_factory):
    """创建 Region 和根 PlaneType，返回 (region, pt, user_headers)。"""
    region = client.post("/api/regions", json={"name": "TestRegion"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "管理平面").json()
    return region, pt, user_headers_factory([region["id"]])


def _create_region_plane(client, region_id, pt_id, cidr, user_headers, **kwargs):
    """创建 Region 网络平面并返回响应。"""
    payload = {"plane_type_id": pt_id, "cidr": cidr}
    payload.update(kwargs)
    return client.post(
        f"/api/regions/{region_id}/planes",
        json=payload,
        headers=user_headers,
    )


def _update_plane(client, region_id, plane_id, user_headers, **kwargs):
    """更新 Region 网络平面并返回响应。"""
    return client.put(
        f"/api/regions/{region_id}/planes/{plane_id}",
        json=kwargs,
        headers=user_headers,
    )


def test_create_root_plane_with_cidr(client, admin_headers, user_headers_factory):
    """创建根平面时传入 CIDR，校验字段正确返回。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _create_region_plane(
        client,
        region["id"],
        pt["id"],
        "10.0.0.0/22",
        user_headers,
        vlan_id=100,
        gateway_position="CE01",
        gateway_ip="10.0.0.1",
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["cidr"] == "10.0.0.0/22"
    assert data["vlan_id"] == 100
    assert data["gateway_position"] == "CE01"
    assert data["gateway_ip"] == "10.0.0.1"
    assert data["scope"] == "Global"
    assert data["parent_id"] is None
    assert data["plane_type_parent_id"] is None
    assert data["updated_at"]


def test_create_root_plane_duplicate(client, admin_headers, user_headers_factory):
    """同一 (region, plane_type, scope) 不能重复创建。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers)
    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers)

    assert resp.status_code == 409
    assert "Global 作用域中创建" in resp.json()["detail"]


def test_create_root_plane_allows_same_type_different_scope(client, admin_headers, user_headers_factory):
    """同一类型可在不同作用域内创建，CIDR 不重叠时允许创建。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, scope="业务AZ1")

    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.1.0/24", user_headers, scope="业务AZ2")

    assert resp.status_code == 201
    assert resp.json()["scope"] == "业务AZ2"


def test_create_root_plane_normalizes_blank_scope_to_global(client, admin_headers, user_headers_factory):
    """空作用域统一归一化为 Global，并参与唯一性约束。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, scope="  ")

    assert resp.status_code == 201
    assert resp.json()["scope"] == "Global"

    duplicate_resp = _create_region_plane(client, region["id"], pt["id"], "10.0.1.0/24", user_headers)
    assert duplicate_resp.status_code == 409


def test_get_plane_tree_orders_root_planes_by_type_name(client, admin_headers, user_headers_factory):
    """Region 平面树根节点默认按网络平面类型名称升序展示。"""
    region = client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers).json()
    pt_z = _create_plane_type(client, admin_headers, "Z平面").json()
    pt_a = _create_plane_type(client, admin_headers, "A平面").json()
    user_headers = user_headers_factory([region["id"]])
    _create_region_plane(client, region["id"], pt_z["id"], "10.0.1.0/24", user_headers)
    _create_region_plane(client, region["id"], pt_a["id"], "10.0.2.0/24", user_headers)

    response = client.get(f"/api/regions/{region['id']}/planes", headers=admin_headers)

    assert response.status_code == 200
    assert [node["plane_type_name"] for node in response.json()] == ["A平面", "Z平面"]


def test_create_root_plane_rejects_same_type_scope_cidr_overlap(client, admin_headers, user_headers_factory):
    """同一类型的不同作用域实例之间 CIDR 不能重叠。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, scope="业务AZ1")

    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.0.128/25", user_headers, scope="业务AZ2")

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "本 Region 非层级关系网络平面 CIDR 重叠" in detail
    assert "Region=TestRegion" in detail
    assert "网络平面=管理平面" in detail
    assert "作用域=业务AZ1" in detail
    assert "CIDR=10.0.0.0/24" in detail


def test_create_root_plane_rejects_same_region_unrelated_cidr_overlap(client, admin_headers, user_headers_factory):
    """创建根平面时不能与本 Region 内其他非层级关系平面 CIDR 重叠。"""
    region, pt_a, user_headers = _setup(client, admin_headers, user_headers_factory)
    pt_b = _create_plane_type(client, admin_headers, "业务平面").json()
    _create_region_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers)

    resp = _create_region_plane(client, region["id"], pt_b["id"], "10.0.0.128/25", user_headers)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "本 Region 非层级关系网络平面 CIDR 重叠" in detail
    assert "Region=TestRegion" in detail
    assert "网络平面=管理平面" in detail
    assert "CIDR=10.0.0.0/24" in detail


def test_create_root_plane_rejects_other_region_cidr_overlap(client, admin_headers, user_headers_factory):
    """创建根平面时不能与其他 Region 的网络平面 CIDR 重叠。"""
    region_a = client.post("/api/regions", json={"name": "RegionA"}, headers=admin_headers).json()
    region_b = client.post("/api/regions", json={"name": "RegionB"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "管理平面").json()
    user_headers = user_headers_factory([region_a["id"], region_b["id"]])
    _create_region_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers)

    resp = _create_region_plane(client, region_b["id"], pt["id"], "10.0.0.128/25", user_headers)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "其他 Region 网络平面 CIDR 重叠" in detail
    assert "Region=RegionA" in detail
    assert "网络平面=管理平面" in detail
    assert "CIDR=10.0.0.0/24" in detail


def test_create_root_plane_allows_other_region_cidr_overlap_when_configured(
    client,
    admin_headers,
    user_headers_factory,
    monkeypatch,
):
    """配置允许时，CIDR 可以跨 Region 重叠。"""
    monkeypatch.setattr(region_plane_service.settings, "ALLOW_CIDR_OVERLAP_ACROSS_REGIONS", True)
    region_a = client.post("/api/regions", json={"name": "RegionA"}, headers=admin_headers).json()
    region_b = client.post("/api/regions", json={"name": "RegionB"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "管理平面").json()
    user_headers = user_headers_factory([region_a["id"], region_b["id"]])
    _create_region_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers)

    resp = _create_region_plane(client, region_b["id"], pt["id"], "10.0.0.128/25", user_headers)

    assert resp.status_code == 201
    assert resp.json()["cidr"] == "10.0.0.128/25"


def test_create_root_plane_keeps_same_region_cidr_overlap_rejection_when_cross_region_allowed(
    client,
    admin_headers,
    user_headers_factory,
    monkeypatch,
):
    """配置只放宽跨 Region，本 Region 非层级 CIDR 重叠仍拒绝。"""
    monkeypatch.setattr(region_plane_service.settings, "ALLOW_CIDR_OVERLAP_ACROSS_REGIONS", True)
    region, pt_a, user_headers = _setup(client, admin_headers, user_headers_factory)
    pt_b = _create_plane_type(client, admin_headers, "业务平面").json()
    _create_region_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers)

    resp = _create_region_plane(client, region["id"], pt_b["id"], "10.0.0.128/25", user_headers)

    assert resp.status_code == 409
    assert "本 Region 非层级关系网络平面 CIDR 重叠" in resp.json()["detail"]


def test_create_root_plane_invalid_cidr(client, admin_headers, user_headers_factory):
    """创建根平面时传入无效 CIDR 应报错。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _create_region_plane(client, region["id"], pt["id"], "invalid-cidr", user_headers)

    assert resp.status_code == 409
    assert "无效的 CIDR" in resp.json()["detail"]


def test_create_root_plane_missing_plane_type_returns_404(client, admin_headers, user_headers_factory):
    """网络平面类型不存在时由 Service 返回 404 语义。"""
    region, _, user_headers = _setup(client, admin_headers, user_headers_factory)

    resp = _create_region_plane(client, region["id"], "missing-plane-type", "10.0.0.0/24", user_headers)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "网络平面类型不存在"


def test_create_root_plane_invalid_cidr_is_rejected_before_database_query():
    """无效 CIDR 属于纯输入错误，应先拦截再访问数据库。"""
    with pytest.raises(region_plane_service.BusinessError):
        region_plane_service.create_plane_for_region(
            cast(Session, _NoQueryDB()),
            "region-id",
            "plane-type-id",
            "invalid-cidr",
            "tester",
        )


@pytest.mark.parametrize(
    ("cidr", "expected_cidr"),
    [
        ("10.0.0.1/30", "10.0.0.0/30"),
        ("2001:db8::1234/64", "2001:db8::/64"),
    ],
)
def test_create_plane_rejects_cidr_using_host_address_before_database_query(cidr, expected_cidr):
    """CIDR 使用网段内的主机地址时，应在访问数据库前提示使用网络地址。"""
    with pytest.raises(region_plane_service.BusinessError) as exc_info:
        region_plane_service.create_plane_for_region(
            cast(Session, _NoQueryDB()),
            "region-id",
            "plane-type-id",
            cidr,
            "tester",
        )

    assert str(exc_info.value) == f"CIDR 必须使用网段的网络地址，当前输入 {cidr}，建议使用 {expected_cidr}"


@pytest.mark.parametrize("cidr", ["10.0.0.0/30", "10.0.0.5/32", "2001:db8::1234/128"])
def test_create_plane_allows_network_address_cidr(client, admin_headers, user_headers_factory, cidr):
    """使用网络地址的 CIDR，包括合法的 /32 和 /128，应允许创建。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)

    resp = _create_region_plane(client, region["id"], pt["id"], cidr, user_headers)

    assert resp.status_code == 201
    assert resp.json()["cidr"] == cidr


def test_create_root_plane_gateway_ip_outside_cidr_is_rejected_before_database_query():
    """网关 IP 明显不在 CIDR 内时，不需要查询网络平面类型。"""
    with pytest.raises(region_plane_service.BusinessError):
        region_plane_service.create_plane_for_region(
            cast(Session, _NoQueryDB()),
            "region-id",
            "plane-type-id",
            "10.0.0.0/24",
            "tester",
            gateway_ip="10.0.1.1",
        )


def test_create_root_plane_invalid_vlan_id(client, admin_headers, user_headers_factory):
    """创建平面时 VLAN ID 必须在 1-4094 范围内。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers, vlan_id=4095)

    assert resp.status_code == 422


def test_create_root_plane_rejects_duplicate_vlan_in_region(client, admin_headers, user_headers_factory):
    """创建平面时 VLAN ID 在同一 Region 内不能重复。"""
    region, pt_a, user_headers = _setup(client, admin_headers, user_headers_factory)
    pt_b = _create_plane_type(client, admin_headers, "业务平面").json()
    _create_region_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers, vlan_id=100)

    resp = _create_region_plane(client, region["id"], pt_b["id"], "10.0.1.0/24", user_headers, vlan_id=100)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "VLAN 100 已在该 Region 中使用" in detail
    assert "Region=TestRegion" in detail
    assert "网络平面=管理平面" in detail
    assert "CIDR=10.0.0.0/24" in detail
    assert "VLAN=100" in detail


def test_create_root_plane_allows_duplicate_vlan_across_regions_by_default(
    client,
    admin_headers,
    user_headers_factory,
):
    """默认配置下 VLAN 只要求 Region 内唯一，跨 Region 可重复。"""
    region_a = client.post("/api/regions", json={"name": "RegionA"}, headers=admin_headers).json()
    region_b = client.post("/api/regions", json={"name": "RegionB"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "管理平面").json()
    user_headers = user_headers_factory([region_a["id"], region_b["id"]])
    _create_region_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers, vlan_id=100)

    resp = _create_region_plane(client, region_b["id"], pt["id"], "10.0.1.0/24", user_headers, vlan_id=100)

    assert resp.status_code == 201
    assert resp.json()["vlan_id"] == 100


def test_create_root_plane_rejects_duplicate_vlan_across_regions_when_configured(
    client,
    admin_headers,
    user_headers_factory,
    monkeypatch,
):
    """配置不允许时，VLAN 跨 Region 重复也会被拒绝。"""
    monkeypatch.setattr(region_plane_service.settings, "ALLOW_VLAN_OVERLAP_ACROSS_REGIONS", False)
    region_a = client.post("/api/regions", json={"name": "RegionA"}, headers=admin_headers).json()
    region_b = client.post("/api/regions", json={"name": "RegionB"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "管理平面").json()
    user_headers = user_headers_factory([region_a["id"], region_b["id"]])
    _create_region_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers, vlan_id=100)

    resp = _create_region_plane(client, region_b["id"], pt["id"], "10.0.1.0/24", user_headers, vlan_id=100)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "VLAN 100 已被其他 Region 使用" in detail
    assert "Region=RegionA" in detail


def test_create_root_plane_invalid_gateway_ip(client, admin_headers, user_headers_factory):
    """创建平面时网关 IP 地址格式必须有效。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers, gateway_ip="bad-ip")

    assert resp.status_code == 422


def test_create_root_plane_rejects_gateway_ip_outside_cidr(client, admin_headers, user_headers_factory):
    """创建平面时网关 IP 必须在平面 CIDR 范围内。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers, gateway_ip="192.168.0.1")

    assert resp.status_code == 409
    assert "必须在平面 CIDR" in resp.json()["detail"]


def test_create_private_plane_warns_when_gateway_ip_is_not_first_usable(client, admin_headers, user_headers_factory):
    """私网平面网关 IP 不是 CIDR 第一个可用 IP 时返回弱校验提示。"""
    region = client.post("/api/regions", json={"name": "TestRegion"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "私网平面", is_private=True).json()
    user_headers = user_headers_factory([region["id"]])

    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, gateway_ip="10.0.0.254")

    assert resp.status_code == 201
    assert "第一个可用 IP 10.0.0.1" in resp.json()["gateway_ip_warning"]


def test_create_public_plane_warns_when_gateway_ip_is_not_last_usable(client, admin_headers, user_headers_factory):
    """非私网平面网关 IP 不是 CIDR 最后一个可用 IP 时返回弱校验提示。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)

    resp = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, gateway_ip="10.0.0.1")

    assert resp.status_code == 201
    assert "最后一个可用 IP 10.0.0.254" in resp.json()["gateway_ip_warning"]


@pytest.mark.parametrize("is_private", [False, True])
def test_create_ipv6_plane_gateway_warning_ignores_private_flag(
    client, admin_headers, user_headers_factory, is_private
):
    """IPv6 网关推荐和提示文案不区分私网属性。"""
    region = client.post("/api/regions", json={"name": "TestRegion"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "IPv6 平面", is_private=is_private).json()
    user_headers = user_headers_factory([region["id"]])

    resp = _create_region_plane(
        client,
        region["id"],
        pt["id"],
        "2001:db8::/64",
        user_headers,
        gateway_ip="2001:db8::ffff",
    )

    assert resp.status_code == 201
    assert (
        resp.json()["gateway_ip_warning"]
        == "当前网关 IP 不符合推荐规则：IPv6 平面建议使用 CIDR 内第一个可用 IP 2001:db8::1"
    )


def test_create_plane_accepts_longest_ipv6_text(client, admin_headers, user_headers_factory):
    """API 字段长度应覆盖最长的合法 IPv6 地址及其 CIDR。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    gateway_ip = "ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255"
    cidr = f"{gateway_ip}/128"

    resp = _create_region_plane(
        client,
        region["id"],
        pt["id"],
        cidr,
        user_headers,
        gateway_ip=gateway_ip,
    )

    assert resp.status_code == 201
    assert resp.json()["cidr"] == cidr
    assert resp.json()["gateway_ip"] == gateway_ip


def test_update_root_plane_fields_but_not_plane_type(client, admin_headers, user_headers_factory):
    """编辑 Region 网络平面时可更新业务字段，但不能修改网络平面类型。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    other_pt = _create_plane_type(client, admin_headers, "业务平面").json()
    plane = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers).json()

    resp = _update_plane(
        client,
        region["id"],
        plane["id"],
        user_headers,
        plane_type_id=other_pt["id"],
        scope="业务AZ1",
        cidr="10.0.1.0/24",
        vlan_id=200,
        gateway_position="Core-A",
        gateway_ip="10.0.1.254",
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["plane_type_id"] == pt["id"]
    assert data["scope"] == "业务AZ1"
    assert data["cidr"] == "10.0.1.0/24"
    assert data["vlan_id"] == 200
    assert data["gateway_position"] == "Core-A"
    assert data["gateway_ip"] == "10.0.1.254"


def test_update_plane_rejects_duplicate_scope(client, admin_headers, user_headers_factory):
    """编辑作用域时仍受同一 (region, plane_type, scope) 唯一约束限制。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    global_plane = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers).json()
    _create_region_plane(client, region["id"], pt["id"], "10.0.1.0/24", user_headers, scope="业务AZ1")

    resp = _update_plane(
        client,
        region["id"],
        global_plane["id"],
        user_headers,
        scope="业务AZ1",
        cidr="10.0.0.0/24",
    )

    assert resp.status_code == 409
    assert "业务AZ1 作用域中创建" in resp.json()["detail"]


def test_update_plane_rejects_same_region_cidr_overlap(client, admin_headers, user_headers_factory):
    """编辑 CIDR 时不能与本 Region 内其他非父子关系平面重叠。"""
    region, pt_a, user_headers = _setup(client, admin_headers, user_headers_factory)
    pt_b = _create_plane_type(client, admin_headers, "业务平面").json()
    _create_region_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers)
    plane_b = _create_region_plane(client, region["id"], pt_b["id"], "10.0.1.0/24", user_headers).json()

    resp = _update_plane(
        client,
        region["id"],
        plane_b["id"],
        user_headers,
        cidr="10.0.0.128/25",
    )

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "本 Region 非层级关系网络平面 CIDR 重叠" in detail
    assert "Region=TestRegion" in detail
    assert "网络平面=管理平面" in detail
    assert "CIDR=10.0.0.0/24" in detail


def test_update_plane_rejects_other_region_cidr_overlap(client, admin_headers, user_headers_factory):
    """编辑 CIDR 时不能与其他 Region 的网络平面重叠。"""
    region_a = client.post("/api/regions", json={"name": "RegionA"}, headers=admin_headers).json()
    region_b = client.post("/api/regions", json={"name": "RegionB"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "管理平面").json()
    user_headers = user_headers_factory([region_a["id"], region_b["id"]])
    _create_region_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers)
    plane_b = _create_region_plane(client, region_b["id"], pt["id"], "10.0.1.0/24", user_headers).json()

    resp = _update_plane(
        client,
        region_b["id"],
        plane_b["id"],
        user_headers,
        cidr="10.0.0.128/25",
    )

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "其他 Region 网络平面 CIDR 重叠" in detail
    assert "Region=RegionA" in detail
    assert "网络平面=管理平面" in detail
    assert "CIDR=10.0.0.0/24" in detail


def test_update_child_plane_allows_overlap_with_parent(client, admin_headers, user_headers_factory):
    """编辑子平面 CIDR 时允许与自己的父级平面存在包含关系。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)
    child = _create_region_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers).json()

    resp = _update_plane(
        client,
        region["id"],
        child["id"],
        user_headers,
        scope="Global",
        cidr="10.0.1.0/24",
    )

    assert resp.status_code == 200
    assert resp.json()["cidr"] == "10.0.1.0/24"


def test_update_child_plane_rejects_cidr_outside_parent(client, admin_headers, user_headers_factory):
    """编辑子平面 CIDR 时仍必须落在父平面 CIDR 范围内。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)
    child = _create_region_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers).json()

    resp = _update_plane(
        client,
        region["id"],
        child["id"],
        user_headers,
        scope="Global",
        cidr="192.168.0.0/24",
    )

    assert resp.status_code == 409
    assert "范围内" in resp.json()["detail"]


def test_update_plane_rejects_cidr_using_host_address(client, admin_headers, user_headers_factory):
    """编辑网络平面时，CIDR 地址部分同样不能使用网段内的主机地址。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    plane = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers).json()

    resp = _update_plane(
        client,
        region["id"],
        plane["id"],
        user_headers,
        cidr="10.0.0.1/30",
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == ("CIDR 必须使用网段的网络地址，当前输入 10.0.0.1/30，建议使用 10.0.0.0/30")


def test_update_plane_rejects_gateway_ip_outside_cidr(client, admin_headers, user_headers_factory):
    """编辑网关 IP 时必须位于当前 CIDR 范围内。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    plane = _create_region_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers).json()

    resp = _update_plane(
        client,
        region["id"],
        plane["id"],
        user_headers,
        cidr="10.0.0.0/24",
        gateway_ip="192.168.0.1",
    )

    assert resp.status_code == 409
    assert "必须在平面 CIDR" in resp.json()["detail"]


def test_update_plane_rejects_duplicate_vlan_in_region(client, admin_headers, user_headers_factory):
    """编辑 VLAN ID 时同一 Region 内不能重复。"""
    region, pt_a, user_headers = _setup(client, admin_headers, user_headers_factory)
    pt_b = _create_plane_type(client, admin_headers, "业务平面").json()
    _create_region_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers, vlan_id=100)
    plane_b = _create_region_plane(client, region["id"], pt_b["id"], "10.0.1.0/24", user_headers, vlan_id=200).json()

    resp = _update_plane(
        client,
        region["id"],
        plane_b["id"],
        user_headers,
        cidr="10.0.1.0/24",
        vlan_id=100,
    )

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "VLAN 100 已在该 Region 中使用" in detail
    assert "Region=TestRegion" in detail
    assert "网络平面=管理平面" in detail
    assert "CIDR=10.0.0.0/24" in detail
    assert "VLAN=100" in detail


def test_create_child_plane(client, admin_headers, user_headers_factory):
    """正常创建子平面，校验 CIDR 在父范围内。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    root = _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers).json()

    resp = _create_region_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["cidr"] == "10.0.0.0/24"
    assert data["scope"] == "Global"
    assert data["parent_id"] == root["id"]
    assert data["plane_type_parent_id"] == root_pt["id"]
    assert data["updated_at"]


def test_create_child_requires_parent_created(client, admin_headers, user_headers_factory):
    """子类型平面必须在父级已创建后才能创建。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()

    resp = _create_region_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers)

    assert resp.status_code == 409
    assert "父级网络平面尚未" in resp.json()["detail"]


def test_get_parent_context_for_root_type(client, admin_headers, user_headers_factory):
    """根类型不需要父平面实例，空作用域归一化为 Global。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)

    resp = client.get(
        f"/api/regions/{region['id']}/planes/parent-context",
        params={"plane_type_id": root_pt["id"], "scope": "  "},
        headers=user_headers,
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "root",
        "requested_scope": "Global",
        "parent_type_id": None,
        "parent_type_name": None,
        "parent_plane": None,
    }


def test_get_parent_context_prefers_same_scope_parent(client, admin_headers, user_headers_factory):
    """父平面预检优先返回同作用域实例。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/16", user_headers)
    scoped_parent = _create_region_plane(
        client,
        region["id"],
        root_pt["id"],
        "10.1.0.0/16",
        user_headers,
        scope="业务AZ1",
        vlan_id=100,
        gateway_position="Core-A",
        gateway_ip="10.1.0.254",
    ).json()

    resp = client.get(
        f"/api/regions/{region['id']}/planes/parent-context",
        params={"plane_type_id": child_pt["id"], "scope": "业务AZ1"},
        headers=user_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "found"
    assert data["requested_scope"] == "业务AZ1"
    assert data["parent_type_id"] == root_pt["id"]
    assert data["parent_type_name"] == "管理平面"
    assert data["parent_plane"] == {
        "id": scoped_parent["id"],
        "scope": "业务AZ1",
        "cidr": "10.1.0.0/16",
        "vlan_id": 100,
        "gateway_position": "Core-A",
        "gateway_ip": "10.1.0.254",
    }


def test_get_parent_context_falls_back_to_global_parent(client, admin_headers, user_headers_factory):
    """同作用域父实例不存在时，父平面预检返回 Global 实例。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    global_parent = _create_region_plane(
        client,
        region["id"],
        root_pt["id"],
        "10.0.0.0/16",
        user_headers,
    ).json()

    resp = client.get(
        f"/api/regions/{region['id']}/planes/parent-context",
        params={"plane_type_id": child_pt["id"], "scope": "业务AZ1"},
        headers=user_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "found"
    assert data["requested_scope"] == "业务AZ1"
    assert data["parent_plane"]["id"] == global_parent["id"]
    assert data["parent_plane"]["scope"] == "Global"


def test_get_parent_context_reports_missing_parent_instance(client, admin_headers, user_headers_factory):
    """父类型存在但没有有效实例时返回可展示的 missing 状态。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()

    resp = client.get(
        f"/api/regions/{region['id']}/planes/parent-context",
        params={"plane_type_id": child_pt["id"], "scope": "业务AZ1"},
        headers=user_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "missing"
    assert data["parent_type_id"] == root_pt["id"]
    assert data["parent_type_name"] == "管理平面"
    assert data["parent_plane"] is None


def test_get_parent_context_allows_read_without_region_write_permission(client, admin_headers, user_headers_factory):
    """父平面预检是只读接口，不要求目标 Region 的业务写权限。"""
    _, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    unauthorized_region = client.post("/api/regions", json={"name": "NoPermissionRegion"}, headers=admin_headers).json()

    resp = client.get(
        f"/api/regions/{unauthorized_region['id']}/planes/parent-context",
        params={"plane_type_id": root_pt["id"], "scope": "Global"},
        headers=user_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "root"


def test_create_child_outside_parent(client, admin_headers, user_headers_factory):
    """子 CIDR 超出父范围应报错。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)

    resp = _create_region_plane(client, region["id"], child_pt["id"], "192.168.0.0/24", user_headers)

    assert resp.status_code == 409
    assert "范围内" in resp.json()["detail"]


def test_create_child_sibling_overlap(client, admin_headers, user_headers_factory):
    """兄弟平面 CIDR 重叠应报错。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_a = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    child_b = _create_plane_type(client, admin_headers, "管理子平面B", parent_id=root_pt["id"]).json()
    _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)
    _create_region_plane(client, region["id"], child_a["id"], "10.0.0.0/24", user_headers)

    resp = _create_region_plane(client, region["id"], child_b["id"], "10.0.0.0/25", user_headers)

    assert resp.status_code == 409
    assert "重叠" in resp.json()["detail"]


def test_create_child_unrelated_ok(client, admin_headers, user_headers_factory):
    """兄弟平面 CIDR 不重叠时允许创建。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_a = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    child_b = _create_plane_type(client, admin_headers, "管理子平面B", parent_id=root_pt["id"]).json()
    _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)
    _create_region_plane(client, region["id"], child_a["id"], "10.0.0.0/24", user_headers)

    resp = _create_region_plane(client, region["id"], child_b["id"], "10.0.1.0/24", user_headers)

    assert resp.status_code == 201


def test_validate_network_overlap_policy_on_startup_rejects_existing_cross_region_cidr_conflict(
    test_db,
    client,
    admin_headers,
    user_headers_factory,
    monkeypatch,
):
    """启动检查会拒绝与当前 CIDR 跨 Region 策略不一致的已有数据。"""
    monkeypatch.setattr(region_plane_service.settings, "ALLOW_CIDR_OVERLAP_ACROSS_REGIONS", True)
    region_a = client.post("/api/regions", json={"name": "RegionA"}, headers=admin_headers).json()
    region_b = client.post("/api/regions", json={"name": "RegionB"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "管理平面").json()
    user_headers = user_headers_factory([region_a["id"], region_b["id"]])
    _create_region_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers)
    _create_region_plane(client, region_b["id"], pt["id"], "10.0.0.128/25", user_headers)
    monkeypatch.setattr(region_plane_service.settings, "ALLOW_CIDR_OVERLAP_ACROSS_REGIONS", False)

    session = Session(test_db)
    try:
        with pytest.raises(region_plane_service.BusinessError, match="跨 Region CIDR 重叠"):
            region_plane_service.validate_network_overlap_policy_on_startup(session)
    finally:
        session.close()


def test_validate_network_overlap_policy_on_startup_rejects_existing_cross_region_vlan_conflict(
    test_db,
    client,
    admin_headers,
    user_headers_factory,
    monkeypatch,
):
    """启动检查会拒绝与当前 VLAN 跨 Region 策略不一致的已有数据。"""
    region_a = client.post("/api/regions", json={"name": "RegionA"}, headers=admin_headers).json()
    region_b = client.post("/api/regions", json={"name": "RegionB"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "管理平面").json()
    user_headers = user_headers_factory([region_a["id"], region_b["id"]])
    _create_region_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers, vlan_id=100)
    _create_region_plane(client, region_b["id"], pt["id"], "10.0.1.0/24", user_headers, vlan_id=100)
    monkeypatch.setattr(region_plane_service.settings, "ALLOW_VLAN_OVERLAP_ACROSS_REGIONS", False)

    session = Session(test_db)
    try:
        with pytest.raises(region_plane_service.BusinessError, match="跨 Region VLAN 重复"):
            region_plane_service.validate_network_overlap_policy_on_startup(session)
    finally:
        session.close()


def test_get_plane_tree(client, admin_headers, user_headers_factory):
    """验证 GET /regions/{rid}/planes 返回由全局类型树派生的 Region 平面树。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_a = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    child_b = _create_plane_type(client, admin_headers, "管理子平面B", parent_id=root_pt["id"]).json()
    grandchild = _create_plane_type(client, admin_headers, "管理孙平面", parent_id=child_a["id"]).json()

    _create_region_plane(
        client,
        region["id"],
        root_pt["id"],
        "10.0.0.0/22",
        user_headers,
        vlan_id=200,
        gateway_position="Core-A",
        gateway_ip="10.0.0.254",
    )
    _create_region_plane(client, region["id"], child_a["id"], "10.0.0.0/24", user_headers)
    _create_region_plane(client, region["id"], child_b["id"], "10.0.1.0/24", user_headers)
    _create_region_plane(client, region["id"], grandchild["id"], "10.0.0.0/25", user_headers)

    resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)

    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1
    assert tree[0]["cidr"] == "10.0.0.0/22"
    assert tree[0]["scope"] == "Global"
    assert tree[0]["vlan_id"] == 200
    assert tree[0]["gateway_position"] == "Core-A"
    assert tree[0]["gateway_ip"] == "10.0.0.254"
    assert tree[0]["updated_at"]
    assert len(tree[0]["children"]) == 2
    child_a_node = next(node for node in tree[0]["children"] if node["plane_type_id"] == child_a["id"])
    assert child_a_node["children"][0]["cidr"] == "10.0.0.0/25"


def test_get_plane_tree_prefers_same_scope_parent(client, admin_headers, user_headers_factory):
    """同一作用域父平面存在时，子平面优先挂到同 scope 父级。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/16", user_headers)
    _create_region_plane(client, region["id"], root_pt["id"], "10.1.0.0/16", user_headers, scope="业务AZ1")
    _create_region_plane(client, region["id"], child_pt["id"], "10.1.1.0/24", user_headers, scope="业务AZ1")

    resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)

    assert resp.status_code == 200
    tree = resp.json()
    global_root = next(node for node in tree if node["scope"] == "Global")
    az1_root = next(node for node in tree if node["scope"] == "业务AZ1")
    assert global_root["children"] == []
    assert len(az1_root["children"]) == 1
    assert az1_root["children"][0]["scope"] == "业务AZ1"
    assert az1_root["children"][0]["parent_id"] == az1_root["id"]


def test_get_plane_tree_falls_back_to_global_parent(client, admin_headers, user_headers_factory):
    """同 scope 父平面不存在时，子平面回退挂到 Global 父级。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    global_root = _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/16", user_headers).json()
    _create_region_plane(client, region["id"], child_pt["id"], "10.0.1.0/24", user_headers, scope="业务AZ1")

    resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)

    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1
    assert tree[0]["id"] == global_root["id"]
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["scope"] == "业务AZ1"
    assert tree[0]["children"][0]["parent_id"] == global_root["id"]


def test_delete_parent_plane_rejects_when_children_exist(client, admin_headers, user_headers_factory):
    """删除存在子平面的父平面时应拒绝，并要求先删除子平面。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    root = _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers).json()
    child = _create_region_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers).json()

    resp = client.delete(f"/api/regions/{region['id']}/planes/{root['id']}", headers=user_headers)

    assert resp.status_code == 409
    assert "请先删除子平面" in resp.json()["detail"]
    tree_resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)
    tree = tree_resp.json()
    assert len(tree) == 1
    assert tree[0]["id"] == root["id"]
    assert tree[0]["children"][0]["id"] == child["id"]


def test_delete_leaf_plane_success(client, admin_headers, user_headers_factory):
    """删除叶子平面时应成功。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    root = _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers).json()
    child = _create_region_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers).json()

    resp = client.delete(f"/api/regions/{region['id']}/planes/{child['id']}", headers=user_headers)

    assert resp.status_code == 204
    tree_resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)
    tree = tree_resp.json()
    assert len(tree) == 1
    assert tree[0]["id"] == root["id"]
    assert tree[0]["children"] == []


def test_delete_scoped_parent_ignores_other_scope_children(client, admin_headers, user_headers_factory):
    """删除某个作用域的叶子父平面时，其他作用域子树不应阻止删除。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    az1_root = _create_region_plane(
        client,
        region["id"],
        root_pt["id"],
        "10.0.0.0/22",
        user_headers,
        scope="业务AZ1",
    ).json()
    az2_root = _create_region_plane(
        client, region["id"], root_pt["id"], "10.0.4.0/22", user_headers, scope="业务AZ2"
    ).json()
    az2_child = _create_region_plane(
        client,
        region["id"],
        child_pt["id"],
        "10.0.4.0/24",
        user_headers,
        scope="业务AZ2",
    ).json()

    resp = client.delete(f"/api/regions/{region['id']}/planes/{az1_root['id']}", headers=user_headers)

    assert resp.status_code == 204
    tree_resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)
    tree = tree_resp.json()
    assert len(tree) == 1
    assert tree[0]["id"] == az2_root["id"]
    assert tree[0]["children"][0]["id"] == az2_child["id"]


def test_delete_global_parent_rejects_fallback_children(client, admin_headers, user_headers_factory):
    """同 scope 父平面不存在时，回退挂载到 Global 父平面的子平面会阻止删除。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    global_root = _create_region_plane(client, region["id"], root_pt["id"], "10.0.0.0/16", user_headers).json()
    child = _create_region_plane(
        client, region["id"], child_pt["id"], "10.0.1.0/24", user_headers, scope="业务AZ1"
    ).json()

    resp = client.delete(f"/api/regions/{region['id']}/planes/{global_root['id']}", headers=user_headers)

    assert resp.status_code == 409
    assert "请先删除子平面" in resp.json()["detail"]
    tree_resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)
    tree = tree_resp.json()
    assert len(tree) == 1
    assert tree[0]["id"] == global_root["id"]
    assert tree[0]["children"][0]["id"] == child["id"]


def test_delete_nonexistent_plane(client, admin_headers, user_headers_factory):
    """删除不存在的平面应返回 404。"""
    region, _, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = client.delete(f"/api/regions/{region['id']}/planes/nonexistent", headers=user_headers)
    assert resp.status_code == 404
