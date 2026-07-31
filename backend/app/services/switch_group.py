from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.rack import Rack
from app.models.region import Region
from app.models.switch import Switch, SwitchBusinessType, SwitchGroup
from app.schemas.switch import (
    SwitchGroupCreate,
    SwitchGroupMemberCreate,
    SwitchGroupReadinessIssueCode,
    SwitchGroupUpdate,
)
from app.services.change_log import log_change
from app.services.switch import (
    SwitchWithCounts,
    create_switch_ports_bulk,
    ensure_switch_name_available,
    get_rack_for_region,
    get_switch_with_counts,
    validate_switch_position,
)


@dataclass(frozen=True)
class SwitchGroupReadinessIssue:
    """交换机组成员配置未完整的原因。"""

    code: SwitchGroupReadinessIssueCode
    message: str


@dataclass(frozen=True)
class SwitchGroupWithStatus:
    """交换机组及成员完整性状态。"""

    switch_group: SwitchGroup
    region_name: str
    business_type: SwitchBusinessType
    member_count: int
    is_member_config_ready: bool
    readiness_issues: tuple[SwitchGroupReadinessIssue, ...]


@dataclass(frozen=True)
class SwitchGroupCreateResult:
    """原子创建完成的交换机组及成员交换机。"""

    group: SwitchGroupWithStatus
    members: list[SwitchWithCounts]


def list_switch_groups(
    db: Session,
    region_id: str,
    *,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    business_type_id: str | None = None,
) -> tuple[list[SwitchGroupWithStatus], int]:
    """分页查询指定 Region 的交换机组。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        skip: 分页偏移量。
        limit: 每页数量。
        search: 交换机组名称模糊搜索。
        business_type_id: 业务类型 ID 精确筛选。

    Returns:
        带成员配置完整性状态的交换机组列表与总数。

    Raises:
        ResourceNotFoundError: Region 不存在。
    """
    _get_region_or_raise(db, region_id)
    base_query = db.query(SwitchGroup).filter(SwitchGroup.region_id == region_id)
    if search:
        base_query = base_query.filter(SwitchGroup.name.ilike(f"%{search}%"))
    if business_type_id:
        base_query = base_query.filter(SwitchGroup.business_type_id == business_type_id)
    total = base_query.count()

    group_ids = [item.id for item in base_query.order_by(SwitchGroup.name.asc()).offset(skip).limit(limit).all()]
    if not group_ids:
        return [], total
    items = _query_group_statuses(db, group_ids)
    items.sort(key=lambda item: item.switch_group.name)
    return items, total


def get_switch_group(db: Session, region_id: str, group_id: str) -> SwitchGroup | None:
    """获取当前 Region 内的交换机组。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        group_id: 交换机组 ID。

    Returns:
        交换机组；不存在或不属于指定 Region 时返回 None。
    """
    return db.query(SwitchGroup).filter(SwitchGroup.id == group_id, SwitchGroup.region_id == region_id).first()


def get_switch_group_with_status(
    db: Session,
    region_id: str,
    group_id: str,
) -> SwitchGroupWithStatus | None:
    """获取交换机组及成员完整性状态。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        group_id: 交换机组 ID。

    Returns:
        带成员配置完整性状态的交换机组；不存在或不属于指定 Region 时返回 None。
    """
    group = get_switch_group(db, region_id, group_id)
    if not group:
        return None
    items = _query_group_statuses(db, [group_id])
    return items[0] if items else None


def create_switch_group_with_members(
    db: Session,
    region_id: str,
    data: SwitchGroupCreate,
    operator: str,
) -> SwitchGroupCreateResult:
    """原子创建交换机组及其完整成员。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        data: 交换机组、完整成员和端口范围。
        operator: 审计操作人。

    Returns:
        已创建的交换机组及成员交换机聚合结果。

    Raises:
        ResourceNotFoundError: Region 不存在。
        BusinessError: 组成员、名称、关联资源或上架位置不符合业务约束。
    """
    _validate_create_member_roles(data)
    _validate_create_member_names(data)
    _validate_create_member_port_speeds(data)

    region = _get_region_or_raise(db, region_id)
    business_type = db.get(SwitchBusinessType, data.business_type_id)
    if not business_type:
        raise BusinessError("交换机业务类型不存在")
    _ensure_group_name_available(db, data.name)

    member_racks: list[tuple[SwitchGroupMemberCreate, Rack]] = []
    for member in data.members:
        ensure_switch_name_available(db, member.name)
        rack = get_rack_for_region(db, region_id, member.rack_id)
        validate_switch_position(db, rack, member.start_u, member.height_u)
        _validate_member_position_against_request(member, rack, member_racks)
        member_racks.append((member, rack))

    group = SwitchGroup(
        region_id=region_id,
        business_type_id=business_type.id,
        name=data.name,
        group_mode=data.group_mode,
    )
    db.add(group)
    db.flush()

    switches = [
        Switch(
            rack_id=rack.id,
            switch_group_id=group.id,
            member_role=member.member_role,
            name=member.name,
            port_speed_mbps=member.port_speed_mbps,
            start_u=member.start_u,
            height_u=member.height_u,
        )
        for member, rack in member_racks
    ]
    db.add_all(switches)
    db.flush()

    log_change(
        db,
        entity_type="switch_group",
        entity_id=group.id,
        entity_name=group.name,
        action="create",
        operator=operator,
        new_value=(
            f"name={group.name}, business_type={business_type.name}, "
            f"group_mode={group.group_mode}, region={region.name}, "
            f"ports={data.port_range.card_number}/{data.port_range.subcard_number}/"
            f"{data.port_range.start_port_number}-{data.port_range.end_port_number}"
        ),
    )
    for switch, (_, rack) in zip(switches, member_racks, strict=True):
        log_change(
            db,
            entity_type="switch",
            entity_id=switch.id,
            entity_name=switch.name,
            action="create",
            operator=operator,
            new_value=(
                f"name={switch.name}, rack={rack.name}, start_u={switch.start_u}, height_u={switch.height_u}, "
                f"switch_group={group.name}, member_role={switch.member_role}, "
                f"port_speed_mbps={switch.port_speed_mbps}"
            ),
        )

    for switch in switches:
        created_ports = create_switch_ports_bulk(db, region_id, switch.id, data.port_range, operator)
        if created_ports is None:  # pragma: no cover - 同事务内刚完成交换机写入
            raise RuntimeError("创建交换机后无法生成端口")

    created_group = get_switch_group_with_status(db, region_id, group.id)
    created_members = [get_switch_with_counts(db, region_id, switch.id) for switch in switches]
    if not created_group or any(member is None for member in created_members):  # pragma: no cover - 同事务内刚完成写入
        raise RuntimeError("创建交换机组及成员后无法读取")
    return SwitchGroupCreateResult(
        group=created_group,
        members=[member for member in created_members if member is not None],
    )


def update_switch_group(
    db: Session,
    region_id: str,
    group_id: str,
    data: SwitchGroupUpdate,
    operator: str,
) -> SwitchGroupWithStatus | None:
    """更新交换机组，已有成员时禁止切换组模式。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        group_id: 交换机组 ID。
        data: 交换机组更新数据。
        operator: 审计操作人。

    Returns:
        更新后带成员配置完整性状态的交换机组；不存在或不属于指定 Region 时返回 None。

    Raises:
        BusinessError: 名称重复、业务类型不存在，或已有成员时修改组模式。
    """
    group = get_switch_group(db, region_id, group_id)
    if not group:
        return None
    member_count = _count_group_members(db, group.id)
    if data.group_mode is not None and data.group_mode != group.group_mode and member_count:
        raise BusinessError("交换机组已有成员，不能修改组模式")

    business_type = db.get(SwitchBusinessType, data.business_type_id) if data.business_type_id is not None else None
    if data.business_type_id is not None and not business_type:
        raise BusinessError("交换机业务类型不存在")
    if data.name is not None and data.name != group.name:
        _ensure_group_name_available(db, data.name, exclude_id=group.id)

    entity_name = group.name
    changes: dict[str, tuple[object, object]] = {}
    if data.business_type_id is not None and data.business_type_id != group.business_type_id:
        old_business_type = db.get(SwitchBusinessType, group.business_type_id)
        changes["business_type"] = (
            old_business_type.name if old_business_type else group.business_type_id,
            business_type.name if business_type else data.business_type_id,
        )
        group.business_type_id = data.business_type_id
    if data.name is not None and data.name != group.name:
        changes["name"] = (group.name, data.name)
        group.name = data.name
    if data.group_mode is not None and data.group_mode != group.group_mode:
        changes["group_mode"] = (group.group_mode, data.group_mode)
        group.group_mode = data.group_mode

    for field_name, (old_value, new_value) in changes.items():
        log_change(
            db,
            entity_type="switch_group",
            entity_id=group.id,
            entity_name=entity_name,
            action="update",
            field_name=field_name,
            old_value=str(old_value),
            new_value=str(new_value),
            operator=operator,
        )
    if changes:
        db.flush()
    return get_switch_group_with_status(db, region_id, group.id)


def delete_switch_group(db: Session, region_id: str, group_id: str, operator: str) -> bool:
    """删除无成员的交换机组。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        group_id: 交换机组 ID。
        operator: 审计操作人。

    Returns:
        删除成功返回 True；交换机组不存在或不属于指定 Region 时返回 False。

    Raises:
        BusinessError: 交换机组仍有成员。
    """
    group = get_switch_group(db, region_id, group_id)
    if not group:
        return False
    member_count = _count_group_members(db, group.id)
    if member_count:
        raise BusinessError(f"交换机组 {group.name} 仍有 {member_count} 台交换机，不能删除")

    log_change(
        db,
        entity_type="switch_group",
        entity_id=group.id,
        entity_name=group.name,
        action="delete",
        operator=operator,
        old_value=f"name={group.name}, group_mode={group.group_mode}",
    )
    db.delete(group)
    db.flush()
    return True


def _query_group_statuses(db: Session, group_ids: list[str]) -> list[SwitchGroupWithStatus]:
    """一次聚合查询交换机组成员数量与角色，避免列表 N+1 查询。"""
    rows = (
        db.query(
            SwitchGroup,
            Region.name,
            SwitchBusinessType,
            func.count(Switch.id),
            func.sum(case((Switch.member_role == "a", 1), else_=0)),
            func.sum(case((Switch.member_role == "b", 1), else_=0)),
            func.sum(case((Switch.member_role == "single", 1), else_=0)),
            func.count(func.distinct(Switch.port_speed_mbps)),
        )
        .join(Region, Region.id == SwitchGroup.region_id)
        .join(SwitchBusinessType, SwitchBusinessType.id == SwitchGroup.business_type_id)
        .outerjoin(Switch, Switch.switch_group_id == SwitchGroup.id)
        .filter(SwitchGroup.id.in_(group_ids))
        .group_by(SwitchGroup.id, Region.name, SwitchBusinessType.id)
        .all()
    )
    result: list[SwitchGroupWithStatus] = []
    for group, region_name, business_type, member_count, a_count, b_count, single_count, speed_count in rows:
        count = int(member_count or 0)
        readiness_issues = _build_readiness_issues(
            group.group_mode,
            member_count=count,
            a_count=int(a_count or 0),
            b_count=int(b_count or 0),
            single_count=int(single_count or 0),
            speed_count=int(speed_count or 0),
        )
        result.append(
            SwitchGroupWithStatus(
                switch_group=group,
                region_name=region_name,
                business_type=business_type,
                member_count=count,
                is_member_config_ready=not readiness_issues,
                readiness_issues=readiness_issues,
            )
        )
    return result


def _build_readiness_issues(
    group_mode: str,
    *,
    member_count: int,
    a_count: int,
    b_count: int,
    single_count: int,
    speed_count: int,
) -> tuple[SwitchGroupReadinessIssue, ...]:
    """根据组模式、成员角色和端口速率生成成员配置问题。"""
    issues: list[SwitchGroupReadinessIssue] = []
    if group_mode == "pair":
        if a_count == 0:
            issues.append(SwitchGroupReadinessIssue(code="MISSING_MEMBER_A", message="缺少 A 成员"))
        if b_count == 0:
            issues.append(SwitchGroupReadinessIssue(code="MISSING_MEMBER_B", message="缺少 B 成员"))
        if a_count > 1 or b_count > 1 or member_count != a_count + b_count:
            issues.append(
                SwitchGroupReadinessIssue(
                    code="UNEXPECTED_MEMBER_COUNT",
                    message=f"双机组成员应为 A、B 各 1 台，当前共 {member_count} 台",
                )
            )
        if a_count == 1 and b_count == 1 and member_count == 2 and speed_count != 1:
            issues.append(
                SwitchGroupReadinessIssue(
                    code="PORT_SPEED_MISMATCH",
                    message="A/B 成员端口速率不一致",
                )
            )
    else:
        if single_count == 0:
            issues.append(
                SwitchGroupReadinessIssue(
                    code="MISSING_SINGLE_MEMBER",
                    message="缺少 single 成员",
                )
            )
        if single_count > 1 or member_count != single_count:
            issues.append(
                SwitchGroupReadinessIssue(
                    code="UNEXPECTED_MEMBER_COUNT",
                    message=f"单机组应包含 1 台 single 成员，当前共 {member_count} 台",
                )
            )
    return tuple(issues)


def _get_region_or_raise(db: Session, region_id: str) -> Region:
    """获取 Region，不存在时中止当前操作。"""
    region = db.get(Region, region_id)
    if not region:
        raise ResourceNotFoundError("Region 不存在")
    return region


def _ensure_group_name_available(db: Session, name: str, exclude_id: str | None = None) -> None:
    """确保交换机组名称在全局范围内唯一。"""
    query = db.query(SwitchGroup.id).filter(SwitchGroup.name == name)
    if exclude_id:
        query = query.filter(SwitchGroup.id != exclude_id)
    if query.first():
        raise BusinessError(f"交换机组名称已存在: {name}")


def _validate_create_member_roles(data: SwitchGroupCreate) -> None:
    """确保创建请求一次提交完整且唯一的组内角色。"""
    roles = [member.member_role for member in data.members]
    expected_roles = ["a", "b"] if data.group_mode == "pair" else ["single"]
    if sorted(roles) != expected_roles:
        expected_label = "A、B 两台成员" if data.group_mode == "pair" else "一台 single 成员"
        raise BusinessError(f"{data.group_mode} 交换机组必须一次提交{expected_label}")


def _validate_create_member_names(data: SwitchGroupCreate) -> None:
    """确保同一创建请求中的交换机名称不重复。"""
    names = [member.name for member in data.members]
    if len(names) != len(set(names)):
        raise BusinessError("同一交换机组中的交换机名称不能重复")


def _validate_create_member_port_speeds(data: SwitchGroupCreate) -> None:
    """确保 A/B 双机成员使用相同端口速率。"""
    if data.group_mode != "pair":
        return
    if len({member.port_speed_mbps for member in data.members}) != 1:
        raise BusinessError("A/B 双机成员的端口速率必须一致")


def _validate_member_position_against_request(
    member: SwitchGroupMemberCreate,
    rack: Rack,
    validated_members: list[tuple[SwitchGroupMemberCreate, Rack]],
) -> None:
    """校验本次请求内位于同一机柜的成员不互相占用 U 位。"""
    start_u = member.start_u
    end_u = start_u + member.height_u - 1
    for existing_member, existing_rack in validated_members:
        if existing_rack.id != rack.id:
            continue
        existing_end_u = existing_member.start_u + existing_member.height_u - 1
        if start_u <= existing_end_u and end_u >= existing_member.start_u:
            raise BusinessError(
                f"交换机上架位置 {start_u}U-{end_u}U 与本次请求中的 {existing_member.name} "
                f"的 {existing_member.start_u}U-{existing_end_u}U 重叠"
            )


def _count_group_members(db: Session, group_id: str) -> int:
    """统计交换机组当前成员数量。"""
    return int(db.query(func.count(Switch.id)).filter(Switch.switch_group_id == group_id).scalar() or 0)
