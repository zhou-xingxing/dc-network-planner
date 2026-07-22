"""提供不依赖外部 CDN 的 OpenAPI 文档页面。"""

from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

EXTERNAL_API_PREFIX = "/api/external/v1/"
EXTERNAL_OPENAPI_URL = "/api/external/v1/openapi.json"
API_DOCS_STATIC_URL = "/static/api-docs"
API_DOCS_STATIC_DIR = Path(__file__).resolve().parent / "static" / "api_docs"

router = APIRouter()


def _build_external_openapi_schema(app: FastAPI) -> dict[str, Any]:
    """生成并缓存仅包含 External API 的 OpenAPI Schema。"""
    cached_schema = getattr(app.state, "external_openapi_schema", None)
    if isinstance(cached_schema, dict):
        return cast(dict[str, Any], cached_schema)

    external_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.include_in_schema and route.path.startswith(EXTERNAL_API_PREFIX)
    ]
    schema = get_openapi(
        title="DC Network Planner External API",
        version="1.0.0",
        description="面向外部系统与自动化客户端的数据中心网络平面查询 API。",
        routes=external_routes,
    )
    app.state.external_openapi_schema = schema
    return schema


@router.get(EXTERNAL_OPENAPI_URL, include_in_schema=False)
def external_openapi(request: Request) -> dict[str, Any]:
    """返回独立且版本化的 External OpenAPI Schema。"""
    return _build_external_openapi_schema(request.app)


@router.get("/docs", include_in_schema=False)
def swagger_ui() -> HTMLResponse:
    """返回使用本地静态资源渲染的 Swagger UI。"""
    return get_swagger_ui_html(
        openapi_url=EXTERNAL_OPENAPI_URL,
        title="DC Network Planner External API - Swagger UI",
        swagger_js_url=f"{API_DOCS_STATIC_URL}/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url=f"{API_DOCS_STATIC_URL}/swagger-ui/swagger-ui.css",
        swagger_favicon_url=f"{API_DOCS_STATIC_URL}/favicon.png",
    )


@router.get("/redoc", include_in_schema=False)
def redoc_ui() -> HTMLResponse:
    """返回使用本地静态资源渲染的 ReDoc。"""
    return get_redoc_html(
        openapi_url=EXTERNAL_OPENAPI_URL,
        title="DC Network Planner External API - ReDoc",
        redoc_js_url=f"{API_DOCS_STATIC_URL}/redoc/redoc.standalone.js",
        redoc_favicon_url=f"{API_DOCS_STATIC_URL}/favicon.png",
        with_google_fonts=False,
    )
