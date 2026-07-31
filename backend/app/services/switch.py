from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.cabling import CableEntry
from app.models.rack import Rack
from app.models.region import Region
from app.models.switch import Switch, SwitchBusinessType, SwitchGroup, SwitchPort
from app.schemas.switch import SwitchPortBulkCreate, SwitchUpdate
from app.services.change_log import log_change


@dataclass(frozen=True)
class SwitchWithCounts:
    """交换机及关联名称、端口统计。"""

    switch: Switch
    region_id: str
    region_name: str
    rack_name: str
    switch_group_name: str | None
    business_type_name: str | None
    port_count: int
    used_port_count: int


@dataclass(frozen=True)
class SwitchPortWithOccupancy:
    """交换机端口及由线缆引用派生的占用状态。"""

    switch_port: SwitchPort
    cable_entry_id: str | None


def list_switches(
    db: Session,
    region_id: str,
    *,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    rack_id: str | None = None,
    switch_group_id: str | None = None,
) -> tuple[list[SwitchWithCounts], int]:
    """分页查询指定 Region 的交换机。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        skip: 分页偏移量。
        limit: 每页数量。
        search: 交换机名称模糊搜索。
        rack_id: 机柜 ID 精确筛选。
        switch_group_id: 交换机组 ID 精确筛选。

    Returns:
        交换机聚合结果列表与总数。

    Raises:
        ResourceNotFoundError: Region 不存在。
    """
    _get_region_or_raise(db, region_id)
    query = db.query(Switch.id).join(Rack, Rack.id == Switch.rack_id).filter(Rack.region_id == region_id)
    if search:
        query = query.filter(Switch.name.ilike(f"%{search}%"))
    if rack_id:
        query = query.filter(Switch.rack_id == rack_id)
    if switch_group_id:
        query = query.filter(Switch.switch_group_id == switch_group_id)
    total = query.count()
    switch_ids = [row[0] for row in query.order_by(Switch.name.asc()).offset(skip).limit(limit).all()]
    if not switch_ids:
        return [], total
    items = _query_switch_items(db, switch_ids)
    items.sort(key=lambda item: item.switch.name)
    return items, total


def get_switch(db: Session, region_id: str, switch_id: str) -> Switch | None:
    """获取当前 Region 内的交换机。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        switch_id: 交换机 ID。

    Returns:
        交换机；不存在或不属于指定 Region 时返回 None。
    """
    return (
        db.query(Switch)
        .join(Rack, Rack.id == Switch.rack_id)
        .filter(Switch.id == switch_id, Rack.region_id == region_id)
        .first()
    )


def get_switch_with_counts(db: Session, region_id: str, switch_id: str) -> SwitchWithCounts | None:
    """获取交换机及端口统计。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        switch_id: 交换机 ID。

    Returns:
        交换机聚合结果；交换机不存在或不属于指定 Region 时返回 None。
    """
    switch = get_switch(db, region_id, switch_id)
    if not switch:
        return None
    items = _query_switch_items(db, [switch_id])
    return items[0] if items else None


def update_switch(
    db: Session,
    region_id: str,
    switch_id: str,
    data: SwitchUpdate,
    operator: str,
) -> SwitchWithCounts | None:
    """更新交换机，使用最终候选值统一执行强校验。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        switch_id: 交换机 ID。
        data: 交换机更新数据。
        operator: 审计操作人。

    Returns:
        更新后的交换机聚合结果；交换机不存在或不属于指定 Region 时返回 None。

    Raises:
        BusinessError: 更新后的名称、关联资源、组成员或机位不合法。
    """
    switch = get_switch(db, region_id, switch_id)
    if not switch:
        return None
    fields_set = data.model_fields_set
    rack_id = data.rack_id if "rack_id" in fields_set else switch.rack_id
    group_id = data.switch_group_id if "switch_group_id" in fields_set else switch.switch_group_id
    member_role = data.member_role if "member_role" in fields_set else switch.member_role
    name = data.name if "name" in fields_set else switch.name
    port_speed_mbps = data.port_speed_mbps if "port_speed_mbps" in fields_set else switch.port_speed_mbps
    start_u = data.start_u if "start_u" in fields_set else switch.start_u
    height_u = data.height_u if "height_u" in fields_set else switch.height_u
    if rack_id is None or name is None or port_speed_mbps is None or start_u is None or height_u is None:
        raise BusinessError("交换机必填字段不能为空")
    if (group_id is None) != (member_role is None):
        raise BusinessError("交换机组与成员角色必须同时填写或同时留空")

    ensure_switch_name_available(db, name, exclude_id=switch.id)
    rack = get_rack_for_region(db, region_id, rack_id)
    group = _get_group_for_region(db, region_id, group_id)
    _validate_group_assignment(
        db,
        group,
        member_role,
        exclude_switch_id=switch.id,
    )
    validate_switch_position(db, rack, start_u, height_u, exclude_switch_id=switch.id)

    entity_name = switch.name
    candidates: dict[str, object] = {
        "rack_id": rack.id,
        "switch_group_id": group.id if group else None,
        "member_role": member_role,
        "name": name,
        "port_speed_mbps": port_speed_mbps,
        "start_u": start_u,
        "height_u": height_u,
    }
    changes: dict[str, tuple[object, object]] = {}
    for field_name, new_value in candidates.items():
        old_value = getattr(switch, field_name)
        if old_value != new_value:
            changes[field_name] = (old_value, new_value)
            setattr(switch, field_name, new_value)
    for field_name, (old_value, new_value) in changes.items():
        log_change(
            db,
            entity_type="switch",
            entity_id=switch.id,
            entity_name=entity_name,
            action="update",
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else "无",
            new_value=str(new_value) if new_value is not None else "无",
            operator=operator,
        )
    if changes:
        db.flush()
    return get_switch_with_counts(db, region_id, switch.id)


def delete_switch(db: Session, region_id: str, switch_id: str, operator: str) -> bool:
    """删除没有已占用端口的交换机，未占用端口由数据库级联删除。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        switch_id: 交换机 ID。
        operator: 审计操作人。

    Returns:
        删除成功返回 True；交换机不存在或不属于指定 Region 时返回 False。

    Raises:
        BusinessError: 交换机存在已被线缆引用的端口。
    """
    switch = get_switch(db, region_id, switch_id)
    if not switch:
        return False
    port_count, used_port_count = _count_switch_ports(db, switch.id)
    if used_port_count:
        raise BusinessError(f"交换机 {switch.name} 仍有 {used_port_count} 个端口已被线缆占用，不能删除")

    ports = (
        db.query(SwitchPort)
        .filter(SwitchPort.switch_id == switch.id)
        .order_by(
            SwitchPort.card_number.asc(),
            SwitchPort.subcard_number.asc(),
            SwitchPort.port_number.asc(),
        )
        .all()
    )
    for port in ports:
        _log_switch_port_delete(db, switch, port, operator)

    log_change(
        db,
        entity_type="switch",
        entity_id=switch.id,
        entity_name=switch.name,
        action="delete",
        operator=operator,
        old_value=(
            f"name={switch.name}, rack_id={switch.rack_id}, start_u={switch.start_u}, "
            f"height_u={switch.height_u}, port_count={port_count}"
        ),
    )
    db.delete(switch)
    db.flush()
    return True


def list_switch_ports(
    db: Session,
    region_id: str,
    switch_id: str,
    *,
    skip: int = 0,
    limit: int = 100,
    card_number: int | None = None,
    subcard_number: int | None = None,
) -> tuple[list[SwitchPortWithOccupancy], int] | None:
    """分页查询交换机端口及占用状态，支持按板卡和子板卡筛选。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        switch_id: 交换机 ID。
        skip: 分页偏移量。
        limit: 每页数量。
        card_number: 板卡号精确筛选。
        subcard_number: 子板卡号精确筛选。

    Returns:
        端口聚合结果列表与总数；交换机不存在或不属于指定 Region 时返回 None。
    """
    switch = get_switch(db, region_id, switch_id)
    if not switch:
        return None
    port_query = db.query(SwitchPort).filter(SwitchPort.switch_id == switch.id)
    if card_number is not None:
        port_query = port_query.filter(SwitchPort.card_number == card_number)
    if subcard_number is not None:
        port_query = port_query.filter(SwitchPort.subcard_number == subcard_number)
    total = port_query.with_entities(func.count(SwitchPort.id)).scalar() or 0
    rows = (
        port_query.with_entities(SwitchPort, CableEntry.id)
        .outerjoin(CableEntry, CableEntry.switch_port_id == SwitchPort.id)
        .order_by(
            SwitchPort.card_number.asc(),
            SwitchPort.subcard_number.asc(),
            SwitchPort.port_number.asc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        SwitchPortWithOccupancy(switch_port=port, cable_entry_id=cable_entry_id) for port, cable_entry_id in rows
    ], int(total)


def create_switch_ports_bulk(
    db: Session,
    region_id: str,
    switch_id: str,
    data: SwitchPortBulkCreate,
    operator: str,
) -> list[SwitchPortWithOccupancy] | None:
    """在指定板卡和子板卡上原子创建一段连续端口编号。

    写入前一次检查整个范围；任一物理端口已存在时拒绝整个请求，避免部分成功。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        switch_id: 交换机 ID。
        data: 连续端口范围及板卡位置。
        operator: 审计操作人。

    Returns:
        已创建端口及其空闲状态；交换机不存在或不属于指定 Region 时返回 None。

    Raises:
        BusinessError: 范围内存在已有端口。
    """
    switch = get_switch(db, region_id, switch_id)
    if not switch:
        return None
    existing = (
        db.query(SwitchPort.port_number)
        .filter(
            SwitchPort.switch_id == switch.id,
            SwitchPort.card_number == data.card_number,
            SwitchPort.subcard_number == data.subcard_number,
            SwitchPort.port_number >= data.start_port_number,
            SwitchPort.port_number <= data.end_port_number,
        )
        .order_by(SwitchPort.port_number.asc())
        .first()
    )
    if existing:
        raise BusinessError(f"交换机端口已存在: {data.card_number}/{data.subcard_number}/{existing[0]}")

    ports = [
        SwitchPort(
            switch_id=switch.id,
            card_number=data.card_number,
            subcard_number=data.subcard_number,
            port_number=port_number,
        )
        for port_number in range(data.start_port_number, data.end_port_number + 1)
    ]
    db.add_all(ports)
    db.flush()
    for port in ports:
        log_change(
            db,
            entity_type="switch_port",
            entity_id=port.id,
            entity_name=f"{switch.name}:{port.card_number}/{port.subcard_number}/{port.port_number}",
            action="create",
            operator=operator,
            new_value=(
                f"switch={switch.name}, card_number={port.card_number}, "
                f"subcard_number={port.subcard_number}, port_number={port.port_number}"
            ),
        )
    return [SwitchPortWithOccupancy(switch_port=port, cable_entry_id=None) for port in ports]


def delete_switch_port(
    db: Session,
    region_id: str,
    switch_id: str,
    port_id: str,
    operator: str,
) -> bool:
    """删除未被线缆占用的交换机端口。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        switch_id: 交换机 ID。
        port_id: 交换机端口 ID。
        operator: 审计操作人。

    Returns:
        删除成功返回 True；交换机或端口不存在时返回 False。

    Raises:
        BusinessError: 端口已被线缆占用。
    """
    switch = get_switch(db, region_id, switch_id)
    if not switch:
        return False
    port = db.query(SwitchPort).filter(SwitchPort.id == port_id, SwitchPort.switch_id == switch.id).first()
    if not port:
        return False
    cable_entry_id = db.query(CableEntry.id).filter(CableEntry.switch_port_id == port.id).scalar()
    if cable_entry_id:
        raise BusinessError(
            f"交换机端口 {switch.name}:{port.card_number}/{port.subcard_number}/{port.port_number} "
            "已被线缆占用，不能删除"
        )

    _log_switch_port_delete(db, switch, port, operator)
    db.delete(port)
    db.flush()
    return True


def _query_switch_items(db: Session, switch_ids: list[str]) -> list[SwitchWithCounts]:
    """聚合查询交换机关联名称和端口统计，避免列表 N+1 查询。"""
    rows = (
        db.query(
            Switch,
            Region.id,
            Region.name,
            Rack.name,
            SwitchGroup.name,
            SwitchBusinessType.name,
            func.count(func.distinct(SwitchPort.id)),
            func.count(func.distinct(CableEntry.id)),
        )
        .join(Rack, Rack.id == Switch.rack_id)
        .join(Region, Region.id == Rack.region_id)
        .outerjoin(SwitchGroup, SwitchGroup.id == Switch.switch_group_id)
        .outerjoin(SwitchBusinessType, SwitchBusinessType.id == SwitchGroup.business_type_id)
        .outerjoin(SwitchPort, SwitchPort.switch_id == Switch.id)
        .outerjoin(CableEntry, CableEntry.switch_port_id == SwitchPort.id)
        .filter(Switch.id.in_(switch_ids))
        .group_by(Switch.id, Region.id, Region.name, Rack.name, SwitchGroup.name, SwitchBusinessType.name)
        .all()
    )
    return [
        SwitchWithCounts(
            switch=switch,
            region_id=region_id,
            region_name=region_name,
            rack_name=rack_name,
            switch_group_name=group_name,
            business_type_name=business_type_name,
            port_count=int(port_count or 0),
            used_port_count=int(used_port_count or 0),
        )
        for (
            switch,
            region_id,
            region_name,
            rack_name,
            group_name,
            business_type_name,
            port_count,
            used_port_count,
        ) in rows
    ]


def _get_region_or_raise(db: Session, region_id: str) -> Region:
    """获取 Region，不存在时中止当前操作。"""
    region = db.get(Region, region_id)
    if not region:
        raise ResourceNotFoundError("Region 不存在")
    return region


def get_rack_for_region(db: Session, region_id: str, rack_id: str) -> Rack:
    """获取交换机目标机柜并校验其 Region 归属。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        rack_id: 机柜 ID。

    Returns:
        属于指定 Region 的机柜。

    Raises:
        BusinessError: 机柜不存在或不属于指定 Region。
    """
    rack = db.get(Rack, rack_id)
    if not rack:
        raise BusinessError("机柜不存在")
    if rack.region_id != region_id:
        raise BusinessError("机柜不属于当前 Region")
    return rack


def _get_group_for_region(db: Session, region_id: str, group_id: str | None) -> SwitchGroup | None:
    """获取可选交换机组并校验其 Region 归属。"""
    if group_id is None:
        return None
    group = db.get(SwitchGroup, group_id)
    if not group:
        raise BusinessError("交换机组不存在")
    if group.region_id != region_id:
        raise BusinessError("交换机组不属于当前 Region")
    return group


def ensure_switch_name_available(db: Session, name: str, exclude_id: str | None = None) -> None:
    """确保交换机名称在全局范围内唯一。

    Args:
        db: 数据库会话。
        name: 待校验的交换机名称。
        exclude_id: 更新时排除的交换机 ID。

    Returns:
        None。

    Raises:
        BusinessError: 交换机名称已存在。
    """
    query = db.query(Switch.id).filter(Switch.name == name)
    if exclude_id:
        query = query.filter(Switch.id != exclude_id)
    if query.first():
        raise BusinessError(f"交换机名称已存在: {name}")


def _validate_group_assignment(
    db: Session,
    group: SwitchGroup | None,
    member_role: str | None,
    *,
    exclude_switch_id: str | None = None,
) -> None:
    """校验组模式、成员角色和角色唯一性。"""
    if group is None and member_role is None:
        return
    if group is None or member_role is None:
        raise BusinessError("交换机组与成员角色必须同时填写或同时留空")
    allowed_roles = {"pair": {"a", "b"}, "single": {"single"}}
    if member_role not in allowed_roles[group.group_mode]:
        raise BusinessError(f"{group.group_mode} 交换机组不允许使用 {member_role} 成员角色")
    query = db.query(Switch.id).filter(
        Switch.switch_group_id == group.id,
        Switch.member_role == member_role,
    )
    if exclude_switch_id:
        query = query.filter(Switch.id != exclude_switch_id)
    if query.first():
        raise BusinessError(f"交换机组 {group.name} 已有 {member_role} 成员")


def validate_switch_position(
    db: Session,
    rack: Rack,
    start_u: int,
    height_u: int,
    *,
    exclude_switch_id: str | None = None,
) -> None:
    """校验交换机上架范围不越界，且不与交换机或服务器侧位置重叠。

    Args:
        db: 数据库会话。
        rack: 目标机柜。
        start_u: 起始 U 位。
        height_u: 占用 U 数。
        exclude_switch_id: 更新时排除的交换机 ID。

    Returns:
        None。

    Raises:
        BusinessError: 上架范围越界或与已有资源重叠。
    """
    end_u = start_u + height_u - 1
    if end_u > rack.u_height:
        raise BusinessError(f"交换机上架位置 {start_u}U-{end_u}U 超出机柜 {rack.name} 的 {rack.u_height}U 范围")

    switch_query = db.query(Switch).filter(
        Switch.rack_id == rack.id,
        Switch.start_u <= end_u,
        Switch.start_u + Switch.height_u - 1 >= start_u,
    )
    if exclude_switch_id:
        switch_query = switch_query.filter(Switch.id != exclude_switch_id)
    conflicting_switch = switch_query.first()
    if conflicting_switch:
        conflict_end_u = conflicting_switch.start_u + conflicting_switch.height_u - 1
        raise BusinessError(
            f"交换机上架位置 {start_u}U-{end_u}U 与 {conflicting_switch.name} "
            f"的 {conflicting_switch.start_u}U-{conflict_end_u}U 重叠"
        )

    conflicting_entry = (
        db.query(CableEntry)
        .filter(
            CableEntry.server_rack_id == rack.id,
            CableEntry.server_start_u <= end_u,
            CableEntry.server_start_u + CableEntry.server_height_u - 1 >= start_u,
        )
        .first()
    )
    if conflicting_entry:
        conflict_end_u = conflicting_entry.server_start_u + conflicting_entry.server_height_u - 1
        raise BusinessError(
            f"交换机上架位置 {start_u}U-{end_u}U 与服务器侧位置 "
            f"{conflicting_entry.server_start_u}U-{conflict_end_u}U 重叠"
        )


def _count_switch_ports(db: Session, switch_id: str) -> tuple[int, int]:
    """统计交换机的端口总数与已被线缆占用数量。"""
    port_count = db.query(func.count(SwitchPort.id)).filter(SwitchPort.switch_id == switch_id).scalar() or 0
    used_port_count = (
        db.query(func.count(CableEntry.id))
        .join(SwitchPort, SwitchPort.id == CableEntry.switch_port_id)
        .filter(SwitchPort.switch_id == switch_id)
        .scalar()
        or 0
    )
    return int(port_count), int(used_port_count)


def _log_switch_port_delete(db: Session, switch: Switch, port: SwitchPort, operator: str) -> None:
    """记录直接删除或随交换机级联删除的端口。"""
    log_change(
        db,
        entity_type="switch_port",
        entity_id=port.id,
        entity_name=f"{switch.name}:{port.card_number}/{port.subcard_number}/{port.port_number}",
        action="delete",
        operator=operator,
        old_value=(
            f"switch={switch.name}, card_number={port.card_number}, "
            f"subcard_number={port.subcard_number}, port_number={port.port_number}"
        ),
    )
