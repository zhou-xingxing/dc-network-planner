from __future__ import annotations

import os
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import BACKEND_DIR, settings

REQUIRED_BACKUP_TABLES = {
    "alembic_version",
    "regions",
    "network_plane_types",
    "region_network_planes",
    "users",
    "backup_configs",
    "backup_records",
}


class RestoreError(Exception):
    """数据库恢复失败。"""


@dataclass(frozen=True)
class RestoreResult:
    """数据库恢复结果。"""

    database_path: Path
    backup_path: Path
    safety_backup_path: Path | None


def restore_database_from_backup(
    backup_file: Path,
    database_url: str | None = None,
    *,
    create_safety_backup: bool = True,
) -> RestoreResult:
    """从 SQLite 备份文件恢复当前数据库。

    Args:
        backup_file: 已由系统备份功能生成的 SQLite 备份文件。
        database_url: 目标数据库 URL；默认使用应用配置。
        create_safety_backup: 恢复前是否给当前数据库创建安全快照。

    Returns:
        数据库恢复结果，包含目标库、来源备份和安全快照路径。

    Raises:
        RestoreError: 备份文件无效、目标数据库不支持或文件替换失败。
    """
    backup_path = backup_file.expanduser().resolve()
    database_path = resolve_sqlite_database_path(database_url or settings.DATABASE_URL)
    validate_sqlite_backup(backup_path)

    database_path.parent.mkdir(parents=True, exist_ok=True)
    original_file_mode = _get_existing_file_mode(database_path)
    safety_backup_path = create_current_database_snapshot(database_path) if create_safety_backup else None
    temp_database_path = database_path.parent / f".{database_path.name}.restore_tmp_{uuid.uuid4().hex}"

    try:
        _copy_sqlite_database(backup_path, temp_database_path)
        os.replace(temp_database_path, database_path)
        _apply_existing_file_mode(original_file_mode, database_path)
    except OSError as exc:
        raise RestoreError(f"替换目标数据库失败: {exc}") from exc
    finally:
        temp_database_path.unlink(missing_ok=True)

    return RestoreResult(
        database_path=database_path,
        backup_path=backup_path,
        safety_backup_path=safety_backup_path,
    )


def resolve_sqlite_database_path(database_url: str, backend_dir: Path = BACKEND_DIR) -> Path:
    """解析应用 SQLite 数据库文件路径。

    相对路径与运行时 `app.database` 的规则保持一致，统一固定到 backend 目录下。
    """
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        raise RestoreError("当前恢复脚本仅支持 SQLite 数据库")
    if not url.database or url.database == ":memory:":
        raise RestoreError("内存 SQLite 数据库不支持文件恢复")

    database_path = Path(url.database).expanduser()
    if not database_path.is_absolute():
        database_path = backend_dir / database_path
    return database_path.resolve()


def validate_sqlite_backup(backup_path: Path) -> None:
    """校验备份文件是可用的 DC Network Planner SQLite 备份。"""
    if not backup_path.exists():
        raise RestoreError(f"备份文件不存在: {backup_path}")
    if not backup_path.is_file():
        raise RestoreError(f"备份路径不是文件: {backup_path}")

    try:
        with _connect_readonly(backup_path) as connection:
            _ensure_quick_check_ok(connection, backup_path)
            _ensure_required_tables_exist(connection, backup_path)
    except sqlite3.Error as exc:
        raise RestoreError(f"备份文件不是有效的 SQLite 数据库: {exc}") from exc


def create_current_database_snapshot(database_path: Path) -> Path | None:
    """为当前数据库文件创建恢复前安全快照。"""
    if not database_path.exists():
        return None
    if not database_path.is_file():
        raise RestoreError(f"目标数据库路径不是文件: {database_path}")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = database_path.suffix or ".db"
    snapshot_id = uuid.uuid4().hex[:8]
    snapshot_path = database_path.with_name(f"{database_path.stem}.pre_restore_{timestamp}_{snapshot_id}{suffix}")
    shutil.copy2(database_path, snapshot_path)
    return snapshot_path


def _copy_sqlite_database(source_path: Path, target_path: Path) -> None:
    """使用 SQLite 内置 backup API 将源数据库完整复制到目标路径。

    复制完成后执行 PRAGMA optimize 并验证目标库完整性，
    确保恢复出的数据库文件可用且无损坏。
    """
    with _connect_readonly(source_path) as source, sqlite3.connect(target_path) as target:
        source.backup(target)
        target.execute("PRAGMA optimize")
        _ensure_quick_check_ok(target, target_path)


def _connect_readonly(database_path: Path) -> sqlite3.Connection:
    """以只读模式打开 SQLite 数据库，避免恢复过程中意外修改备份源文件。"""
    return sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)


def _ensure_quick_check_ok(connection: sqlite3.Connection, database_path: Path) -> None:
    """执行 PRAGMA quick_check 验证 SQLite 数据库完整性，失败则抛出 RestoreError。"""
    quick_check = connection.execute("PRAGMA quick_check").fetchone()
    if not quick_check or quick_check[0] != "ok":
        detail = quick_check[0] if quick_check else "empty result"
        raise RestoreError(f"SQLite quick_check 未通过: {database_path}: {detail}")


def _ensure_required_tables_exist(connection: sqlite3.Connection, backup_path: Path) -> None:
    """检查备份文件是否包含应用运行所需的全部核心数据表，缺失则抛出 RestoreError。"""
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    table_names = {row[0] for row in rows}
    missing_tables = sorted(REQUIRED_BACKUP_TABLES - table_names)
    if missing_tables:
        raise RestoreError(f"备份文件缺少必要数据表: {backup_path}: {', '.join(missing_tables)}")


def _get_existing_file_mode(database_path: Path) -> int | None:
    """读取恢复前数据库文件权限；目标不存在时返回 None。"""
    if not database_path.exists():
        return None
    if not database_path.is_file():
        raise RestoreError(f"目标数据库路径不是文件: {database_path}")
    return database_path.stat().st_mode & 0o777


def _apply_existing_file_mode(file_mode: int | None, target_path: Path) -> None:
    """将恢复前文件权限应用到新数据库，保持恢复前后权限一致。"""
    if file_mode is None:
        return
    target_path.chmod(file_mode)
