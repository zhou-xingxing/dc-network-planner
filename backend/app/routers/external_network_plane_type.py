from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_external_scope
from app.schemas.external import ExternalNetworkPlaneTypeListResponse, ExternalNetworkPlaneTypeResponse
from app.services.network_plane_type import get_plane_type_parent_names, list_plane_types
from app.utils.time_utils import format_datetime

if TYPE_CHECKING:
    from app.models.network_plane_type import NetworkPlaneType

router = APIRouter(
    prefix="/api/external/v1/network-plane-types",
    tags=["External API Network Plane Types"],
    dependencies=[Depends(require_external_scope("network-plane:read"))],
)


@router.get(
    "",
    operation_id="list_network_plane_types",
    response_model=ExternalNetworkPlaneTypeListResponse,
    summary="列出网络平面类型",
    description=(
        "使用外部 API 访问令牌分页列出系统中的全局网络平面类型。"
        "请求必须携带具备 network-plane:read scope 的外部 API 访问令牌。"
        "结果按网络平面类型名称升序返回，并通过 parent_id 和 parent_name 表示类型层级；"
        "调用方可根据 total、skip 和 limit 继续请求后续分页，直至获取完整列表。"
    ),
    response_description="按名称升序排列的网络平面类型分页列表。",
    responses={
        401: {
            "description": "未提供外部 API 访问令牌，或令牌无效、已撤销、已过期、所属用户已停用。",
            "content": {"application/json": {"example": {"detail": "外部 API 访问令牌无效或已失效"}}},
        },
        403: {
            "description": "外部 API 访问令牌缺少 network-plane:read scope。",
            "content": {"application/json": {"example": {"detail": "外部 API 访问令牌权限不足"}}},
        },
        422: {"description": "分页参数不满足取值范围。"},
    },
)
def list_external_network_plane_types(
    skip: int = Query(0, ge=0, description="跳过的记录数，从 0 开始。", examples=[0]),
    limit: int = Query(100, ge=1, le=500, description="本次最多返回的记录数，取值范围为 1 到 500。", examples=[100]),
    db: Session = Depends(get_db),
) -> ExternalNetworkPlaneTypeListResponse:
    """External OpenAPI：分页列出所有网络平面类型。"""
    items, total = list_plane_types(db, skip=skip, limit=limit)
    parent_names = get_plane_type_parent_names(db, [plane_type.id for plane_type in items])
    return ExternalNetworkPlaneTypeListResponse(
        items=[_external_plane_type_response(plane_type, parent_names) for plane_type in items],
        total=total,
        skip=skip,
        limit=limit,
    )


def _external_plane_type_response(
    plane_type: "NetworkPlaneType",
    parent_names: Mapping[str, str | None],
) -> ExternalNetworkPlaneTypeResponse:
    """将网络平面类型转换为稳定的 External API 响应。"""
    return ExternalNetworkPlaneTypeResponse(
        id=plane_type.id,
        name=plane_type.name,
        description=plane_type.description or "",
        is_private=plane_type.is_private,
        vrf=plane_type.vrf,
        parent_id=plane_type.parent_id,
        parent_name=parent_names.get(plane_type.id),
        created_at=format_datetime(plane_type.created_at),
        updated_at=format_datetime(plane_type.updated_at),
    )
