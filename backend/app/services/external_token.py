from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Literal, TypedDict

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


class ExternalAccessTokenResponseData(TypedDict):
    """管理员页面所需的外部 API 访问令牌元数据。"""

    id: str
    username: str
    owner_is_active: bool
    created_at: str
    expires_at: str


def create_external_access_token_for_user(
    db: Session,
    user: User,
    requested_scopes: list[ExternalTokenScope],
) -> tuple[ExternalAccessToken, str]:
    """为通过用户名密码认证的用户签发短期外部 API 访问令牌。

    采用 UPDATE-first 策略：先通过一条 bulk UPDATE 直接撤销该用户所有有效令牌，
    再查询被撤销的记录写入审计日志。该写操作会竞争 SQLite 写锁；并发事务通常会
    等待持锁事务提交后继续执行，若等待超过锁超时时间则失败并回滚，从而避免两个
    请求同时签发出有效令牌。
    """
    scopes = _validate_requested_scopes(user, requested_scopes)
    now = to_db_datetime(utcnow())

    # 第一步：bulk UPDATE 直接撤销；并发事务通常等待写锁，等待超时则失败并回滚
    db.query(ExternalAccessToken).filter(
        ExternalAccessToken.user_id == user.id,
        ExternalAccessToken.revoked_at.is_(None),
        ExternalAccessToken.expires_at > now,
    ).update({"revoked_at": now}, synchronize_session="fetch")

    # 第二步：查询刚刚被撤销的令牌，写入审计日志
    previous_tokens = (
        db.query(ExternalAccessToken)
        .filter(
            ExternalAccessToken.user_id == user.id,
            ExternalAccessToken.revoked_at == now,
        )
        .all()
    )
    for previous_token in previous_tokens:
        log_change(
            db,
            entity_type="external_access_token",
            entity_id=previous_token.id,
            entity_name="外部 API 访问令牌",
            action="revoke",
            operator=user.username,
            old_value="状态=有效",
            new_value="状态=已撤销",
            comment="签发新外部 API 访问令牌时自动替换旧令牌",
            operation_method="external_api",
        )

    raw_token = f"{EXTERNAL_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    expires_at = now + timedelta(minutes=settings.EXTERNAL_ACCESS_TOKEN_EXPIRE_MINUTES)
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


def list_unrevoked_unexpired_external_access_tokens(
    db: Session, skip: int = 0, limit: int = 100
) -> tuple[list[tuple[ExternalAccessToken, str, bool]], int]:
    """列出未撤销、未过期的外部 API 访问令牌及其所属用户状态。"""
    now = to_db_datetime(utcnow())
    query = (
        db.query(ExternalAccessToken, User.username, User.is_active)
        .join(User, ExternalAccessToken.user_id == User.id)
        .filter(
            ExternalAccessToken.revoked_at.is_(None),
            ExternalAccessToken.expires_at > now,
        )
    )
    total = query.count()
    rows = query.order_by(ExternalAccessToken.expires_at.asc()).offset(skip).limit(limit).all()
    tokens: list[tuple[ExternalAccessToken, str, bool]] = [(row[0], row[1], row[2]) for row in rows]
    return tokens, total


def revoke_unrevoked_external_access_token(db: Session, token_id: str, operator: str) -> ExternalAccessToken | None:
    """由管理员撤销尚未撤销的外部 API 访问令牌并写入审计日志。"""
    now = to_db_datetime(utcnow())
    token = (
        db.query(ExternalAccessToken)
        .filter(
            ExternalAccessToken.id == token_id,
            ExternalAccessToken.revoked_at.is_(None),
        )
        .first()
    )
    if not token:
        existing_token = db.get(ExternalAccessToken, token_id)
        if not existing_token:
            return None
        raise BusinessError("外部 API 访问令牌已撤销，无法重复撤销")

    token.revoked_at = now
    db.flush()
    log_change(
        db,
        entity_type="external_access_token",
        entity_id=token.id,
        entity_name="外部 API 访问令牌",
        action="revoke",
        operator=operator,
        old_value="状态=未撤销",
        new_value="状态=已撤销",
        comment="管理员手动撤销外部 API 访问令牌",
        operation_method="client",
    )
    return token


def external_access_token_to_response(
    token: ExternalAccessToken, username: str, owner_is_active: bool
) -> ExternalAccessTokenResponseData:
    """序列化管理员页面所需的外部 API 访问令牌元数据。"""
    return {
        "id": token.id,
        "username": username,
        "owner_is_active": owner_is_active,
        "created_at": format_datetime(token.created_at),
        "expires_at": format_datetime(token.expires_at),
    }


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
