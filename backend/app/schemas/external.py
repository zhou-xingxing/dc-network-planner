from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ExternalTokenScope = Literal["network-plane:read"]


class ExternalTokenRequest(BaseModel):
    """使用本地账户凭据签发短期外部 API 访问令牌。"""

    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="本地账号用户名。签发成功后，外部访问令牌会映射到该用户的权限边界。",
        examples=["api-user"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="本地账号密码。仅用于签发令牌，不会在响应或数据库中保存明文。",
        examples=["your-password"],
    )
    requested_scopes: list[ExternalTokenScope] = Field(
        ...,
        min_length=1,
        max_length=1,
        description="申请的外部 API 权限范围。目前仅支持 network-plane:read。",
        examples=[["network-plane:read"]],
    )


class ExternalTokenResponse(BaseModel):
    access_token: str = Field(
        ...,
        description="只在签发响应中返回一次的外部 API 访问令牌。数据库仅保存其 SHA-256 哈希。",
        examples=["dcnp_ext_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"],
    )
    token_type: str = Field(
        "bearer",
        description="令牌类型。调用外部 API 时使用 Authorization: Bearer <access_token>。",
    )
    expires_in: int = Field(..., description="令牌有效期，单位为秒。", examples=[1800])
    scope: list[ExternalTokenScope] = Field(
        ...,
        description="实际签发的 scope 列表。",
        examples=[["network-plane:read"]],
    )
    expires_at: str = Field(..., description="令牌过期时间，使用系统统一的日期时间字符串格式。")


class ExternalNetworkPlaneTypeResponse(BaseModel):
    """External API 返回的网络平面类型。"""

    id: str = Field(..., description="网络平面类型的唯一 ID。")
    name: str = Field(..., description="网络平面类型名称。")
    description: str = Field(..., description="网络平面类型说明；未填写时为空字符串。")
    is_private: bool = Field(..., description="是否为私网类型。")
    vrf: str | None = Field(..., description="VRF 名称；未配置时为 null。")
    parent_id: str | None = Field(..., description="父级网络平面类型 ID；根类型为 null。")
    parent_name: str | None = Field(..., description="父级网络平面类型名称；根类型为 null。")
    created_at: str = Field(..., description="创建时间，使用系统统一的日期时间字符串格式。")
    updated_at: str = Field(..., description="最后更新时间，使用系统统一的日期时间字符串格式。")


class ExternalNetworkPlaneTypeListResponse(BaseModel):
    """External API 网络平面类型分页列表。"""

    items: list[ExternalNetworkPlaneTypeResponse] = Field(..., description="当前分页中的网络平面类型。")
    total: int = Field(..., description="网络平面类型总数，不受当前分页范围影响。")
    skip: int = Field(..., description="当前分页跳过的记录数。")
    limit: int = Field(..., description="当前分页请求的最大返回条数。")


class ExternalAccessTokenListItem(BaseModel):
    """管理员页面展示的未撤销且未过期外部 API 访问令牌。"""

    id: str
    username: str
    owner_is_active: bool
    created_at: str
    expires_at: str
