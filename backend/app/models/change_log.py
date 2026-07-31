from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, gen_uuid
from app.utils.time_utils import utcnow_db


class ChangeLog(Base):
    __tablename__ = "change_logs"
    __table_args__ = (
        Index("idx_changelog_entity", "entity_type", "entity_id"),
        Index("idx_changelog_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(100), nullable=False)
    operation_method: Mapped[str] = mapped_column(String(30), nullable=False, default="client", server_default="client")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db)
