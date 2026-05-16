from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.services.stats import get_system_stats

router = APIRouter(prefix="/api/stats", tags=["Stats"], dependencies=[Depends(get_current_user)])


@router.get("")
def get_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """获取系统概览统计数据。"""
    return get_system_stats(db)
