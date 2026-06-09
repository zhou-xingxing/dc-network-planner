from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.exceptions import BusinessError
from app.models.network_plane_type import NetworkPlaneType
from app.models.region_network_plane import RegionNetworkPlane
from app.schemas.network_plane_type import PlaneTypeCreate, PlaneTypeUpdate
from app.services.change_log import log_change

MAX_PLANE_TYPE_DEPTH = 2


def list_plane_types(db: Session, skip: int = 0, limit: int = 100) -> tuple[list[NetworkPlaneType], int]:
    """查询网络平面类型列表。

    Args:
        db: 数据库会话。
        skip: 分页偏移量。
        limit: 每页条数。

    Returns:
        (平面类型列表, 总数) 的元组。
    """
    total = db.query(NetworkPlaneType).count()
    items = db.query(NetworkPlaneType).order_by(NetworkPlaneType.name.asc()).offset(skip).limit(limit).all()
    return items, total


def get_plane_type_parent_names(
    db: Session,
    plane_type_ids: Sequence[str],
) -> dict[str, str | None]:
    """批量查询网络平面类型响应所需的父级名称。"""
    if not plane_type_ids:
        return {}

    parent_type = aliased(NetworkPlaneType)
    rows = (
        db.query(
            NetworkPlaneType.id,
            parent_type.name,
        )
        .outerjoin(parent_type, NetworkPlaneType.parent_id == parent_type.id)
        .filter(NetworkPlaneType.id.in_(plane_type_ids))
        .all()
    )
    return {plane_type_id: parent_name for plane_type_id, parent_name in rows}


def get_plane_type(db: Session, pt_id: str) -> Optional[NetworkPlaneType]:
    """根据 ID 获取网络平面类型。

    Args:
        db: 数据库会话。
        pt_id: 平面类型 ID。

    Returns:
        NetworkPlaneType 对象，不存在时返回 None。
    """
    return db.query(NetworkPlaneType).filter(NetworkPlaneType.id == pt_id).first()


def get_plane_type_by_name(db: Session, name: str) -> Optional[NetworkPlaneType]:
    """根据名称获取网络平面类型。

    Args:
        db: 数据库会话。
        name: 平面类型名称。

    Returns:
        NetworkPlaneType 对象，不存在时返回 None。
    """
    return db.query(NetworkPlaneType).filter(NetworkPlaneType.name == name).first()


def count_children_for_plane_type(db: Session, pt_id: str) -> int:
    """统计指定网络平面类型的直接子类型数量。"""
    return db.query(func.count(NetworkPlaneType.id)).filter(NetworkPlaneType.parent_id == pt_id).scalar() or 0


def create_plane_type(db: Session, data: PlaneTypeCreate, operator: str) -> NetworkPlaneType:
    """创建网络平面类型。

    Args:
        db: 数据库会话。
        data: 创建参数。
        operator: 操作者名称。

    Returns:
        新创建的 NetworkPlaneType 对象。
    """
    parent = _validate_parent_assignment(db, target_id=None, parent_id=data.parent_id)
    _ensure_privacy_matches_parent(parent, is_private=data.is_private)
    pt = NetworkPlaneType(
        name=data.name,
        description=data.description or "",
        is_private=data.is_private,
        vrf=data.vrf or None,
        parent=parent,
    )
    db.add(pt)
    db.flush()
    log_change(
        db,
        entity_type="network_plane_type",
        entity_id=pt.id,
        entity_name=pt.name,
        action="create",
        operator=operator,
        new_value=f"name={pt.name}, parent={_format_parent_name(parent)}",
    )
    return pt


def update_plane_type(db: Session, pt_id: str, data: PlaneTypeUpdate, operator: str) -> Optional[NetworkPlaneType]:
    """更新网络平面类型。

    Args:
        db: 数据库会话。
        pt_id: 要更新的平面类型 ID。
        data: 更新参数。
        operator: 操作者名称。

    Returns:
        更新后的 NetworkPlaneType 对象，不存在时返回 None。
    """
    pt = get_plane_type(db, pt_id)
    if not pt:
        return None
    entity_name = pt.name
    changes = {}
    if data.name is not None and data.name != pt.name:
        changes["name"] = (pt.name, data.name)
        pt.name = data.name
    if data.description is not None and data.description != pt.description:
        changes["description"] = (pt.description or "", data.description or "")
        pt.description = data.description
    descendant_privacy_changed = False
    if "vrf" in data.model_fields_set:
        new_vrf = data.vrf or None
        if new_vrf != pt.vrf:
            changes["vrf"] = (pt.vrf or "", new_vrf or "")
            pt.vrf = new_vrf
    if "parent_id" in data.model_fields_set:
        new_parent_id = data.parent_id or None
        if new_parent_id != pt.parent_id:
            if _count_regions_for_type_and_descendants(db, pt_id) > 0:
                raise BusinessError("已被 Region 使用的网络平面类型不能调整父级")
            old_parent = pt.parent if pt.parent_id else None
            new_parent = _validate_parent_assignment(db, target_id=pt_id, parent_id=new_parent_id)
            requested_is_private = data.is_private if data.is_private is not None else pt.is_private
            _ensure_privacy_matches_parent(new_parent, is_private=requested_is_private)
            changes["parent"] = (_format_parent_name(old_parent), _format_parent_name(new_parent))
            pt.parent = new_parent
    elif pt.parent_id and data.is_private is not None:
        _ensure_privacy_matches_parent(pt.parent, is_private=data.is_private)
    new_is_private = _resolve_inherited_privacy(db, pt, data)
    if new_is_private != pt.is_private:
        changes["is_private"] = (pt.is_private, new_is_private)
        pt.is_private = new_is_private
        descendant_privacy_changed = True
    if changes:
        for field, (old, new) in changes.items():
            log_change(
                db,
                entity_type="network_plane_type",
                entity_id=pt_id,
                entity_name=entity_name,
                action="update",
                field_name=field,
                old_value=str(old),
                new_value=str(new),
                operator=operator,
            )
        if descendant_privacy_changed:
            _sync_descendant_privacy(db, pt, new_is_private, operator)
        db.flush()
    return pt


def delete_plane_type(db: Session, pt_id: str, operator: str) -> bool:
    """删除网络平面类型。

    如果该类型已被 Region 使用则拒绝删除。

    Args:
        db: 数据库会话。
        pt_id: 要删除的平面类型 ID。
        operator: 操作者名称。

    Returns:
        删除成功返回 True，不存在时返回 False。

    Raises:
        BusinessError: 平面类型正在被 Region 使用中。
    """
    pt = get_plane_type(db, pt_id)
    if not pt:
        return False
    if _has_region_plane_reference(db, pt_id):
        raise BusinessError("该网络平面类型已被 Region 使用，不能删除")
    child_count = count_children_for_plane_type(db, pt_id)
    if child_count > 0:
        raise BusinessError(f"该网络平面类型存在 {child_count} 个子类型，不能删除")
    log_change(
        db,
        entity_type="network_plane_type",
        entity_id=pt_id,
        entity_name=pt.name,
        action="delete",
        operator=operator,
        old_value=pt.name,
    )
    db.delete(pt)
    db.flush()
    return True


def _has_region_plane_reference(db: Session, plane_type_id: str) -> bool:
    """判断网络平面类型是否已被 Region 启用。"""
    return db.query(RegionNetworkPlane.id).filter(RegionNetworkPlane.plane_type_id == plane_type_id).first() is not None


def _validate_parent_assignment(
    db: Session, target_id: Optional[str], parent_id: Optional[str]
) -> NetworkPlaneType | None:
    """校验目标类型设置父级是否合法，防止循环引用及超出最大层级限制。"""
    if parent_id is None:
        if target_id:
            _ensure_descendant_depths_within_limit(db, target_id, parent_depth=-1)
        return None
    if target_id and parent_id == target_id:
        raise BusinessError("网络平面类型不能将自身设为父级")
    parent = get_plane_type(db, parent_id)
    if not parent:
        raise BusinessError("父级网络平面类型不存在")
    if target_id and _is_descendant(db, candidate_id=parent_id, ancestor_id=target_id):
        raise BusinessError("网络平面类型不能移动到自己的子级下")
    parent_depth = _get_type_depth(db, parent)
    if parent_depth >= MAX_PLANE_TYPE_DEPTH:
        raise BusinessError("已达到最大嵌套层级限制（3级）")
    if target_id:
        _ensure_descendant_depths_within_limit(db, target_id, parent_depth=parent_depth)
    return parent


def _resolve_inherited_privacy(db: Session, pt: NetworkPlaneType, data: PlaneTypeUpdate) -> bool:
    """按父级继承规则计算目标类型最终私网属性。"""
    if pt.parent:
        return pt.parent.is_private
    if pt.parent_id:
        parent = db.get(NetworkPlaneType, pt.parent_id)
        if parent:
            return parent.is_private
    if data.is_private is not None:
        return data.is_private
    return pt.is_private


def _ensure_privacy_matches_parent(parent: NetworkPlaneType | None, is_private: bool) -> None:
    """确保子类型请求的私网属性与父类型一致。"""
    if parent and parent.is_private != is_private:
        raise BusinessError("子级网络平面类型的私网/公网属性必须与父级一致")


def _format_parent_name(parent: NetworkPlaneType | None) -> str:
    """将父级类型对象转成审计日志中面向用户的名称。"""
    return parent.name if parent else "无"


def _sync_descendant_privacy(db: Session, pt: NetworkPlaneType, is_private: bool, operator: str) -> None:
    """同步指定类型所有后代的私网属性，保持整棵类型子树一致。"""
    for child in _collect_type_descendants(db, pt.id):
        if child.is_private == is_private:
            continue
        log_change(
            db,
            entity_type="network_plane_type",
            entity_id=child.id,
            entity_name=child.name,
            action="update",
            field_name="is_private",
            old_value=str(child.is_private),
            new_value=str(is_private),
            operator=operator,
        )
        child.is_private = is_private


def _get_type_depth(db: Session, plane_type: NetworkPlaneType) -> int:
    """计算指定网络平面类型相对于根节点的深度（0-based）。"""
    depth = 0
    current = plane_type
    visited = {current.id}
    while current.parent_id:
        parent = db.get(NetworkPlaneType, current.parent_id)
        if not parent or parent.id in visited:
            break
        visited.add(parent.id)
        depth += 1
        current = parent
    return depth


def _is_descendant(db: Session, candidate_id: str, ancestor_id: str) -> bool:
    """判断 candidate_id 是否为 ancestor_id 的后代节点。"""
    current = db.get(NetworkPlaneType, candidate_id)
    visited: set[str] = set()
    while current and current.parent_id and current.id not in visited:
        visited.add(current.id)
        if current.parent_id == ancestor_id:
            return True
        current = db.get(NetworkPlaneType, current.parent_id)
    return False


def _ensure_descendant_depths_within_limit(db: Session, target_id: str, parent_depth: int) -> None:
    """确保 target_id 及其所有后代在挂到指定父深度下后，不会超过最大层级限制。"""
    descendants = _collect_type_descendant_depths(db, target_id, relative_depth=1)
    new_target_depth = parent_depth + 1
    if descendants and max(new_target_depth + relative_depth for relative_depth in descendants) > MAX_PLANE_TYPE_DEPTH:
        raise BusinessError("移动后会超过最大嵌套层级限制（3级）")


def _collect_type_descendant_depths(db: Session, plane_type_id: str, relative_depth: int) -> list[int]:
    """递归收集指定类型所有后代相对于该类型的深度列表。"""
    result: list[int] = []
    children = db.query(NetworkPlaneType).filter(NetworkPlaneType.parent_id == plane_type_id).all()
    for child in children:
        result.append(relative_depth)
        result.extend(_collect_type_descendant_depths(db, child.id, relative_depth + 1))
    return result


def _count_regions_for_type_and_descendants(db: Session, plane_type_id: str) -> int:
    """统计指定类型及其所有后代被 RegionNetworkPlane 引用的总次数。"""
    type_ids = [plane_type_id] + [child.id for child in _collect_type_descendants(db, plane_type_id)]
    return (
        db.query(func.count(RegionNetworkPlane.id)).filter(RegionNetworkPlane.plane_type_id.in_(type_ids)).scalar() or 0
    )


def _collect_type_descendants(db: Session, plane_type_id: str) -> list[NetworkPlaneType]:
    """递归收集指定类型的所有后代节点。"""
    result: list[NetworkPlaneType] = []
    children = db.query(NetworkPlaneType).filter(NetworkPlaneType.parent_id == plane_type_id).all()
    for child in children:
        result.append(child)
        result.extend(_collect_type_descendants(db, child.id))
    return result
