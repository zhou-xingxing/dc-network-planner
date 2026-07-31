from __future__ import annotations

from typing import Annotated, ClassVar, Generic, List, Self, TypeVar

from pydantic import BaseModel, StringConstraints, model_validator

T = TypeVar("T")

TrimmedNonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
TrimmedNonEmptyString20 = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
]
TrimmedNonEmptyString50 = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
]
TrimmedNonEmptyString100 = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class PartialUpdateModel(BaseModel):
    """拒绝空请求和必填字段显式传入 null 的部分更新基类。"""

    nullable_update_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def validate_update_fields(self) -> Self:
        """确保请求至少包含一个字段，且非 nullable 字段不为 null。"""
        if not self.model_fields_set:
            raise ValueError("至少提供一个待更新字段")
        null_fields = sorted(
            field_name
            for field_name in self.model_fields_set
            if field_name not in self.nullable_update_fields and getattr(self, field_name) is None
        )
        if null_fields:
            raise ValueError(f"字段不能为 null: {', '.join(null_fields)}")
        return self


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int = 0
    limit: int = 100


class MessageResponse(BaseModel):
    detail: str
