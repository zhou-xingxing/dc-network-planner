from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


class ImportRow(BaseModel):
    row_number: int
    region_name: str
    plane_type_name: str
    scope: str = "Global"
    ip_range: str
    vlan_id: Optional[int] = None
    gateway_position: Optional[str] = None
    gateway_ip: Optional[str] = None


class ImportError(BaseModel):
    row: int
    errors: list[str]
    region_name: Optional[str] = None
    error_type: Literal["validation", "permission", "business"] = "validation"


class ImportPreviewResponse(BaseModel):
    preview_id: str
    total_rows: int
    valid_rows: int
    error_rows: list[ImportError]
    rows: list[ImportRow]


class ImportConfirmRequest(BaseModel):
    preview_id: str


class ImportRowResult(BaseModel):
    """Excel 确认导入的单行最终结果。"""

    row: int
    status: Literal["success", "failed"]
    region_name: str
    plane_type_name: str
    scope: str
    ip_range: str
    vlan_id: Optional[int] = None
    gateway_position: Optional[str] = None
    gateway_ip: Optional[str] = None
    plane_id: Optional[str] = None
    errors: list[str]


class ImportResultResponse(BaseModel):
    success: bool
    imported_count: int
    error_count: int
    errors: list[ImportError]
    row_results: list[ImportRowResult]


class StatsResponse(BaseModel):
    total_regions: int
    total_plane_types: int
    total_region_planes: int
    total_change_logs: int
    plane_by_scope: dict[str, int]
    plane_by_region: list[dict[str, Any]]
    recent_changes: list[dict[str, Any]]
