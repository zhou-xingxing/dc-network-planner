from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_name, require_administrator
from app.exceptions import BusinessError
from app.models.switch import SwitchBusinessType
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.switch import (
    SwitchBusinessTypeCreate,
    SwitchBusinessTypeResponse,
    SwitchBusinessTypeUpdate,
)
from app.services.switch_business_type import (
    create_switch_business_type,
    delete_switch_business_type,
    list_switch_business_types,
    update_switch_business_type,
)
from app.utils.time_utils import format_datetime

router = APIRouter(
    prefix="/api/switch-business-types",
    tags=["Switch Business Types"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=PaginatedResponse[SwitchBusinessTypeResponse])
def list_switch_business_types_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SwitchBusinessTypeResponse]:
    """查询交换机业务类型列表。"""
    items, total = list_switch_business_types(db, skip=skip, limit=limit)
    return PaginatedResponse(
        items=[_business_type_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=SwitchBusinessTypeResponse, status_code=201)
def create_switch_business_type_endpoint(
    data: SwitchBusinessTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> SwitchBusinessTypeResponse:
    """创建交换机业务类型。"""
    try:
        item = create_switch_business_type(db, data, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _business_type_response(item)


@router.put("/{business_type_id}", response_model=SwitchBusinessTypeResponse)
def update_switch_business_type_endpoint(
    business_type_id: str,
    data: SwitchBusinessTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> SwitchBusinessTypeResponse:
    """更新交换机业务类型。"""
    try:
        item = update_switch_business_type(db, business_type_id, data, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="交换机业务类型不存在")
    return _business_type_response(item)


@router.delete("/{business_type_id}", status_code=204)
def delete_switch_business_type_endpoint(
    business_type_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> None:
    """删除交换机业务类型。"""
    try:
        deleted = delete_switch_business_type(db, business_type_id, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="交换机业务类型不存在")


def _business_type_response(business_type: SwitchBusinessType) -> SwitchBusinessTypeResponse:
    """将业务类型模型转换为 API 响应。"""
    return SwitchBusinessTypeResponse(
        id=business_type.id,
        code=business_type.code,
        name=business_type.name,
        created_at=format_datetime(business_type.created_at),
        updated_at=format_datetime(business_type.updated_at),
    )
