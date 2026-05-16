from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_name, require_administrator
from app.exceptions import BusinessError
from app.models.network_plane_type import NetworkPlaneType
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.network_plane_type import PlaneTypeCreate, PlaneTypeResponse, PlaneTypeUpdate
from app.services.network_plane_type import (
    count_usages_for_plane_type,
    create_plane_type,
    delete_plane_type,
    get_plane_type,
    list_plane_types,
    update_plane_type,
)
from app.utils.time_utils import format_datetime

router = APIRouter(
    prefix="/api/network-plane-types",
    tags=["Network Plane Types"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=PaginatedResponse[PlaneTypeResponse])
def list_plane_types_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PlaneTypeResponse]:
    """查询网络平面类型列表。"""
    items, total = list_plane_types(db, skip=skip, limit=limit)
    result = []
    for pt in items:
        result.append(_plane_type_response(db, pt))
    return PaginatedResponse(items=result, total=total, skip=skip, limit=limit)


@router.post("", response_model=PlaneTypeResponse, status_code=201)
def create_plane_type_endpoint(
    data: PlaneTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> PlaneTypeResponse:
    """创建网络平面类型。"""
    try:
        pt = create_plane_type(db, data, operator_name(current_user))
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _plane_type_response(db, pt, usage_count=0)


@router.get("/{pt_id}", response_model=PlaneTypeResponse)
def get_plane_type_endpoint(pt_id: str, db: Session = Depends(get_db)) -> PlaneTypeResponse:
    """根据 ID 获取网络平面类型详情。"""
    pt = get_plane_type(db, pt_id)
    if not pt:
        raise HTTPException(status_code=404, detail="Plane type not found")
    return _plane_type_response(db, pt)


@router.put("/{pt_id}", response_model=PlaneTypeResponse)
def update_plane_type_endpoint(
    pt_id: str,
    data: PlaneTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> PlaneTypeResponse:
    """更新网络平面类型。"""
    try:
        pt = update_plane_type(db, pt_id, data, operator_name(current_user))
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not pt:
        raise HTTPException(status_code=404, detail="Plane type not found")
    return _plane_type_response(db, pt)


def _plane_type_response(db: Session, pt: NetworkPlaneType, usage_count: int | None = None) -> PlaneTypeResponse:
    return PlaneTypeResponse(
        id=pt.id,
        name=pt.name,
        description=pt.description or "",
        is_private=pt.is_private,
        vrf=pt.vrf,
        parent_id=pt.parent_id,
        parent_name=pt.parent.name if pt.parent else None,
        usage_count=count_usages_for_plane_type(db, pt.id) if usage_count is None else usage_count,
        created_at=format_datetime(pt.created_at),
        updated_at=format_datetime(pt.updated_at),
    )


@router.delete("/{pt_id}", status_code=204)
def delete_plane_type_endpoint(
    pt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> None:
    """删除网络平面类型。"""
    try:
        deleted = delete_plane_type(db, pt_id, operator_name(current_user))
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Plane type not found")
