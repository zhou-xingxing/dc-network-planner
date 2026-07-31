"""交换机 API 响应转换。"""

from fastapi import HTTPException

from app.schemas.switch import SwitchMemberRole, SwitchResponse
from app.services.switch import SwitchWithCounts
from app.utils.time_utils import format_datetime


def build_switch_response(item: SwitchWithCounts) -> SwitchResponse:
    """将 Service 聚合结果转换为交换机 API 响应。"""
    switch = item.switch
    return SwitchResponse(
        id=switch.id,
        region_id=item.region_id,
        region_name=item.region_name,
        rack_id=switch.rack_id,
        rack_name=item.rack_name,
        switch_group_id=switch.switch_group_id,
        switch_group_name=item.switch_group_name,
        business_type_name=item.business_type_name,
        member_role=_to_switch_member_role(switch.member_role),
        name=switch.name,
        port_speed_mbps=switch.port_speed_mbps,
        start_u=switch.start_u,
        height_u=switch.height_u,
        port_count=item.port_count,
        used_port_count=item.used_port_count,
        created_at=format_datetime(switch.created_at),
        updated_at=format_datetime(switch.updated_at),
    )


def _to_switch_member_role(value: str | None) -> SwitchMemberRole | None:
    """校验数据库中的交换机成员角色并收窄类型。"""
    if value is None:
        return None
    if value == "a":
        return "a"
    if value == "b":
        return "b"
    if value == "single":
        return "single"
    raise HTTPException(status_code=500, detail=f"无效的交换机成员角色: {value}")
