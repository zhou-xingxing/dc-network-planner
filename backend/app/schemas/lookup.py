from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LookupResult(BaseModel):
    id: str
    cidr: str
    region_name: str
    plane_type_name: str
    scope: str = "Global"
    vlan_id: Optional[int] = None
    gateway_position: Optional[str] = None
    gateway_ip: Optional[str] = None
    # 树形展示字段：parent_id 表示当前节点挂载到哪个父级平面实例。
    parent_id: Optional[str] = None
    # 保留网络平面类型父级 ID，方便前端或调试时理解树结构来源。
    plane_type_parent_id: Optional[str] = None
    # True 表示查询真正命中；False 表示仅作为父级上下文展示。
    is_match: bool = True
    # 子平面节点列表，用于 Element Plus 树表格展示。
    children: list["LookupResult"] = Field(default_factory=list)


class LookupResponse(BaseModel):
    results: list[LookupResult]
    total: int
