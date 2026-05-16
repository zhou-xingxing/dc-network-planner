from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.change_log import ChangeLog
from app.models.network_plane_type import NetworkPlaneType
from app.models.region import Region
from app.models.region_network_plane import RegionNetworkPlane
from app.utils.time_utils import format_datetime


def get_system_stats(db: Session) -> dict[str, Any]:
    """获取系统概览统计数据。"""
    total_regions = db.query(func.count(Region.id)).scalar() or 0
    total_plane_types = db.query(func.count(NetworkPlaneType.id)).scalar() or 0
    total_region_planes = db.query(func.count(RegionNetworkPlane.id)).scalar() or 0
    total_change_logs = db.query(func.count(ChangeLog.id)).scalar() or 0

    scope_counts = (
        db.query(NetworkPlaneType.is_private, func.count(RegionNetworkPlane.id))
        .join(NetworkPlaneType, RegionNetworkPlane.plane_type_id == NetworkPlaneType.id)
        .group_by(NetworkPlaneType.is_private)
        .all()
    )
    scope_order = {"非私网": 0, "私网": 1}
    scope_items = [("私网" if is_private else "非私网", count) for is_private, count in scope_counts]
    plane_by_scope = dict(sorted(scope_items, key=lambda item: scope_order[item[0]]))

    region_counts = (
        db.query(Region.name, func.count(RegionNetworkPlane.id))
        .join(RegionNetworkPlane, Region.id == RegionNetworkPlane.region_id, isouter=True)
        .group_by(Region.id, Region.name)
        .order_by(Region.name.asc())
        .all()
    )
    plane_by_region = [{"region_name": name, "count": count} for name, count in region_counts]

    recent = db.query(ChangeLog).order_by(ChangeLog.created_at.desc()).limit(10).all()
    recent_changes = [
        {
            "id": change_log.id,
            "entity_type": change_log.entity_type,
            "action": change_log.action,
            "operator": change_log.operator,
            "summary": _build_summary(change_log),
            "created_at": format_datetime(change_log.created_at),
        }
        for change_log in recent
    ]

    return {
        "total_regions": total_regions,
        "total_plane_types": total_plane_types,
        "total_region_planes": total_region_planes,
        "total_change_logs": total_change_logs,
        "plane_by_scope": plane_by_scope,
        "plane_by_region": plane_by_region,
        "recent_changes": recent_changes,
    }


def _build_summary(change_log: ChangeLog) -> str:
    """生成概览页最近变更摘要。"""
    if change_log.action == "create":
        return f"创建了 {change_log.entity_type}: {change_log.new_value or ''}"
    if change_log.action == "update":
        return (
            f"更新了 {change_log.entity_type} {change_log.field_name or ''}: "
            f"{change_log.old_value or ''} -> {change_log.new_value or ''}"
        )
    if change_log.action == "delete":
        return f"删除了 {change_log.entity_type}: {change_log.old_value or ''}"
    if change_log.action == "import":
        return f"批量导入网络平面: {change_log.new_value or ''}"
    return f"{change_log.action} {change_log.entity_type}"
