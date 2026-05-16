from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessError
from app.models.region import Region
from app.models.user import User, UserRegionPermission
from app.schemas.user import UserCreate, UserUpdate
from app.utils.password import hash_password
from app.utils.time_utils import format_datetime


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
