"""交换机管理 API 测试。"""

from sqlalchemy.orm import Session

from app.models.cabling import CableEntry, CablingBatch
from app.models.change_log import ChangeLog


def _create_region(client, admin_headers, name: str = "Region-A") -> dict[str, object]:
    """创建测试使用的 Region。"""
    response = client.post("/api/regions", json={"name": name}, headers=admin_headers)
    assert response.status_code == 201
    return response.json()


def _create_rack(client, headers, region_id: str, name: str) -> dict[str, object]:
    """创建测试使用的机柜。"""
    response = client.post(
        f"/api/regions/{region_id}/racks",
        json={
            "items": [
                {
                    "room_name": name,
                    "rack_column": "A",
                    "rack_number": 1,
                }
            ],
            "u_height": 42,
        },
        headers=headers,
    )
    assert response.status_code == 201
    created = response.json()
    assert len(created) == 1
    return created[0]


def _create_business_type(client, admin_headers, code: str = "custom", name: str = "自定义") -> dict[str, object]:
    """创建交换机业务类型。"""
    response = client.post(
        "/api/switch-business-types",
        json={"code": code, "name": name},
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def _switch_member(
    rack_id: str,
    *,
    role: str,
    name: str,
    start_u: int,
    height_u: int = 1,
    port_speed_mbps: int = 25000,
) -> dict[str, object]:
    """构造组合创建请求中的成员交换机。"""
    return {
        "rack_id": rack_id,
        "member_role": role,
        "name": name,
        "port_speed_mbps": port_speed_mbps,
        "start_u": start_u,
        "height_u": height_u,
    }


def _create_group_with_members(
    client,
    headers,
    region_id: str,
    business_type_id: str,
    *,
    members: list[dict[str, object]],
    name: str = "业务交换机对-01",
    group_mode: str = "pair",
    port_range: dict[str, int] | None = None,
) -> dict[str, object]:
    """原子创建交换机组及完整成员。"""
    payload: dict[str, object] = {
        "business_type_id": business_type_id,
        "name": name,
        "group_mode": group_mode,
        "members": members,
    }
    if port_range is not None:
        payload["port_range"] = port_range
    response = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _get_switch_group_from_list(client, headers, region_id: str, group_id: str) -> dict[str, object]:
    """从交换机组列表响应中获取指定交换机组。"""
    response = client.get(
        f"/api/regions/{region_id}/switch-groups?skip=0&limit=500",
        headers=headers,
    )
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["id"] == group_id)


def test_switch_business_type_crud_and_permissions(client, admin_headers, user_headers_factory, test_db) -> None:
    """业务类型对所有登录用户可读，仅 administrator 可写并记录审计日志。"""
    user_headers = user_headers_factory([], username="type-reader")
    created = _create_business_type(client, admin_headers)

    listed = client.get("/api/switch-business-types", headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    denied = client.post(
        "/api/switch-business-types",
        json={"code": "denied", "name": "禁止"},
        headers=user_headers,
    )
    assert denied.status_code == 403

    updated = client.put(
        f"/api/switch-business-types/{created['id']}",
        json={"code": "custom-updated", "name": "自定义更新"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["code"] == "custom-updated"

    deleted = client.delete(f"/api/switch-business-types/{created['id']}", headers=admin_headers)
    assert deleted.status_code == 204

    session = Session(test_db)
    try:
        logs = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "switch_business_type", ChangeLog.entity_id == created["id"])
            .order_by(ChangeLog.created_at.asc())
            .all()
        )
        assert [item.action for item in logs] == ["create", "update", "update", "delete"]
        assert {item.operator for item in logs} == {"admin"}
    finally:
        session.close()


def test_switch_business_type_rejects_duplicates_and_in_use_delete(client, admin_headers, user_headers_factory) -> None:
    """业务类型 code/name 不能重复，且被交换机组引用时不能删除。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="type-usage")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)

    duplicate_code = client.post(
        "/api/switch-business-types",
        json={"code": "custom", "name": "另一名称"},
        headers=admin_headers,
    )
    duplicate_name = client.post(
        "/api/switch-business-types",
        json={"code": "another", "name": "自定义"},
        headers=admin_headers,
    )
    assert duplicate_code.status_code == 409
    assert duplicate_name.status_code == 409

    _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        name="单机组-01",
        group_mode="single",
        members=[_switch_member(str(rack["id"]), role="single", name="switch-single", start_u=42)],
    )
    in_use = client.delete(f"/api/switch-business-types/{business_type['id']}", headers=admin_headers)
    assert in_use.status_code == 409
    assert in_use.json()["detail"] == "交换机业务类型 自定义 仍被 1 个交换机组使用，不能删除"


def test_switch_management_trims_text_fields_and_rejects_blank_values(
    client, admin_headers, user_headers_factory
) -> None:
    """交换机管理请求统一清理首尾空白，并拒绝清理后的空字符串。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="switch-text-validator")
    rack = _create_rack(client, user_headers, region_id, "N01")

    business_type_response = client.post(
        "/api/switch-business-types",
        json={"code": " custom-trim ", "name": " 自定义清理 "},
        headers=admin_headers,
    )
    assert business_type_response.status_code == 201
    business_type = business_type_response.json()
    assert business_type["code"] == "custom-trim"
    assert business_type["name"] == "自定义清理"

    group_response = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": f" {business_type['id']} ",
            "name": " 单机组-清理 ",
            "group_mode": "single",
            "members": [
                _switch_member(
                    f" {rack['id']} ",
                    role="single",
                    name=" switch-trimmed ",
                    start_u=42,
                )
            ],
        },
        headers=user_headers,
    )
    assert group_response.status_code == 201
    assert group_response.json()["group"]["name"] == "单机组-清理"
    assert group_response.json()["members"][0]["name"] == "switch-trimmed"

    blank_business_type = client.post(
        "/api/switch-business-types",
        json={"code": "   ", "name": "空白标识"},
        headers=admin_headers,
    )
    blank_group_name = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "   ",
            "group_mode": "single",
            "members": [_switch_member(str(rack["id"]), role="single", name="blank-group", start_u=41)],
        },
        headers=user_headers,
    )
    assert blank_business_type.status_code == 422
    assert blank_group_name.status_code == 422


def test_switch_management_partial_updates_reject_silent_noops(client, admin_headers, user_headers_factory) -> None:
    """部分更新拒绝空请求、空字符串以及不可为空字段显式传入 null。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="switch-update-validator")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)
    result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        name="单机组-更新校验",
        group_mode="single",
        members=[_switch_member(str(rack["id"]), role="single", name="switch-update-validator", start_u=42)],
    )
    group = result["group"]
    switch = result["members"][0]

    invalid_requests = [
        client.put(
            f"/api/switch-business-types/{business_type['id']}",
            json={},
            headers=admin_headers,
        ),
        client.put(
            f"/api/switch-business-types/{business_type['id']}",
            json={"name": None},
            headers=admin_headers,
        ),
        client.put(
            f"/api/regions/{region_id}/switch-groups/{group['id']}",
            json={"business_type_id": "   "},
            headers=user_headers,
        ),
        client.put(
            f"/api/regions/{region_id}/switch-groups/{group['id']}",
            json={"name": None},
            headers=user_headers,
        ),
        client.put(
            f"/api/regions/{region_id}/switches/{switch['id']}",
            json={},
            headers=user_headers,
        ),
        client.put(
            f"/api/regions/{region_id}/switches/{switch['id']}",
            json={"rack_id": None},
            headers=user_headers,
        ),
        client.put(
            f"/api/regions/{region_id}/switches/{switch['id']}",
            json={"name": "   "},
            headers=user_headers,
        ),
    ]
    assert all(response.status_code == 422 for response in invalid_requests)


def test_switch_group_and_members_reach_ready_state(client, admin_headers, user_headers_factory) -> None:
    """组合接口应原子创建 pair 组及 a、b 两个完整成员。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="switch-builder")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)
    result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        members=[
            _switch_member(str(rack["id"]), role="a", name="switch-a", start_u=42),
            _switch_member(str(rack["id"]), role="b", name="switch-b", start_u=41),
        ],
    )
    group = result["group"]
    switch_a = result["members"][0]
    assert group["member_count"] == 2
    assert group["is_member_config_ready"] is True
    assert group["readiness_issues"] == []
    assert switch_a["switch_group_name"] == "业务交换机对-01"
    assert switch_a["business_type_name"] == "自定义"
    assert switch_a["port_count"] == 48
    assert switch_a["used_port_count"] == 0
    ports = client.get(
        f"/api/regions/{region_id}/switches/{switch_a['id']}/ports?skip=0&limit=100",
        headers=admin_headers,
    )
    assert ports.status_code == 200
    assert ports.json()["total"] == 48
    assert all(item["is_occupied"] is False for item in ports.json()["items"])
    listed = client.get(f"/api/regions/{region_id}/switch-groups", headers=admin_headers)
    assert listed.status_code == 200
    stored_group = listed.json()["items"][0]
    assert stored_group["member_count"] == 2
    assert stored_group["is_member_config_ready"] is True


def test_switch_group_create_is_atomic_when_member_validation_fails(
    client, admin_headers, user_headers_factory
) -> None:
    """任一成员校验失败时，交换机组和所有成员都不应写入。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="atomic-group")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)

    response = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "atomic-failed-group",
            "group_mode": "pair",
            "members": [
                _switch_member(str(rack["id"]), role="a", name="atomic-a", start_u=42),
                _switch_member(str(rack["id"]), role="b", name="atomic-b", start_u=42),
            ],
        },
        headers=user_headers,
    )
    assert response.status_code == 409
    assert "本次请求中的 atomic-a" in response.json()["detail"]

    groups = client.get(
        f"/api/regions/{region_id}/switch-groups?search=atomic-failed-group",
        headers=admin_headers,
    )
    switches = client.get(f"/api/regions/{region_id}/switches?search=atomic-", headers=admin_headers)
    assert groups.json()["total"] == 0
    assert switches.json()["total"] == 0


def test_switch_group_create_rejects_invalid_port_range_atomically(client, admin_headers, user_headers_factory) -> None:
    """端口范围非法时，交换机组、成员和端口均不应写入。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="port-range-validator")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)

    response = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "invalid-port-range-group",
            "group_mode": "single",
            "members": [_switch_member(str(rack["id"]), role="single", name="invalid-port-range-switch", start_u=42)],
            "port_range": {"start_port_number": 48, "end_port_number": 1},
        },
        headers=user_headers,
    )
    assert response.status_code == 422

    oversized = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "oversized-port-range-group",
            "group_mode": "single",
            "members": [_switch_member(str(rack["id"]), role="single", name="oversized-port-range-switch", start_u=42)],
            "port_range": {"start_port_number": 1, "end_port_number": 129},
        },
        headers=user_headers,
    )
    assert oversized.status_code == 422
    assert "一次最多生成 128 个端口" in str(oversized.json()["detail"])

    groups = client.get(
        f"/api/regions/{region_id}/switch-groups?search=invalid-port-range-group",
        headers=admin_headers,
    )
    switches = client.get(
        f"/api/regions/{region_id}/switches?search=invalid-port-range-switch",
        headers=admin_headers,
    )
    assert groups.json()["total"] == 0
    assert switches.json()["total"] == 0


def test_switch_group_pair_requires_same_port_speed(client, admin_headers, user_headers_factory) -> None:
    """A/B 双机端口速率不一致时，交换机组和成员均不应写入。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="pair-speed-validator")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)

    response = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "different-speed-group",
            "group_mode": "pair",
            "members": [
                _switch_member(str(rack["id"]), role="a", name="different-speed-a", start_u=42, port_speed_mbps=25000),
                _switch_member(str(rack["id"]), role="b", name="different-speed-b", start_u=41, port_speed_mbps=100000),
            ],
        },
        headers=user_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "A/B 双机成员的端口速率必须一致"

    groups = client.get(
        f"/api/regions/{region_id}/switch-groups?search=different-speed-group",
        headers=admin_headers,
    )
    switches = client.get(f"/api/regions/{region_id}/switches?search=different-speed-", headers=admin_headers)
    assert groups.json()["total"] == 0
    assert switches.json()["total"] == 0


def test_switch_group_pair_speed_change_temporarily_marks_group_not_ready(
    client, admin_headers, user_headers_factory
) -> None:
    """pair 成员可依次变更速率，过渡期间未就绪，一致后恢复就绪。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="pair-speed-updater")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)
    result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        members=[
            _switch_member(str(rack["id"]), role="a", name="pair-speed-a", start_u=42),
            _switch_member(str(rack["id"]), role="b", name="pair-speed-b", start_u=41),
        ],
    )
    group = result["group"]
    members = {member["member_role"]: member for member in result["members"]}

    updated_a = client.put(
        f"/api/regions/{region_id}/switches/{members['a']['id']}",
        json={"port_speed_mbps": 10000},
        headers=user_headers,
    )
    assert updated_a.status_code == 200
    assert updated_a.json()["port_speed_mbps"] == 10000

    group_response = _get_switch_group_from_list(client, admin_headers, region_id, str(group["id"]))
    assert group_response["is_member_config_ready"] is False
    assert group_response["readiness_issues"] == [
        {
            "code": "PORT_SPEED_MISMATCH",
            "message": "A/B 成员端口速率不一致",
        }
    ]

    updated_b = client.put(
        f"/api/regions/{region_id}/switches/{members['b']['id']}",
        json={"port_speed_mbps": 10000},
        headers=user_headers,
    )
    assert updated_b.status_code == 200
    assert updated_b.json()["port_speed_mbps"] == 10000

    ready_group_response = _get_switch_group_from_list(client, admin_headers, region_id, str(group["id"]))
    assert ready_group_response["is_member_config_ready"] is True
    assert ready_group_response["readiness_issues"] == []


def test_switch_group_readiness_issues_report_missing_members(client, admin_headers, user_headers_factory) -> None:
    """成员删除后应按组模式返回缺少成员的精准原因。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="group-readiness-reader")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)

    pair_result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        members=[
            _switch_member(str(rack["id"]), role="a", name="missing-pair-a", start_u=42),
            _switch_member(str(rack["id"]), role="b", name="missing-pair-b", start_u=41),
        ],
    )
    pair_members = {member["member_role"]: member for member in pair_result["members"]}
    deleted_b = client.delete(
        f"/api/regions/{region_id}/switches/{pair_members['b']['id']}",
        headers=user_headers,
    )
    assert deleted_b.status_code == 204

    pair_group = _get_switch_group_from_list(
        client,
        admin_headers,
        region_id,
        str(pair_result["group"]["id"]),
    )
    assert pair_group["readiness_issues"] == [{"code": "MISSING_MEMBER_B", "message": "缺少 B 成员"}]

    single_result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        name="缺少成员的单机组",
        group_mode="single",
        members=[_switch_member(str(rack["id"]), role="single", name="missing-single", start_u=41)],
    )
    deleted_single = client.delete(
        f"/api/regions/{region_id}/switches/{single_result['members'][0]['id']}",
        headers=user_headers,
    )
    assert deleted_single.status_code == 204

    single_group = _get_switch_group_from_list(
        client,
        admin_headers,
        region_id,
        str(single_result["group"]["id"]),
    )
    assert single_group["readiness_issues"] == [
        {"code": "MISSING_SINGLE_MEMBER", "message": "缺少 single 成员"}
    ]


def test_switch_group_and_switch_crud_records_audit_logs(client, admin_headers, user_headers_factory, test_db) -> None:
    """交换机组和未占用交换机支持完整 CRUD，并记录变更日志。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="switch-crud")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)
    result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        name="单机组-01",
        group_mode="single",
        members=[_switch_member(str(rack["id"]), role="single", name="switch-single", start_u=42)],
    )
    group = result["group"]
    switch = result["members"][0]

    listed = client.get(
        f"/api/regions/{region_id}/switches?search=single&rack_id={rack['id']}&switch_group_id={group['id']}",
        headers=admin_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated_switch = client.put(
        f"/api/regions/{region_id}/switches/{switch['id']}",
        json={"name": "switch-single-updated", "port_speed_mbps": 10000, "start_u": 41},
        headers=user_headers,
    )
    assert updated_switch.status_code == 200
    assert updated_switch.json()["name"] == "switch-single-updated"
    assert updated_switch.json()["port_speed_mbps"] == 10000
    assert updated_switch.json()["start_u"] == 41

    delete_in_use_group = client.delete(
        f"/api/regions/{region_id}/switch-groups/{group['id']}",
        headers=user_headers,
    )
    assert delete_in_use_group.status_code == 409

    deleted_switch = client.delete(
        f"/api/regions/{region_id}/switches/{switch['id']}",
        headers=user_headers,
    )
    assert deleted_switch.status_code == 204

    updated_group = client.put(
        f"/api/regions/{region_id}/switch-groups/{group['id']}",
        json={"name": "单机组-UPDATED", "group_mode": "pair"},
        headers=user_headers,
    )
    assert updated_group.status_code == 200
    assert updated_group.json()["name"] == "单机组-UPDATED"
    assert updated_group.json()["group_mode"] == "pair"

    deleted_group = client.delete(
        f"/api/regions/{region_id}/switch-groups/{group['id']}",
        headers=user_headers,
    )
    assert deleted_group.status_code == 204

    session = Session(test_db)
    try:
        switch_logs = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "switch", ChangeLog.entity_id == switch["id"])
            .all()
        )
        group_logs = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "switch_group", ChangeLog.entity_id == group["id"])
            .all()
        )
        deleted_port_logs = (
            session.query(ChangeLog)
            .filter(
                ChangeLog.entity_type == "switch_port",
                ChangeLog.action == "delete",
                ChangeLog.entity_name.like("switch-single-updated:%"),
            )
            .all()
        )
        assert {item.action for item in switch_logs} == {"create", "update", "delete"}
        assert {item.action for item in group_logs} == {"create", "update", "delete"}
        assert len(deleted_port_logs) == 48
        assert {item.operator for item in switch_logs + group_logs + deleted_port_logs} == {"switch-crud"}
    finally:
        session.close()


def test_switch_group_validates_mode_roles_and_mode_changes(client, admin_headers, user_headers_factory) -> None:
    """组合创建必须提交与组模式一致的完整角色，已有成员时不能切换模式。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="group-validator")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)

    invalid_role = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "invalid-role-group",
            "group_mode": "pair",
            "members": [_switch_member(str(rack["id"]), role="single", name="invalid-role", start_u=42)],
        },
        headers=user_headers,
    )
    assert invalid_role.status_code == 409
    assert "pair" in invalid_role.json()["detail"]

    duplicate_role = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "duplicate-role-group",
            "group_mode": "pair",
            "members": [
                _switch_member(str(rack["id"]), role="a", name="switch-a", start_u=42),
                _switch_member(str(rack["id"]), role="a", name="switch-a-duplicate", start_u=41),
            ],
        },
        headers=user_headers,
    )
    assert duplicate_role.status_code == 409
    assert "A、B 两台成员" in duplicate_role.json()["detail"]

    result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        members=[
            _switch_member(str(rack["id"]), role="a", name="switch-a", start_u=42),
            _switch_member(str(rack["id"]), role="b", name="switch-b", start_u=41),
        ],
    )
    group = result["group"]

    mode_change = client.put(
        f"/api/regions/{region_id}/switch-groups/{group['id']}",
        json={"group_mode": "single"},
        headers=user_headers,
    )
    assert mode_change.status_code == 409
    assert mode_change.json()["detail"] == "交换机组已有成员，不能修改组模式"


def test_switch_group_create_rejects_cross_region_rack_and_standalone_switch_post(
    client, admin_headers, user_headers_factory
) -> None:
    """组合创建拒绝跨 Region 机柜，交换机列表不再提供独立 POST。"""
    region_a = _create_region(client, admin_headers, "Region-A")
    region_b = _create_region(client, admin_headers, "Region-B")
    region_a_id = str(region_a["id"])
    region_b_id = str(region_b["id"])
    user_headers = user_headers_factory([region_a_id, region_b_id], username="cross-region")
    rack_b = _create_rack(client, user_headers, region_b_id, "N02")
    business_type = _create_business_type(client, admin_headers)

    wrong_rack = client.post(
        f"/api/regions/{region_a_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "wrong-rack-group",
            "group_mode": "single",
            "members": [_switch_member(str(rack_b["id"]), role="single", name="wrong-rack", start_u=42)],
        },
        headers=user_headers,
    )
    standalone_switch = client.post(
        f"/api/regions/{region_a_id}/switches",
        json={
            "rack_id": rack_b["id"],
            "name": "standalone-switch",
            "port_speed_mbps": 25000,
            "start_u": 42,
            "height_u": 1,
        },
        headers=user_headers,
    )
    group_without_members = client.post(
        f"/api/regions/{region_a_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "standalone-group",
            "group_mode": "single",
        },
        headers=user_headers,
    )

    assert wrong_rack.status_code == 409
    assert wrong_rack.json()["detail"] == "机柜不属于当前 Region"
    assert standalone_switch.status_code == 405
    assert group_without_members.status_code == 422


def test_switch_validates_rack_bounds_and_position_overlap(client, admin_headers, user_headers_factory) -> None:
    """交换机上架位置不能越界，也不能与同机柜其他交换机重叠。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="switch-position")
    rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)

    out_of_bounds = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "out-of-bounds-group",
            "group_mode": "single",
            "members": [_switch_member(str(rack["id"]), role="single", name="out-of-bounds", start_u=42, height_u=2)],
        },
        headers=user_headers,
    )
    assert out_of_bounds.status_code == 409
    assert "超出机柜" in out_of_bounds.json()["detail"]

    _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        name="existing-switch-group",
        group_mode="single",
        members=[_switch_member(str(rack["id"]), role="single", name="switch-a", start_u=40, height_u=2)],
    )
    overlap = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "overlap-group",
            "group_mode": "single",
            "members": [_switch_member(str(rack["id"]), role="single", name="switch-overlap", start_u=41)],
        },
        headers=user_headers,
    )
    assert overlap.status_code == 409
    assert "switch-a" in overlap.json()["detail"]
    assert "重叠" in overlap.json()["detail"]


def test_switch_validates_overlap_with_server_side_position(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """交换机不能上架到已被线缆记录为服务器侧位置的 U 位。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="server-overlap")
    shared_rack = _create_rack(client, user_headers, region_id, "A01")
    switch_rack = _create_rack(client, user_headers, region_id, "N01")
    business_type = _create_business_type(client, admin_headers)
    source_result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        name="source-group",
        group_mode="single",
        members=[_switch_member(str(switch_rack["id"]), role="single", name="source-switch", start_u=42)],
        port_range={"start_port_number": 1, "end_port_number": 1},
    )
    source_switch = source_result["members"][0]
    ports = client.get(
        f"/api/regions/{region_id}/switches/{source_switch['id']}/ports",
        headers=admin_headers,
    )
    assert ports.status_code == 200

    session = Session(test_db)
    try:
        batch = CablingBatch(region_id=region_id, name="第一批布线", created_by="server-overlap")
        session.add(
            CableEntry(
                batch=batch,
                server_rack_id=str(shared_rack["id"]),
                server_start_u=10,
                server_height_u=2,
                server_port_name="NIC1",
                switch_port_id=str(ports.json()["items"][0]["id"]),
                cable_label="CBL-000001",
                cable_sequence=1,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "overlap-server-group",
            "group_mode": "single",
            "members": [_switch_member(str(shared_rack["id"]), role="single", name="overlap-server", start_u=11)],
        },
        headers=user_headers,
    )
    assert response.status_code == 409
    assert "服务器侧位置 10U-11U" in response.json()["detail"]


def test_switch_ports_bulk_creation_is_atomic_and_reports_occupancy(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """端口批量创建不允许部分成功，占用状态由线缆引用派生。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="port-manager")
    switch_rack = _create_rack(client, user_headers, region_id, "N01")
    server_rack = _create_rack(client, user_headers, region_id, "A01")
    business_type = _create_business_type(client, admin_headers)
    result = _create_group_with_members(
        client,
        user_headers,
        region_id,
        str(business_type["id"]),
        name="port-test-group",
        group_mode="single",
        members=[_switch_member(str(switch_rack["id"]), role="single", name="switch-a", start_u=42)],
        port_range={"start_port_number": 1, "end_port_number": 4},
    )
    switch = result["members"][0]

    created = client.post(
        f"/api/regions/{region_id}/switches/{switch['id']}/ports/bulk",
        json={"card_number": 2, "subcard_number": 1, "start_port_number": 1, "end_port_number": 4},
        headers=user_headers,
    )
    assert created.status_code == 201
    assert [item["port_number"] for item in created.json()] == [1, 2, 3, 4]
    assert {(item["card_number"], item["subcard_number"]) for item in created.json()} == {(2, 1)}

    duplicate_range = client.post(
        f"/api/regions/{region_id}/switches/{switch['id']}/ports/bulk",
        json={"card_number": 2, "subcard_number": 1, "start_port_number": 4, "end_port_number": 6},
        headers=user_headers,
    )
    assert duplicate_range.status_code == 409
    assert "2/1/4" in duplicate_range.json()["detail"]

    session = Session(test_db)
    try:
        batch = CablingBatch(region_id=region_id, name="第一批布线", created_by="port-manager")
        session.add(
            CableEntry(
                batch=batch,
                server_rack_id=str(server_rack["id"]),
                server_start_u=10,
                server_height_u=2,
                server_port_name="NIC1",
                switch_port_id=str(created.json()[0]["id"]),
                cable_label="CBL-000001",
                cable_sequence=1,
            )
        )
        session.commit()
    finally:
        session.close()

    listed = client.get(
        f"/api/regions/{region_id}/switches/{switch['id']}/ports?skip=0&limit=20",
        headers=admin_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 8
    assert [(item["card_number"], item["subcard_number"], item["port_number"]) for item in listed.json()["items"]] == [
        (1, 0, 1),
        (1, 0, 2),
        (1, 0, 3),
        (1, 0, 4),
        (2, 1, 1),
        (2, 1, 2),
        (2, 1, 3),
        (2, 1, 4),
    ]
    occupied_port = next(item for item in listed.json()["items"] if item["id"] == created.json()[0]["id"])
    assert occupied_port["is_occupied"] is True
    assert occupied_port["cable_entry_id"] is not None

    filtered = client.get(
        f"/api/regions/{region_id}/switches/{switch['id']}/ports" "?card_number=2&subcard_number=1&skip=0&limit=2",
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 4
    assert [item["port_number"] for item in filtered.json()["items"]] == [1, 2]

    occupied_delete = client.delete(
        f"/api/regions/{region_id}/switches/{switch['id']}/ports/{occupied_port['id']}",
        headers=user_headers,
    )
    switch_delete = client.delete(
        f"/api/regions/{region_id}/switches/{switch['id']}",
        headers=user_headers,
    )
    assert occupied_delete.status_code == 409
    assert switch_delete.status_code == 409

    free_port = next(item for item in listed.json()["items"] if item["is_occupied"] is False)
    free_delete = client.delete(
        f"/api/regions/{region_id}/switches/{switch['id']}/ports/{free_port['id']}",
        headers=user_headers,
    )
    assert free_delete.status_code == 204

    after_failed_bulk = client.get(
        f"/api/regions/{region_id}/switches/{switch['id']}/ports",
        headers=admin_headers,
    )
    assert after_failed_bulk.json()["total"] == 7


def test_switch_write_requires_assigned_region_user(client, admin_headers, user_headers_factory) -> None:
    """交换机组、交换机和端口的写操作遵守 Region 业务权限。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    business_type = _create_business_type(client, admin_headers)
    writer_headers = user_headers_factory([region_id], username="switch-writer")
    unassigned_headers = user_headers_factory([], username="switch-unassigned")
    rack = _create_rack(client, writer_headers, region_id, "N01")

    admin_group = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "admin-denied",
            "group_mode": "single",
            "members": [_switch_member(str(rack["id"]), role="single", name="admin-switch", start_u=42)],
        },
        headers=admin_headers,
    )
    unassigned_group = client.post(
        f"/api/regions/{region_id}/switch-groups",
        json={
            "business_type_id": business_type["id"],
            "name": "user-denied",
            "group_mode": "single",
            "members": [_switch_member(str(rack["id"]), role="single", name="user-switch", start_u=42)],
        },
        headers=unassigned_headers,
    )
    readable = client.get(f"/api/regions/{region_id}/switches", headers=unassigned_headers)

    assert admin_group.status_code == 403
    assert unassigned_group.status_code == 403
    assert readable.status_code == 200
