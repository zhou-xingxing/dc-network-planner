"""Alembic 数据库配置测试。"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
LEGACY_CABLING_REVISION = "7b1d9e4c2a6f"
RACK_STRUCTURE_REVISION = "9d7e4a1c6b2f"
SWITCH_PORT_STRUCTURE_REVISION = "c4b2e8f1a9d3"
RACK_POSITION_INDEX_REVISION = "e7a3f1d5b9c2"
TIMESTAMP = "2026-07-30 00:00:00"


def _run_alembic(database_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """对指定临时 SQLite 数据库执行 Alembic 命令。"""
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_alembic_upgrade_uses_application_database_url(tmp_path: Path) -> None:
    """迁移必须写入 DATABASE_URL 指定的数据库。"""
    database_path = tmp_path / "alembic_target.db"
    result = _run_alembic(database_path, "upgrade", "head")

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        users_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        plane_columns = {
            row[1]: row[2] for row in connection.execute("PRAGMA table_info(region_network_planes)").fetchall()
        }
        cabling_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name IN ('racks', 'switch_business_types', 'switch_groups', 'switches', "
                "'switch_ports', 'cabling_batches', 'cable_entries')"
            ).fetchall()
        }
        switch_business_types = connection.execute(
            "SELECT code, name FROM switch_business_types ORDER BY code"
        ).fetchall()
        rack_columns = {
            row[1]: {"type": row[2], "not_null": bool(row[3])}
            for row in connection.execute("PRAGMA table_info(racks)").fetchall()
        }
        rack_table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'racks'"
        ).fetchone()[0]
        rack_indexes = {
            row[1]: {"unique": bool(row[2])} for row in connection.execute("PRAGMA index_list(racks)").fetchall()
        }
        rack_position_index_columns = [
            row[2] for row in connection.execute("PRAGMA index_info(ix_rack_position)").fetchall()
        ]
        switch_port_columns = {
            row[1]: {"type": row[2], "not_null": bool(row[3]), "default": row[4]}
            for row in connection.execute("PRAGMA table_info(switch_ports)").fetchall()
        }
        switch_port_table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'switch_ports'"
        ).fetchone()[0]

    assert revision == (RACK_POSITION_INDEX_REVISION,)
    assert users_table == ("users",)
    assert plane_columns["cidr"] == "VARCHAR(49)"
    assert plane_columns["gateway_ip"] == "VARCHAR(45)"
    assert cabling_tables == {
        "racks",
        "switch_business_types",
        "switch_groups",
        "switches",
        "switch_ports",
        "cabling_batches",
        "cable_entries",
    }
    assert switch_business_types == [
        ("business", "业务"),
        ("management", "管理"),
        ("oob", "带外"),
        ("storage", "存储"),
    ]
    assert rack_columns["room_name"] == {"type": "VARCHAR(100)", "not_null": True}
    assert rack_columns["rack_column"] == {"type": "VARCHAR(20)", "not_null": True}
    assert rack_columns["rack_number"] == {"type": "INTEGER", "not_null": True}
    assert "ck_rack_name_matches_parts" in rack_table_sql
    assert "uq_rack_position" not in rack_table_sql
    assert rack_indexes["ix_rack_position"] == {"unique": False}
    assert rack_position_index_columns == ["region_id", "room_name", "rack_column", "rack_number"]
    assert switch_port_columns["card_number"]["not_null"] is True
    assert switch_port_columns["subcard_number"]["not_null"] is True
    assert switch_port_columns["card_number"]["default"] in {"1", "'1'"}
    assert switch_port_columns["subcard_number"]["default"] in {"0", "'0'"}
    assert "ck_switch_port_card_number_nonnegative" in switch_port_table_sql
    assert "ck_switch_port_subcard_number_nonnegative" in switch_port_table_sql
    assert "uq_switch_port_position" in switch_port_table_sql


def test_rack_structure_migration_clears_unreferenced_legacy_racks(tmp_path: Path) -> None:
    """旧机柜没有交换机或线缆引用时，结构化迁移应按设计清空旧数据。"""
    database_path = tmp_path / "rack_clear.db"
    initial_upgrade = _run_alembic(database_path, "upgrade", LEGACY_CABLING_REVISION)
    assert initial_upgrade.returncode == 0, initial_upgrade.stderr
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO regions (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("region-1", "Region-A", TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO racks (id, region_id, name, u_height, created_at, updated_at) " "VALUES (?, ?, ?, ?, ?, ?)",
            ("rack-1", "region-1", "LEGACY-RACK", 42, TIMESTAMP, TIMESTAMP),
        )
        connection.commit()

    result = _run_alembic(database_path, "upgrade", RACK_STRUCTURE_REVISION)

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        rack_count = connection.execute("SELECT COUNT(*) FROM racks").fetchone()
    assert revision == (RACK_STRUCTURE_REVISION,)
    assert rack_count == (0,)


def test_rack_structure_migration_rejects_referenced_legacy_racks(tmp_path: Path) -> None:
    """旧机柜仍有交换机时，结构化迁移必须中止并保留原数据。"""
    database_path = tmp_path / "rack_referenced.db"
    initial_upgrade = _run_alembic(database_path, "upgrade", LEGACY_CABLING_REVISION)
    assert initial_upgrade.returncode == 0, initial_upgrade.stderr
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO regions (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("region-1", "Region-A", TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO racks (id, region_id, name, u_height, created_at, updated_at) " "VALUES (?, ?, ?, ?, ?, ?)",
            ("rack-1", "region-1", "LEGACY-RACK", 42, TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO switches "
            "(id, rack_id, name, port_speed_mbps, start_u, height_u, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("switch-1", "rack-1", "switch-1", 25000, 42, 1, TIMESTAMP, TIMESTAMP),
        )
        connection.commit()

    result = _run_alembic(database_path, "upgrade", RACK_STRUCTURE_REVISION)

    assert result.returncode != 0
    assert "旧机柜仍被交换机或线缆引用" in result.stderr
    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        rack = connection.execute("SELECT id, name FROM racks").fetchone()
        switch = connection.execute("SELECT id, rack_id FROM switches").fetchone()
    assert revision == (LEGACY_CABLING_REVISION,)
    assert rack == ("rack-1", "LEGACY-RACK")
    assert switch == ("switch-1", "rack-1")


def test_switch_port_structure_migration_preserves_ids_and_cable_references(tmp_path: Path) -> None:
    """端口结构化迁移必须保留既有端口 ID 及线缆外键引用。"""
    database_path = tmp_path / "switch_port_preserve.db"
    initial_upgrade = _run_alembic(database_path, "upgrade", RACK_STRUCTURE_REVISION)
    assert initial_upgrade.returncode == 0, initial_upgrade.stderr
    _insert_cabling_topology_before_switch_port_structure(database_path)

    result = _run_alembic(database_path, "upgrade", "head")

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        port = connection.execute(
            "SELECT id, switch_id, card_number, subcard_number, port_number FROM switch_ports"
        ).fetchone()
        cable = connection.execute("SELECT id, switch_port_id FROM cable_entries").fetchone()
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    assert revision == (RACK_POSITION_INDEX_REVISION,)
    assert port == ("port-1", "switch-1", 1, 0, 1)
    assert cable == ("cable-1", "port-1")
    assert foreign_key_errors == []


def test_switch_port_structure_downgrade_rejects_cross_card_duplicate_numbers(tmp_path: Path) -> None:
    """跨板卡存在同号端口时，降级必须中止以避免唯一约束冲突。"""
    database_path = tmp_path / "switch_port_downgrade_guard.db"
    initial_upgrade = _run_alembic(database_path, "upgrade", "head")
    assert initial_upgrade.returncode == 0, initial_upgrade.stderr
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO regions (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("region-1", "Region-A", TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO racks "
            "(id, region_id, name, room_name, rack_column, rack_number, u_height, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("rack-1", "region-1", "ROOM-A01", "ROOM", "A", 1, 42, TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO switches "
            "(id, rack_id, name, port_speed_mbps, start_u, height_u, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("switch-1", "rack-1", "switch-1", 25000, 42, 1, TIMESTAMP, TIMESTAMP),
        )
        connection.executemany(
            "INSERT INTO switch_ports "
            "(id, switch_id, card_number, subcard_number, port_number, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("port-1", "switch-1", 1, 0, 1, TIMESTAMP, TIMESTAMP),
                ("port-2", "switch-1", 2, 0, 1, TIMESTAMP, TIMESTAMP),
            ],
        )
        connection.commit()

    result = _run_alembic(database_path, "downgrade", RACK_STRUCTURE_REVISION)

    assert result.returncode != 0
    assert "存在跨板卡或子板卡的同号端口" in result.stderr
    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        port_count = connection.execute("SELECT COUNT(*) FROM switch_ports").fetchone()
    assert revision == (SWITCH_PORT_STRUCTURE_REVISION,)
    assert port_count == (2,)


def _insert_cabling_topology_before_switch_port_structure(database_path: Path) -> None:
    """在端口结构化迁移前写入一条带线缆引用的完整拓扑。"""
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO regions (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("region-1", "Region-A", TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO racks "
            "(id, region_id, name, room_name, rack_column, rack_number, u_height, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("rack-1", "region-1", "ROOM-A01", "ROOM", "A", 1, 42, TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO switches "
            "(id, rack_id, name, port_speed_mbps, start_u, height_u, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("switch-1", "rack-1", "switch-1", 25000, 42, 1, TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO switch_ports (id, switch_id, port_number, created_at, updated_at) " "VALUES (?, ?, ?, ?, ?)",
            ("port-1", "switch-1", 1, TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO cabling_batches "
            "(id, region_id, name, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("batch-1", "region-1", "第一批布线", "tester", TIMESTAMP, TIMESTAMP),
        )
        connection.execute(
            "INSERT INTO cable_entries "
            "(id, batch_id, server_rack_id, server_start_u, server_height_u, server_port_name, "
            "switch_port_id, cable_label, cable_sequence, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cable-1",
                "batch-1",
                "rack-1",
                10,
                1,
                "NIC1",
                "port-1",
                "CBL-000001",
                1,
                TIMESTAMP,
                TIMESTAMP,
            ),
        )
        connection.commit()
