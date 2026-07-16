def _setup_lookup_data(client, admin_headers, user_headers_factory) -> None:
    """创建一条可被 lookup 命中的 Region 网络平面。"""
    region = client.post("/api/regions", json={"name": "ExternalLookupRegion"}, headers=admin_headers).json()
    plane_type = client.post("/api/network-plane-types", json={"name": "外部查询平面"}, headers=admin_headers).json()
    user_headers = user_headers_factory([region["id"]], username="external-lookup-writer")
    client.post(
        f"/api/regions/{region['id']}/planes",
        json={"plane_type_id": plane_type["id"], "cidr": "10.0.0.0/24"},
        headers=user_headers,
    )


def _issue_external_token(client, username: str = "admin", scopes: list[str] | None = None) -> str:
    response = client.post(
        "/api/external/v1/auth/token",
        json={
            "username": username,
            "password": "admin" if username == "admin" else "password",
            "requested_scopes": scopes or ["network-plane:read"],
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _external_headers(raw_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_token}"}


def test_external_lookup_cidr_match_overlap(client, admin_headers, user_headers_factory):
    """外部 lookup 将 cidr_match=overlap 映射为内部重叠查询。"""
    _setup_lookup_data(client, admin_headers, user_headers_factory)
    raw_token = _issue_external_token(client)

    exact_response = client.get("/api/external/v1/lookup?q=10.0.0.0/25", headers=_external_headers(raw_token))
    overlap_response = client.get(
        "/api/external/v1/lookup?q=10.0.0.0/25&cidr_match=overlap",
        headers=_external_headers(raw_token),
    )

    assert exact_response.status_code == 200
    assert exact_response.json()["total"] == 0
    assert overlap_response.status_code == 200
    assert overlap_response.json()["total"] == 1
    assert overlap_response.json()["results"][0]["cidr"] == "10.0.0.0/24"
