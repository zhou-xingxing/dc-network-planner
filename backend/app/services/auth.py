from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from typing import Any, Optional, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessError
from app.models.region import Region
from app.models.user import User, UserRegionPermission
from app.schemas.user import UserCreate, UserUpdate
from app.utils.time_utils import format_datetime, utcnow

PASSWORD_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash."""
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_raw.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_raw.encode("ascii"))
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_access_token(user: User) -> str:
    """Create a signed HS256 JWT access token."""
    now = utcnow()
    expires = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return _encode_jwt(payload)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed HS256 JWT access token."""
    parts = token.split(".")
    if len(parts) != 3:
        raise BusinessError("Invalid token")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected_signature = _sign(signing_input)
    actual_signature = _b64decode(parts[2])
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise BusinessError("Invalid token")
    payload = cast(dict[str, Any], json.loads(_b64decode(parts[1]).decode("utf-8")))
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(utcnow().timestamp()):
        raise BusinessError("Token expired")
    return payload


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate active user by username and password."""
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_user(db: Session, user_id: str) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()


def list_users(db: Session, skip: int = 0, limit: int = 100) -> tuple[list[User], int]:
    """List users ordered by username."""
    query = db.query(User)
    total = query.count()
    users = query.order_by(User.username.asc()).offset(skip).limit(limit).all()
    return users, total


def create_user(db: Session, data: UserCreate) -> User:
    """Create a local user and assign optional Region permissions."""
    if get_user_by_username(db, data.username):
        raise BusinessError("用户名已存在")
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=data.is_active,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        if _is_username_unique_conflict(exc):
            raise BusinessError("用户名已存在") from exc
        raise
    _replace_user_region_permissions(db, user, data.permitted_region_ids)
    db.flush()
    return user


def update_user(db: Session, user_id: str, data: UserUpdate) -> Optional[User]:
    """Update user profile, role, active status, and Region permissions."""
    user = get_user(db, user_id)
    if not user:
        return None
    if data.role is not None and data.role != user.role:
        _ensure_not_last_administrator(db, user, target_role=data.role)
        user.role = data.role
    if data.is_active is not None and data.is_active != user.is_active:
        if data.is_active is False:
            _ensure_not_last_administrator(db, user, target_active=False)
        user.is_active = data.is_active
    if data.permitted_region_ids is not None:
        _replace_user_region_permissions(db, user, data.permitted_region_ids)
    db.flush()
    return user


def reset_password(db: Session, user_id: str, password: str) -> Optional[User]:
    """Reset a user's password."""
    user = get_user(db, user_id)
    if not user:
        return None
    user.password_hash = hash_password(password)
    db.flush()
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> User:
    """Change the current user's password after verifying the old password."""
    if not verify_password(current_password, user.password_hash):
        raise BusinessError("原密码错误")
    user.password_hash = hash_password(new_password)
    db.flush()
    return user


def delete_user(db: Session, user_id: str) -> bool:
    """Delete a user."""
    user = get_user(db, user_id)
    if not user:
        return False
    db.delete(user)
    db.flush()
    return True


def ensure_bootstrap_admin(db: Session) -> None:
    """Create the bootstrap administrator when the user table is empty."""
    if db.query(User).count() > 0:
        return
    admin = User(
        username=settings.BOOTSTRAP_ADMIN_USERNAME,
        password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
        role="administrator",
        is_active=True,
    )
    db.add(admin)
    db.flush()


def user_to_response(user: User) -> dict[str, Any]:
    """Serialize a user for API responses."""
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "permitted_regions": [
            {"id": permission.region.id, "name": permission.region.name}
            for permission in sorted(
                user.region_permissions,
                key=lambda permission: (
                    permission.region.name if permission.region else "",
                    permission.region_id,
                ),
            )
            if permission.region
        ],
        "created_at": format_datetime(user.created_at),
        "updated_at": format_datetime(user.updated_at),
    }


def current_user_to_response(user: User) -> dict[str, Any]:
    """Serialize current user and coarse permissions."""
    permissions = ["read:all"]
    if user.role == "administrator":
        permissions.extend(["manage:users", "manage:global-config", "manage:region-metadata"])
    else:
        permissions.append("manage:assigned-region-business")
    return {**user_to_response(user), "permissions": permissions}


def get_user_permitted_region_ids(user: User) -> set[str]:
    """Return the Region IDs that a user is permitted to write."""
    return {permission.region_id for permission in user.region_permissions}


def _replace_user_region_permissions(db: Session, user: User, permitted_region_ids: list[str]) -> None:
    existing_regions = (
        {r.id for r in db.query(Region).filter(Region.id.in_(permitted_region_ids)).all()}
        if permitted_region_ids
        else set()
    )
    missing = set(permitted_region_ids) - existing_regions
    if missing:
        raise BusinessError(f"Region 不存在: {', '.join(sorted(missing))}")
    user.region_permissions.clear()
    db.flush()
    for region_id in sorted(existing_regions):
        user.region_permissions.append(UserRegionPermission(region_id=region_id))


def _ensure_not_last_administrator(
    db: Session,
    user: User,
    target_role: Optional[str] = None,
    target_active: Optional[bool] = None,
) -> None:
    new_role = target_role if target_role is not None else user.role
    new_active = target_active if target_active is not None else user.is_active
    if user.role != "administrator" or (new_role == "administrator" and new_active):
        return
    active_admins = db.query(User).filter(User.role == "administrator", User.is_active.is_(True)).count()
    if active_admins <= 1:
        raise BusinessError("至少需要保留一个启用的 administrator")


def _is_username_unique_conflict(exc: IntegrityError) -> bool:
    message = str(exc.orig).lower()
    return "username" in message and ("unique" in message or "duplicate" in message)


def _encode_jwt(payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_raw = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_raw = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_raw}.{payload_raw}".encode("ascii")
    return f"{header_raw}.{payload_raw}.{_b64encode(_sign(signing_input))}"


def _sign(signing_input: bytes) -> bytes:
    return hmac.new(settings.JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))
