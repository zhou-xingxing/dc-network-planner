from typing import TYPE_CHECKING, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user,
    operator_name,
    require_administrator,
    require_region_business_write,
)
from app.exceptions import BusinessError
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.region import (
    RegionCreate,
    RegionDetailResponse,
    RegionPlaneCreate,
    RegionPlaneUpdate,
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
from app.services.region_plane import (
    disable_plane_for_region,
    enable_plane_for_region,
    get_region_plane_tree,
    normalize_plane_scope,
    update_plane_for_region,
)
from app.utils.time_utils import format_datetime

if TYPE_CHECKING:
    from app.models.region_network_plane import RegionNetworkPlane

router = APIRouter(prefix="/api/regions", tags=["Regions"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=PaginatedResponse[RegionResponse])
def list_regions_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[RegionResponse]:
    """查询 Region 列表。"""
    regions, total = list_regions(db, skip=skip, limit=limit, search=search)
    items = []
    for r in regions:
        items.append(
            RegionResponse(
                id=r.id,
                name=r.name,
                description=r.description or "",
                plane_count=len(r.region_planes) if r.region_planes else 0,
                created_at=format_datetime(r.created_at),
                updated_at=format_datetime(r.updated_at),
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
    region = update_region(db, region_id, data, operator_name(current_user))
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description or "",
        plane_count=len(region.region_planes) if region.region_planes else 0,
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


# Region-Plan association endpoints
@router.get("/{region_id}/planes")
def list_region_planes_endpoint(region_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """查询 Region 下所有网络平面的树形结构。"""
    from app.services.region import get_region

    region = get_region(db, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return get_region_plane_tree(db, region_id)


@router.post("/{region_id}/planes", status_code=201)
def enable_plane_endpoint(
    region_id: str,
    data: RegionPlaneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> dict[str, Any]:
    """为 Region 启用根级网络平面。"""
    from app.models.network_plane_type import NetworkPlaneType
    from app.services.region import get_region

    region = get_region(db, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    pt = db.query(NetworkPlaneType).filter(NetworkPlaneType.id == data.plane_type_id).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Plane type not found")
    try:
        rp, gateway_ip_warning = enable_plane_for_region(
            db,
            region_id,
            data.plane_type_id,
            data.cidr,
            operator_name(current_user),
            scope=normalize_plane_scope(data.scope),
            vlan_id=data.vlan_id,
            gateway_position=data.gateway_position,
            gateway_ip=data.gateway_ip,
        )
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _serialize_region_plane(db, rp, gateway_ip_warning)


@router.put("/{region_id}/planes/{plane_id}")
def update_plane_endpoint(
    region_id: str,
    plane_id: str,
    data: RegionPlaneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> dict[str, Any]:
    """更新 Region 网络平面实例；网络平面类型不可修改。"""
    try:
        rp, gateway_ip_warning = update_plane_for_region(
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
    if not rp:
        raise HTTPException(status_code=404, detail="Region plane association not found")
    return _serialize_region_plane(db, rp, gateway_ip_warning)


@router.delete("/{region_id}/planes/{plane_id}", status_code=204)
def disable_plane_endpoint(
    region_id: str,
    plane_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_region_business_write),
) -> None:
    """删除平面节点（级联删除子平面）。"""
    deleted = disable_plane_for_region(db, region_id, plane_id, operator_name(current_user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Region plane association not found")


def _serialize_region_plane(
    db: Session,
    rp: "RegionNetworkPlane",
    gateway_ip_warning: str | None = None,
) -> dict[str, Any]:
    """序列化 Region 网络平面，并按当前树规则补充父节点 ID。"""
    from app.models.region_network_plane import RegionNetworkPlane

    pt = rp.plane_type
    parent_plane_id = None
    if pt and pt.parent_id:
        parent_plane = (
            db.query(RegionNetworkPlane)
            .filter(
                RegionNetworkPlane.region_id == rp.region_id,
                RegionNetworkPlane.plane_type_id == pt.parent_id,
                RegionNetworkPlane.scope == rp.scope,
            )
            .first()
        )
        if not parent_plane and rp.scope != "Global":
            parent_plane = (
                db.query(RegionNetworkPlane)
                .filter(
                    RegionNetworkPlane.region_id == rp.region_id,
                    RegionNetworkPlane.plane_type_id == pt.parent_id,
                    RegionNetworkPlane.scope == "Global",
                )
                .first()
            )
        parent_plane_id = parent_plane.id if parent_plane else None

    return {
        "id": rp.id,
        "region_id": rp.region_id,
        "plane_type_id": rp.plane_type_id,
        "plane_type_name": pt.name if pt else "",
        "scope": rp.scope,
        "cidr": rp.cidr,
        "vlan_id": rp.vlan_id,
        "gateway_position": rp.gateway_position,
        "gateway_ip": rp.gateway_ip,
        "gateway_ip_warning": gateway_ip_warning,
        "parent_id": parent_plane_id,
        "plane_type_parent_id": pt.parent_id if pt else None,
        "created_at": format_datetime(rp.created_at),
        "updated_at": format_datetime(rp.updated_at),
        "children": [],
    }
