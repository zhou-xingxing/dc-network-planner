from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LookupResult(BaseModel):
    id: str = Field(..., description="Region 网络平面实例 ID。")
    cidr: str = Field(..., description="网络平面 CIDR。")
    region_name: str = Field(..., description="Region 名称。")
    plane_type_name: str = Field(..., description="网络平面类型名称。")
    scope: str = Field("Global", description="网络平面作用域，空值会按 Global 处理。")
    vlan_id: Optional[int] = Field(None, description="VLAN ID；未配置时为 null。")
    gateway_position: Optional[str] = Field(None, description="网关位置策略；未配置时为 null。")
    gateway_ip: Optional[str] = Field(None, description="网关 IP；未配置时为 null。")
    # 树形展示字段：parent_id 表示当前节点挂载到哪个父级平面实例。
    parent_id: Optional[str] = Field(None, description="父级网络平面实例 ID；根节点为 null。")
    # 保留网络平面类型父级 ID，方便前端或调试时理解树结构来源。
    plane_type_parent_id: Optional[str] = Field(None, description="网络平面类型父级 ID；根类型为 null。")
    # True 表示查询真正命中；False 表示仅作为父级上下文展示。
    is_match: bool = Field(True, description="是否为本次查询真正命中的节点；false 表示仅作为树形父级上下文返回。")
    # 子平面节点列表，用于 Element Plus 树表格展示。
    children: list["LookupResult"] = Field(default_factory=list, description="子网络平面节点列表。")


class LookupResponse(BaseModel):
    results: list[LookupResult] = Field(..., description="查询结果。命中子节点时会带出必要的父级上下文。")
    total: int = Field(..., description="真正命中的网络平面数量，不包含仅作为父级上下文返回的节点。")
