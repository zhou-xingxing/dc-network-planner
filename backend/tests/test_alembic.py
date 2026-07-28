"""Alembic 数据库配置测试。"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_uses_application_database_url(tmp_path: Path) -> None:
    """迁移必须写入 DATABASE_URL 指定的数据库。"""
    database_path = tmp_path / "alembic_target.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

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

    assert revision == ("7b1d9e4c2a6f",)
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
