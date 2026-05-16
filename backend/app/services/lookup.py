"""IP/CIDR 查询服务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import BusinessError
from app.models.network_plane_type import NetworkPlaneType
from app.models.region import Region
from app.models.region_network_plane import RegionNetworkPlane
from app.schemas.lookup import LookupResult
from app.utils.ip_utils import check_overlap, ip_belongs_to_network, parse_cidr, parse_ip

DEFAULT_PLANE_SCOPE = "Global"


def lookup_region_planes(db: Session, q: str, exact: bool = True) -> tuple[list[LookupResult], int]:
    """按 IP 地址或 CIDR 查询 Region 网络平面。

    Args:
        db: 数据库会话。
        q: 查询字符串。可以是 IP 地址（如 10.0.0.5）或 CIDR（如 10.0.0.0/24）。
        exact: 是否精确匹配。True 只返回完全匹配的 CIDR，
               False 则返回所有与查询重叠的记录。

    Returns:
        树形查询结果，以及真正命中的网络平面数量。

    Raises:
        BusinessError: q 不是合法的 IP 或 CIDR 格式。
    """
    ip = parse_ip(q)
    net = parse_cidr(q) if not ip else None
    if not ip and not net:
        raise BusinessError(f"Invalid IP address or CIDR: {q}")

    planes = (
        db.query(RegionNetworkPlane)
        .join(Region, RegionNetworkPlane.region_id == Region.id)
        .join(NetworkPlaneType, RegionNetworkPlane.plane_type_id == NetworkPlaneType.id)
        .filter(RegionNetworkPlane.cidr.isnot(None))
        .order_by(
            Region.name.asc(),
            NetworkPlaneType.name.asc(),
            RegionNetworkPlane.scope.asc(),
            RegionNetworkPlane.cidr.asc(),
        )
        .all()
    )
    matched_planes: list[RegionNetworkPlane] = []

    if ip:
        for plane in planes:
            existing = parse_cidr(plane.cidr or "")
            if existing and ip_belongs_to_network(ip, existing):
                matched_planes.append(plane)
    elif net:
        if exact:
            for plane in planes:
                existing = parse_cidr(plane.cidr or "")
                if existing and existing == net:
                    matched_planes.append(plane)
        else:
            for plane in planes:
                existing = parse_cidr(plane.cidr or "")
                if existing and check_overlap(existing, net):
                    matched_planes.append(plane)

    return _build_lookup_tree(planes, matched_planes), len(matched_planes)


def _build_lookup_tree(
    planes: list[RegionNetworkPlane], matched_planes: list[RegionNetworkPlane]
) -> list[LookupResult]:
    """将命中平面和父级上下文拼装为树形结构。"""
    matched_ids = {plane.id for plane in matched_planes}
    display_ids = set(matched_ids)
    plane_by_type_scope = {(plane.region_id, plane.plane_type_id, plane.scope): plane for plane in planes}

    for plane in matched_planes:
        parent_plane = _find_parent_plane(plane, plane_by_type_scope)
        while parent_plane:
            display_ids.add(parent_plane.id)
            parent_plane = _find_parent_plane(parent_plane, plane_by_type_scope)

    node_by_id: dict[str, LookupResult] = {}
    for plane in planes:
        if plane.id in display_ids:
            node_by_id[plane.id] = _to_lookup_node(plane, is_match=plane.id in matched_ids)

    roots: list[LookupResult] = []
    for plane in planes:
        node = node_by_id.get(plane.id)
        if not node:
            continue
        parent_plane = _find_parent_plane(plane, plane_by_type_scope)
        if parent_plane and parent_plane.id in node_by_id:
            _attach_tree_child_node(node_by_id[parent_plane.id], node)
        else:
            roots.append(node)
    return roots


def _attach_tree_child_node(parent: LookupResult, child: LookupResult) -> None:
    """挂载树形响应子节点，并保持 parent_id 与 children 关系一致。"""
    child.parent_id = parent.id
    parent.children.append(child)


def _find_parent_plane(
    plane: RegionNetworkPlane,
    plane_by_type_scope: dict[tuple[str, str, str], RegionNetworkPlane],
) -> RegionNetworkPlane | None:
    """按同作用域优先、Global 兜底规则查找当前平面的父级实例。"""
    parent_type_id = plane.plane_type.parent_id if plane.plane_type else None
    if not parent_type_id:
        return None

    parent_plane = plane_by_type_scope.get((plane.region_id, parent_type_id, plane.scope))
    if not parent_plane and plane.scope != DEFAULT_PLANE_SCOPE:
        parent_plane = plane_by_type_scope.get((plane.region_id, parent_type_id, DEFAULT_PLANE_SCOPE))
    return parent_plane


def _to_lookup_node(plane: RegionNetworkPlane, *, is_match: bool) -> LookupResult:
    """转换为 IP/CIDR 查询响应节点。"""
    return LookupResult(
        id=plane.id,
        cidr=plane.cidr or "",
        region_name=plane.region.name if plane.region else "",
        plane_type_name=plane.plane_type.name if plane.plane_type else "",
        scope=plane.scope,
        vlan_id=plane.vlan_id,
        gateway_position=plane.gateway_position,
        gateway_ip=plane.gateway_ip,
        parent_id=None,
        plane_type_parent_id=plane.plane_type.parent_id if plane.plane_type else None,
        is_match=is_match,
    )
