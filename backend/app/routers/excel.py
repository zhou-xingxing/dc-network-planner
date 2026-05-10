from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    ensure_region_business_write_allowed,
    get_current_user,
    operator_name,
)
from app.models.region_network_plane import RegionNetworkPlane
from app.models.user import User
from app.schemas.excel import ImportConfirmRequest, ImportError, ImportResultResponse
from app.services import excel as excel_service
from app.utils.excel_utils import build_export, generate_template

router = APIRouter(prefix="/api/excel", tags=["Excel"], dependencies=[Depends(get_current_user)])


@router.get("/template")
def download_template() -> StreamingResponse:
    """下载 Excel 导入模板。"""
    buf = generate_template()
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dc_network_planner_import_template.xlsx"},
    )


@router.post("/import/preview")
async def preview_import(
    file: UploadFile,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """上传 Excel 文件并预览导入结果。"""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls 文件")

    contents = await file.read()
    result = excel_service.preview_import(contents, db)
    return result


@router.post("/import/confirm", response_model=ImportResultResponse)
def confirm_import(
    data: ImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportResultResponse:
    """确认执行导入预览数据。"""
    region_ids: set[str] | None = excel_service.get_preview_region_ids(data.preview_id)
    result: dict[str, Any]
    if region_ids is None:
        result = {
            "success": False,
            "imported_count": 0,
            "error_count": 0,
            "errors": [{"row": 0, "errors": ["预览数据已过期，请重新上传"]}],
        }
    else:
        for region_id in region_ids:
            ensure_region_business_write_allowed(current_user, region_id)
        result = excel_service.confirm_import(data.preview_id, operator_name(current_user), db)
    return ImportResultResponse(
        success=result["success"],
        imported_count=result["imported_count"],
        error_count=result["error_count"],
        errors=[ImportError(**e) for e in result["errors"]],
    )


@router.get("/export")
def export_excel(
    region_id: Optional[str] = Query(None),
    plane_type_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出 Region 网络平面数据到 Excel。"""
    query = db.query(RegionNetworkPlane)
    if region_id:
        query = query.filter(RegionNetworkPlane.region_id == region_id)
    if plane_type_id:
        query = query.filter(RegionNetworkPlane.plane_type_id == plane_type_id)

    planes = query.order_by(RegionNetworkPlane.created_at.desc()).all()

    data = []
    for plane in planes:
        data.append(
            {
                "region_name": plane.region.name if plane.region else "",
                "plane_type_name": plane.plane_type.name if plane.plane_type else "",
                "scope": plane.scope,
                "ip_range": plane.cidr or "",
                "vlan_id": plane.vlan_id,
                "gateway_position": plane.gateway_position or "",
                "gateway_ip": plane.gateway_ip or "",
            }
        )

    buf = build_export(data)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dc_network_planner_export.xlsx"},
    )
