from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import BusinessError
from app.models.region import Region
from app.models.region_network_plane import RegionNetworkPlane
from app.schemas.region import RegionCreate, RegionUpdate
from app.services.change_log import log_change
from app.utils.time_utils import format_datetime


@dataclass(frozen=True)
class RegionWithPlaneCount:
    """Region 及其已启用网络平面数量。"""

    region: Region
    plane_count: int


def list_regions(
    db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None
) -> tuple[list[RegionWithPlaneCount], int]:
    """查询 Region 列表。

    Args:
        db: 数据库会话。
        skip: 分页偏移量。
        limit: 每页条数。
        search: 按名称模糊搜索（可选）。

    Returns:
        (Region 及平面数量列表, 总数) 的元组。
    """
    query = db.query(Region)
    if search:
        query = query.filter(Region.name.ilike(f"%{search}%"))
    total = query.count()
    rows = (
        query.outerjoin(RegionNetworkPlane, Region.id == RegionNetworkPlane.region_id)
        .with_entities(Region, func.count(RegionNetworkPlane.id))
        .group_by(Region.id)
        .order_by(Region.name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    regions = [RegionWithPlaneCount(region=region, plane_count=plane_count) for region, plane_count in rows]
    return regions, total


def get_region(db: Session, region_id: str) -> Optional[Region]:
    """根据 ID 获取 Region。

    Args:
        db: 数据库会话。
        region_id: Region ID。

    Returns:
        Region 对象，不存在时返回 None。
    """
    return db.query(Region).filter(Region.id == region_id).first()


def get_region_detail(db: Session, region_id: str) -> Optional[dict[str, Any]]:
    """获取 Region 详情，planes 返回树形结构。

    Args:
        db: 数据库会话。
        region_id: Region ID。

    Returns:
        包含 Region 信息及嵌套平面树的字典，不存在时返回 None。
    """
    from app.services.region_plane import get_region_plane_tree

    region = get_region(db, region_id)
    if not region:
        return None
    plane_tree = get_region_plane_tree(db, region_id)

    def _count_planes(nodes: list[dict[str, Any]]) -> int:
        count = 0
        for n in nodes:
            count += 1 + _count_planes(n.get("children", []))
        return count

    return {
        "id": region.id,
        "name": region.name,
        "description": region.description or "",
        "plane_count": _count_planes(plane_tree),
        "planes": plane_tree,
        "created_at": format_datetime(region.created_at),
        "updated_at": format_datetime(region.updated_at),
    }


def create_region(db: Session, data: RegionCreate, operator: str) -> Region:
    """创建新 Region。

    Args:
        db: 数据库会话。
        data: 创建参数。
        operator: 操作者名称。

    Returns:
        新创建的 Region 对象。

    Raises:
        BusinessError: 同名 Region 已存在。
    """
    existing = db.query(Region).filter(Region.name == data.name).first()
    if existing:
        raise BusinessError(f"Region with name '{data.name}' already exists")

    region = Region(name=data.name, description=data.description or "")
    db.add(region)
    db.flush()
    log_change(
        db,
        entity_type="region",
        entity_id=region.id,
        action="create",
        operator=operator,
        new_value=region.name,
    )
    return region


def update_region(db: Session, region_id: str, data: RegionUpdate, operator: str) -> Optional[RegionWithPlaneCount]:
    """更新 Region 信息。

    Args:
        db: 数据库会话。
        region_id: 要更新的 Region ID。
        data: 更新参数。
        operator: 操作者名称。

    Returns:
        更新后的 Region 及平面数量，不存在时返回 None。
    """
    region = get_region(db, region_id)
    if not region:
        return None
    changes = {}
    if data.name is not None and data.name != region.name:
        changes["name"] = (region.name, data.name)
        region.name = data.name
    if data.description is not None and data.description != region.description:
        changes["description"] = (region.description or "", data.description or "")
        region.description = data.description
    if changes:
        for field, (old, new) in changes.items():
            log_change(
                db,
                entity_type="region",
                entity_id=region_id,
                action="update",
                field_name=field,
                old_value=str(old),
                new_value=str(new),
                operator=operator,
            )
        db.flush()
    return RegionWithPlaneCount(region=region, plane_count=count_region_planes(db, region.id))


def count_region_planes(db: Session, region_id: str) -> int:
    """统计指定 Region 下已启用的网络平面数量。"""
    return db.query(func.count(RegionNetworkPlane.id)).filter(RegionNetworkPlane.region_id == region_id).scalar() or 0


def delete_region(db: Session, region_id: str, operator: str) -> bool:
    """删除 Region。

    Args:
        db: 数据库会话。
        region_id: 要删除的 Region ID。
        operator: 操作者名称。

    Returns:
        删除成功返回 True，不存在时返回 False。
    """
    region = get_region(db, region_id)
    if not region:
        return False
    log_change(
        db,
        entity_type="region",
        entity_id=region_id,
        action="delete",
        operator=operator,
        old_value=region.name,
    )
    db.delete(region)
    db.flush()
    return True
