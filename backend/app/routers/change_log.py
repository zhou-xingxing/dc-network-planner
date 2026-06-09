from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.change_log import ChangeLogResponse
from app.schemas.common import PaginatedResponse
from app.services.change_log import list_change_logs as list_change_logs_service
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
    items, total = list_change_logs_service(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        operator=operator,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(
        items=[
            ChangeLogResponse(
                id=cl.id,
                entity_type=cl.entity_type,
                entity_id=cl.entity_id,
                entity_name=cl.entity_name,
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
