from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import timedelta
from typing import Any, Optional, cast

from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessError
from app.models.user import User
from app.utils.password import hash_password, verify_password
from app.utils.time_utils import utcnow


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
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> User:
    """Change the current user's password after verifying the old password."""
    if not verify_password(current_password, user.password_hash):
        raise BusinessError("原密码错误")
    user.password_hash = hash_password(new_password)
    db.flush()
    return user


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
