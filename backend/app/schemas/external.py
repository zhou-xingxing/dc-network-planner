from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ExternalTokenScope = Literal[
    "network-plane:read",
    "network-plane:import-preview",
    "network-plane:import-apply",
]


class ExternalTokenRequest(BaseModel):
    """使用本地账户凭据签发短期外部 API 访问令牌。"""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=128)
    requested_scopes: list[ExternalTokenScope] = Field(..., min_length=1, max_length=3)


class ExternalTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scope: list[ExternalTokenScope]
    expires_at: str


class ExternalAccessTokenListItem(BaseModel):
    """管理员页面展示的未撤销且未过期外部 API 访问令牌。"""

    id: str
    username: str
    owner_is_active: bool
    created_at: str
    expires_at: str
