from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time_utils import utcnow_db

if TYPE_CHECKING:
    from app.models.rack import Rack
    from app.models.region import Region
    from app.models.switch import SwitchPort


def gen_uuid() -> str:
    return str(uuid.uuid4())


class CablingBatch(Base):
    """一次确认并持久化的布线批次。"""

    __tablename__ = "cabling_batches"
    __table_args__ = (UniqueConstraint("region_id", "name", name="uq_cabling_batch_region_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    region_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db, onupdate=utcnow_db)

    region: Mapped[Region] = relationship("Region", back_populates="cabling_batches")
    cable_entries: Mapped[list[CableEntry]] = relationship("CableEntry", back_populates="batch", passive_deletes=True)


class CableEntry(Base):
    """布线批次中一根线的线签及交换机端口到服务器端点的对应关系。"""

    __tablename__ = "cable_entries"
    __table_args__ = (
        UniqueConstraint("server_rack_id", "server_start_u", "server_port_name", name="uq_cable_entry_server_endpoint"),
        UniqueConstraint("switch_port_id", name="uq_cable_entry_switch_port"),
        UniqueConstraint("cable_label", name="uq_cable_entry_cable_label"),
        CheckConstraint("cable_sequence > 0", name="ck_cable_entry_cable_sequence_positive"),
        CheckConstraint("server_start_u > 0", name="ck_cable_entry_server_start_u_positive"),
        CheckConstraint("server_height_u > 0", name="ck_cable_entry_server_height_u_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cabling_batches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    server_rack_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("racks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    server_start_u: Mapped[int] = mapped_column(Integer, nullable=False)
    server_height_u: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    server_port_name: Mapped[str] = mapped_column(String(100), nullable=False)
    switch_port_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("switch_ports.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cable_label: Mapped[str] = mapped_column(String(100), nullable=False)
    cable_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db, onupdate=utcnow_db)

    batch: Mapped[CablingBatch] = relationship("CablingBatch", back_populates="cable_entries")
    server_rack: Mapped[Rack] = relationship("Rack", back_populates="server_cable_entries")
    switch_port: Mapped[SwitchPort] = relationship("SwitchPort", back_populates="cable_entry")
