from __future__ import annotations

import ipaddress
from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import BusinessError
from app.models.network_plane_type import NetworkPlaneType
from app.models.region_network_plane import RegionNetworkPlane
from app.services.change_log import log_change
from app.utils.ip_utils import (
    IPNetwork,
    ip_belongs_to_network,
    network_is_subnet_of,
    parse_cidr,
    parse_ip,
)
from app.utils.time_utils import format_datetime

DEFAULT_PLANE_SCOPE = "Global"


def get_region_plane_tree(db: Session, region_id: str) -> list[dict[str, Any]]:
    """获取 Region 下所有网络平面的树形结构。

    返回嵌套的树形列表，树结构来自全局 NetworkPlaneType.parent_id，
    RegionNetworkPlane 只提供当前 Region 的启用状态和 CIDR。

    Args:
        db: 数据库会话。
        region_id: Region ID。

    Returns:
        树形结构列表，每个节点包含 id、plane_type_id、cidr、
        parent_id、children 等字段。
    """
    all_planes = (
        db.query(RegionNetworkPlane)
        .join(NetworkPlaneType, RegionNetworkPlane.plane_type_id == NetworkPlaneType.id)
        .filter(RegionNetworkPlane.region_id == region_id)
        .order_by(
            NetworkPlaneType.name.asc(),
            RegionNetworkPlane.scope.asc(),
            RegionNetworkPlane.cidr.asc(),
        )
        .all()
    )

    # 构建内存字典，方便 O(1) 查找和拼装树
    plane_dict: dict[str, dict[str, Any]] = {}
    plane_by_type_scope = {(p.plane_type_id, p.scope): p for p in all_planes}
    for p in all_planes:
        plane_dict[p.id] = {
            "id": p.id,
            "region_id": p.region_id,
            "plane_type_id": p.plane_type_id,
            "plane_type_name": p.plane_type.name if p.plane_type else "",
            "scope": p.scope,
            "cidr": p.cidr,
            "vlan_id": p.vlan_id,
            "gateway_position": p.gateway_position,
            "gateway_ip": p.gateway_ip,
            "parent_id": None,
            "plane_type_parent_id": p.plane_type.parent_id if p.plane_type else None,
            "created_at": format_datetime(p.created_at),
            "updated_at": format_datetime(p.updated_at),
            "children": [],
        }

    # 拼装树：将子节点挂到同 Region 中已启用的父类型节点下
    roots = []
    for plane in all_planes:
        node = plane_dict[plane.id]
        type_parent_id = plane.plane_type.parent_id if plane.plane_type else None
        parent_plane = None
        if type_parent_id:
            parent_plane = plane_by_type_scope.get((type_parent_id, plane.scope))
            if not parent_plane and plane.scope != DEFAULT_PLANE_SCOPE:
                parent_plane = plane_by_type_scope.get((type_parent_id, DEFAULT_PLANE_SCOPE))
        if parent_plane and parent_plane.id in plane_dict:
            node["parent_id"] = parent_plane.id
            plane_dict[parent_plane.id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def enable_plane_for_region(
    db: Session,
    region_id: str,
    plane_type_id: str,
    cidr: str,
    operator: str,
    *,
    scope: str = DEFAULT_PLANE_SCOPE,
    vlan_id: int | None = None,
    gateway_position: str | None = None,
    gateway_ip: str | None = None,
) -> tuple[RegionNetworkPlane, str | None]:
    """为 Region 启用一个网络平面类型。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        plane_type_id: 网络平面类型 ID。
        cidr: 根平面的 CIDR 范围。
        operator: 操作者名称。
        scope: 作用域，空值调用方应归一化为 Global。
        vlan_id: VLAN ID，可选。
        gateway_position: 网关位置，可选。
        gateway_ip: 网关 IP 地址，可选。

    Returns:
        新创建的 RegionNetworkPlane 对象和可选弱校验提示。

    Raises:
        BusinessError: 该类型已启用、CIDR 格式无效、父级未启用或 CIDR 越界。
    """
    pt = db.query(NetworkPlaneType).filter(NetworkPlaneType.id == plane_type_id).first()
    if not pt:
        raise BusinessError("网络平面类型不存在")
    scope = normalize_plane_scope(scope)

    existing = (
        db.query(RegionNetworkPlane)
        .filter(
            RegionNetworkPlane.region_id == region_id,
            RegionNetworkPlane.plane_type_id == plane_type_id,
            RegionNetworkPlane.scope == scope,
        )
        .first()
    )
    if existing:
        raise BusinessError(f"该网络平面类型已在 Region 的 {scope} 作用域中启用，不能重复创建")

    gateway_ip_warning = _validate_plane_assignment(
        db,
        region_id=region_id,
        plane_type=pt,
        scope=scope,
        cidr=cidr,
        vlan_id=vlan_id,
        gateway_ip=gateway_ip,
    )

    rp = RegionNetworkPlane(
        region_id=region_id,
        plane_type_id=plane_type_id,
        scope=scope,
        cidr=cidr,
        vlan_id=vlan_id,
        gateway_position=gateway_position or None,
        gateway_ip=gateway_ip or None,
    )
    db.add(rp)
    db.flush()

    log_change(
        db,
        entity_type="region_network_plane",
        entity_id=rp.id,
        action="create",
        operator=operator,
        new_value=(
            f"region={region_id}, plane_type={pt.name}, cidr={cidr}, "
            f"scope={scope}, vlan_id={vlan_id or ''}, "
            f"gateway_position={gateway_position or ''}, gateway_ip={gateway_ip or ''}"
        ),
    )
    return rp, gateway_ip_warning


def create_child_plane(db: Session, region_id: str, parent_id: str, cidr: str, operator: str) -> RegionNetworkPlane:
    """兼容旧接口：子平面关系现在由 NetworkPlaneType.parent_id 维护。"""
    raise BusinessError("子平面关系由网络平面类型维护，请启用对应的子级网络平面类型")


def update_plane_for_region(
    db: Session,
    region_id: str,
    plane_id: str,
    operator: str,
    *,
    scope: str | None = None,
    cidr: str | None = None,
    vlan_id: int | None = None,
    gateway_position: str | None = None,
    gateway_ip: str | None = None,
) -> tuple[RegionNetworkPlane | None, str | None]:
    """更新 Region 网络平面实例，不允许修改网络平面类型。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        plane_id: 要更新的 Region 网络平面 ID。
        operator: 操作者名称。
        scope: 新作用域，None 表示保持不变。
        cidr: 新 CIDR，None 表示保持不变。
        vlan_id: 新 VLAN ID，None 表示清空或保持由调用方决定。
        gateway_position: 新网关位置。
        gateway_ip: 新网关 IP。

    Returns:
        更新后的 RegionNetworkPlane 对象和可选弱校验提示；不存在时返回 (None, None)。

    Raises:
        BusinessError: 更新后的唯一性、CIDR、父子范围或网关 IP 校验不通过。
    """
    plane = (
        db.query(RegionNetworkPlane)
        .filter(
            RegionNetworkPlane.id == plane_id,
            RegionNetworkPlane.region_id == region_id,
        )
        .first()
    )
    if not plane:
        return None, None
    if not plane.plane_type:
        raise BusinessError("网络平面类型不存在")

    new_scope = normalize_plane_scope(scope if scope is not None else plane.scope)
    new_cidr = cidr if cidr is not None else plane.cidr
    if not new_cidr:
        raise BusinessError("CIDR 不能为空")

    existing = (
        db.query(RegionNetworkPlane)
        .filter(
            RegionNetworkPlane.region_id == region_id,
            RegionNetworkPlane.plane_type_id == plane.plane_type_id,
            RegionNetworkPlane.scope == new_scope,
            RegionNetworkPlane.id != plane_id,
        )
        .first()
    )
    if existing:
        raise BusinessError(f"该网络平面类型已在 Region 的 {new_scope} 作用域中启用，不能重复创建")

    gateway_ip_warning = _validate_plane_assignment(
        db,
        region_id=region_id,
        plane_type=plane.plane_type,
        scope=new_scope,
        cidr=new_cidr,
        vlan_id=vlan_id,
        gateway_ip=gateway_ip,
        current_plane=plane,
    )

    changes: dict[str, tuple[str, str]] = {}
    if new_scope != plane.scope:
        changes["scope"] = (plane.scope, new_scope)
        plane.scope = new_scope
    if new_cidr != plane.cidr:
        changes["cidr"] = (plane.cidr or "", new_cidr)
        plane.cidr = new_cidr
    if vlan_id != plane.vlan_id:
        changes["vlan_id"] = (str(plane.vlan_id or ""), str(vlan_id or ""))
        plane.vlan_id = vlan_id
    if (gateway_position or None) != plane.gateway_position:
        changes["gateway_position"] = (plane.gateway_position or "", gateway_position or "")
        plane.gateway_position = gateway_position or None
    if (gateway_ip or None) != plane.gateway_ip:
        changes["gateway_ip"] = (plane.gateway_ip or "", gateway_ip or "")
        plane.gateway_ip = gateway_ip or None

    if changes:
        for field, (old, new) in changes.items():
            log_change(
                db,
                entity_type="region_network_plane",
                entity_id=plane_id,
                action="update",
                field_name=field,
                old_value=old,
                new_value=new,
                operator=operator,
            )
        db.flush()
    return plane, gateway_ip_warning


def disable_plane_for_region(db: Session, region_id: str, plane_id: str, operator: str) -> bool:
    """删除平面节点，级联删除所有已启用的子类型平面。

    删除前手动记录所有受影响实体的审计日志。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        plane_id: 要删除的平面节点 ID。
        operator: 操作者名称。

    Returns:
        删除成功返回 True，不存在时返回 False。
    """
    plane = (
        db.query(RegionNetworkPlane)
        .filter(
            RegionNetworkPlane.id == plane_id,
            RegionNetworkPlane.region_id == region_id,
        )
        .first()
    )
    if not plane:
        return False

    # 递归收集所有子代平面 ID（用于审计日志）
    descendant_ids = _collect_descendant_ids(db, plane)

    # 审计日志：记录被级联删除的子平面
    for child_id in descendant_ids:
        cp = db.get(RegionNetworkPlane, child_id)
        log_change(
            db,
            entity_type="region_network_plane",
            entity_id=child_id,
            action="delete",
            operator=operator,
            old_value=f"由父平面 {plane_id} 删除级联触发, cidr={cp.cidr if cp else ''}",
        )

    # 审计日志：记录本平面删除
    pt_name = plane.plane_type.name if plane.plane_type else "unknown"
    log_change(
        db,
        entity_type="region_network_plane",
        entity_id=plane_id,
        action="delete",
        operator=operator,
        old_value=f"region={region_id}, plane_type={pt_name}, scope={plane.scope}, cidr={plane.cidr}",
    )

    for child_id in reversed(descendant_ids):
        child = db.get(RegionNetworkPlane, child_id)
        if child:
            db.delete(child)
    db.delete(plane)
    db.flush()
    return True


def _collect_descendant_ids(db: Session, plane: RegionNetworkPlane) -> list[str]:
    """递归收集所有后代平面 ID（深度优先）。"""
    result: list[str] = []
    child_candidates = (
        db.query(RegionNetworkPlane)
        .join(NetworkPlaneType, RegionNetworkPlane.plane_type_id == NetworkPlaneType.id)
        .filter(
            RegionNetworkPlane.region_id == plane.region_id,
            NetworkPlaneType.parent_id == plane.plane_type_id,
        )
        .all()
    )
    for child in child_candidates:
        if not _is_effective_parent(db, parent=plane, child=child):
            continue
        result.append(child.id)
        result.extend(_collect_descendant_ids(db, child))
    return result


def _is_effective_parent(db: Session, *, parent: RegionNetworkPlane, child: RegionNetworkPlane) -> bool:
    if child.scope == parent.scope:
        return True
    if parent.scope != DEFAULT_PLANE_SCOPE:
        return False
    same_scope_parent = (
        db.query(RegionNetworkPlane.id)
        .filter(
            RegionNetworkPlane.region_id == child.region_id,
            RegionNetworkPlane.plane_type_id == parent.plane_type_id,
            RegionNetworkPlane.scope == child.scope,
        )
        .first()
    )
    return same_scope_parent is None


def _validate_plane_assignment(
    db: Session,
    *,
    region_id: str,
    plane_type: NetworkPlaneType,
    scope: str,
    cidr: str,
    vlan_id: int | None,
    gateway_ip: str | None,
    current_plane: RegionNetworkPlane | None = None,
) -> str | None:
    """校验 Region 网络平面的 CIDR、VLAN 和网关信息。"""
    net = parse_cidr(cidr)
    if not net:
        raise BusinessError(f"无效的 CIDR 格式: {cidr}")

    _validate_vlan_unique_in_region(
        db,
        region_id,
        vlan_id,
        exclude_plane_id=current_plane.id if current_plane else None,
    )

    related_plane_ids = _collect_effective_ancestor_ids(db, region_id, plane_type, scope)
    if current_plane:
        related_plane_ids.append(current_plane.id)
        related_plane_ids.extend(_collect_descendant_ids(db, current_plane))
        _ensure_descendants_within_cidr(db, current_plane, net, cidr)

    overlaps = _find_overlapping_region_planes(db, cidr, exclude_plane_ids=set(related_plane_ids))
    if overlaps:
        same_region = [plane for plane in overlaps if plane.region_id == region_id]
        other_region = [plane for plane in overlaps if plane.region_id != region_id]
        messages = []
        if same_region:
            messages.append(f"与本 Region 非层级关系网络平面 CIDR 重叠：{_format_plane_refs(same_region)}")
        if other_region:
            messages.append(f"与其他 Region 网络平面 CIDR 重叠：{_format_plane_refs(other_region)}")
        raise BusinessError("；".join(messages))

    if plane_type.parent_id:
        parent_plane = _find_parent_plane(db, region_id, plane_type.parent_id, scope)
        if not parent_plane:
            raise BusinessError("父级网络平面尚未在该 Region 启用")
        if not parent_plane.cidr:
            raise BusinessError("父级网络平面没有 CIDR 范围，无法启用或更新子平面")
        parent_net = parse_cidr(parent_plane.cidr)
        if not parent_net:
            raise BusinessError("父级网络平面 CIDR 格式无效")
        if not network_is_subnet_of(net, parent_net):
            raise BusinessError(f"子平面 CIDR {cidr} 必须在父平面 CIDR {parent_plane.cidr} 范围内")

    return _validate_gateway_ip_policy(net, gateway_ip, is_private=plane_type.is_private)


def _validate_vlan_unique_in_region(
    db: Session,
    region_id: str,
    vlan_id: int | None,
    *,
    exclude_plane_id: str | None = None,
) -> None:
    if vlan_id is None:
        return
    existing = (
        db.query(RegionNetworkPlane)
        .filter(
            RegionNetworkPlane.region_id == region_id,
            RegionNetworkPlane.vlan_id == vlan_id,
            RegionNetworkPlane.id != exclude_plane_id,
        )
        .first()
    )
    if existing:
        raise BusinessError(f"VLAN {vlan_id} 已在该 Region 中使用：{_format_plane_ref(existing)}")


def _collect_effective_ancestor_ids(
    db: Session,
    region_id: str,
    plane_type: NetworkPlaneType,
    scope: str,
) -> list[str]:
    ancestor_ids: list[str] = []
    parent_type_id = plane_type.parent_id
    current_scope = scope
    while parent_type_id:
        parent_plane = _find_parent_plane(db, region_id, parent_type_id, current_scope)
        if not parent_plane:
            break
        ancestor_ids.append(parent_plane.id)
        parent_type_id = parent_plane.plane_type.parent_id if parent_plane.plane_type else None
        current_scope = parent_plane.scope
    return ancestor_ids


def _ensure_descendants_within_cidr(
    db: Session,
    plane: RegionNetworkPlane,
    net: IPNetwork,
    cidr: str,
) -> None:
    for child_id in _collect_descendant_ids(db, plane):
        child = db.get(RegionNetworkPlane, child_id)
        if not child or not child.cidr:
            continue
        child_net = parse_cidr(child.cidr)
        if child_net and not network_is_subnet_of(child_net, net):
            raise BusinessError(f"子平面 CIDR {child.cidr} 必须在父平面 CIDR {cidr} 范围内")


def _find_overlapping_region_planes(
    db: Session,
    cidr: str,
    *,
    exclude_plane_ids: set[str],
) -> list[RegionNetworkPlane]:
    net = parse_cidr(cidr)
    if not net:
        return []
    rows = db.query(RegionNetworkPlane).filter(RegionNetworkPlane.cidr.isnot(None)).all()
    overlapped = []
    for plane in rows:
        if plane.id in exclude_plane_ids or not plane.cidr:
            continue
        other_net = parse_cidr(plane.cidr)
        if other_net and other_net.version == net.version and other_net.overlaps(net):
            overlapped.append(plane)
    return overlapped


def _format_plane_refs(planes: list[RegionNetworkPlane]) -> str:
    return "；".join(_format_plane_ref(plane) for plane in planes)


def _format_plane_ref(plane: RegionNetworkPlane) -> str:
    region_name = plane.region.name if plane.region else plane.region_id
    plane_type_name = plane.plane_type.name if plane.plane_type else plane.plane_type_id
    vlan_text = f", VLAN={plane.vlan_id}" if plane.vlan_id is not None else ""
    return f"Region={region_name}, 网络平面={plane_type_name}, 作用域={plane.scope}, CIDR={plane.cidr}{vlan_text}"


def _find_parent_plane(
    db: Session,
    region_id: str,
    parent_type_id: str,
    scope: str,
) -> RegionNetworkPlane | None:
    parent_plane = (
        db.query(RegionNetworkPlane)
        .filter(
            RegionNetworkPlane.region_id == region_id,
            RegionNetworkPlane.plane_type_id == parent_type_id,
            RegionNetworkPlane.scope == scope,
        )
        .first()
    )
    if not parent_plane and scope != DEFAULT_PLANE_SCOPE:
        parent_plane = (
            db.query(RegionNetworkPlane)
            .filter(
                RegionNetworkPlane.region_id == region_id,
                RegionNetworkPlane.plane_type_id == parent_type_id,
                RegionNetworkPlane.scope == DEFAULT_PLANE_SCOPE,
            )
            .first()
        )
    return parent_plane


def normalize_plane_scope(scope: str | None) -> str:
    """归一化 Region 网络平面作用域，空值统一为 Global。"""
    if scope is None:
        return DEFAULT_PLANE_SCOPE
    scope = scope.strip()
    return scope or DEFAULT_PLANE_SCOPE


def _validate_gateway_ip_policy(net: IPNetwork, gateway_ip: str | None, *, is_private: bool) -> str | None:
    """强校验网关 IP 在 CIDR 内，弱校验网关 IP 是否符合推荐位置。"""
    if not gateway_ip:
        return None
    ip = parse_ip(gateway_ip)
    if not ip:
        raise BusinessError(f"无效的网关 IP 地址: {gateway_ip}")
    if not ip_belongs_to_network(ip, net):
        if ip.version != net.version:
            raise BusinessError(f"网关 IP {gateway_ip} 必须与平面 CIDR {net.with_prefixlen} 使用相同 IP 版本")
        raise BusinessError(f"网关 IP {gateway_ip} 必须在平面 CIDR {net.with_prefixlen} 范围内")

    expected = _expected_gateway_ip(net, is_private=is_private)
    if ip != expected:
        position = "第一个可用 IP" if is_private else "最后一个可用 IP"
        plane_scope = "私网" if is_private else "非私网"
        return f"当前网关 IP 不符合推荐规则：{plane_scope}平面建议使用 CIDR 内{position} {expected}"
    return None


def _expected_gateway_ip(net: IPNetwork, *, is_private: bool) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    if net.num_addresses == 1:
        return net.network_address
    if is_private:
        if isinstance(net, ipaddress.IPv4Network) and net.prefixlen < 31:
            return net.network_address + 1
        if isinstance(net, ipaddress.IPv6Network) and net.prefixlen < 127:
            return net.network_address + 1
        return net.network_address
    if isinstance(net, ipaddress.IPv4Network):
        if net.prefixlen < 31:
            return net.broadcast_address - 1
        return net.broadcast_address
    return net.network_address + net.num_addresses - 1
