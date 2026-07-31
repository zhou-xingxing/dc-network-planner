from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from app.schemas.common import PartialUpdateModel, TrimmedNonEmptyString20, TrimmedNonEmptyString100


class RackCreateItem(BaseModel):
    """待创建机柜的结构化位置。"""

    room_name: TrimmedNonEmptyString100
    rack_column: TrimmedNonEmptyString20
    rack_number: int = Field(..., gt=0)


class RackCreate(BaseModel):
    """原子创建一个或多个结构化机柜的请求。"""

    items: list[RackCreateItem] = Field(..., min_length=1, max_length=500)
    u_height: int = Field(42, gt=0)


class RackUpdate(PartialUpdateModel):
    """更新机柜请求。"""

    room_name: TrimmedNonEmptyString100 | SkipJsonSchema[None] = None
    rack_column: TrimmedNonEmptyString20 | SkipJsonSchema[None] = None
    rack_number: int | SkipJsonSchema[None] = Field(None, gt=0)
    u_height: int | SkipJsonSchema[None] = Field(None, gt=0)


class RackColumnSummary(BaseModel):
    """同机房、同机柜列的聚合统计。"""

    room_name: str
    rack_column: str
    rack_count: int
    switch_count: int
    cable_count: int


class RackColumnListResponse(BaseModel):
    """机柜列分页列表及当前条件下的汇总。"""

    items: list[RackColumnSummary]
    total_columns: int
    total_racks: int
    skip: int
    limit: int


class RackResponse(BaseModel):
    """机柜响应，包含列表页需要的关联统计。"""

    id: str
    region_id: str
    region_name: str
    name: str
    room_name: str
    rack_column: str
    rack_number: int
    u_height: int
    switch_count: int = 0
    cable_count: int = 0
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
