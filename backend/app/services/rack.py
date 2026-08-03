from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.cabling import CableEntry
from app.models.rack import Rack
from app.models.region import Region
from app.models.switch import Switch
from app.schemas.rack import RackCreate, RackCreateItem, RackUpdate
from app.services.change_log import log_change


@dataclass(frozen=True)
class RackWithCounts:
    """机柜及其交换机、线缆引用统计。"""

    rack: Rack
    region_name: str
    switch_count: int
    cable_count: int


@dataclass(frozen=True)
class RackColumnWithCounts:
    """机房内单个机柜列及其资源统计。"""

    room_name: str
    rack_column: str
    rack_count: int
    switch_count: int
    cable_count: int


@dataclass(frozen=True)
class RackServerPosition:
    """同一起始 U 位下由线缆条目聚合的隐式服务器位置。"""

    start_u: int
    height_u: int
    server_port_names: tuple[str, ...]
    cable_count: int


@dataclass(frozen=True)
class RackOccupancy:
    """机柜内交换机与服务器侧位置占用快照。"""

    rack: Rack
    switches: tuple[Switch, ...]
    server_positions: tuple[RackServerPosition, ...]


def list_racks(
    db: Session,
    region_id: str,
    *,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    room_name: str | None = None,
    rack_column: str | None = None,
) -> tuple[list[RackWithCounts], int]:
    """查询指定 Region 的机柜列表。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        skip: 分页偏移量。
        limit: 每页数量。
        search: 机柜名称模糊搜索。
        room_name: 精确匹配机房名。
        rack_column: 精确匹配机柜列。

    Returns:
        机柜及引用统计列表与总数。

    Raises:
        ResourceNotFoundError: Region 不存在。
    """
    region = _get_region_or_raise(db, region_id)
    query = db.query(Rack).filter(Rack.region_id == region_id)
    if search:
        query = query.filter(Rack.name.ilike(f"%{search}%"))
    if room_name is not None:
        query = query.filter(Rack.room_name == room_name)
    if rack_column is not None:
        query = query.filter(Rack.rack_column == rack_column)
    total = query.count()

    switch_count = db.query(func.count(Switch.id)).filter(Switch.rack_id == Rack.id).correlate(Rack).scalar_subquery()
    cable_count = (
        db.query(func.count(CableEntry.id))
        .filter(CableEntry.server_rack_id == Rack.id)
        .correlate(Rack)
        .scalar_subquery()
    )
    rows = (
        query.with_entities(Rack, switch_count, cable_count)
        .order_by(Rack.room_name.asc(), Rack.rack_column.asc(), Rack.rack_number.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [
        RackWithCounts(
            rack=rack,
            region_name=region.name,
            switch_count=int(row_switch_count or 0),
            cable_count=int(row_cable_count or 0),
        )
        for rack, row_switch_count, row_cable_count in rows
    ]
    return items, total


def list_rack_columns(
    db: Session,
    region_id: str,
    *,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> tuple[list[RackColumnWithCounts], int, int]:
    """按机房和机柜列聚合指定 Region 的机柜及资源数量。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        skip: 机柜列分页偏移量。
        limit: 每页机柜列数量。
        search: 机柜名称模糊搜索。

    Returns:
        机柜列统计列表、机柜列总数和机柜总数。

    Raises:
        ResourceNotFoundError: Region 不存在。
    """
    _get_region_or_raise(db, region_id)
    rack_query = db.query(Rack).filter(Rack.region_id == region_id)
    if search:
        rack_query = rack_query.filter(Rack.name.ilike(f"%{search}%"))

    total_racks = rack_query.count()
    total_columns = (
        rack_query.with_entities(Rack.room_name, Rack.rack_column).group_by(Rack.room_name, Rack.rack_column).count()
    )

    switch_counts = (
        db.query(Switch.rack_id.label("rack_id"), func.count(Switch.id).label("switch_count"))
        .group_by(Switch.rack_id)
        .subquery()
    )
    cable_counts = (
        db.query(
            CableEntry.server_rack_id.label("rack_id"),
            func.count(CableEntry.id).label("cable_count"),
        )
        .group_by(CableEntry.server_rack_id)
        .subquery()
    )
    rows = (
        rack_query.outerjoin(switch_counts, switch_counts.c.rack_id == Rack.id)
        .outerjoin(cable_counts, cable_counts.c.rack_id == Rack.id)
        .with_entities(
            Rack.room_name,
            Rack.rack_column,
            func.count(Rack.id),
            func.coalesce(func.sum(switch_counts.c.switch_count), 0),
            func.coalesce(func.sum(cable_counts.c.cable_count), 0),
        )
        .group_by(Rack.room_name, Rack.rack_column)
        .order_by(Rack.room_name.asc(), Rack.rack_column.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [
        RackColumnWithCounts(
            room_name=room_name,
            rack_column=rack_column,
            rack_count=int(rack_count),
            switch_count=int(switch_count),
            cable_count=int(cable_count),
        )
        for room_name, rack_column, rack_count, switch_count, cable_count in rows
    ]
    return items, total_columns, total_racks


def get_rack(db: Session, region_id: str, rack_id: str) -> Rack | None:
    """获取当前 Region 内的机柜。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        rack_id: 机柜 ID。

    Returns:
        机柜；不存在或不属于指定 Region 时返回 None。
    """
    return db.query(Rack).filter(Rack.id == rack_id, Rack.region_id == region_id).first()


def get_rack_occupancy(db: Session, region_id: str, rack_id: str) -> RackOccupancy | None:
    """获取机柜内交换机和由线缆推导的服务器侧占用。

    同一机柜、同一起始 U 位视为同一隐式服务器位置。
    如果该位置的已有线缆记录使用不同设备高度，则拒绝
    返回自相矛盾的占用快照。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        rack_id: 机柜 ID。

    Returns:
        机柜占用快照；机柜不存在或不属于指定 Region 时返回 None。

    Raises:
        BusinessError: 同一隐式服务器位置存在不一致的设备高度。
    """
    rack = get_rack(db, region_id, rack_id)
    if not rack:
        return None

    switches = tuple(
        db.query(Switch).filter(Switch.rack_id == rack.id).order_by(Switch.start_u.asc(), Switch.name.asc()).all()
    )
    rows = (
        db.query(
            CableEntry.server_start_u,
            CableEntry.server_height_u,
            CableEntry.server_port_name,
        )
        .filter(CableEntry.server_rack_id == rack.id)
        .order_by(CableEntry.server_start_u.asc(), CableEntry.server_port_name.asc())
        .all()
    )

    grouped: dict[int, tuple[int, list[str]]] = {}
    for start_u, height_u, port_name in rows:
        current = grouped.get(start_u)
        if current is None:
            grouped[start_u] = (height_u, [port_name])
            continue
        current_height, port_names = current
        if current_height != height_u:
            raise BusinessError(
                f"机柜 {rack.name} 的服务器侧位置 {start_u}U " f"存在不一致的设备高度: {current_height}U、{height_u}U"
            )
        port_names.append(port_name)

    server_positions = tuple(
        RackServerPosition(
            start_u=start_u,
            height_u=height_u,
            server_port_names=tuple(port_names),
            cable_count=len(port_names),
        )
        for start_u, (height_u, port_names) in grouped.items()
    )
    return RackOccupancy(rack=rack, switches=switches, server_positions=server_positions)


def create_racks(
    db: Session,
    region_id: str,
    data: RackCreate,
    operator: str,
) -> list[RackWithCounts]:
    """按结构化位置原子创建一个或多个机柜。

    最终名称由后端使用同一规则生成。写入前先完成请求内重复和数据库
    名称冲突检查，避免部分创建。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        data: 机柜批量创建数据。
        operator: 审计操作人。

    Returns:
        已创建机柜及其初始引用统计。

    Raises:
        ResourceNotFoundError: Region 不存在。
        BusinessError: 请求内位置重复或名称已存在。
    """
    generated = [_rack_identity(item) for item in data.items]
    _validate_unique_request_identities(generated)
    region = _get_region_or_raise(db, region_id)
    names = [name for _, _, _, name in generated]
    existing_names = {name for (name,) in db.query(Rack.name).filter(Rack.name.in_(names)).all()}
    if existing_names:
        conflicting_name = next(name for name in names if name in existing_names)
        raise BusinessError(f"机柜名称已存在: {conflicting_name}")

    racks = [
        Rack(
            region_id=region_id,
            room_name=room_name,
            rack_column=rack_column,
            rack_number=rack_number,
            name=name,
            u_height=data.u_height,
        )
        for room_name, rack_column, rack_number, name in generated
    ]
    db.add_all(racks)
    db.flush()
    batch_size = len(racks)
    for rack in racks:
        log_change(
            db,
            entity_type="rack",
            entity_id=rack.id,
            entity_name=rack.name,
            action="create",
            operator=operator,
            new_value=(
                f"name={rack.name}, room_name={rack.room_name}, rack_column={rack.rack_column}, "
                f"rack_number={rack.rack_number}, u_height={rack.u_height}, batch_size={batch_size}"
            ),
        )
    return [
        RackWithCounts(
            rack=rack,
            region_name=region.name,
            switch_count=0,
            cable_count=0,
        )
        for rack in racks
    ]


def update_rack(
    db: Session,
    region_id: str,
    rack_id: str,
    data: RackUpdate,
    operator: str,
) -> RackWithCounts | None:
    """更新机柜，缩小高度前校验已上架设备和服务器侧位置。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        rack_id: 机柜 ID。
        data: 机柜更新数据。
        operator: 审计操作人。

    Returns:
        更新后的机柜及引用统计；机柜不存在或不属于指定 Region 时返回 None。

    Raises:
        BusinessError: 新位置重复、生成名称重复，或新高度会截断已有资源。
    """
    rack = get_rack(db, region_id, rack_id)
    if not rack:
        return None
    region = db.get(Region, region_id)
    if not region:
        return None

    room_name = data.room_name if data.room_name is not None else rack.room_name
    rack_column = data.rack_column if data.rack_column is not None else rack.rack_column
    rack_number = data.rack_number if data.rack_number is not None else rack.rack_number
    room_name, rack_column, rack_number, generated_name = _rack_identity(
        RackCreateItem(
            room_name=room_name,
            rack_column=rack_column,
            rack_number=rack_number,
        )
    )

    changes: dict[str, tuple[object, object]] = {}
    if generated_name != rack.name:
        _ensure_rack_name_available(db, generated_name, exclude_id=rack.id)
    for field_name, new_value in (
        ("room_name", room_name),
        ("rack_column", rack_column),
        ("rack_number", rack_number),
        ("name", generated_name),
    ):
        old_value = getattr(rack, field_name)
        if new_value != old_value:
            changes[field_name] = (old_value, new_value)
            setattr(rack, field_name, new_value)
    if data.u_height is not None and data.u_height != rack.u_height:
        _validate_rack_height_change(db, rack, data.u_height)
        changes["u_height"] = (rack.u_height, data.u_height)
        rack.u_height = data.u_height

    entity_name = str(changes.get("name", (rack.name, rack.name))[0])
    for field_name, (old_value, new_value) in changes.items():
        log_change(
            db,
            entity_type="rack",
            entity_id=rack.id,
            entity_name=entity_name,
            action="update",
            field_name=field_name,
            old_value=str(old_value),
            new_value=str(new_value),
            operator=operator,
        )
    if changes:
        db.flush()

    switch_count, cable_count = _count_rack_dependencies(db, rack.id)
    return RackWithCounts(
        rack=rack,
        region_name=region.name,
        switch_count=switch_count,
        cable_count=cable_count,
    )


def delete_rack(db: Session, region_id: str, rack_id: str, operator: str) -> bool:
    """删除无交换机和线缆引用的机柜。

    Args:
        db: 数据库会话。
        region_id: Region ID。
        rack_id: 机柜 ID。
        operator: 审计操作人。

    Returns:
        删除成功返回 True；机柜不存在或不属于指定 Region 时返回 False。

    Raises:
        BusinessError: 机柜仍有交换机或线缆引用。
    """
    rack = get_rack(db, region_id, rack_id)
    if not rack:
        return False
    switch_count, cable_count = _count_rack_dependencies(db, rack.id)
    if switch_count:
        raise BusinessError(f"机柜 {rack.name} 仍有 {switch_count} 台交换机，不能删除")
    if cable_count:
        raise BusinessError(f"机柜 {rack.name} 仍被 {cable_count} 条线缆使用，不能删除")

    log_change(
        db,
        entity_type="rack",
        entity_id=rack.id,
        entity_name=rack.name,
        action="delete",
        operator=operator,
        old_value=f"name={rack.name}, u_height={rack.u_height}",
    )
    db.delete(rack)
    db.flush()
    return True


def _get_region_or_raise(db: Session, region_id: str) -> Region:
    """获取 Region，不存在时中止当前业务操作。"""
    region = db.get(Region, region_id)
    if not region:
        raise ResourceNotFoundError("Region 不存在")
    return region


def _ensure_rack_name_available(db: Session, name: str, exclude_id: str | None = None) -> None:
    """确保机柜名称在全局范围内唯一。"""
    query = db.query(Rack.id).filter(Rack.name == name)
    if exclude_id:
        query = query.filter(Rack.id != exclude_id)
    if query.first():
        raise BusinessError(f"机柜名称已存在: {name}")


def _rack_identity(item: RackCreateItem) -> tuple[str, str, int, str]:
    """根据已规范化的结构化位置生成唯一、可展示的机柜名称。"""
    name = f"{item.room_name}-{item.rack_column}{item.rack_number:02d}"
    if len(name) > 100:
        raise BusinessError(f"生成的机柜名称超过 100 个字符: {name}")
    return item.room_name, item.rack_column, item.rack_number, name


def _validate_unique_request_identities(
    identities: list[tuple[str, str, int, str]],
) -> None:
    """确保同一创建请求内没有重复结构化位置或生成名称。"""
    seen_positions: set[tuple[str, str, int]] = set()
    seen_names: set[str] = set()
    for room_name, rack_column, rack_number, name in identities:
        position = (room_name, rack_column, rack_number)
        if position in seen_positions:
            raise BusinessError(f"请求中的机柜位置重复: {name}")
        if name in seen_names:
            raise BusinessError(f"请求中的机柜名称重复: {name}")
        seen_positions.add(position)
        seen_names.add(name)


def _validate_rack_height_change(db: Session, rack: Rack, new_height: int) -> None:
    """校验机柜新高度不会截断已有交换机或服务器侧位置。"""
    max_switch_u = (
        db.query(func.max(Switch.start_u + Switch.height_u - 1)).filter(Switch.rack_id == rack.id).scalar() or 0
    )
    if max_switch_u > new_height:
        raise BusinessError(f"机柜内交换机最高占用到 {max_switch_u}U，不能将总 U 数调整为 {new_height}")

    max_server_u = (
        db.query(func.max(CableEntry.server_start_u + CableEntry.server_height_u - 1))
        .filter(CableEntry.server_rack_id == rack.id)
        .scalar()
        or 0
    )
    if max_server_u > new_height:
        raise BusinessError(f"机柜内服务器侧位置最高占用到 {max_server_u}U，不能将总 U 数调整为 {new_height}")


def _count_rack_dependencies(db: Session, rack_id: str) -> tuple[int, int]:
    """统计机柜直接关联的交换机和线缆条目数量。"""
    switch_count = db.query(func.count(Switch.id)).filter(Switch.rack_id == rack_id).scalar() or 0
    cable_count = db.query(func.count(CableEntry.id)).filter(CableEntry.server_rack_id == rack_id).scalar() or 0
    return int(switch_count), int(cable_count)
