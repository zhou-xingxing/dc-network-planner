from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time_utils import utcnow_db

if TYPE_CHECKING:
    from app.models.cabling import CableEntry
    from app.models.rack import Rack
    from app.models.region import Region


def gen_uuid() -> str:
    return str(uuid.uuid4())


class SwitchBusinessType(Base):
    """交换机组可配置的业务类型。"""

    __tablename__ = "switch_business_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_switch_business_type_code"),
        UniqueConstraint("name", name="uq_switch_business_type_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db, onupdate=utcnow_db)

    switch_groups: Mapped[list[SwitchGroup]] = relationship(
        "SwitchGroup", back_populates="business_type", passive_deletes=True
    )


class SwitchGroup(Base):
    """按业务属性组织的一组单机或 A/B 交换机。"""

    __tablename__ = "switch_groups"
    __table_args__ = (
        UniqueConstraint("name", name="uq_switch_group_name"),
        CheckConstraint("group_mode IN ('pair', 'single')", name="ck_switch_group_mode"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    region_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("switch_business_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db, onupdate=utcnow_db)

    region: Mapped[Region] = relationship("Region", back_populates="switch_groups")
    business_type: Mapped[SwitchBusinessType] = relationship("SwitchBusinessType", back_populates="switch_groups")
    switches: Mapped[list[Switch]] = relationship("Switch", back_populates="switch_group", passive_deletes=True)


class Switch(Base):
    """Region 内上架到机柜并可加入一个交换机组的交换机。"""

    __tablename__ = "switches"
    __table_args__ = (
        UniqueConstraint("name", name="uq_switch_name"),
        UniqueConstraint("switch_group_id", "member_role", name="uq_switch_group_member_role"),
        CheckConstraint("start_u > 0", name="ck_switch_start_u_positive"),
        CheckConstraint("height_u > 0", name="ck_switch_height_u_positive"),
        CheckConstraint("port_speed_mbps > 0", name="ck_switch_port_speed_mbps_positive"),
        CheckConstraint(
            "member_role IS NULL OR member_role IN ('a', 'b', 'single')",
            name="ck_switch_member_role",
        ),
        CheckConstraint(
            "(switch_group_id IS NULL AND member_role IS NULL) OR "
            "(switch_group_id IS NOT NULL AND member_role IS NOT NULL)",
            name="ck_switch_group_member_pairing",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    rack_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("racks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    switch_group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("switch_groups.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    member_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    port_speed_mbps: Mapped[int] = mapped_column(Integer, nullable=False)
    start_u: Mapped[int] = mapped_column(Integer, nullable=False)
    height_u: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db, onupdate=utcnow_db)

    rack: Mapped[Rack] = relationship("Rack", back_populates="switches")
    switch_group: Mapped[SwitchGroup | None] = relationship("SwitchGroup", back_populates="switches")
    ports: Mapped[list[SwitchPort]] = relationship(
        "SwitchPort", back_populates="switch", cascade="all, delete-orphan", passive_deletes=True
    )


class SwitchPort(Base):
    """交换机侧可参与布线规划的物理端口。"""

    __tablename__ = "switch_ports"
    __table_args__ = (
        UniqueConstraint("switch_id", "port_number", name="uq_switch_port_number"),
        CheckConstraint("port_number > 0", name="ck_switch_port_number_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    switch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("switches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    port_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db, onupdate=utcnow_db)

    switch: Mapped[Switch] = relationship("Switch", back_populates="ports")
    cable_entry: Mapped[CableEntry | None] = relationship(
        "CableEntry", back_populates="switch_port", passive_deletes=True
    )
