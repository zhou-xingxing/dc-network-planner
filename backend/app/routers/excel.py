from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    ensure_region_business_write_allowed,
    get_current_user,
    operator_name,
    require_excel_import_user,
)
from app.exceptions import BusinessError
from app.models.network_plane_type import NetworkPlaneType
from app.models.region import Region
from app.models.user import User
from app.schemas.excel import ImportConfirmRequest, ImportError, ImportResultResponse
from app.services import excel as excel_service
from app.utils.excel_utils import generate_template

router = APIRouter(prefix="/api/excel", tags=["Excel"], dependencies=[Depends(get_current_user)])


@router.get("/template")
def download_template(db: Session = Depends(get_db)) -> StreamingResponse:
    """下载 Excel 导入模板。"""
    region_names = [name for (name,) in db.query(Region.name).order_by(Region.name.asc()).all()]
    plane_type_names = [name for (name,) in db.query(NetworkPlaneType.name).order_by(NetworkPlaneType.name.asc()).all()]
    buf = generate_template(region_names=region_names, plane_type_names=plane_type_names)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dc_network_planner_import_template.xlsx"},
    )


@router.post("/import/preview")
async def preview_import(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_excel_import_user),
) -> dict[str, Any]:
    """上传 Excel 文件并预览导入结果。"""
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    contents = await file.read()
    try:
        result = excel_service.preview_import(contents, db, current_user)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/import/confirm", response_model=ImportResultResponse)
def confirm_import(
    data: ImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_excel_import_user),
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
    region_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出 Region 网络平面数据到 Excel。"""
    buf = excel_service.export_region_planes(db, region_id=region_id)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dc_network_planner_export.xlsx"},
    )
