"""网络平面全局树状结构测试。

覆盖：网络平面类型父子关系、Region 启用平面、CIDR 约束校验、树形结构查询、级联删除。
"""


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


def _enable_plane(client, region_id, pt_id, cidr, user_headers, **kwargs):
    """启用 Region 网络平面并返回响应。"""
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
    resp = _enable_plane(
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
    """同一 (region, plane_type, scope) 不能重复启用。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    _enable_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers)
    resp = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers)

    assert resp.status_code == 409
    assert "Global 作用域中启用" in resp.json()["detail"]


def test_create_root_plane_allows_same_type_different_scope(client, admin_headers, user_headers_factory):
    """同一类型可在不同作用域内启用，CIDR 不重叠时允许创建。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    _enable_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, scope="业务AZ1")

    resp = _enable_plane(client, region["id"], pt["id"], "10.0.1.0/24", user_headers, scope="业务AZ2")

    assert resp.status_code == 201
    assert resp.json()["scope"] == "业务AZ2"


def test_create_root_plane_normalizes_blank_scope_to_global(client, admin_headers, user_headers_factory):
    """空作用域统一归一化为 Global，并参与唯一性约束。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, scope="  ")

    assert resp.status_code == 201
    assert resp.json()["scope"] == "Global"

    duplicate_resp = _enable_plane(client, region["id"], pt["id"], "10.0.1.0/24", user_headers)
    assert duplicate_resp.status_code == 409


def test_get_plane_tree_orders_root_planes_by_type_name(client, admin_headers, user_headers_factory):
    """Region 平面树根节点默认按网络平面类型名称升序展示。"""
    region = client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers).json()
    pt_z = _create_plane_type(client, admin_headers, "Z平面").json()
    pt_a = _create_plane_type(client, admin_headers, "A平面").json()
    user_headers = user_headers_factory([region["id"]])
    _enable_plane(client, region["id"], pt_z["id"], "10.0.1.0/24", user_headers)
    _enable_plane(client, region["id"], pt_a["id"], "10.0.2.0/24", user_headers)

    response = client.get(f"/api/regions/{region['id']}/planes", headers=admin_headers)

    assert response.status_code == 200
    assert [node["plane_type_name"] for node in response.json()] == ["A平面", "Z平面"]


def test_create_root_plane_rejects_same_type_scope_cidr_overlap(client, admin_headers, user_headers_factory):
    """同一类型的不同作用域实例之间 CIDR 不能重叠。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    _enable_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, scope="业务AZ1")

    resp = _enable_plane(client, region["id"], pt["id"], "10.0.0.128/25", user_headers, scope="业务AZ2")

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
    _enable_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers)

    resp = _enable_plane(client, region["id"], pt_b["id"], "10.0.0.128/25", user_headers)

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
    _enable_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers)

    resp = _enable_plane(client, region_b["id"], pt["id"], "10.0.0.128/25", user_headers)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "其他 Region 网络平面 CIDR 重叠" in detail
    assert "Region=RegionA" in detail
    assert "网络平面=管理平面" in detail
    assert "CIDR=10.0.0.0/24" in detail


def test_create_root_plane_invalid_cidr(client, admin_headers, user_headers_factory):
    """创建根平面时传入无效 CIDR 应报错。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _enable_plane(client, region["id"], pt["id"], "invalid-cidr", user_headers)

    assert resp.status_code == 409
    assert "无效的 CIDR" in resp.json()["detail"]


def test_create_root_plane_invalid_vlan_id(client, admin_headers, user_headers_factory):
    """启用平面时 VLAN ID 必须在 1-4094 范围内。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers, vlan_id=4095)

    assert resp.status_code == 422


def test_create_root_plane_rejects_duplicate_vlan_in_region(client, admin_headers, user_headers_factory):
    """创建平面时 VLAN ID 在同一 Region 内不能重复。"""
    region, pt_a, user_headers = _setup(client, admin_headers, user_headers_factory)
    pt_b = _create_plane_type(client, admin_headers, "业务平面").json()
    _enable_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers, vlan_id=100)

    resp = _enable_plane(client, region["id"], pt_b["id"], "10.0.1.0/24", user_headers, vlan_id=100)

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "VLAN 100 已在该 Region 中使用" in detail
    assert "Region=TestRegion" in detail
    assert "网络平面=管理平面" in detail
    assert "CIDR=10.0.0.0/24" in detail
    assert "VLAN=100" in detail


def test_create_root_plane_invalid_gateway_ip(client, admin_headers, user_headers_factory):
    """启用平面时网关 IP 地址格式必须有效。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers, gateway_ip="bad-ip")

    assert resp.status_code == 422


def test_create_root_plane_rejects_gateway_ip_outside_cidr(client, admin_headers, user_headers_factory):
    """启用平面时网关 IP 必须在平面 CIDR 范围内。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/22", user_headers, gateway_ip="192.168.0.1")

    assert resp.status_code == 409
    assert "必须在平面 CIDR" in resp.json()["detail"]


def test_create_private_plane_warns_when_gateway_ip_is_not_first_usable(client, admin_headers, user_headers_factory):
    """私网平面网关 IP 不是 CIDR 第一个可用 IP 时返回弱校验提示。"""
    region = client.post("/api/regions", json={"name": "TestRegion"}, headers=admin_headers).json()
    pt = _create_plane_type(client, admin_headers, "私网平面", is_private=True).json()
    user_headers = user_headers_factory([region["id"]])

    resp = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, gateway_ip="10.0.0.254")

    assert resp.status_code == 201
    assert "第一个可用 IP 10.0.0.1" in resp.json()["gateway_ip_warning"]


def test_create_public_plane_warns_when_gateway_ip_is_not_last_usable(client, admin_headers, user_headers_factory):
    """非私网平面网关 IP 不是 CIDR 最后一个可用 IP 时返回弱校验提示。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)

    resp = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers, gateway_ip="10.0.0.1")

    assert resp.status_code == 201
    assert "最后一个可用 IP 10.0.0.254" in resp.json()["gateway_ip_warning"]


def test_update_root_plane_fields_but_not_plane_type(client, admin_headers, user_headers_factory):
    """编辑 Region 网络平面时可更新业务字段，但不能修改网络平面类型。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    other_pt = _create_plane_type(client, admin_headers, "业务平面").json()
    plane = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers).json()

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
    global_plane = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers).json()
    _enable_plane(client, region["id"], pt["id"], "10.0.1.0/24", user_headers, scope="业务AZ1")

    resp = _update_plane(
        client,
        region["id"],
        global_plane["id"],
        user_headers,
        scope="业务AZ1",
        cidr="10.0.0.0/24",
    )

    assert resp.status_code == 409
    assert "业务AZ1 作用域中启用" in resp.json()["detail"]


def test_update_plane_rejects_same_region_cidr_overlap(client, admin_headers, user_headers_factory):
    """编辑 CIDR 时不能与本 Region 内其他非父子关系平面重叠。"""
    region, pt_a, user_headers = _setup(client, admin_headers, user_headers_factory)
    pt_b = _create_plane_type(client, admin_headers, "业务平面").json()
    _enable_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers)
    plane_b = _enable_plane(client, region["id"], pt_b["id"], "10.0.1.0/24", user_headers).json()

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
    _enable_plane(client, region_a["id"], pt["id"], "10.0.0.0/24", user_headers)
    plane_b = _enable_plane(client, region_b["id"], pt["id"], "10.0.1.0/24", user_headers).json()

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
    _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)
    child = _enable_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers).json()

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
    _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)
    child = _enable_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers).json()

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


def test_update_plane_rejects_gateway_ip_outside_cidr(client, admin_headers, user_headers_factory):
    """编辑网关 IP 时必须位于当前 CIDR 范围内。"""
    region, pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    plane = _enable_plane(client, region["id"], pt["id"], "10.0.0.0/24", user_headers).json()

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
    _enable_plane(client, region["id"], pt_a["id"], "10.0.0.0/24", user_headers, vlan_id=100)
    plane_b = _enable_plane(client, region["id"], pt_b["id"], "10.0.1.0/24", user_headers, vlan_id=200).json()

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


def test_enable_child_plane(client, admin_headers, user_headers_factory):
    """正常启用子平面，校验 CIDR 在父范围内。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    root = _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers).json()

    resp = _enable_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["cidr"] == "10.0.0.0/24"
    assert data["scope"] == "Global"
    assert data["parent_id"] == root["id"]
    assert data["plane_type_parent_id"] == root_pt["id"]
    assert data["updated_at"]


def test_enable_child_requires_parent_enabled(client, admin_headers, user_headers_factory):
    """子类型平面必须在父级已启用后才能启用。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()

    resp = _enable_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers)

    assert resp.status_code == 409
    assert "父级网络平面尚未" in resp.json()["detail"]


def test_create_child_outside_parent(client, admin_headers, user_headers_factory):
    """子 CIDR 超出父范围应报错。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)

    resp = _enable_plane(client, region["id"], child_pt["id"], "192.168.0.0/24", user_headers)

    assert resp.status_code == 409
    assert "范围内" in resp.json()["detail"]


def test_create_child_sibling_overlap(client, admin_headers, user_headers_factory):
    """兄弟平面 CIDR 重叠应报错。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_a = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    child_b = _create_plane_type(client, admin_headers, "管理子平面B", parent_id=root_pt["id"]).json()
    _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)
    _enable_plane(client, region["id"], child_a["id"], "10.0.0.0/24", user_headers)

    resp = _enable_plane(client, region["id"], child_b["id"], "10.0.0.0/25", user_headers)

    assert resp.status_code == 409
    assert "重叠" in resp.json()["detail"]


def test_create_child_unrelated_ok(client, admin_headers, user_headers_factory):
    """兄弟平面 CIDR 不重叠时允许创建。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_a = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    child_b = _create_plane_type(client, admin_headers, "管理子平面B", parent_id=root_pt["id"]).json()
    _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers)
    _enable_plane(client, region["id"], child_a["id"], "10.0.0.0/24", user_headers)

    resp = _enable_plane(client, region["id"], child_b["id"], "10.0.1.0/24", user_headers)

    assert resp.status_code == 201


def test_create_child_depth_exceeded(client, admin_headers):
    """全局类型树超过 3 级嵌套应报错。"""
    root = _create_plane_type(client, admin_headers, "根平面").json()
    child = _create_plane_type(client, admin_headers, "子平面", parent_id=root["id"]).json()
    grandchild = _create_plane_type(client, admin_headers, "孙平面", parent_id=child["id"]).json()

    resp = _create_plane_type(client, admin_headers, "四级平面", parent_id=grandchild["id"])

    assert resp.status_code == 409
    assert "最大嵌套层级" in resp.json()["detail"]


def test_get_plane_tree(client, admin_headers, user_headers_factory):
    """验证 GET /regions/{rid}/planes 返回由全局类型树派生的 Region 平面树。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_a = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    child_b = _create_plane_type(client, admin_headers, "管理子平面B", parent_id=root_pt["id"]).json()
    grandchild = _create_plane_type(client, admin_headers, "管理孙平面", parent_id=child_a["id"]).json()

    _enable_plane(
        client,
        region["id"],
        root_pt["id"],
        "10.0.0.0/22",
        user_headers,
        vlan_id=200,
        gateway_position="Core-A",
        gateway_ip="10.0.0.254",
    )
    _enable_plane(client, region["id"], child_a["id"], "10.0.0.0/24", user_headers)
    _enable_plane(client, region["id"], child_b["id"], "10.0.1.0/24", user_headers)
    _enable_plane(client, region["id"], grandchild["id"], "10.0.0.0/25", user_headers)

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
    _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/16", user_headers)
    _enable_plane(client, region["id"], root_pt["id"], "10.1.0.0/16", user_headers, scope="业务AZ1")
    _enable_plane(client, region["id"], child_pt["id"], "10.1.1.0/24", user_headers, scope="业务AZ1")

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
    global_root = _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/16", user_headers).json()
    _enable_plane(client, region["id"], child_pt["id"], "10.0.1.0/24", user_headers, scope="业务AZ1")

    resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)

    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1
    assert tree[0]["id"] == global_root["id"]
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["scope"] == "业务AZ1"
    assert tree[0]["children"][0]["parent_id"] == global_root["id"]


def test_delete_parent_plane_cascades(client, admin_headers, user_headers_factory):
    """删除父平面后，子平面也被级联删除。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    root = _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/22", user_headers).json()
    _enable_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers)

    resp = client.delete(f"/api/regions/{region['id']}/planes/{root['id']}", headers=user_headers)

    assert resp.status_code == 204
    tree_resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)
    assert len(tree_resp.json()) == 0


def test_delete_scoped_parent_only_cascades_same_scope(client, admin_headers, user_headers_factory):
    """删除某个作用域的父平面时，不应级联删除其他作用域的子树。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    az1_root = _enable_plane(
        client,
        region["id"],
        root_pt["id"],
        "10.0.0.0/22",
        user_headers,
        scope="业务AZ1",
    ).json()
    _enable_plane(client, region["id"], root_pt["id"], "10.0.4.0/22", user_headers, scope="业务AZ2")
    _enable_plane(client, region["id"], child_pt["id"], "10.0.0.0/24", user_headers, scope="业务AZ1")
    _enable_plane(client, region["id"], child_pt["id"], "10.0.4.0/24", user_headers, scope="业务AZ2")

    resp = client.delete(f"/api/regions/{region['id']}/planes/{az1_root['id']}", headers=user_headers)

    assert resp.status_code == 204
    tree_resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)
    tree = tree_resp.json()
    assert len(tree) == 1
    assert tree[0]["scope"] == "业务AZ2"
    assert tree[0]["children"][0]["scope"] == "业务AZ2"


def test_delete_global_parent_cascades_fallback_children(client, admin_headers, user_headers_factory):
    """删除 Global 父平面时，应级联删除实际回退挂载到它下面的子平面。"""
    region, root_pt, user_headers = _setup(client, admin_headers, user_headers_factory)
    child_pt = _create_plane_type(client, admin_headers, "管理子平面A", parent_id=root_pt["id"]).json()
    global_root = _enable_plane(client, region["id"], root_pt["id"], "10.0.0.0/16", user_headers).json()
    _enable_plane(client, region["id"], child_pt["id"], "10.0.1.0/24", user_headers, scope="业务AZ1")

    resp = client.delete(f"/api/regions/{region['id']}/planes/{global_root['id']}", headers=user_headers)

    assert resp.status_code == 204
    tree_resp = client.get(f"/api/regions/{region['id']}/planes", headers=user_headers)
    assert tree_resp.json() == []


def test_delete_nonexistent_plane(client, admin_headers, user_headers_factory):
    """删除不存在的平面应返回 404。"""
    region, _, user_headers = _setup(client, admin_headers, user_headers_factory)
    resp = client.delete(f"/api/regions/{region['id']}/planes/nonexistent", headers=user_headers)
    assert resp.status_code == 404
