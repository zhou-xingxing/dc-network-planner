from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.change_log import ChangeLog
from app.schemas.change_log import ChangeLogResponse
from app.schemas.common import PaginatedResponse
from app.utils.time_utils import format_datetime

router = APIRouter(prefix="/api/change-logs", tags=["Change Logs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=PaginatedResponse[ChangeLogResponse])
def list_change_logs(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ChangeLogResponse]:
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
    return PaginatedResponse(
        items=[
            ChangeLogResponse(
                id=cl.id,
                entity_type=cl.entity_type,
                entity_id=cl.entity_id,
                action=cl.action,
                field_name=cl.field_name,
                old_value=cl.old_value,
                new_value=cl.new_value,
                operator=cl.operator,
                comment=cl.comment,
                created_at=format_datetime(cl.created_at),
            )
            for cl in items
        ],
        total=total,
        skip=skip,
        limit=limit,
    )
