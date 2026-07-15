from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.exceptions import BusinessError
from app.schemas.external import ExternalTokenRequest, ExternalTokenResponse
from app.services.auth import authenticate_user
from app.services.external_token import create_external_access_token_for_user
from app.utils.time_utils import format_datetime

router = APIRouter(prefix="/api/external/v1/auth", tags=["External API Authentication"])


@router.post("/token", response_model=ExternalTokenResponse)
def create_external_access_token(data: ExternalTokenRequest, db: Session = Depends(get_db)) -> ExternalTokenResponse:
    """通过本地用户名密码签发短期外部 API 访问令牌。"""
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    try:
        token, raw_token = create_external_access_token_for_user(db, user, data.requested_scopes)
    except BusinessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return ExternalTokenResponse(
        access_token=raw_token,
        expires_in=settings.EXTERNAL_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        scope=sorted(data.requested_scopes),
        expires_at=format_datetime(token.expires_at),
    )
