from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import BusinessError
from app.models.switch import SwitchBusinessType, SwitchGroup
from app.schemas.switch import SwitchBusinessTypeCreate, SwitchBusinessTypeUpdate
from app.services.change_log import log_change


def list_switch_business_types(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[SwitchBusinessType], int]:
    """分页查询交换机业务类型。

    Args:
        db: 数据库会话。
        skip: 分页偏移量。
        limit: 每页数量。

    Returns:
        交换机业务类型列表与总数。
    """
    query = db.query(SwitchBusinessType)
    total = query.count()
    rows = query.order_by(SwitchBusinessType.name.asc()).offset(skip).limit(limit).all()
    return rows, total


def get_switch_business_type(db: Session, business_type_id: str) -> SwitchBusinessType | None:
    """根据 ID 获取交换机业务类型。

    Args:
        db: 数据库会话。
        business_type_id: 交换机业务类型 ID。

    Returns:
        交换机业务类型；不存在时返回 None。
    """
    return db.get(SwitchBusinessType, business_type_id)


def create_switch_business_type(
    db: Session,
    data: SwitchBusinessTypeCreate,
    operator: str,
) -> SwitchBusinessType:
    """创建交换机业务类型。

    Args:
        db: 数据库会话。
        data: 交换机业务类型创建数据。
        operator: 审计操作人。

    Returns:
        已创建的交换机业务类型。

    Raises:
        BusinessError: code 或名称已存在。
    """
    _ensure_business_type_identity_available(db, data.code, data.name)
    business_type = SwitchBusinessType(code=data.code, name=data.name)
    db.add(business_type)
    db.flush()
    log_change(
        db,
        entity_type="switch_business_type",
        entity_id=business_type.id,
        entity_name=business_type.name,
        action="create",
        operator=operator,
        new_value=f"code={business_type.code}, name={business_type.name}",
    )
    return business_type


def update_switch_business_type(
    db: Session,
    business_type_id: str,
    data: SwitchBusinessTypeUpdate,
    operator: str,
) -> SwitchBusinessType | None:
    """更新交换机业务类型。

    Args:
        db: 数据库会话。
        business_type_id: 交换机业务类型 ID。
        data: 交换机业务类型更新数据。
        operator: 审计操作人。

    Returns:
        更新后的交换机业务类型；不存在时返回 None。

    Raises:
        BusinessError: 新 code 或新名称已存在。
    """
    business_type = get_switch_business_type(db, business_type_id)
    if not business_type:
        return None
    new_code = data.code if data.code is not None else business_type.code
    new_name = data.name if data.name is not None else business_type.name
    _ensure_business_type_identity_available(
        db,
        new_code,
        new_name,
        exclude_id=business_type.id,
    )

    entity_name = business_type.name
    changes: dict[str, tuple[str, str]] = {}
    if new_code != business_type.code:
        changes["code"] = (business_type.code, new_code)
        business_type.code = new_code
    if new_name != business_type.name:
        changes["name"] = (business_type.name, new_name)
        business_type.name = new_name
    for field_name, (old_value, new_value) in changes.items():
        log_change(
            db,
            entity_type="switch_business_type",
            entity_id=business_type.id,
            entity_name=entity_name,
            action="update",
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            operator=operator,
        )
    if changes:
        db.flush()
    return business_type


def delete_switch_business_type(db: Session, business_type_id: str, operator: str) -> bool:
    """删除未被交换机组引用的业务类型。

    Args:
        db: 数据库会话。
        business_type_id: 交换机业务类型 ID。
        operator: 审计操作人。

    Returns:
        删除成功返回 True；业务类型不存在时返回 False。

    Raises:
        BusinessError: 业务类型仍被交换机组引用。
    """
    business_type = get_switch_business_type(db, business_type_id)
    if not business_type:
        return False
    group_count = (
        db.query(func.count(SwitchGroup.id)).filter(SwitchGroup.business_type_id == business_type_id).scalar() or 0
    )
    if group_count:
        raise BusinessError(f"交换机业务类型 {business_type.name} 仍被 {group_count} 个交换机组使用，不能删除")

    log_change(
        db,
        entity_type="switch_business_type",
        entity_id=business_type.id,
        entity_name=business_type.name,
        action="delete",
        operator=operator,
        old_value=f"code={business_type.code}, name={business_type.name}",
    )
    db.delete(business_type)
    db.flush()
    return True


def _ensure_business_type_identity_available(
    db: Session,
    code: str,
    name: str,
    exclude_id: str | None = None,
) -> None:
    """确保交换机业务类型的 code 和名称均为全局唯一。"""
    code_query = db.query(SwitchBusinessType.id).filter(SwitchBusinessType.code == code)
    name_query = db.query(SwitchBusinessType.id).filter(SwitchBusinessType.name == name)
    if exclude_id:
        code_query = code_query.filter(SwitchBusinessType.id != exclude_id)
        name_query = name_query.filter(SwitchBusinessType.id != exclude_id)
    if code_query.first():
        raise BusinessError(f"交换机业务类型 code 已存在: {code}")
    if name_query.first():
        raise BusinessError(f"交换机业务类型名称已存在: {name}")
