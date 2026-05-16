from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user,
    operator_name,
    require_administrator,
)
from app.exceptions import BusinessError
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.region import (
    RegionCreate,
    RegionDetailResponse,
    RegionResponse,
    RegionUpdate,
)
from app.services.region import (
    create_region,
    delete_region,
    get_region_detail,
    list_regions,
    update_region,
)
from app.utils.time_utils import format_datetime

router = APIRouter(prefix="/api/regions", tags=["Regions"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=PaginatedResponse[RegionResponse])
def list_regions_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[RegionResponse]:
    """查询 Region 列表。"""
    region_items, total = list_regions(db, skip=skip, limit=limit, search=search)
    items = []
    for item in region_items:
        region = item.region
        items.append(
            RegionResponse(
                id=region.id,
                name=region.name,
                description=region.description or "",
                plane_count=item.plane_count,
                created_at=format_datetime(region.created_at),
                updated_at=format_datetime(region.updated_at),
            )
        )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=RegionResponse, status_code=201)
def create_region_endpoint(
    data: RegionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> RegionResponse:
    """创建新 Region。"""
    try:
        region = create_region(db, data, operator_name(current_user))
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description or "",
        plane_count=0,
        created_at=format_datetime(region.created_at),
        updated_at=format_datetime(region.updated_at),
    )


@router.get("/{region_id}", response_model=RegionDetailResponse)
def get_region_endpoint(region_id: str, db: Session = Depends(get_db)) -> RegionDetailResponse:
    """获取 Region 详情（含网络平面树形结构）。"""
    detail = get_region_detail(db, region_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Region not found")
    return RegionDetailResponse(**detail)


@router.put("/{region_id}", response_model=RegionResponse)
def update_region_endpoint(
    region_id: str,
    data: RegionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> RegionResponse:
    """更新 Region 信息。"""
    item = update_region(db, region_id, data, operator_name(current_user))
    if not item:
        raise HTTPException(status_code=404, detail="Region not found")
    region = item.region
    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description or "",
        plane_count=item.plane_count,
        created_at=format_datetime(region.created_at),
        updated_at=format_datetime(region.updated_at),
    )


@router.delete("/{region_id}", status_code=204)
def delete_region_endpoint(
    region_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> None:
    """删除 Region。"""
    deleted = delete_region(db, region_id, operator_name(current_user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Region not found")
