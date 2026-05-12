import sqlite3
import stat
from pathlib import Path

import pytest

from app.services.restore_database import (
    REQUIRED_BACKUP_TABLES,
    RestoreError,
    create_current_database_snapshot,
    resolve_sqlite_database_path,
    restore_database_from_backup,
    validate_sqlite_backup,
)


def test_restore_database_from_backup_replaces_database_and_keeps_snapshot(tmp_path: Path) -> None:
    """恢复脚本应先保存当前库快照，再用备份内容替换目标数据库。"""
    backup_path = tmp_path / "backup.db"
    database_path = tmp_path / "dc_network_planner.db"
    _create_valid_backup(backup_path, region_name="恢复后的 Region")
    _create_current_database(database_path, region_name="恢复前的 Region")

    result = restore_database_from_backup(backup_path, f"sqlite:///{database_path}")

    assert result.database_path == database_path
    assert result.backup_path == backup_path
    assert result.safety_backup_path is not None
    assert result.safety_backup_path.exists()
    assert _region_names(database_path) == ["恢复后的 Region"]
    assert _region_names(result.safety_backup_path) == ["恢复前的 Region"]


def test_restore_database_from_backup_supports_missing_target_database(tmp_path: Path) -> None:
    """目标库不存在时也能直接恢复，并跳过恢复前快照。"""
    backup_path = tmp_path / "backup.db"
    database_path = tmp_path / "nested" / "dc_network_planner.db"
    _create_valid_backup(backup_path, region_name="新库 Region")

    result = restore_database_from_backup(backup_path, f"sqlite:///{database_path}")

    assert result.safety_backup_path is None
    assert _region_names(database_path) == ["新库 Region"]


def test_restore_database_from_backup_skips_snapshot_when_disabled(tmp_path: Path) -> None:
    """create_safety_backup=False 时不创建安全快照。"""
    backup_path = tmp_path / "backup.db"
    database_path = tmp_path / "dc_network_planner.db"
    _create_valid_backup(backup_path, region_name="恢复后的 Region")
    _create_current_database(database_path, region_name="恢复前的 Region")

    result = restore_database_from_backup(backup_path, f"sqlite:///{database_path}", create_safety_backup=False)

    assert result.safety_backup_path is None
    assert _region_names(database_path) == ["恢复后的 Region"]


def test_restore_database_from_backup_preserves_file_mode(tmp_path: Path) -> None:
    """恢复后新数据库应继承原数据库的文件权限。"""
    backup_path = tmp_path / "backup.db"
    database_path = tmp_path / "dc_network_planner.db"
    _create_valid_backup(backup_path, region_name="恢复后的 Region")
    _create_current_database(database_path, region_name="恢复前的 Region")
    database_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    restore_database_from_backup(backup_path, f"sqlite:///{database_path}")

    assert database_path.stat().st_mode & 0o777 == 0o600


def test_restore_database_from_backup_preserves_file_mode_without_snapshot(tmp_path: Path) -> None:
    """跳过安全快照时也应保留原数据库文件权限。"""
    backup_path = tmp_path / "backup.db"
    database_path = tmp_path / "dc_network_planner.db"
    _create_valid_backup(backup_path, region_name="恢复后的 Region")
    _create_current_database(database_path, region_name="恢复前的 Region")
    database_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    restore_database_from_backup(
        backup_path,
        f"sqlite:///{database_path}",
        create_safety_backup=False,
    )

    assert database_path.stat().st_mode & 0o777 == 0o600


def test_validate_sqlite_backup_rejects_nonexistent_file(tmp_path: Path) -> None:
    """不存在的备份路径应被拒绝。"""
    with pytest.raises(RestoreError, match="备份文件不存在"):
        validate_sqlite_backup(tmp_path / "not_exists.db")


def test_validate_sqlite_backup_rejects_directory(tmp_path: Path) -> None:
    """目录路径不能作为备份文件。"""
    with pytest.raises(RestoreError, match="备份路径不是文件"):
        validate_sqlite_backup(tmp_path)


def test_validate_sqlite_backup_rejects_corrupted_file(tmp_path: Path) -> None:
    """损坏的非 SQLite 文件应被拒绝。"""
    corrupted_path = tmp_path / "corrupted.db"
    corrupted_path.write_text("not a sqlite database")

    with pytest.raises(RestoreError, match="不是有效的 SQLite 数据库"):
        validate_sqlite_backup(corrupted_path)


def test_validate_sqlite_backup_rejects_non_project_database(tmp_path: Path) -> None:
    """普通 SQLite 文件缺少项目表结构时不能作为恢复来源。"""
    backup_path = tmp_path / "invalid.db"
    with sqlite3.connect(backup_path) as connection:
        connection.execute("CREATE TABLE unrelated (id TEXT PRIMARY KEY)")

    with pytest.raises(RestoreError, match="缺少必要数据表"):
        validate_sqlite_backup(backup_path)


def test_resolve_sqlite_database_path_rejects_unsupported_database_url() -> None:
    """非 SQLite 驱动应被拒绝。"""
    with pytest.raises(RestoreError, match="仅支持 SQLite"):
        resolve_sqlite_database_path("postgresql://user:pass@example.com/app")


def test_resolve_sqlite_database_path_rejects_memory_database() -> None:
    """:memory: 数据库不支持文件恢复。"""
    with pytest.raises(RestoreError, match="内存 SQLite"):
        resolve_sqlite_database_path("sqlite:///:memory:")


def test_resolve_sqlite_database_path_keeps_absolute_path() -> None:
    """绝对路径应原样保留。"""
    path = resolve_sqlite_database_path("sqlite:////absolute/path/to/app.db")
    assert path == Path("/absolute/path/to/app.db")


def test_resolve_sqlite_database_path_resolves_relative_path(tmp_path: Path) -> None:
    """相对路径应解析到传入的 backend_dir 下。"""
    path = resolve_sqlite_database_path("sqlite:///relative.db", backend_dir=tmp_path)
    assert path == (tmp_path / "relative.db").resolve()


def test_create_current_database_snapshot_returns_none_for_missing_database(tmp_path: Path) -> None:
    """目标数据库不存在时返回 None。"""
    result = create_current_database_snapshot(tmp_path / "not_exists.db")
    assert result is None


def test_create_current_database_snapshot_rejects_directory(tmp_path: Path) -> None:
    """目标路径是目录时应报错。"""
    with pytest.raises(RestoreError, match="不是文件"):
        create_current_database_snapshot(tmp_path)


def test_create_current_database_snapshot_creates_copy(tmp_path: Path) -> None:
    """成功创建快照文件且内容一致。"""
    database_path = tmp_path / "app.db"
    _create_current_database(database_path, region_name="原始 Region")

    snapshot_path = create_current_database_snapshot(database_path)

    assert snapshot_path is not None
    assert snapshot_path.exists()
    assert snapshot_path != database_path
    assert _region_names(snapshot_path) == ["原始 Region"]


def _create_valid_backup(path: Path, region_name: str) -> None:
    with sqlite3.connect(path) as connection:
        for table_name in REQUIRED_BACKUP_TABLES:
            connection.execute(f"CREATE TABLE {table_name} (id TEXT PRIMARY KEY, name TEXT)")
        connection.execute(
            "INSERT INTO regions (id, name) VALUES (?, ?)",
            ("region-1", region_name),
        )


def _create_current_database(path: Path, region_name: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE regions (id TEXT PRIMARY KEY, name TEXT)")
        connection.execute(
            "INSERT INTO regions (id, name) VALUES (?, ?)",
            ("region-old", region_name),
        )


def _region_names(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT name FROM regions ORDER BY id").fetchall()
    return [row[0] for row in rows]
