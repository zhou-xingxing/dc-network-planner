from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import BusinessError
from app.models.user import User
from app.request_context import set_current_username
from app.services.auth import decode_access_token
from app.services.user import get_user, get_user_permitted_region_ids


def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current active user from a Bearer token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录", headers={"WWW-Authenticate": "Bearer"})
    token = authorization.split(" ", 1)[1].strip()
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


def require_administrator(current_user: User = Depends(get_current_user)) -> User:
    """Require administrator role."""
    if current_user.role != "administrator":
        raise HTTPException(status_code=403, detail="需要 administrator 权限")
    return current_user


def ensure_region_business_write_allowed(current_user: User, region_id: str) -> None:
    """Require a normal user permitted to write business data in the target Region."""
    if current_user.role == "administrator":
        raise HTTPException(status_code=403, detail="administrator 不可管理 Region 内业务数据")
    if region_id not in get_user_permitted_region_ids(current_user):
        raise HTTPException(status_code=403, detail="无权管理该 Region 的业务数据")


def require_region_business_write(
    region_id: str,
    current_user: User = Depends(get_current_user),
) -> User:
    """Require Region business write permission for endpoints with a region_id path parameter."""
    ensure_region_business_write_allowed(current_user, region_id)
    return current_user


def operator_name(current_user: User) -> str:
    """Return the username used as the audit operator."""
    return current_user.username
