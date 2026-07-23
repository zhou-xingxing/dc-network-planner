from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.network_plane_type import NetworkPlaneType
from app.models.region import Region
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


@dataclass(frozen=True)
class RegionPlaneMutationResult:
    """Region 平面变更结果及响应所需上下文。"""

    plane: RegionNetworkPlane
    gateway_ip_warning: str | None
    parent_plane_id: str | None


@dataclass(frozen=True)
class AssignmentValidationContext:
    """Region 平面写入校验后可复用的上下文。"""

    gateway_ip_warning: str | None
    parent_plane_id: str | None


@dataclass(frozen=True)
class ParentPlaneContext:
    """写入网络平面前解析出的直接父平面上下文。"""

    requested_scope: str
    parent_type: NetworkPlaneType | None
    parent_plane: RegionNetworkPlane | None


def get_region_plane_tree(db: Session, region_id: str) -> list[dict[str, Any]]:
    """获取 Region 下所有网络平面的树形结构。

    返回嵌套的树形列表，树结构来自全局 NetworkPlaneType.parent_id，
    RegionNetworkPlane 只提供当前 Region 的网络平面实例和 CIDR。

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

    # 拼装树：将子节点挂到同 Region 中已创建的父类型节点下
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


def get_region_plane_tree_for_region(db: Session, region_id: str) -> list[dict[str, Any]] | None:
    """查询指定 Region 的网络平面树，Region 不存在时返回 None。"""
    region = db.get(Region, region_id)
    if not region:
        return None
    return get_region_plane_tree(db, region_id)


def get_parent_plane_context(
    db: Session,
    region_id: str,
    plane_type_id: str,
    scope: str | None = DEFAULT_PLANE_SCOPE,
) -> ParentPlaneContext:
    """解析创建或编辑网络平面时实际生效的直接父平面实例。

    父实例与写入校验使用相同规则：优先匹配同作用域实例，未命中时
    回退到 Global。根类型返回空父级上下文，子类型未找到实例时保留
    父类型信息供前端展示。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        plane_type_id: 待创建的网络平面类型 ID。
        scope: 待创建实例的作用域。

    Returns:
        已归一化作用域、直接父类型和实际生效父实例组成的上下文。

    Raises:
        ResourceNotFoundError: Region、网络平面类型或其父类型不存在。
    """
    if not db.get(Region, region_id):
        raise ResourceNotFoundError("Region 不存在")
    plane_type = db.get(NetworkPlaneType, plane_type_id)
    if not plane_type:
        raise ResourceNotFoundError("网络平面类型不存在")

    normalized_scope = normalize_plane_scope(scope)
    if not plane_type.parent_id:
        return ParentPlaneContext(normalized_scope, None, None)

    parent_type = db.get(NetworkPlaneType, plane_type.parent_id)
    if not parent_type:
        raise ResourceNotFoundError("父级网络平面类型不存在")
    parent_plane = _find_parent_plane(db, region_id, parent_type.id, normalized_scope)
    return ParentPlaneContext(normalized_scope, parent_type, parent_plane)


def create_plane_for_region(
    db: Session,
    region_id: str,
    plane_type_id: str,
    cidr: str,
    operator: str,
    *,
    scope: str | None = DEFAULT_PLANE_SCOPE,
    vlan_id: int | None = None,
    gateway_position: str | None = None,
    gateway_ip: str | None = None,
) -> RegionPlaneMutationResult:
    """为 Region 创建一个网络平面实例。

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
        新创建的 RegionNetworkPlane 对象及响应上下文。

    Raises:
        BusinessError: 该类型已创建、CIDR 格式无效、父级不存在或 CIDR 越界。
    """
    validated_net, validated_gateway_ip = _validate_network_format(cidr, gateway_ip)

    region = db.get(Region, region_id)
    if not region:
        raise ResourceNotFoundError("Region 不存在")
    pt = db.query(NetworkPlaneType).filter(NetworkPlaneType.id == plane_type_id).first()
    if not pt:
        raise ResourceNotFoundError("网络平面类型不存在")
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
        raise BusinessError(f"该网络平面类型已在本Region 的 {scope} 作用域中创建，不能重复创建")

    assignment_context = _validate_plane_assignment(
        db,
        region_id=region_id,
        plane_type=pt,
        scope=scope,
        cidr=cidr,
        vlan_id=vlan_id,
        gateway_ip=gateway_ip,
        validated_cidr=validated_net,
        validated_gateway_ip=validated_gateway_ip,
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
        entity_name=_format_plane_ref(rp),
        action="create",
        operator=operator,
        new_value=(
            f"region={region.name}, plane_type={pt.name}, cidr={cidr}, "
            f"scope={scope}, vlan_id={vlan_id or ''}, "
            f"gateway_position={gateway_position or ''}, gateway_ip={gateway_ip or ''}"
        ),
    )
    return RegionPlaneMutationResult(
        plane=rp,
        gateway_ip_warning=assignment_context.gateway_ip_warning,
        parent_plane_id=assignment_context.parent_plane_id,
    )


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
) -> RegionPlaneMutationResult | None:
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
        更新后的 RegionNetworkPlane 对象及响应上下文；不存在时返回 None。

    Raises:
        BusinessError: 更新后的唯一性、CIDR、父子范围或网关 IP 校验不通过。
    """
    validated_net: IPNetwork | None = None
    validated_gateway_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    if cidr is not None:
        validated_net, validated_gateway_ip = _validate_network_format(cidr, gateway_ip)

    plane = (
        db.query(RegionNetworkPlane)
        .filter(
            RegionNetworkPlane.id == plane_id,
            RegionNetworkPlane.region_id == region_id,
        )
        .first()
    )
    if not plane:
        return None
    if not plane.plane_type:
        raise BusinessError("网络平面类型不存在")
    entity_name = _format_plane_ref(plane)

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
        raise BusinessError(f"该网络平面类型已在本Region 的 {new_scope} 作用域中创建，不能重复创建")

    assignment_context = _validate_plane_assignment(
        db,
        region_id=region_id,
        plane_type=plane.plane_type,
        scope=new_scope,
        cidr=new_cidr,
        vlan_id=vlan_id,
        gateway_ip=gateway_ip,
        current_plane=plane,
        validated_cidr=validated_net,
        validated_gateway_ip=validated_gateway_ip,
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
                entity_name=entity_name,
                action="update",
                field_name=field,
                old_value=old,
                new_value=new,
                operator=operator,
            )
        db.flush()
    return RegionPlaneMutationResult(
        plane=plane,
        gateway_ip_warning=assignment_context.gateway_ip_warning,
        parent_plane_id=assignment_context.parent_plane_id,
    )


def serialize_region_plane_result(result: RegionPlaneMutationResult) -> dict[str, Any]:
    """序列化 Region 网络平面变更结果。"""
    plane = result.plane
    plane_type = plane.plane_type
    return {
        "id": plane.id,
        "region_id": plane.region_id,
        "plane_type_id": plane.plane_type_id,
        "plane_type_name": plane_type.name if plane_type else "",
        "scope": plane.scope,
        "cidr": plane.cidr,
        "vlan_id": plane.vlan_id,
        "gateway_position": plane.gateway_position,
        "gateway_ip": plane.gateway_ip,
        "gateway_ip_warning": result.gateway_ip_warning,
        "parent_id": result.parent_plane_id,
        "plane_type_parent_id": plane_type.parent_id if plane_type else None,
        "created_at": format_datetime(plane.created_at),
        "updated_at": format_datetime(plane.updated_at),
        "children": [],
    }


def serialize_parent_plane_context(context: ParentPlaneContext) -> dict[str, Any]:
    """序列化写入网络平面所需的父平面预检上下文。"""
    parent_type = context.parent_type
    parent_plane = context.parent_plane
    if not parent_type:
        status = "root"
    elif parent_plane:
        status = "found"
    else:
        status = "missing"
    return {
        "status": status,
        "requested_scope": context.requested_scope,
        "parent_type_id": parent_type.id if parent_type else None,
        "parent_type_name": parent_type.name if parent_type else None,
        "parent_plane": (
            {
                "id": parent_plane.id,
                "scope": parent_plane.scope,
                "cidr": parent_plane.cidr,
                "vlan_id": parent_plane.vlan_id,
                "gateway_position": parent_plane.gateway_position,
                "gateway_ip": parent_plane.gateway_ip,
            }
            if parent_plane
            else None
        ),
    }


def delete_plane_for_region(db: Session, region_id: str, plane_id: str, operator: str) -> bool:
    """删除 Region 下的叶子平面节点。

    如果该平面存在实际挂载的子平面，则拒绝删除，要求用户先自底向上删除子平面。

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

    descendants = _collect_descendants(db, plane)
    if descendants:
        raise BusinessError(f"该平面存在 {len(descendants)} 个子平面，请先删除子平面")

    # 审计日志：记录本平面删除
    log_change(
        db,
        entity_type="region_network_plane",
        entity_id=plane_id,
        entity_name=_format_plane_ref(plane),
        action="delete",
        operator=operator,
        old_value=_format_plane_ref(plane),
    )

    db.delete(plane)
    db.flush()
    return True


def _collect_descendants(db: Session, plane: RegionNetworkPlane) -> list[RegionNetworkPlane]:
    """递归收集某个 Region 平面的实际后代实例（深度优先）。

    Region 平面实例本身不保存 parent_id，父子关系由全局网络平面类型树
    `NetworkPlaneType.parent_id` 推导；同一个父类型在不同 scope 下可能存在多个
    实例，因此需要再通过 `_is_effective_parent()` 判断 child 是否实际挂载在当前
    parent 下。
    """
    result: list[RegionNetworkPlane] = []
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
        result.append(child)
        result.extend(_collect_descendants(db, child))
    return result


def _is_effective_parent(db: Session, *, parent: RegionNetworkPlane, child: RegionNetworkPlane) -> bool:
    """判断 child 是否实际挂载在 parent 下。

    判断规则：
    1. parent 与 child 的 scope 相同，父子关系成立。
    2. parent 不是 Global 且 scope 不同，父子关系不成立。
    3. parent 是 Global，只有在 child 的 scope 下不存在对应父平面时，父子关系才成立。
    """
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
    validated_cidr: IPNetwork | None = None,
    validated_gateway_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None,
) -> AssignmentValidationContext:
    """校验 Region 网络平面的 CIDR、VLAN 和网关信息。

    校验顺序（按依赖关系排列，无依赖的优先）：
    1. CIDR 格式解析（可由调用方提前完成并传入 validated_cidr 复用结果）。
    2. 网关 IP 格式、版本、是否落在 CIDR 内（纯计算，不依赖 DB）。
    3. VLAN 是否冲突（查 DB）。
    4. CIDR 是否与同级/跨 Region 平面重叠（查 DB）。
    5. 子平面 CIDR 是否在父平面范围内（查 DB）。
    6. 网关 IP 是否符合推荐位置（纯计算，返回弱校验提示）。
    """
    if validated_cidr is None:
        validated_cidr, validated_gateway_ip = _validate_network_format(cidr, gateway_ip)
    parent_plane = _validate_assignment_context(
        db,
        region_id=region_id,
        plane_type=plane_type,
        scope=scope,
        cidr=cidr,
        net=validated_cidr,
        vlan_id=vlan_id,
        current_plane=current_plane,
    )
    gateway_ip_warning = _validate_gateway_ip_policy(
        validated_cidr, validated_gateway_ip, is_private=plane_type.is_private
    )
    return AssignmentValidationContext(
        gateway_ip_warning=gateway_ip_warning,
        parent_plane_id=parent_plane.id if parent_plane else None,
    )


def _validate_network_format(
    cidr: str, gateway_ip: str | None
) -> tuple[IPNetwork, ipaddress.IPv4Address | ipaddress.IPv6Address | None]:
    """纯输入形式校验：校验并解析 CIDR 与网关 IP。"""
    net = parse_cidr(cidr)
    if not net:
        raise BusinessError(f"无效的 CIDR 格式: {cidr}")
    ip = _validate_gateway_ip_format(net, gateway_ip)
    return net, ip


def _validate_assignment_context(
    db: Session,
    *,
    region_id: str,
    plane_type: NetworkPlaneType,
    scope: str,
    cidr: str,
    net: IPNetwork,
    vlan_id: int | None,
    current_plane: RegionNetworkPlane | None,
) -> RegionNetworkPlane | None:
    """依赖数据库与上下文的语义校验：VLAN、CIDR 重叠、父子范围。"""
    _validate_vlan_assignment_by_policy(
        db,
        region_id,
        vlan_id,
        exclude_plane_id=current_plane.id if current_plane else None,
    )

    ancestors = _collect_effective_ancestors(db, region_id, plane_type, scope)
    parent_plane = ancestors[0] if ancestors else None
    related_plane_ids = [plane.id for plane in ancestors]
    if current_plane:
        related_plane_ids.append(current_plane.id)
        descendants = _collect_descendants(db, current_plane)
        related_plane_ids.extend(child.id for child in descendants)
        _ensure_descendants_within_cidr(descendants, net, cidr)

    overlaps = _find_cidr_overlaps_for_assignment(
        db,
        cidr,
        region_id=region_id if settings.ALLOW_CIDR_OVERLAP_ACROSS_REGIONS else None,
        exclude_plane_ids=set(related_plane_ids),
    )
    if overlaps:
        same_region = [plane for plane in overlaps if plane.region_id == region_id]
        other_region = []
        if not settings.ALLOW_CIDR_OVERLAP_ACROSS_REGIONS:
            other_region = [plane for plane in overlaps if plane.region_id != region_id]
        messages = []
        if same_region:
            messages.append(f"与本 Region 非层级关系网络平面 CIDR 重叠：{_format_plane_refs(same_region)}")
        if other_region:
            messages.append(f"与其他 Region 网络平面 CIDR 重叠：{_format_plane_refs(other_region)}")
        if messages:
            raise BusinessError("；".join(messages))

    if plane_type.parent_id:
        if not parent_plane:
            raise BusinessError("父级网络平面尚未在该 Region 创建")
        if not parent_plane.cidr:
            raise BusinessError("父级网络平面没有 CIDR 范围，无法创建或更新子平面")
        parent_net = parse_cidr(parent_plane.cidr)
        if not parent_net:
            raise BusinessError("父级网络平面 CIDR 格式无效")
        if not network_is_subnet_of(net, parent_net):
            raise BusinessError(f"子平面 CIDR {cidr} 必须在父平面 CIDR {parent_plane.cidr} 范围内")
    return parent_plane


def _validate_vlan_assignment_by_policy(
    db: Session,
    region_id: str,
    vlan_id: int | None,
    *,
    exclude_plane_id: str | None = None,
) -> None:
    """写入时按当前跨 Region 策略校验 VLAN 是否重复。"""
    if vlan_id is None:
        return

    query = db.query(RegionNetworkPlane).filter(RegionNetworkPlane.vlan_id == vlan_id)
    if exclude_plane_id is not None:
        query = query.filter(RegionNetworkPlane.id != exclude_plane_id)
    if settings.ALLOW_VLAN_OVERLAP_ACROSS_REGIONS:
        query = query.filter(RegionNetworkPlane.region_id == region_id)

    existing = query.first()
    if existing:
        if existing.region_id == region_id:
            raise BusinessError(f"VLAN {vlan_id} 已在该 Region 中使用：{_format_plane_ref(existing)}")
        raise BusinessError(f"VLAN {vlan_id} 已被其他 Region 使用：{_format_plane_ref(existing)}")


def _collect_effective_ancestors(
    db: Session,
    region_id: str,
    plane_type: NetworkPlaneType,
    scope: str,
) -> list[RegionNetworkPlane]:
    ancestors: list[RegionNetworkPlane] = []
    parent_type_id = plane_type.parent_id
    current_scope = scope
    while parent_type_id:
        parent_plane = _find_parent_plane(db, region_id, parent_type_id, current_scope)
        if not parent_plane:
            break
        ancestors.append(parent_plane)
        parent_type_id = parent_plane.plane_type.parent_id if parent_plane.plane_type else None
        current_scope = parent_plane.scope
    return ancestors


def _ensure_descendants_within_cidr(
    descendants: list[RegionNetworkPlane],
    net: IPNetwork,
    cidr: str,
) -> None:
    for child in descendants:
        if not child.cidr:
            continue
        child_net = parse_cidr(child.cidr)
        if child_net and not network_is_subnet_of(child_net, net):
            raise BusinessError(f"子平面 CIDR {child.cidr} 必须在父平面 CIDR {cidr} 范围内")


def _find_cidr_overlaps_for_assignment(
    db: Session,
    cidr: str,
    *,
    region_id: str | None = None,
    exclude_plane_ids: set[str],
) -> list[RegionNetworkPlane]:
    """写入时查找与目标 CIDR 重叠的已有网络平面。"""
    net = parse_cidr(cidr)
    if not net:
        return []
    query = db.query(RegionNetworkPlane).filter(RegionNetworkPlane.cidr.isnot(None))
    if region_id is not None:
        query = query.filter(RegionNetworkPlane.region_id == region_id)
    rows = query.all()
    overlapped = []
    for plane in rows:
        if plane.id in exclude_plane_ids or not plane.cidr:
            continue
        other_net = parse_cidr(plane.cidr)
        if other_net and other_net.version == net.version and other_net.overlaps(net):
            overlapped.append(plane)
    return overlapped


def validate_network_overlap_policy_on_startup(db: Session) -> None:
    """校验当前数据库数据是否满足当前启动配置中的跨 Region 重叠策略。"""
    messages: list[str] = []
    if not settings.ALLOW_CIDR_OVERLAP_ACROSS_REGIONS:
        messages.extend(_find_startup_cross_region_cidr_violations(db))
    if not settings.ALLOW_VLAN_OVERLAP_ACROSS_REGIONS:
        messages.extend(_find_startup_cross_region_vlan_violations(db))
    if messages:
        raise BusinessError("当前数据库数据不满足网络重叠检测配置：" + "；".join(messages))


def _find_startup_cross_region_cidr_violations(db: Session) -> list[str]:
    """启动时查找已有根平面数据中的跨 Region CIDR 重叠。"""
    rows = (
        db.query(RegionNetworkPlane)
        .join(NetworkPlaneType, RegionNetworkPlane.plane_type_id == NetworkPlaneType.id)
        .filter(
            RegionNetworkPlane.cidr.isnot(None),
            NetworkPlaneType.parent_id.is_(None),
        )
        .all()
    )
    parsed_planes: list[tuple[RegionNetworkPlane, IPNetwork]] = []
    messages: list[str] = []
    for plane in rows:
        if not plane.cidr:
            continue
        net = parse_cidr(plane.cidr)
        if not net:
            messages.append(f"已有网络平面 CIDR 格式无效：{_format_plane_ref(plane)}")
            continue
        for existing_plane, existing_net in parsed_planes:
            if existing_plane.region_id == plane.region_id:
                continue
            if existing_net.version == net.version and existing_net.overlaps(net):
                messages.append(
                    f"跨 Region CIDR 重叠：{_format_plane_ref(existing_plane)} <-> {_format_plane_ref(plane)}"
                )
        parsed_planes.append((plane, net))
    return messages


def _find_startup_cross_region_vlan_violations(db: Session) -> list[str]:
    """启动时查找已有数据中的跨 Region VLAN 重复。"""
    rows = db.query(RegionNetworkPlane).filter(RegionNetworkPlane.vlan_id.isnot(None)).all()
    seen_by_vlan: dict[int, list[RegionNetworkPlane]] = {}
    messages: list[str] = []
    for plane in rows:
        if plane.vlan_id is None:
            continue
        for existing_plane in seen_by_vlan.get(plane.vlan_id, []):
            if existing_plane.region_id != plane.region_id:
                messages.append(
                    f"跨 Region VLAN 重复：{_format_plane_ref(existing_plane)} <-> {_format_plane_ref(plane)}"
                )
        seen_by_vlan.setdefault(plane.vlan_id, []).append(plane)
    return messages


def _format_plane_refs(planes: list[RegionNetworkPlane]) -> str:
    return "；".join(_format_plane_ref(plane) for plane in planes)


def _format_plane_ref(plane: RegionNetworkPlane) -> str:
    region_name = plane.region.name if plane.region else "未知Region"
    plane_type_name = plane.plane_type.name if plane.plane_type else "未知网络平面"
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


def _validate_gateway_ip_format(
    net: IPNetwork, gateway_ip: str | None
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """强校验网关 IP 的格式、IP 版本与是否落在 CIDR 内。"""
    if not gateway_ip:
        return None
    ip = parse_ip(gateway_ip)
    if not ip:
        raise BusinessError(f"无效的网关 IP 地址: {gateway_ip}")
    if not ip_belongs_to_network(ip, net):
        if ip.version != net.version:
            raise BusinessError(f"网关 IP {gateway_ip} 必须与平面 CIDR {net.with_prefixlen} 使用相同 IP 版本")
        raise BusinessError(f"网关 IP {gateway_ip} 必须在平面 CIDR {net.with_prefixlen} 范围内")
    return ip


def _validate_gateway_ip_policy(
    net: IPNetwork,
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None,
    *,
    is_private: bool,
) -> str | None:
    """弱校验网关 IP 是否符合推荐位置（强校验应在调用前由 _validate_gateway_ip_format 完成）。"""
    if ip is None:
        return None

    expected = _expected_gateway_ip(net, is_private=is_private)
    if ip != expected:
        if isinstance(net, ipaddress.IPv6Network):
            plane_description = "IPv6 平面"
            position = "第一个可用 IP"
        else:
            plane_description = "私网平面" if is_private else "非私网平面"
            position = "第一个可用 IP" if is_private else "最后一个可用 IP"
        return f"当前网关 IP 不符合推荐规则：{plane_description}建议使用 CIDR 内{position} {expected}"
    return None


def _expected_gateway_ip(net: IPNetwork, *, is_private: bool) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """计算给定 CIDR 的推荐网关 IP 位置。

    IPv6 平面：网络地址 + 1（/127、/128 回退到网络地址）。
    IPv4 私网平面：网络地址 + 1（/31、/32 回退到网络地址）。
    IPv4 非私网平面：广播地址 - 1（/31、/32 回退到广播地址）。
    """
    if net.num_addresses == 1:
        return net.network_address
    if isinstance(net, ipaddress.IPv6Network):
        return net.network_address + 1 if net.prefixlen < 127 else net.network_address
    if is_private:
        if net.prefixlen < 31:
            return net.network_address + 1
        return net.network_address
    if net.prefixlen < 31:
        return net.broadcast_address - 1
    return net.broadcast_address
