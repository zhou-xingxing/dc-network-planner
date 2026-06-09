from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ChangeLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    entity_name: Optional[str] = None
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    operator: str
    comment: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}
