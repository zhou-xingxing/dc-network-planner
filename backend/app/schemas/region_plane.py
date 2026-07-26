from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.utils.ip_utils import parse_ip


class RegionPlaneResponse(BaseModel):
    id: str
    region_id: str
    plane_type_id: str
    plane_type_name: str
    scope: str = "Global"
    cidr: str | None = None
    vlan_id: int | None = None
    gateway_position: str | None = None
    gateway_ip: str | None = None
    gateway_ip_warning: str | None = None
    parent_id: str | None = None
    plane_type_parent_id: str | None = None
    created_at: str
    updated_at: str
    children: list["RegionPlaneResponse"] = []

    model_config = {"from_attributes": True}


class ParentPlaneInstanceResponse(BaseModel):
    """创建或编辑网络平面时展示的有效父平面实例。"""

    id: str
    scope: str
    cidr: str
    vlan_id: int | None = None
    gateway_position: str | None = None
    gateway_ip: str | None = None


class ParentPlaneContextResponse(BaseModel):
    """网络平面类型和作用域对应的父平面预检结果。"""

    status: Literal["root", "found", "missing"]
    requested_scope: str
    parent_type_id: str | None = None
    parent_type_name: str | None = None
    parent_plane: ParentPlaneInstanceResponse | None = None


class CidrRecommendationResponse(BaseModel):
    """父平面内的可用 CIDR 推荐结果。"""

    cidr: str
    parent_plane_id: str
    parent_cidr: str


class RegionPlaneCreate(BaseModel):
    plane_type_id: str
    scope: str | None = Field("Global", max_length=100, description="作用域，空值会归一化为 Global")
    cidr: str = Field(..., max_length=49, description="CIDR 地址段，如 10.0.0.0/22 或 2001:db8::/64")
    vlan_id: int | None = Field(None, ge=1, le=4094)
    gateway_position: str | None = Field(None, max_length=255)
    gateway_ip: str | None = Field(None, max_length=45)

    @field_validator("scope")
    @classmethod
    def normalize_scope(cls, value: str | None) -> str:
        """归一化网络平面作用域，空值统一视为 Global。"""
        if value is None:
            return "Global"
        value = value.strip()
        return value or "Global"

    @field_validator("gateway_ip")
    @classmethod
    def validate_gateway_ip(cls, value: str | None) -> str | None:
        """校验可选网关 IP 地址格式。"""
        if value is None:
            return None
        value = value.strip()
        if value == "":
            return None
        if not parse_ip(value):
            raise ValueError("网关 IP 地址格式无效")
        return value


class RegionPlaneUpdate(BaseModel):
    scope: str | None = Field(None, max_length=100, description="作用域，空值会归一化为 Global")
    cidr: str | None = Field(None, max_length=49, description="CIDR 地址段，如 10.0.0.0/22 或 2001:db8::/64")
    vlan_id: int | None = Field(None, ge=1, le=4094)
    gateway_position: str | None = Field(None, max_length=255)
    gateway_ip: str | None = Field(None, max_length=45)

    @field_validator("scope")
    @classmethod
    def normalize_scope(cls, value: str | None) -> str | None:
        """归一化可选网络平面作用域，空字符串统一视为 Global。"""
        if value is None:
            return None
        value = value.strip()
        return value or "Global"

    @field_validator("gateway_ip")
    @classmethod
    def validate_gateway_ip(cls, value: str | None) -> str | None:
        """校验可选网关 IP 地址格式。"""
        if value is None:
            return None
        value = value.strip()
        if value == "":
            return None
        if not parse_ip(value):
            raise ValueError("网关 IP 地址格式无效")
        return value
