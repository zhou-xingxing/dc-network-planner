from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.change_log import ChangeLog
from app.models.network_plane_type import NetworkPlaneType
from app.models.region import Region
from app.models.region_network_plane import RegionNetworkPlane
from app.utils.time_utils import format_datetime

router = APIRouter(prefix="/api/stats", tags=["Stats"], dependencies=[Depends(get_current_user)])


@router.get("")
def get_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """获取系统概览统计数据。"""
    total_regions = db.query(func.count(Region.id)).scalar() or 0
    total_plane_types = db.query(func.count(NetworkPlaneType.id)).scalar() or 0
    total_region_planes = db.query(func.count(RegionNetworkPlane.id)).scalar() or 0
    total_change_logs = db.query(func.count(ChangeLog.id)).scalar() or 0

    # Region network plane by scope
    scope_counts = (
        db.query(NetworkPlaneType.is_private, func.count(RegionNetworkPlane.id))
        .join(NetworkPlaneType, RegionNetworkPlane.plane_type_id == NetworkPlaneType.id)
        .group_by(NetworkPlaneType.is_private)
        .all()
    )
    scope_order = {"非私网": 0, "私网": 1}
    scope_items = [("私网" if is_private else "非私网", count) for is_private, count in scope_counts]
    plane_by_scope = dict(sorted(scope_items, key=lambda item: scope_order[item[0]]))

    # Region network plane by region
    region_counts = (
        db.query(Region.name, func.count(RegionNetworkPlane.id))
        .join(RegionNetworkPlane, Region.id == RegionNetworkPlane.region_id, isouter=True)
        .group_by(Region.id, Region.name)
        .order_by(Region.name.asc())
        .all()
    )
    plane_by_region = [{"region_name": name, "count": c} for name, c in region_counts]

    # Recent changes
    recent = db.query(ChangeLog).order_by(ChangeLog.created_at.desc()).limit(10).all()
    recent_changes = []
    for cl in recent:
        recent_changes.append(
            {
                "id": cl.id,
                "entity_type": cl.entity_type,
                "action": cl.action,
                "operator": cl.operator,
                "summary": _build_summary(cl),
                "created_at": format_datetime(cl.created_at),
            }
        )

    return {
        "total_regions": total_regions,
        "total_plane_types": total_plane_types,
        "total_region_planes": total_region_planes,
        "total_change_logs": total_change_logs,
        "plane_by_scope": plane_by_scope,
        "plane_by_region": plane_by_region,
        "recent_changes": recent_changes,
    }


def _build_summary(cl: ChangeLog) -> str:
    if cl.action == "create":
        return f"创建了 {cl.entity_type}: {cl.new_value or ''}"
    elif cl.action == "update":
        return f"更新了 {cl.entity_type} {cl.field_name or ''}: {cl.old_value or ''} -> {cl.new_value or ''}"
    elif cl.action == "delete":
        return f"删除了 {cl.entity_type}: {cl.old_value or ''}"
    elif cl.action == "import":
        return f"批量导入网络平面: {cl.new_value or ''}"
    return f"{cl.action} {cl.entity_type}"
