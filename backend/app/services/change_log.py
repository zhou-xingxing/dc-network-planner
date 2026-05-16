from __future__ import annotations

from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.change_log import ChangeLog


def list_change_logs(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    operator: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[ChangeLog], int]:
    """查询变更日志列表，支持按实体、操作、时间筛选。"""
    query = db.query(ChangeLog)

    if entity_type:
        query = query.filter(ChangeLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(ChangeLog.entity_id == entity_id)
    if action:
        query = query.filter(ChangeLog.action == action)
    if operator:
        query = query.filter(ChangeLog.operator.ilike(f"%{operator}%"))
    if date_from:
        query = query.filter(ChangeLog.created_at >= date_from)
    if date_to:
        query = query.filter(ChangeLog.created_at <= date_to)

    total = query.count()
    items = query.order_by(desc(ChangeLog.created_at)).offset(skip).limit(limit).all()
    return items, total


def log_change(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    operator: str,
    field_name: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    comment: Optional[str] = None,
) -> ChangeLog:
    """记录一条变更日志。

    Args:
        db: 数据库会话。
        entity_type: 实体类型（如 region、region_network_plane）。
        entity_id: 实体 ID。
        action: 操作类型（create、update、delete、import）。
        operator: 操作者名称。
        field_name: 变更的字段名（update 操作时）。
        old_value: 变更前的值。
        new_value: 变更后的值。
        comment: 备注说明。

    Returns:
        新创建的 ChangeLog 记录。
    """
    entry = ChangeLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        operator=operator or "system",
        comment=comment,
    )
    db.add(entry)
    db.flush()
    return entry
