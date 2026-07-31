from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.exception_handlers import (
    business_error_handler,
    resource_not_found_handler,
    unexpected_error_handler,
    wrapped_http_exception_handler,
)
from app.exceptions import BusinessError, ResourceNotFoundError
from app.logging_config import setup_logging
from app.middleware import request_logging_middleware
from app.openapi_docs import API_DOCS_STATIC_DIR, API_DOCS_STATIC_URL
from app.openapi_docs import router as openapi_docs_router
from app.routers import (
    auth,
    backup,
    change_log,
    excel,
    external_access_token,
    external_auth,
    external_lookup,
    external_network_plane_type,
    lookup,
    network_plane_type,
    rack,
    region,
    region_plane,
    stats,
    switch,
    switch_business_type,
    switch_group,
    user,
)
from app.services.backup import ensure_backup_config
from app.services.backup_scheduler import backup_scheduler
from app.services.region_plane import validate_network_overlap_policy_on_startup
from app.services.user import ensure_bootstrap_admin


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    # startup: create tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_bootstrap_admin(db)
        ensure_backup_config(db)
        validate_network_overlap_policy_on_startup(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    backup_scheduler.start()
    try:
        yield
    finally:
        backup_scheduler.stop()


app = FastAPI(
    title="DC Network Planner",
    description="数据中心网络平面规划系统的后端 API 服务",
    version="0.1.0",
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.mount(
    API_DOCS_STATIC_URL,
    StaticFiles(directory=API_DOCS_STATIC_DIR),
    name="api-docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_logging_middleware)

"""
- BusinessError 未被 Router 转换时，由 business_error_handler 转成 409。
- ResourceNotFoundError 未被 Router 转换时，由 resource_not_found_handler 转成 404。
- Router、依赖等抛出的所有 HTTPException 由 wrapped_http_exception_handler 包装 FastAPI 默认处理器；
  其中 4xx 只返回响应并交给访问日志记录，5xx 额外记录 app.exceptions 堆栈。
- 其他非预期 Exception 通常先由 request_logging_middleware 的 except 捕获并返回统一 500；
  unexpected_error_handler 是第二道防线，处理未被中间件捕获的漏网异常并复用同一套 500 响应。
"""
app.add_exception_handler(BusinessError, cast(Any, business_error_handler))
app.add_exception_handler(ResourceNotFoundError, cast(Any, resource_not_found_handler))
app.add_exception_handler(HTTPException, cast(Any, wrapped_http_exception_handler))
app.add_exception_handler(Exception, cast(Any, unexpected_error_handler))


# Register routers
app.include_router(openapi_docs_router)
app.include_router(auth.router)
app.include_router(region.router)
app.include_router(rack.router)
app.include_router(region_plane.router)
app.include_router(network_plane_type.router)
app.include_router(switch_business_type.router)
app.include_router(switch_group.router)
app.include_router(switch.router)
app.include_router(lookup.router)
app.include_router(excel.router)
app.include_router(external_auth.router)
app.include_router(external_lookup.router)
app.include_router(external_network_plane_type.router)
app.include_router(external_access_token.router)
app.include_router(change_log.router)
app.include_router(stats.router)
app.include_router(backup.router)
app.include_router(user.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
