from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PlaneTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = ""
    is_private: bool = False
    vrf: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[str] = None


class PlaneTypeCreate(PlaneTypeBase):
    pass


class PlaneTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_private: Optional[bool] = None
    vrf: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[str] = None


class PlaneTypeResponse(PlaneTypeBase):
    id: str
    parent_name: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
