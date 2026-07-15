from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessError
from app.models.external_access_token import ExternalAccessToken
from app.models.user import User
from app.services.change_log import log_change
from app.utils.time_utils import format_datetime, to_db_datetime, utcnow

ExternalTokenScope = Literal[
    "network-plane:read",
    "network-plane:import-preview",
    "network-plane:import-apply",
]

EXTERNAL_TOKEN_PREFIX = "dcnp_ext_"
ALL_EXTERNAL_SCOPES: frozenset[str] = frozenset(
    {
        "network-plane:read",
        "network-plane:import-preview",
        "network-plane:import-apply",
    }
)
ADMIN_EXTERNAL_SCOPES: frozenset[str] = frozenset({"network-plane:read"})


def create_external_access_token_for_user(
    db: Session,
    user: User,
    requested_scopes: list[ExternalTokenScope],
) -> tuple[ExternalAccessToken, str]:
    """为通过用户名密码认证的用户签发短期外部 API 访问令牌。"""
    scopes = _validate_requested_scopes(user, requested_scopes)
    raw_token = f"{EXTERNAL_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    expires_at = to_db_datetime(utcnow() + timedelta(minutes=settings.EXTERNAL_ACCESS_TOKEN_EXPIRE_MINUTES))
    token = ExternalAccessToken(
        token_hash=_hash_token(raw_token),
        user_id=user.id,
        scopes=json.dumps(sorted(scopes), ensure_ascii=False),
        expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    log_change(
        db,
        entity_type="external_access_token",
        entity_id=token.id,
        entity_name="外部 API 访问令牌",
        action="create",
        operator=user.username,
        new_value=f"scope={','.join(sorted(scopes))}; expires_at={format_datetime(token.expires_at)}",
        comment="签发外部 API 访问令牌",
        operation_method="external_api",
    )
    return token, raw_token


def _validate_requested_scopes(user: User, requested_scopes: list[ExternalTokenScope]) -> frozenset[str]:
    requested = frozenset(requested_scopes)
    if len(requested) != len(requested_scopes):
        raise BusinessError("requested_scopes 不能包含重复项")
    allowed_scopes = ADMIN_EXTERNAL_SCOPES if user.role == "administrator" else ALL_EXTERNAL_SCOPES
    if not requested.issubset(allowed_scopes):
        raise BusinessError("当前用户无权申请所请求的外部 API 权限")
    return requested


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
