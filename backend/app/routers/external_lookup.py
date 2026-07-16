from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_external_scope
from app.exceptions import BusinessError
from app.schemas.lookup import LookupResponse
from app.services.lookup import lookup_region_planes

router = APIRouter(
    prefix="/api/external/v1/lookup",
    tags=["External API Lookup"],
    dependencies=[Depends(require_external_scope("network-plane:read"))],
)


@router.get(
    "",
    response_model=LookupResponse,
    summary="查询 IP 或 CIDR 所属网络平面",
    description=(
        "使用外部 API 访问令牌查询 IP 地址或 CIDR 与已规划 Region 网络平面的关系。"
        "请求必须携带具备 network-plane:read scope 的外部 API 访问令牌。"
        "当 q 为单个 IP 时，返回包含该 IP 的网络平面；当 q 为 CIDR 时，"
        "cidr_match=exact 表示仅返回 CIDR 完全一致的网络平面，"
        "cidr_match=overlap 表示返回与该 CIDR 有重叠的网络平面。"
        "响应中的 total 只统计真正命中的节点，不包含仅为展示树形上下文而返回的父级节点。"
    ),
    response_description="匹配到的网络平面树形结果和命中总数。",
    responses={
        400: {
            "description": "q 不是合法的 IP 或 CIDR。",
            "content": {"application/json": {"example": {"detail": "请输入合法的 IP 或 CIDR"}}},
        },
        401: {
            "description": "未提供外部 API 访问令牌，或令牌无效、已撤销、已过期、所属用户已停用。",
            "content": {"application/json": {"example": {"detail": "外部 API 访问令牌无效或已失效"}}},
        },
        403: {
            "description": "外部 API 访问令牌缺少 network-plane:read scope。",
            "content": {"application/json": {"example": {"detail": "外部 API 访问令牌权限不足"}}},
        },
        422: {"description": "查询参数格式或枚举取值不满足要求。"},
    },
)
def external_lookup_endpoint(
    q: str = Query(
        ...,
        min_length=1,
        description="要查询的单个 IP 地址或 CIDR，例如 10.0.0.5 或 10.0.0.0/24。",
        examples=["10.0.0.5", "10.0.0.0/24"],
    ),
    cidr_match: Literal["exact", "overlap"] = Query(
        "exact",
        description="CIDR 查询匹配方式：exact 精确匹配，overlap 重叠匹配；q 为单个 IP 时不影响结果",
    ),
    db: Session = Depends(get_db),
) -> LookupResponse:
    """外部 OpenAPI：按 IP 或 CIDR 查询 Region 网络平面。"""
    try:
        results, total = lookup_region_planes(db, q, exact=cidr_match == "exact")
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return LookupResponse(results=results, total=total)
