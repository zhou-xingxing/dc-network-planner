"""External API 网络平面类型列表适配层测试。"""


def _issue_external_token(client) -> str:
    response = client.post(
        "/api/external/v1/auth/token",
        json={
            "username": "admin",
            "password": "admin",
            "requested_scopes": ["network-plane:read"],
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_external_network_plane_types_exposes_external_response_contract(client, admin_headers):
    """外部入口应使用 External Token 返回稳定的对外响应结构。"""
    created = client.post(
        "/api/network-plane-types",
        json={
            "name": "外部接口平面",
            "description": "供外部系统识别的网络平面类型",
            "is_private": True,
            "vrf": "vrf-external",
        },
        headers=admin_headers,
    ).json()
    raw_token = _issue_external_token(client)

    response = client.get(
        "/api/external/v1/network-plane-types",
        headers={"Authorization": f"Bearer {raw_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["skip"] == 0
    assert body["limit"] == 100
    assert body["items"] == [created]
