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
    assert data["items"][0]["action"] == "create"
    assert data["items"][0]["operator"] == "admin"
