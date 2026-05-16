from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import BusinessError
from app.schemas.lookup import LookupResponse
from app.services.lookup import lookup_region_planes

router = APIRouter(prefix="/api/lookup", tags=["Lookup"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=LookupResponse)
def lookup_endpoint(
    q: str = Query(..., min_length=1),
    exact: bool = Query(True),
    db: Session = Depends(get_db),
) -> LookupResponse:
    """按 IP 或 CIDR 查询 Region 网络平面。"""
    try:
        results, total = lookup_region_planes(db, q, exact)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return LookupResponse(results=results, total=total)
