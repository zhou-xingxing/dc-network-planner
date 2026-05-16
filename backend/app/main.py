from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    auth,
    backup,
    change_logs,
    excel,
    lookup,
    network_plane_types,
    region_planes,
    regions,
    stats,
    users,
)
from app.services.auth import ensure_bootstrap_admin
from app.services.backup import ensure_backup_config
from app.services.backup_scheduler import backup_scheduler
from app.services.region_plane import validate_network_overlap_policy_on_startup


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register routers
app.include_router(auth.router)
app.include_router(regions.router)
app.include_router(region_planes.router)
app.include_router(network_plane_types.router)
app.include_router(lookup.router)
app.include_router(excel.router)
app.include_router(change_logs.router)
app.include_router(stats.router)
app.include_router(backup.router)
app.include_router(users.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
