from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_name, require_region_business_write
from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.user import User
from app.schemas.region_plane import (
    CidrRecommendationResponse,
    ParentPlaneContextResponse,
    RegionPlaneCreate,
    RegionPlaneUpdate,
)
from app.services.region_plane import (
    create_plane_for_region,
    delete_plane_for_region,
    get_parent_plane_context,
    get_region_plane_tree_for_region,
    recommend_cidr_for_region,
    serialize_parent_plane_context,
    serialize_region_plane_result,
    update_plane_for_region,
)

router = APIRouter(
    prefix="/api/regions/{region_id}/planes",
    tags=["Region Planes"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
def list_region_planes_endpoint(region_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """查询 Region 下所有网络平面的树形结构。"""
    tree = get_region_plane_tree_for_region(db, region_id)
    if tree is None:
        raise HTTPException(status_code=404, detail="Region 不存在")
    return tree


@router.get("/parent-context", response_model=ParentPlaneContextResponse)
def get_parent_plane_context_endpoint(
    region_id: str,
    plane_type_id: str = Query(..., min_length=1),
    scope: str = Query("Global", max_length=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """查询指定 Region 中网络平面类型和 scope 对应的父平面实例。"""
    try:
        context = get_parent_plane_context(db, region_id, plane_type_id, scope)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return serialize_parent_plane_context(context)


@router.get("/cidr-recommendation", response_model=CidrRecommendationResponse)
def recommend_cidr_endpoint(
    region_id: str,
    plane_type_id: str = Query(..., min_length=1),
    prefix_length: int = Query(..., ge=0, le=128),
    scope: str = Query("Global", max_length=100),
    db: Session = Depends(get_db),
) -> CidrRecommendationResponse:
    """按实际父平面和目标掩码推荐可用 CIDR。"""
    try:
        recommendation = recommend_cidr_for_region(
            db,
            region_id,
            plane_type_id,
            prefix_length,
            scope,
        )
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return CidrRecommendationResponse(
        cidr=recommendation.cidr,
        parent_plane_id=recommendation.parent_plane.id,
        parent_cidr=recommendation.parent_plane.cidr,
    )


@router.post("", status_code=201)
def create_plane_endpoint(
    region_id: str,
    data: RegionPlaneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> dict[str, Any]:
    """为 Region 创建网络平面实例。"""
    try:
        result = create_plane_for_region(
            db,
            region_id,
            data.plane_type_id,
            data.cidr,
            operator_name(current_user),
            scope=data.scope,
            vlan_id=data.vlan_id,
            gateway_position=data.gateway_position,
            gateway_ip=data.gateway_ip,
        )
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return serialize_region_plane_result(result)


@router.put("/{plane_id}")
def update_plane_endpoint(
    region_id: str,
    plane_id: str,
    data: RegionPlaneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> dict[str, Any]:
    """更新 Region 网络平面实例；网络平面类型不可修改。"""
    try:
        result = update_plane_for_region(
            db,
            region_id,
            plane_id,
            operator_name(current_user),
            scope=data.scope,
            cidr=data.cidr,
            vlan_id=data.vlan_id,
            gateway_position=data.gateway_position,
            gateway_ip=data.gateway_ip,
        )
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Region 网络平面不存在")
    return serialize_region_plane_result(result)


@router.delete("/{plane_id}", status_code=204)
def delete_plane_endpoint(
    region_id: str,
    plane_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> None:
    """删除平面节点。"""
    try:
        deleted = delete_plane_for_region(db, region_id, plane_id, operator_name(current_user))
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Region 网络平面不存在")
