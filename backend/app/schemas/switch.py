from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.schemas.common import (
    PartialUpdateModel,
    TrimmedNonEmptyString,
    TrimmedNonEmptyString50,
    TrimmedNonEmptyString100,
)

SwitchGroupMode = Literal["pair", "single"]
SwitchMemberRole = Literal["a", "b", "single"]
SwitchGroupReadinessIssueCode = Literal[
    "MISSING_MEMBER_A",
    "MISSING_MEMBER_B",
    "MISSING_SINGLE_MEMBER",
    "UNEXPECTED_MEMBER_COUNT",
    "PORT_SPEED_MISMATCH",
]
# 限制单个请求创建的端口数量，避免批量写入规模失控。
MAX_SWITCH_PORT_BATCH_SIZE = 128


class SwitchBusinessTypeBase(BaseModel):
    """交换机业务类型共享字段。"""

    code: TrimmedNonEmptyString50
    name: TrimmedNonEmptyString100


class SwitchBusinessTypeCreate(SwitchBusinessTypeBase):
    """创建交换机业务类型请求。"""


class SwitchBusinessTypeUpdate(PartialUpdateModel):
    """更新交换机业务类型请求。"""

    code: TrimmedNonEmptyString50 | SkipJsonSchema[None] = None
    name: TrimmedNonEmptyString100 | SkipJsonSchema[None] = None


class SwitchBusinessTypeResponse(SwitchBusinessTypeBase):
    """交换机业务类型响应。"""

    id: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class SwitchGroupBase(BaseModel):
    """交换机组共享字段。"""

    business_type_id: TrimmedNonEmptyString
    name: TrimmedNonEmptyString100
    group_mode: SwitchGroupMode


class SwitchPortBulkCreate(BaseModel):
    """批量创建连续交换机端口请求。"""

    card_number: int = Field(1, ge=0)
    subcard_number: int = Field(0, ge=0)
    start_port_number: int = Field(..., gt=0)
    end_port_number: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_port_range(self) -> "SwitchPortBulkCreate":
        """校验端口范围方向和单次生成数量。"""
        if self.end_port_number < self.start_port_number:
            raise ValueError("端口结束编号不能小于起始编号")
        if self.end_port_number - self.start_port_number + 1 > MAX_SWITCH_PORT_BATCH_SIZE:
            raise ValueError(f"一次最多生成 {MAX_SWITCH_PORT_BATCH_SIZE} 个端口")
        return self


def _default_switch_port_range() -> SwitchPortBulkCreate:
    """返回组合创建交换机时的默认端口范围。"""
    return SwitchPortBulkCreate(card_number=1, subcard_number=0, start_port_number=1, end_port_number=48)


class SwitchGroupMemberCreate(BaseModel):
    """随交换机组创建的成员交换机。"""

    rack_id: TrimmedNonEmptyString
    member_role: SwitchMemberRole
    name: TrimmedNonEmptyString100
    port_speed_mbps: int = Field(..., gt=0)
    start_u: int = Field(..., gt=0)
    height_u: int = Field(1, gt=0)


class SwitchGroupCreate(SwitchGroupBase):
    """原子创建交换机组及完整成员的请求。"""

    members: list[SwitchGroupMemberCreate] = Field(..., min_length=1, max_length=2)
    port_range: SwitchPortBulkCreate = Field(default_factory=_default_switch_port_range)


class SwitchGroupUpdate(PartialUpdateModel):
    """更新交换机组请求。"""

    business_type_id: TrimmedNonEmptyString | SkipJsonSchema[None] = None
    name: TrimmedNonEmptyString100 | SkipJsonSchema[None] = None
    group_mode: SwitchGroupMode | SkipJsonSchema[None] = None


class SwitchGroupReadinessIssueResponse(BaseModel):
    """交换机组成员配置未完整的原因。"""

    code: SwitchGroupReadinessIssueCode
    message: str


class SwitchGroupResponse(SwitchGroupBase):
    """交换机组响应。"""

    id: str
    region_id: str
    region_name: str
    business_type_code: str
    business_type_name: str
    member_count: int = 0
    is_member_config_ready: bool = False
    readiness_issues: list[SwitchGroupReadinessIssueResponse] = Field(default_factory=list)
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class SwitchBase(BaseModel):
    """交换机共享字段。"""

    rack_id: TrimmedNonEmptyString
    switch_group_id: TrimmedNonEmptyString | None = None
    member_role: SwitchMemberRole | None = None
    name: TrimmedNonEmptyString100
    port_speed_mbps: int = Field(..., gt=0)
    start_u: int = Field(..., gt=0)
    height_u: int = Field(1, gt=0)

    @model_validator(mode="after")
    def validate_group_member_pairing(self) -> "SwitchBase":
        """交换机组与成员角色必须同时填写或同时留空。"""
        if (self.switch_group_id is None) != (self.member_role is None):
            raise ValueError("交换机组与成员角色必须同时填写或同时留空")
        return self


class SwitchUpdate(PartialUpdateModel):
    """更新交换机请求。"""

    nullable_update_fields: ClassVar[frozenset[str]] = frozenset({"switch_group_id", "member_role"})

    rack_id: TrimmedNonEmptyString | SkipJsonSchema[None] = None
    switch_group_id: TrimmedNonEmptyString | None = None
    member_role: SwitchMemberRole | None = None
    name: TrimmedNonEmptyString100 | SkipJsonSchema[None] = None
    port_speed_mbps: int | SkipJsonSchema[None] = Field(None, gt=0)
    start_u: int | SkipJsonSchema[None] = Field(None, gt=0)
    height_u: int | SkipJsonSchema[None] = Field(None, gt=0)


class SwitchResponse(SwitchBase):
    """交换机列表与详情响应。"""

    id: str
    region_id: str
    region_name: str
    rack_name: str
    switch_group_name: str | None = None
    business_type_name: str | None = None
    port_count: int = 0
    used_port_count: int = 0
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class SwitchGroupCreateResponse(BaseModel):
    """原子创建交换机组及成员的响应。"""

    group: SwitchGroupResponse
    members: list[SwitchResponse]


class SwitchPortResponse(BaseModel):
    """交换机端口响应，占用状态由线缆引用派生。"""

    id: str
    switch_id: str
    card_number: int
    subcard_number: int
    port_number: int
    is_occupied: bool = False
    cable_entry_id: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
