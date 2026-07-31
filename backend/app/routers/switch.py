from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_name, require_region_business_write
from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.user import User
from app.routers.switch_response import build_switch_response
from app.schemas.common import PaginatedResponse
from app.schemas.switch import (
    SwitchPortBulkCreate,
    SwitchPortResponse,
    SwitchResponse,
    SwitchUpdate,
)
from app.services.switch import (
    SwitchPortWithOccupancy,
    create_switch_ports_bulk,
    delete_switch,
    delete_switch_port,
    list_switch_ports,
    list_switches,
    update_switch,
)
from app.utils.time_utils import format_datetime

router = APIRouter(
    prefix="/api/regions/{region_id}/switches",
    tags=["Switches"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=PaginatedResponse[SwitchResponse])
def list_switches_endpoint(
    region_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    rack_id: str | None = Query(None),
    switch_group_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SwitchResponse]:
    """查询 Region 内的交换机列表。"""
    try:
        items, total = list_switches(
            db,
            region_id,
            skip=skip,
            limit=limit,
            search=search,
            rack_id=rack_id,
            switch_group_id=switch_group_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PaginatedResponse(
        items=[build_switch_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.put("/{switch_id}", response_model=SwitchResponse)
def update_switch_endpoint(
    region_id: str,
    switch_id: str,
    data: SwitchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> SwitchResponse:
    """更新交换机。"""
    try:
        item = update_switch(db, region_id, switch_id, data, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="交换机不存在")
    return build_switch_response(item)


@router.delete("/{switch_id}", status_code=204)
def delete_switch_endpoint(
    region_id: str,
    switch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> None:
    """删除交换机。"""
    try:
        deleted = delete_switch(db, region_id, switch_id, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="交换机不存在")


@router.get("/{switch_id}/ports", response_model=PaginatedResponse[SwitchPortResponse])
def list_switch_ports_endpoint(
    region_id: str,
    switch_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    card_number: int | None = Query(None, ge=0),
    subcard_number: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SwitchPortResponse]:
    """查询交换机端口列表及占用状态。"""
    result = list_switch_ports(
        db,
        region_id,
        switch_id,
        skip=skip,
        limit=limit,
        card_number=card_number,
        subcard_number=subcard_number,
    )
    if not result:
        raise HTTPException(status_code=404, detail="交换机不存在")
    items, total = result
    return PaginatedResponse(
        items=[_switch_port_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/{switch_id}/ports/bulk", response_model=list[SwitchPortResponse], status_code=201)
def create_switch_ports_bulk_endpoint(
    region_id: str,
    switch_id: str,
    data: SwitchPortBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> list[SwitchPortResponse]:
    """批量创建交换机连续端口。"""
    try:
        items = create_switch_ports_bulk(db, region_id, switch_id, data, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if items is None:
        raise HTTPException(status_code=404, detail="交换机不存在")
    return [_switch_port_response(item) for item in items]


@router.delete("/{switch_id}/ports/{port_id}", status_code=204)
def delete_switch_port_endpoint(
    region_id: str,
    switch_id: str,
    port_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> None:
    """删除交换机端口。"""
    try:
        deleted = delete_switch_port(db, region_id, switch_id, port_id, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="交换机或端口不存在")


def _switch_port_response(item: SwitchPortWithOccupancy) -> SwitchPortResponse:
    """将 Service 聚合结果转换为交换机端口 API 响应。"""
    port = item.switch_port
    return SwitchPortResponse(
        id=port.id,
        switch_id=port.switch_id,
        card_number=port.card_number,
        subcard_number=port.subcard_number,
        port_number=port.port_number,
        is_occupied=item.cable_entry_id is not None,
        cable_entry_id=item.cable_entry_id,
        created_at=format_datetime(port.created_at),
        updated_at=format_datetime(port.updated_at),
    )
