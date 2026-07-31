from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, gen_uuid
from app.utils.time_utils import utcnow_db

if TYPE_CHECKING:
    from app.models.region import Region


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_db, onupdate=utcnow_db)

    region_permissions: Mapped[list[UserRegionPermission]] = relationship(
        "UserRegionPermission", back_populates="user", cascade="all, delete-orphan"
    )


class UserRegionPermission(Base):
    __tablename__ = "user_region_permissions"
    __table_args__ = (UniqueConstraint("user_id", "region_id", name="uq_user_region_permission"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    region_id: Mapped[str] = mapped_column(String(36), ForeignKey("regions.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_db)

    user: Mapped[User] = relationship("User", back_populates="region_permissions")
    region: Mapped[Region] = relationship("Region", back_populates="region_permissions")
