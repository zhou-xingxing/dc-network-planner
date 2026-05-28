"""Health endpoint tests."""


def test_health_returns_ok(client):
    """健康检查接口应返回 200 和 ok 状态。"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
