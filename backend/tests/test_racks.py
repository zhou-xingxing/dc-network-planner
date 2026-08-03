"""机柜管理 API 测试。"""

from sqlalchemy.orm import Session

from app.models.cabling import CableEntry, CablingBatch
from app.models.change_log import ChangeLog
from app.models.rack import Rack
from app.models.switch import Switch, SwitchPort


def _create_region(client, admin_headers, name: str = "Region-A") -> dict[str, object]:
    """创建测试使用的 Region。"""
    response = client.post("/api/regions", json={"name": name}, headers=admin_headers)
    assert response.status_code == 201
    return response.json()


def _rack_item(room_name: str = "ROOM-A", rack_column: str = "A", rack_number: int = 1) -> dict[str, object]:
    """构造结构化机柜创建条目。"""
    return {
        "room_name": room_name,
        "rack_column": rack_column,
        "rack_number": rack_number,
    }


def _create_rack(
    client,
    headers,
    region_id: str,
    *,
    room_name: str = "ROOM-A",
    rack_column: str = "A",
    rack_number: int = 1,
    u_height: int = 42,
) -> dict[str, object]:
    """通过 API 创建机柜并返回响应数据。"""
    response = client.post(
        f"/api/regions/{region_id}/racks",
        json={"items": [_rack_item(room_name, rack_column, rack_number)], "u_height": u_height},
        headers=headers,
    )
    assert response.status_code == 201
    created = response.json()
    assert len(created) == 1
    return created[0]


def test_rack_crud_records_audit_logs(client, admin_headers, user_headers_factory, test_db) -> None:
    """授权用户可完成机柜 CRUD，且所有变更都记录审计日志。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-operator")

    created = _create_rack(client, user_headers, region_id)
    assert created["region_id"] == region_id
    assert created["region_name"] == "Region-A"
    assert created["name"] == "ROOM-A-A01"
    assert created["room_name"] == "ROOM-A"
    assert created["rack_column"] == "A"
    assert created["rack_number"] == 1
    assert created["u_height"] == 42
    assert created["switch_count"] == 0
    assert created["cable_count"] == 0

    listed = client.get(
        f"/api/regions/{region_id}/racks?search=ROOM-A&skip=0&limit=20",
        headers=admin_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == created["id"]

    updated = client.put(
        f"/api/regions/{region_id}/racks/{created['id']}",
        json={"room_name": "ROOM-B", "rack_column": "B", "rack_number": 2, "u_height": 48},
        headers=user_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "ROOM-B-B02"
    assert updated.json()["room_name"] == "ROOM-B"
    assert updated.json()["rack_column"] == "B"
    assert updated.json()["rack_number"] == 2
    assert updated.json()["u_height"] == 48

    deleted = client.delete(
        f"/api/regions/{region_id}/racks/{created['id']}",
        headers=user_headers,
    )
    assert deleted.status_code == 204

    session = Session(test_db)
    try:
        logs = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "rack", ChangeLog.entity_id == created["id"])
            .order_by(ChangeLog.created_at.asc())
            .all()
        )
        assert [item.action for item in logs] == ["create", "update", "update", "update", "update", "update", "delete"]
        assert {item.field_name for item in logs if item.action == "update"} == {
            "room_name",
            "rack_column",
            "rack_number",
            "name",
            "u_height",
        }
        assert {item.operator for item in logs} == {"rack-operator"}
    finally:
        session.close()


def test_rack_write_requires_assigned_region_user(client, admin_headers, user_headers_factory) -> None:
    """机柜写操作只允许获得目标 Region 授权的普通用户。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    unassigned_headers = user_headers_factory([], username="rack-unassigned")

    admin_response = client.post(
        f"/api/regions/{region_id}/racks",
        json={"items": [_rack_item()], "u_height": 42},
        headers=admin_headers,
    )
    unassigned_response = client.post(
        f"/api/regions/{region_id}/racks",
        json={"items": [_rack_item()], "u_height": 42},
        headers=unassigned_headers,
    )
    readable = client.get(f"/api/regions/{region_id}/racks", headers=unassigned_headers)

    assert admin_response.status_code == 403
    assert unassigned_response.status_code == 403
    assert readable.status_code == 200


def test_rack_occupancy_aggregates_switches_and_implicit_server_positions(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """机柜占用接口应返回有序的交换机和按起始 U 位聚合的服务器侧位置。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-occupancy-reader")
    rack = _create_rack(client, user_headers, region_id, room_name="MIXED")

    empty = client.get(
        f"/api/regions/{region_id}/racks/{rack['id']}/occupancy",
        headers=user_headers,
    )
    assert empty.status_code == 200
    assert empty.json() == {
        "rack_id": rack["id"],
        "rack_name": rack["name"],
        "u_height": 42,
        "switch_positions": [],
        "server_positions": [],
    }

    session = Session(test_db)
    try:
        switch_b = Switch(
            rack_id=str(rack["id"]),
            name="switch-b",
            port_speed_mbps=25000,
            start_u=42,
        )
        switch_a = Switch(
            rack_id=str(rack["id"]),
            name="switch-a",
            port_speed_mbps=25000,
            start_u=40,
            height_u=2,
        )
        ports = [SwitchPort(switch=switch_a, port_number=number) for number in range(1, 4)]
        batch = CablingBatch(region_id=region_id, name="第一批布线", created_by="rack-occupancy-reader")
        session.add_all(
            [
                switch_b,
                CableEntry(
                    batch=batch,
                    server_rack_id=str(rack["id"]),
                    server_start_u=10,
                    server_height_u=2,
                    server_port_name="eth1",
                    switch_port=ports[0],
                    cable_label="cable-1",
                    cable_sequence=1,
                ),
                CableEntry(
                    batch=batch,
                    server_rack_id=str(rack["id"]),
                    server_start_u=10,
                    server_height_u=2,
                    server_port_name="eth0",
                    switch_port=ports[1],
                    cable_label="cable-2",
                    cable_sequence=2,
                ),
                CableEntry(
                    batch=batch,
                    server_rack_id=str(rack["id"]),
                    server_start_u=20,
                    server_height_u=1,
                    server_port_name="idrac",
                    switch_port=ports[2],
                    cable_label="cable-3",
                    cable_sequence=3,
                ),
            ]
        )
        session.commit()
        switch_a_id = switch_a.id
        switch_b_id = switch_b.id
    finally:
        session.close()

    response = client.get(
        f"/api/regions/{region_id}/racks/{rack['id']}/occupancy",
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["switch_positions"] == [
        {
            "switch_id": switch_a_id,
            "switch_name": "switch-a",
            "start_u": 40,
            "height_u": 2,
        },
        {
            "switch_id": switch_b_id,
            "switch_name": "switch-b",
            "start_u": 42,
            "height_u": 1,
        },
    ]
    assert response.json()["server_positions"] == [
        {
            "start_u": 10,
            "height_u": 2,
            "server_port_names": ["eth0", "eth1"],
            "cable_count": 2,
        },
        {
            "start_u": 20,
            "height_u": 1,
            "server_port_names": ["idrac"],
            "cable_count": 1,
        },
    ]


def test_rack_occupancy_rejects_inconsistent_server_heights(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """同一隐式服务器位置的已有线缆高度不一致时应拒绝返回占用快照。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-occupancy-conflict")
    server_rack = _create_rack(client, user_headers, region_id, room_name="SERVER")
    switch_rack = _create_rack(client, user_headers, region_id, room_name="NETWORK")

    session = Session(test_db)
    try:
        switch = Switch(
            rack_id=str(switch_rack["id"]),
            name="switch-a",
            port_speed_mbps=25000,
            start_u=42,
        )
        ports = [SwitchPort(switch=switch, port_number=number) for number in (1, 2)]
        batch = CablingBatch(region_id=region_id, name="第一批布线", created_by="rack-occupancy-conflict")
        session.add_all(
            [
                CableEntry(
                    batch=batch,
                    server_rack_id=str(server_rack["id"]),
                    server_start_u=10,
                    server_height_u=1,
                    server_port_name="eth0",
                    switch_port=ports[0],
                    cable_label="cable-1",
                    cable_sequence=1,
                ),
                CableEntry(
                    batch=batch,
                    server_rack_id=str(server_rack["id"]),
                    server_start_u=10,
                    server_height_u=2,
                    server_port_name="eth1",
                    switch_port=ports[1],
                    cable_label="cable-2",
                    cable_sequence=2,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        f"/api/regions/{region_id}/racks/{server_rack['id']}/occupancy",
        headers=user_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "机柜 SERVER-A01 的服务器侧位置 10U 存在不一致的设备高度: 1U、2U"


def test_rack_occupancy_requires_authentication_and_matching_region(
    client, admin_headers, user_headers_factory
) -> None:
    """机柜占用接口需要登录，且不得通过其他 Region 路径访问机柜。"""
    region_a = _create_region(client, admin_headers, "Region-A")
    region_b = _create_region(client, admin_headers, "Region-B")
    region_a_id = str(region_a["id"])
    region_b_id = str(region_b["id"])
    user_headers = user_headers_factory([region_a_id], username="rack-occupancy-auth")
    rack = _create_rack(client, user_headers, region_a_id)

    unauthenticated = client.get(f"/api/regions/{region_a_id}/racks/{rack['id']}/occupancy")
    wrong_region = client.get(
        f"/api/regions/{region_b_id}/racks/{rack['id']}/occupancy",
        headers=user_headers,
    )

    assert unauthenticated.status_code == 401
    assert wrong_region.status_code == 404
    assert wrong_region.json()["detail"] == "机柜不存在"


def test_rack_rejects_invalid_height_and_duplicate_global_name(client, admin_headers, user_headers_factory) -> None:
    """机柜总 U 数必须为正整数，名称在不同 Region 间也不能重复。"""
    region_a = _create_region(client, admin_headers, "Region-A")
    region_b = _create_region(client, admin_headers, "Region-B")
    region_a_id = str(region_a["id"])
    region_b_id = str(region_b["id"])
    user_headers = user_headers_factory([region_a_id, region_b_id], username="rack-validator")

    invalid = client.post(
        f"/api/regions/{region_a_id}/racks",
        json={"items": [_rack_item()], "u_height": 0},
        headers=user_headers,
    )
    assert invalid.status_code == 422

    _create_rack(client, user_headers, region_a_id, room_name="GLOBAL")
    duplicate = client.post(
        f"/api/regions/{region_b_id}/racks",
        json={"items": [_rack_item(room_name="GLOBAL")], "u_height": 42},
        headers=user_headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "机柜名称已存在: GLOBAL-A01"


def test_update_rack_rejects_height_below_existing_switch(client, admin_headers, user_headers_factory, test_db) -> None:
    """缩小机柜高度时不能截断已上架的交换机。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-shrink-switch")
    rack = _create_rack(client, user_headers, region_id)

    session = Session(test_db)
    try:
        session.add(
            Switch(
                rack_id=str(rack["id"]),
                name="switch-a",
                port_speed_mbps=25000,
                start_u=41,
                height_u=2,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.put(
        f"/api/regions/{region_id}/racks/{rack['id']}",
        json={"u_height": 41},
        headers=user_headers,
    )
    assert response.status_code == 409
    assert "交换机" in response.json()["detail"]
    assert "42U" in response.json()["detail"]


def test_update_rack_rejects_height_below_server_side_position(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """缩小机柜高度时不能截断线缆记录中的服务器侧位置。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-shrink-server")
    server_rack = _create_rack(client, user_headers, region_id, room_name="SERVER")
    switch_rack = _create_rack(client, user_headers, region_id, room_name="NETWORK")

    session = Session(test_db)
    try:
        switch = Switch(
            rack_id=str(switch_rack["id"]),
            name="switch-a",
            port_speed_mbps=25000,
            start_u=42,
        )
        port = SwitchPort(switch=switch, port_number=1)
        batch = CablingBatch(region_id=region_id, name="第一批布线", created_by="rack-shrink-server")
        entry = CableEntry(
            batch=batch,
            server_rack_id=str(server_rack["id"]),
            server_start_u=40,
            server_height_u=3,
            server_port_name="NIC1",
            switch_port=port,
            cable_label="CBL-000001",
            cable_sequence=1,
        )
        session.add(entry)
        session.commit()
    finally:
        session.close()

    response = client.put(
        f"/api/regions/{region_id}/racks/{server_rack['id']}",
        json={"u_height": 41},
        headers=user_headers,
    )
    assert response.status_code == 409
    assert "服务器侧位置" in response.json()["detail"]
    assert "42U" in response.json()["detail"]


def test_delete_rack_reports_switch_and_cable_dependencies(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """机柜存在交换机或线缆引用时返回可读的冲突错误。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-delete")
    switch_rack = _create_rack(client, user_headers, region_id, room_name="NETWORK")
    server_rack = _create_rack(client, user_headers, region_id, room_name="SERVER")

    session = Session(test_db)
    try:
        switch = Switch(
            rack_id=str(switch_rack["id"]),
            name="switch-a",
            port_speed_mbps=25000,
            start_u=42,
        )
        port = SwitchPort(switch=switch, port_number=1)
        batch = CablingBatch(region_id=region_id, name="第一批布线", created_by="rack-delete")
        session.add(
            CableEntry(
                batch=batch,
                server_rack_id=str(server_rack["id"]),
                server_start_u=10,
                server_height_u=2,
                server_port_name="NIC1",
                switch_port=port,
                cable_label="CBL-000001",
                cable_sequence=1,
            )
        )
        session.commit()
    finally:
        session.close()

    switch_rack_response = client.delete(
        f"/api/regions/{region_id}/racks/{switch_rack['id']}",
        headers=user_headers,
    )
    server_rack_response = client.delete(
        f"/api/regions/{region_id}/racks/{server_rack['id']}",
        headers=user_headers,
    )

    assert switch_rack_response.status_code == 409
    assert switch_rack_response.json()["detail"] == "机柜 NETWORK-A01 仍有 1 台交换机，不能删除"
    assert server_rack_response.status_code == 409
    assert server_rack_response.json()["detail"] == "机柜 SERVER-A01 仍被 1 条线缆使用，不能删除"


def test_delete_region_with_rack_returns_dependency_error(client, admin_headers, user_headers_factory, test_db) -> None:
    """Region 仍有机柜时应在强校验阶段拒绝删除，不写入虚假删除日志。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="region-rack-owner")
    _create_rack(client, user_headers, region_id)

    response = client.delete(f"/api/regions/{region_id}", headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Region Region-A 仍有 1 个机柜，不能删除"
    session = Session(test_db)
    try:
        delete_logs = (
            session.query(ChangeLog)
            .filter(
                ChangeLog.entity_type == "region",
                ChangeLog.entity_id == region_id,
                ChangeLog.action == "delete",
            )
            .all()
        )
        assert delete_logs == []
    finally:
        session.close()


def test_create_racks_generates_names_and_records_audit_logs(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """批量创建应由结构化字段生成名称，并为每个机柜记录审计日志。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-bulk-operator")
    items = [_rack_item("A1-403", "A", number) for number in range(1, 13)]
    names = [f"A1-403-A{number:02d}" for number in range(1, 13)]

    response = client.post(
        f"/api/regions/{region_id}/racks",
        json={"items": items, "u_height": 42},
        headers=user_headers,
    )

    assert response.status_code == 201
    created = response.json()
    assert [item["name"] for item in created] == names
    assert {item["room_name"] for item in created} == {"A1-403"}
    assert {item["rack_column"] for item in created} == {"A"}
    assert [item["rack_number"] for item in created] == list(range(1, 13))
    assert {item["u_height"] for item in created} == {42}
    assert {item["region_id"] for item in created} == {region_id}
    assert {item["switch_count"] for item in created} == {0}
    assert {item["cable_count"] for item in created} == {0}

    created_ids = [item["id"] for item in created]
    session = Session(test_db)
    try:
        logs = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "rack", ChangeLog.entity_id.in_(created_ids))
            .order_by(ChangeLog.created_at.asc())
            .all()
        )
        assert len(logs) == 12
        assert {item.action for item in logs} == {"create"}
        assert {item.entity_name for item in logs} == set(names)
        assert {item.operator for item in logs} == {"rack-bulk-operator"}
    finally:
        session.close()


def test_rack_columns_aggregate_region_and_expand_in_number_order(client, admin_headers, user_headers_factory) -> None:
    """机柜列接口应准确聚合整个 Region，并支持按列展开具体机柜。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-column-reader")
    response = client.post(
        f"/api/regions/{region_id}/racks",
        json={
            "items": [
                _rack_item("A1-403", "A", 2),
                _rack_item("A1-403", "B", 1),
                _rack_item("A1-403", "A", 1),
            ],
            "u_height": 42,
        },
        headers=user_headers,
    )
    assert response.status_code == 201

    grouped = client.get(
        f"/api/regions/{region_id}/racks/columns?skip=0&limit=20",
        headers=admin_headers,
    )
    assert grouped.status_code == 200
    grouped_data = grouped.json()
    assert grouped_data["total_columns"] == 2
    assert grouped_data["total_racks"] == 3
    assert grouped_data["items"] == [
        {
            "room_name": "A1-403",
            "rack_column": "A",
            "rack_count": 2,
            "switch_count": 0,
            "cable_count": 0,
        },
        {
            "room_name": "A1-403",
            "rack_column": "B",
            "rack_count": 1,
            "switch_count": 0,
            "cable_count": 0,
        },
    ]

    expanded = client.get(
        f"/api/regions/{region_id}/racks?room_name=A1-403&rack_column=A&skip=0&limit=20",
        headers=admin_headers,
    )
    assert expanded.status_code == 200
    assert [item["rack_number"] for item in expanded.json()["items"]] == [1, 2]

    searched = client.get(
        f"/api/regions/{region_id}/racks/columns?search=B01",
        headers=admin_headers,
    )
    assert searched.status_code == 200
    assert searched.json()["total_columns"] == 1
    assert searched.json()["total_racks"] == 1


def test_create_racks_rejects_existing_name_atomically(client, admin_headers, user_headers_factory, test_db) -> None:
    """批量名称命中已有机柜时应整批拒绝，不写入其他合法名称。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-bulk-conflict")
    _create_rack(client, user_headers, region_id, room_name="A1-403", rack_number=2)

    response = client.post(
        f"/api/regions/{region_id}/racks",
        json={
            "items": [_rack_item("A1-403", "A", number) for number in range(1, 4)],
            "u_height": 42,
        },
        headers=user_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "机柜名称已存在: A1-403-A02"
    session = Session(test_db)
    try:
        stored_names = {
            name
            for (name,) in session.query(Rack.name)
            .filter(Rack.name.in_(["A1-403-A01", "A1-403-A02", "A1-403-A03"]))
            .all()
        }
        assert stored_names == {"A1-403-A02"}
    finally:
        session.close()


def test_create_racks_rejects_duplicate_and_oversized_batches_and_trims_whitespace(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """批量创建拒绝请求内重名和超大批次，并清理结构化字段首尾空格。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-bulk-validator")

    duplicate = client.post(
        f"/api/regions/{region_id}/racks",
        json={"items": [_rack_item("A1-403", "A", 1), _rack_item("A1-403", "A", 1)], "u_height": 42},
        headers=user_headers,
    )
    whitespace = client.post(
        f"/api/regions/{region_id}/racks",
        json={"items": [_rack_item(" A1-403", "A", 1)], "u_height": 42},
        headers=user_headers,
    )
    blank = client.post(
        f"/api/regions/{region_id}/racks",
        json={"items": [_rack_item("   ", "A", 2)], "u_height": 42},
        headers=user_headers,
    )
    oversized = client.post(
        f"/api/regions/{region_id}/racks",
        json={"items": [_rack_item("RACK", "A", number + 1) for number in range(501)], "u_height": 42},
        headers=user_headers,
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "请求中的机柜位置重复: A1-403-A01"
    assert whitespace.status_code == 201
    assert whitespace.json()[0]["room_name"] == "A1-403"
    assert whitespace.json()[0]["name"] == "A1-403-A01"
    assert blank.status_code == 422
    assert oversized.status_code == 422
    session = Session(test_db)
    try:
        assert session.query(Rack).count() == 1
    finally:
        session.close()


def test_update_rack_rejects_empty_payload_and_explicit_null(client, admin_headers, user_headers_factory) -> None:
    """机柜部分更新拒绝空请求和不可为空字段显式传入 null。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-update-validator")
    rack = _create_rack(client, user_headers, region_id)

    empty = client.put(
        f"/api/regions/{region_id}/racks/{rack['id']}",
        json={},
        headers=user_headers,
    )
    explicit_null = client.put(
        f"/api/regions/{region_id}/racks/{rack['id']}",
        json={"room_name": None},
        headers=user_headers,
    )

    assert empty.status_code == 422
    assert explicit_null.status_code == 422


def test_create_racks_rejects_different_positions_with_same_generated_name(
    client, admin_headers, user_headers_factory, test_db
) -> None:
    """不同结构化位置生成同一名称时应在写入前整批拒绝。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    user_headers = user_headers_factory([region_id], username="rack-name-collision")

    response = client.post(
        f"/api/regions/{region_id}/racks",
        json={
            "items": [
                _rack_item("A-B", "C", 1),
                _rack_item("A", "B-C", 1),
            ],
            "u_height": 42,
        },
        headers=user_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "请求中的机柜名称重复: A-B-C01"
    session = Session(test_db)
    try:
        assert session.query(Rack).count() == 0
        assert session.query(ChangeLog).filter(ChangeLog.entity_type == "rack").count() == 0
    finally:
        session.close()


def test_create_racks_requires_assigned_region_user(client, admin_headers, user_headers_factory) -> None:
    """批量创建沿用 Region 业务写权限，管理员和未授权用户均不可操作。"""
    region = _create_region(client, admin_headers)
    region_id = str(region["id"])
    unassigned_headers = user_headers_factory([], username="rack-bulk-unassigned")
    payload = {"items": [_rack_item("A1-403", "A", 1)], "u_height": 42}

    admin_response = client.post(
        f"/api/regions/{region_id}/racks",
        json=payload,
        headers=admin_headers,
    )
    unassigned_response = client.post(
        f"/api/regions/{region_id}/racks",
        json=payload,
        headers=unassigned_headers,
    )

    assert admin_response.status_code == 403
    assert unassigned_response.status_code == 403
