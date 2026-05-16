from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.region_plane import RegionPlaneResponse


class RegionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = ""


class RegionCreate(RegionBase):
    pass


class RegionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class RegionResponse(RegionBase):
    id: str
    plane_count: int = 0
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class RegionDetailResponse(RegionResponse):
    planes: list["RegionPlaneResponse"] = []
