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


@router.post(
    "/token",
    operation_id="issue_external_access_token",
    response_model=ExternalTokenResponse,
    summary="签发外部 API 访问令牌",
    description=(
        "使用本地账号用户名和密码签发短期外部 API 访问令牌。"
        "令牌为 dcnp_ext_ 前缀的不透明随机字符串，原始值只在本响应中返回一次；"
        "数据库仅保存 SHA-256 哈希。同一用户重新签发时会自动撤销此前仍有效的外部令牌。"
    ),
    response_description="签发成功的外部 API 访问令牌及其有效期信息。",
    responses={
        401: {
            "description": "用户名或密码错误，或账号已停用。",
            "content": {"application/json": {"example": {"detail": "用户名或密码错误"}}},
        },
        403: {
            "description": "当前用户无权申请请求的 scope。",
            "content": {"application/json": {"example": {"detail": "当前用户无权申请所请求的外部 API 权限"}}},
        },
        422: {"description": "请求体格式或字段约束不满足要求。"},
    },
)
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
        token_type="bearer",
        expires_in=settings.EXTERNAL_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        scope=sorted(data.requested_scopes),
        expires_at=format_datetime(token.expires_at),
    )
