"""OpenAPI 文档页面及本地静态资源测试。"""

import hashlib
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.openapi_docs import API_DOCS_STATIC_DIR


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/static/api-docs/swagger-ui/swagger-ui-bundle.js", "text/javascript"),
        ("/static/api-docs/swagger-ui/swagger-ui.css", "text/css"),
        ("/static/api-docs/redoc/redoc.standalone.js", "text/javascript"),
        ("/static/api-docs/redoc/logo-mini.svg", "image/svg+xml"),
        ("/static/api-docs/favicon.png", "image/png"),
    ],
)
def test_openapi_document_assets_are_served_locally(
    client: TestClient,
    path: str,
    content_type: str,
) -> None:
    """文档渲染所需静态资源应由后端本地提供。"""
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.content


@pytest.mark.parametrize(
    ("path", "expected_asset"),
    [
        ("/docs", "/static/api-docs/swagger-ui/swagger-ui-bundle.js"),
        ("/redoc", "/static/api-docs/redoc/redoc.standalone.js"),
    ],
)
def test_openapi_document_pages_only_reference_local_assets(
    client: TestClient,
    path: str,
    expected_asset: str,
) -> None:
    """Swagger UI 和 ReDoc 页面不应依赖外部静态资源。"""
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert expected_asset in response.text
    assert "url: '/api/external/v1/openapi.json'" in response.text or (
        'spec-url="/api/external/v1/openapi.json"' in response.text
    )
    assert "https://" not in response.text
    assert "http://" not in response.text


def test_default_openapi_schema_is_disabled(client: TestClient) -> None:
    """默认全量 OpenAPI Schema 不应公开。"""
    response = client.get("/openapi.json")

    assert response.status_code == 404


def test_external_openapi_schema_only_contains_external_api(client: TestClient) -> None:
    """公开 Schema 应只包含版本化 External API，不暴露内部业务接口。"""
    response = client.get("/api/external/v1/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert schema["info"]["title"] == "DC Network Planner External API"
    assert schema["info"]["version"] == "1.0.0"
    assert paths
    assert all(path.startswith("/api/external/v1/") for path in paths)
    assert "/docs" not in paths
    assert "/redoc" not in paths
    assert all(not path.startswith("/static/api-docs") for path in paths)
    assert "/api/external/v1/auth/token" in paths
    assert "/api/external/v1/lookup" in paths
    assert "/api/auth/login" not in paths
    assert "/api/regions" not in paths
    assert "/api/external-access-tokens" not in paths
    assert "/api/external/v1/openapi.json" not in paths

    token_operation = paths["/api/external/v1/auth/token"]["post"]
    lookup_operation = paths["/api/external/v1/lookup"]["get"]
    assert token_operation["operationId"] == "issue_external_access_token"
    assert lookup_operation["operationId"] == "lookup_network_planes"

    token_request = schema["components"]["schemas"]["ExternalTokenRequest"]
    assert token_request["properties"]["username"]["examples"] == ["api-user"]
    assert token_request["properties"]["password"]["examples"] == ["your-password"]


def test_redoc_bundle_uses_local_branding_asset(client: TestClient) -> None:
    """ReDoc 运行时加载的页脚图标也应使用本地资源。"""
    response = client.get("/static/api-docs/redoc/redoc.standalone.js")

    assert response.status_code == 200
    assert "https://cdn.redoc.ly/redoc/logo-mini.svg" not in response.text
    assert "/static/api-docs/redoc/logo-mini.svg" in response.text


def test_openapi_document_asset_checksums() -> None:
    """本地文档资源应与已提交的 SHA-256 清单一致。"""
    checksum_file = API_DOCS_STATIC_DIR / "SHA256SUMS"
    expected_files = {
        "favicon.png",
        "redoc/logo-mini.svg",
        "redoc/redoc.standalone.js",
        "swagger-ui/swagger-ui-bundle.js",
        "swagger-ui/swagger-ui.css",
    }

    entries: dict[str, str] = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        checksum, relative_path = line.split(maxsplit=1)
        entries[relative_path] = checksum

    assert set(entries) == expected_files
    for relative_path, expected_checksum in entries.items():
        actual_checksum = hashlib.sha256((API_DOCS_STATIC_DIR / relative_path).read_bytes()).hexdigest()
        assert actual_checksum == expected_checksum


def test_openapi_document_assets_are_in_python_package_data() -> None:
    """wheel 构建配置应包含运行 OpenAPI 文档所需的静态资源。"""
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    package_data = set(pyproject["tool"]["setuptools"]["package-data"]["app"])

    assert {
        "static/api_docs/*",
        "static/api_docs/redoc/*",
        "static/api_docs/swagger-ui/*",
    }.issubset(package_data)
