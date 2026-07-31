from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_name, require_region_business_write
from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.rack import (
    RackColumnListResponse,
    RackColumnSummary,
    RackCreate,
    RackResponse,
    RackUpdate,
)
from app.services.rack import (
    RackColumnWithCounts,
    RackWithCounts,
    create_racks,
    delete_rack,
    list_rack_columns,
    list_racks,
    update_rack,
)
from app.utils.time_utils import format_datetime

router = APIRouter(
    prefix="/api/regions/{region_id}/racks",
    tags=["Racks"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=PaginatedResponse[RackResponse])
def list_racks_endpoint(
    region_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    room_name: str | None = Query(None),
    rack_column: str | None = Query(None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[RackResponse]:
    """查询 Region 内的机柜列表。"""
    try:
        items, total = list_racks(
            db,
            region_id,
            skip=skip,
            limit=limit,
            search=search,
            room_name=room_name,
            rack_column=rack_column,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PaginatedResponse(
        items=[_rack_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=list[RackResponse], status_code=201)
def create_racks_endpoint(
    region_id: str,
    data: RackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> list[RackResponse]:
    """在 Region 内按结构化位置原子创建一个或多个机柜。"""
    try:
        items = create_racks(db, region_id, data, operator_name(current_user))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return [_rack_response(item) for item in items]


@router.get("/columns", response_model=RackColumnListResponse)
def list_rack_columns_endpoint(
    region_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> RackColumnListResponse:
    """按机房和机柜列聚合 Region 内的机柜及资源数量。"""
    try:
        items, total_columns, total_racks = list_rack_columns(
            db,
            region_id,
            skip=skip,
            limit=limit,
            search=search,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RackColumnListResponse(
        items=[_rack_column_response(item) for item in items],
        total_columns=total_columns,
        total_racks=total_racks,
        skip=skip,
        limit=limit,
    )


@router.put("/{rack_id}", response_model=RackResponse)
def update_rack_endpoint(
    region_id: str,
    rack_id: str,
    data: RackUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> RackResponse:
    """更新机柜。"""
    try:
        item = update_rack(db, region_id, rack_id, data, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="机柜不存在")
    return _rack_response(item)


@router.delete("/{rack_id}", status_code=204)
def delete_rack_endpoint(
    region_id: str,
    rack_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> None:
    """删除机柜。"""
    try:
        deleted = delete_rack(db, region_id, rack_id, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="机柜不存在")


def _rack_response(item: RackWithCounts) -> RackResponse:
    """将 Service 聚合结果转换为机柜 API 响应。"""
    rack = item.rack
    return RackResponse(
        id=rack.id,
        region_id=rack.region_id,
        region_name=item.region_name,
        name=rack.name,
        room_name=rack.room_name,
        rack_column=rack.rack_column,
        rack_number=rack.rack_number,
        u_height=rack.u_height,
        switch_count=item.switch_count,
        cable_count=item.cable_count,
        created_at=format_datetime(rack.created_at),
        updated_at=format_datetime(rack.updated_at),
    )


def _rack_column_response(item: RackColumnWithCounts) -> RackColumnSummary:
    """将 Service 聚合结果转换为机柜列响应。"""
    return RackColumnSummary(
        room_name=item.room_name,
        rack_column=item.rack_column,
        rack_count=item.rack_count,
        switch_count=item.switch_count,
        cable_count=item.cable_count,
    )
