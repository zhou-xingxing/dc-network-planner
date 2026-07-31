from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_name, require_region_business_write
from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.user import User
from app.routers.switch_response import build_switch_response
from app.schemas.common import PaginatedResponse
from app.schemas.switch import (
    SwitchGroupCreate,
    SwitchGroupCreateResponse,
    SwitchGroupMode,
    SwitchGroupReadinessIssueResponse,
    SwitchGroupResponse,
    SwitchGroupUpdate,
)
from app.services.switch_group import (
    SwitchGroupCreateResult,
    SwitchGroupWithStatus,
    create_switch_group_with_members,
    delete_switch_group,
    list_switch_groups,
    update_switch_group,
)
from app.utils.time_utils import format_datetime

router = APIRouter(
    prefix="/api/regions/{region_id}/switch-groups",
    tags=["Switch Groups"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=PaginatedResponse[SwitchGroupResponse])
def list_switch_groups_endpoint(
    region_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    business_type_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SwitchGroupResponse]:
    """查询 Region 内的交换机组列表。"""
    try:
        items, total = list_switch_groups(
            db,
            region_id,
            skip=skip,
            limit=limit,
            search=search,
            business_type_id=business_type_id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PaginatedResponse(
        items=[_switch_group_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=SwitchGroupCreateResponse, status_code=201)
def create_switch_group_endpoint(
    region_id: str,
    data: SwitchGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> SwitchGroupCreateResponse:
    """在 Region 内原子创建交换机组及完整成员。"""
    try:
        result = create_switch_group_with_members(db, region_id, data, operator_name(current_user))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _switch_group_create_response(result)


@router.put("/{group_id}", response_model=SwitchGroupResponse)
def update_switch_group_endpoint(
    region_id: str,
    group_id: str,
    data: SwitchGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> SwitchGroupResponse:
    """更新交换机组。"""
    try:
        item = update_switch_group(db, region_id, group_id, data, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="交换机组不存在")
    return _switch_group_response(item)


@router.delete("/{group_id}", status_code=204)
def delete_switch_group_endpoint(
    region_id: str,
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> None:
    """删除交换机组。"""
    try:
        deleted = delete_switch_group(db, region_id, group_id, operator_name(current_user))
    except BusinessError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="交换机组不存在")


def _switch_group_response(item: SwitchGroupWithStatus) -> SwitchGroupResponse:
    """将 Service 聚合结果转换为交换机组 API 响应。"""
    group = item.switch_group
    return SwitchGroupResponse(
        id=group.id,
        region_id=group.region_id,
        region_name=item.region_name,
        business_type_id=group.business_type_id,
        business_type_code=item.business_type.code,
        business_type_name=item.business_type.name,
        name=group.name,
        group_mode=_to_switch_group_mode(group.group_mode),
        member_count=item.member_count,
        is_member_config_ready=item.is_member_config_ready,
        readiness_issues=[
            SwitchGroupReadinessIssueResponse(code=issue.code, message=issue.message) for issue in item.readiness_issues
        ],
        created_at=format_datetime(group.created_at),
        updated_at=format_datetime(group.updated_at),
    )


def _to_switch_group_mode(value: str) -> SwitchGroupMode:
    """校验数据库中的交换机组模式并收窄类型。"""
    if value == "pair":
        return "pair"
    if value == "single":
        return "single"
    raise HTTPException(status_code=500, detail=f"无效的交换机组模式: {value}")


def _switch_group_create_response(result: SwitchGroupCreateResult) -> SwitchGroupCreateResponse:
    """将组合创建结果转换为 API 响应。"""
    return SwitchGroupCreateResponse(
        group=_switch_group_response(result.group),
        members=[build_switch_response(item) for item in result.members],
    )
