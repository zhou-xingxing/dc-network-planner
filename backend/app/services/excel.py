from __future__ import annotations

import uuid
from io import BytesIO
from threading import RLock
from typing import Any, Optional

from cachetools import TTLCache
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessError, ResourceNotFoundError
from app.models.user import User
from app.services.region_plane import create_plane_for_region, normalize_plane_scope
from app.services.user import get_user_permitted_region_ids
from app.utils.excel_utils import build_export, parse_excel
from app.utils.ip_utils import ip_belongs_to_network, parse_cidr, parse_ip
from app.utils.time_utils import format_datetime

# 单实例进程级导入预览缓存；访问由锁保护，避免并发请求破坏 TTL/LRU 元数据。
_import_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache[str, list[dict[str, Any]]](
    maxsize=settings.IMPORT_CACHE_MAXSIZE,
    ttl=settings.IMPORT_TTL_MINUTES * 60,
)
_import_cache_lock = RLock()


def store_preview(rows: list[dict[str, Any]]) -> str:
    """存储导入预览数据到进程级 TTL 缓存。

    Args:
        rows: 解析后的行数据列表。

    Returns:
        预览数据的唯一标识 ID（UUID4 字符串）。
    """
    preview_id = str(uuid.uuid4())
    with _import_cache_lock:
        _import_cache.expire()
        _import_cache[preview_id] = rows
    return preview_id


def get_preview(preview_id: str) -> Optional[list[dict[str, Any]]]:
    """查看导入预览数据，不消费缓存。

    Args:
        preview_id: 预览数据 ID。

    Returns:
        预览的行数据列表，已过期或不存在时返回 None。
    """
    with _import_cache_lock:
        _import_cache.expire()
        return _import_cache.get(preview_id)


def consume_preview(preview_id: str) -> Optional[list[dict[str, Any]]]:
    """读取并删除导入预览数据，用于确认导入的一次性消费。"""
    with _import_cache_lock:
        _import_cache.expire()
        return _import_cache.pop(preview_id, None)


def cleanup_expired_previews() -> int:
    """清理过期导入预览缓存，返回清理条目数量。"""
    with _import_cache_lock:
        return len(_import_cache.expire())


def get_preview_region_ids(preview_id: str) -> Optional[set[str]]:
    """Return Region IDs covered by a cached import preview."""
    rows = get_preview(preview_id)
    if rows is None:
        return None
    return {str(row["_region_id"]) for row in rows}


def preview_import(file_bytes: bytes, db: Session, current_user: User) -> dict[str, Any]:
    """解析导入文件并校验数据，返回预览结果。

    校验内容：Region 和网络平面类型是否存在、CIDR 格式、
    VLAN ID 范围、网关 IP 格式是否合法，以及当前用户是否有权
    对目标 Region 执行导入确认。

    Args:
        file_bytes: Excel 文件的二进制内容。
        db: 数据库会话。
        current_user: 当前登录用户。

    Returns:
        包含 preview_id、total_rows、valid_rows、error_rows 及
        每行详细数据的预览结果字典。
    """
    from app.models.network_plane_type import NetworkPlaneType
    from app.models.region import Region

    try:
        parsed_rows = parse_excel(file_bytes)
    except ValueError as exc:
        raise BusinessError(str(exc)) from exc
    valid_rows = []
    error_rows = []

    # Preload lookup data
    all_regions = {r.name: r.id for r in db.query(Region).all()}
    all_plane_types = {pt.name: pt.id for pt in db.query(NetworkPlaneType).all()}
    permitted_region_ids = (
        get_user_permitted_region_ids(current_user) if current_user.role != "administrator" else set()
    )

    for row in parsed_rows:
        row_errors = []
        error_type = "validation"
        region_id = all_regions.get(row["region_name"])
        plane_type_id = all_plane_types.get(row["plane_type_name"])
        scope = normalize_plane_scope(row.get("scope"))
        vlan_id, vlan_id_error = _parse_optional_vlan_id(row.get("vlan_id"))
        net = None

        if not region_id:
            row_errors.append(f"区域不存在: {row['region_name']}")
        elif not _can_confirm_import_region(current_user, region_id, permitted_region_ids):
            row_errors.append(f"用户未授权管理此 Region：{row['region_name']}，仅提供预览功能，不能实际导入")
            error_type = "permission"
        if not plane_type_id:
            row_errors.append(f"网络平面类型不存在: {row['plane_type_name']}")
        if not row["ip_range"]:
            row_errors.append("IP地址段不能为空")
        else:
            net = parse_cidr(row["ip_range"])
            if not net:
                row_errors.append(f"无效CIDR: {row['ip_range']}")

        if vlan_id_error:
            row_errors.append(f"无效 VLAN ID: {vlan_id_error}")
        elif vlan_id is not None and not 1 <= vlan_id <= 4094:
            row_errors.append(f"无效 VLAN ID: {vlan_id}")
        if row["gateway_ip"]:
            gateway_ip = parse_ip(row["gateway_ip"])
            if not gateway_ip:
                row_errors.append(f"无效网关IP: {row['gateway_ip']}")
            elif net and not ip_belongs_to_network(gateway_ip, net):
                row_errors.append(f"网关 IP {row['gateway_ip']} 必须在平面 CIDR {net.with_prefixlen} 范围内")

        if row_errors:
            error_rows.append(
                {
                    "row": row["row_number"],
                    "region_name": row["region_name"],
                    "error_type": error_type,
                    "errors": row_errors,
                }
            )
        else:
            valid_rows.append(
                {
                    **row,
                    "_region_id": region_id,
                    "_plane_type_id": plane_type_id,
                    "scope": scope,
                    "vlan_id": vlan_id,
                }
            )

    preview_id = store_preview(valid_rows)

    return {
        "preview_id": preview_id,
        "total_rows": len(parsed_rows),
        "valid_rows": len(valid_rows),
        "error_rows": error_rows,
        "rows": [
            {
                "row_number": r["row_number"],
                "region_name": r["region_name"],
                "plane_type_name": r["plane_type_name"],
                "scope": r["scope"],
                "ip_range": r["ip_range"],
                "vlan_id": r["vlan_id"],
                "gateway_position": r["gateway_position"],
                "gateway_ip": r["gateway_ip"],
            }
            for r in valid_rows
        ],
    }


def _can_confirm_import_region(current_user: User, region_id: str, permitted_region_ids: set[str]) -> bool:
    """判断当前用户是否可确认导入指定 Region 的业务数据。"""
    return current_user.role != "administrator" and region_id in permitted_region_ids


def _parse_optional_vlan_id(value: Any) -> tuple[int | None, str | None]:
    """将导入行中的 VLAN 原始值解析为业务使用的整数。"""
    if value is None:
        return None, None
    raw_value = str(value).strip()
    if raw_value == "":
        return None, None
    if isinstance(value, float) and not value.is_integer():
        return None, raw_value
    try:
        return int(value), None
    except (ValueError, TypeError):
        return None, raw_value


def confirm_import(preview_id: str, operator: str, db: Session) -> dict[str, Any]:
    """确认执行导入，将预览数据写入数据库。

    逐行创建 Region 网络平面。
    已过期的预览数据会被拒绝导入。

    Args:
        preview_id: 预览数据 ID。
        operator: 操作者名称。
        db: 数据库会话。

    Returns:
        包含 success、imported_count、error_count、errors 的导入结果字典。
    """
    rows = consume_preview(preview_id)
    if rows is None:
        return {
            "success": False,
            "imported_count": 0,
            "error_count": 0,
            "errors": [{"row": 0, "error_type": "validation", "errors": ["预览数据已过期，请重新上传"]}],
        }

    imported = 0
    errors = []

    for row in rows:
        try:
            create_plane_for_region(
                db,
                row["_region_id"],
                row["_plane_type_id"],
                row["ip_range"],
                operator,
                scope=row.get("scope"),
                vlan_id=row["vlan_id"],
                gateway_position=row.get("gateway_position"),
                gateway_ip=row.get("gateway_ip"),
            )
            imported += 1
        except (BusinessError, ResourceNotFoundError) as e:
            errors.append(
                {
                    "row": row["row_number"],
                    "region_name": row["region_name"],
                    "error_type": "business",
                    "errors": [str(e)],
                }
            )

    return {
        "success": True,
        "imported_count": imported,
        "error_count": len(errors),
        "errors": errors,
    }


def export_region_planes(
    db: Session,
    *,
    region_id: str | None = None,
) -> BytesIO:
    """导出 Region 网络平面数据到 Excel 工作簿。"""
    from app.models.network_plane_type import NetworkPlaneType
    from app.models.region import Region
    from app.models.region_network_plane import RegionNetworkPlane

    query = (
        db.query(RegionNetworkPlane)
        .join(Region, RegionNetworkPlane.region_id == Region.id)
        .join(NetworkPlaneType, RegionNetworkPlane.plane_type_id == NetworkPlaneType.id)
    )
    if region_id:
        query = query.filter(RegionNetworkPlane.region_id == region_id)

    planes = query.order_by(
        Region.name.asc(),
        NetworkPlaneType.name.asc(),
        RegionNetworkPlane.scope.asc(),
        RegionNetworkPlane.cidr.asc(),
    ).all()

    data = [
        {
            "region_name": plane.region.name if plane.region else "",
            "plane_type_name": plane.plane_type.name if plane.plane_type else "",
            "parent_plane_type_name": (
                plane.plane_type.parent.name if plane.plane_type and plane.plane_type.parent else ""
            ),
            "scope": plane.scope,
            "is_private": "是" if plane.plane_type and plane.plane_type.is_private else "否",
            "vrf": plane.plane_type.vrf if plane.plane_type and plane.plane_type.vrf else "",
            "ip_range": plane.cidr or "",
            "vlan_id": plane.vlan_id,
            "gateway_position": plane.gateway_position or "",
            "gateway_ip": plane.gateway_ip or "",
            "updated_at": format_datetime(plane.updated_at),
        }
        for plane in planes
    ]
    return build_export(data)
