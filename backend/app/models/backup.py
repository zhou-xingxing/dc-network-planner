from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time_utils import utcnow_db


def gen_uuid() -> str:
    return str(uuid.uuid4())


class BackupConfig(Base):
    __tablename__ = "backup_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cron_expression: Mapped[str] = mapped_column(
        String(100), nullable=False, default="0 2 * * *"
    )
    backup_file_prefix: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="dc_network_planner_data_backup_",
    )
    method: Mapped[str] = mapped_column(String(30), nullable=False, default="local")
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    access_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    secret_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bucket: Mapped[str | None] = mapped_column(String(200), nullable=True)
    object_prefix: Mapped[str | None] = mapped_column(String(300), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_db
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_db, onupdate=utcnow_db
    )


class BackupRecord(Base):
    __tablename__ = "backup_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    target: Mapped[str | None] = mapped_column(String(800), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow_db
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
