"""变更日志接口测试。"""


def test_list_change_logs_filters_by_entity_type_action_and_operator(client, admin_headers):
    """变更日志列表支持组合筛选，并保持分页响应结构。"""
    client.post("/api/regions", json={"name": "Region-A"}, headers=admin_headers)

    response = client.get(
        "/api/change-logs?entity_type=region&action=create&operator=adm",
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["skip"] == 0
    assert data["limit"] == 50
    assert data["total"] == 1
    assert data["items"][0]["entity_type"] == "region"
    assert data["items"][0]["entity_name"] == "Region-A"
    assert data["items"][0]["action"] == "create"
    assert data["items"][0]["operator"] == "admin"


def test_list_change_logs_returns_entity_name_for_plane_type_update(client, admin_headers):
    """更新网络平面类型时，变更日志应返回具体变更对象名称。"""
    created = client.post(
        "/api/network-plane-types",
        json={"name": "业务平面", "is_private": True},
        headers=admin_headers,
    ).json()
    update_response = client.put(
        f"/api/network-plane-types/{created['id']}",
        json={"is_private": False},
        headers=admin_headers,
    )
    assert update_response.status_code == 200

    response = client.get(
        "/api/change-logs?entity_type=network_plane_type&action=update",
        headers=admin_headers,
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["entity_id"] == created["id"]
    assert item["entity_name"] == "业务平面"
    assert item["field_name"] == "is_private"
    assert item["old_value"] == "True"
    assert item["new_value"] == "False"
