#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.services.restore_database import RestoreError, restore_database_from_backup  # noqa: E402


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="从备份文件一键恢复 DC Network Planner SQLite 数据库。",
    )
    parser.add_argument("backup_file", type=Path, help="备份文件路径")
    parser.add_argument(
        "--database-url",
        default=settings.DATABASE_URL,
        help="目标数据库 URL，默认读取后端配置 DATABASE_URL",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="跳过交互确认，适合自动化脚本使用",
    )
    parser.add_argument(
        "--no-safety-backup",
        action="store_true",
        help="恢复前不保留当前数据库快照，谨慎使用",
    )
    args = parser.parse_args()

    if not args.yes:
        print("恢复会替换当前数据库文件。请先停止后端服务，避免仍在运行的进程继续持有旧数据库连接。")
        confirm = input("确认继续恢复？输入 YES 继续: ")
        if confirm != "YES":
            print("已取消恢复。")
            return 1

    try:
        result = restore_database_from_backup(
            args.backup_file,
            args.database_url,
            create_safety_backup=not args.no_safety_backup,
        )
    except RestoreError as exc:
        print(f"恢复失败: {exc}", file=sys.stderr)
        return 1

    print("恢复完成。")
    print(f"目标数据库: {result.database_path}")
    print(f"来源备份: {result.backup_path}")
    if result.safety_backup_path:
        print(f"恢复前快照: {result.safety_backup_path}")
    else:
        print("恢复前快照: 未创建（目标数据库原本不存在或已显式跳过）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
