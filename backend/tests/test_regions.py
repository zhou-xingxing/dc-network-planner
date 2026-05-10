"""Region CRUD tests."""

REGION_DATA = {"name": "北京数据中心", "description": "Production region"}


def test_create_region(client, admin_headers):
    resp = client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == REGION_DATA["name"]
    assert data["description"] == REGION_DATA["description"]
    assert "id" in data


def test_create_duplicate_region(client, admin_headers):
    client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    resp = client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    assert resp.status_code == 409


def test_list_regions(client, admin_headers):
    client.post("/api/regions", json={"name": "Region-B", "description": ""}, headers=admin_headers)
    client.post("/api/regions", json={"name": "Region-A", "description": ""}, headers=admin_headers)
    resp = client.get("/api/regions?skip=0&limit=10", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert [item["name"] for item in data["items"]] == ["Region-A", "Region-B"]


def test_list_regions_search(client, admin_headers):
    client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    client.post(
        "/api/regions",
        json={"name": "上海数据中心", "description": ""},
        headers=admin_headers,
    )
    resp = client.get("/api/regions?search=北京", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "北京数据中心"


def test_update_region(client, admin_headers):
    resp = client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    region_id = resp.json()["id"]

    resp = client.put(
        f"/api/regions/{region_id}",
        json={"name": "北京数据中心-UPDATED"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "北京数据中心-UPDATED"


def test_delete_region(client, admin_headers):
    resp = client.post("/api/regions", json=REGION_DATA, headers=admin_headers)
    region_id = resp.json()["id"]

    resp = client.delete(f"/api/regions/{region_id}", headers=admin_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/regions/{region_id}", headers=admin_headers)
    assert resp.status_code == 404


def test_get_nonexistent_region(client, admin_headers):
    resp = client.get("/api/regions/nonexistent-id", headers=admin_headers)
    assert resp.status_code == 404
