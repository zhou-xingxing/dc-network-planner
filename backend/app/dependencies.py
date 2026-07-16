from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import BusinessError
from app.models.user import User
from app.request_context import set_current_username
from app.services.auth import decode_access_token
from app.services.external_token import ExternalApiActor, resolve_external_api_actor
from app.services.user import get_user, get_user_permitted_region_ids

external_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="External API Bearer Token",
    description="外部 OpenAPI 访问令牌。请填写 /api/external/v1/auth/token 签发的 dcnp_ext_ 前缀 token。",
)


def _extract_bearer_token(authorization: str | None) -> str | None:
    """从 Authorization header 提取 Bearer token。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return token or None


def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """从 Bearer token 解析当前已启用用户。"""
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="未登录", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(token)
    except (BusinessError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="登录已失效", headers={"WWW-Authenticate": "Bearer"})
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="登录已失效", headers={"WWW-Authenticate": "Bearer"})
    user = get_user(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="账号不可用", headers={"WWW-Authenticate": "Bearer"})
    set_current_username(user.username)
    request.state.username = user.username
    return user


def get_external_api_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(external_bearer_scheme),
    db: Session = Depends(get_db),
) -> ExternalApiActor:
    """从不透明 Bearer token 解析外部 API 调用身份。"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未提供外部 API 访问令牌", headers={"WWW-Authenticate": "Bearer"})

    actor = resolve_external_api_actor(db, credentials.credentials)
    if not actor:
        raise HTTPException(
            status_code=401, detail="外部 API 访问令牌无效或已失效", headers={"WWW-Authenticate": "Bearer"}
        )

    set_current_username(actor.user.username)
    request.state.username = actor.user.username
    return actor


def require_external_scope(required_scope: str) -> Callable[..., ExternalApiActor]:
    """要求外部 API 访问令牌具备指定 scope。"""

    def _require_scope(actor: ExternalApiActor = Depends(get_external_api_actor)) -> ExternalApiActor:
        if required_scope not in actor.scopes:
            raise HTTPException(status_code=403, detail="外部 API 访问令牌权限不足")
        return actor

    return _require_scope


def require_administrator(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户具备 administrator 角色。"""
    if current_user.role != "administrator":
        raise HTTPException(status_code=403, detail="需要 administrator 权限")
    return current_user


def require_excel_import_user(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户是可使用 Excel 导入的普通用户。"""
    if current_user.role == "administrator":
        raise HTTPException(status_code=403, detail="administrator 不可使用 Excel 导入功能")
    return current_user


def ensure_region_business_write_allowed(current_user: User, region_id: str) -> None:
    """要求普通用户具备目标 Region 的业务数据写权限。"""
    if current_user.role == "administrator":
        raise HTTPException(status_code=403, detail="administrator 不可管理 Region 内业务数据")
    if region_id not in get_user_permitted_region_ids(current_user):
        raise HTTPException(status_code=403, detail="无权管理该 Region 的业务数据")


def require_region_business_write(
    region_id: str,
    current_user: User = Depends(get_current_user),
) -> User:
    """要求路径参数中的 Region 具备业务数据写权限。"""
    ensure_region_business_write_allowed(current_user, region_id)
    return current_user


def operator_name(current_user: User) -> str:
    """返回用于审计日志的操作者用户名。"""
    return current_user.username
