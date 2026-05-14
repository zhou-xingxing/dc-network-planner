from __future__ import annotations

import logging
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Protocol, cast

from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessError
from app.models.backup import BackupConfig, BackupRecord
from app.schemas.backup import BackupConfigUpdate
from app.services.change_log import log_change
from app.utils.time_utils import app_timezone, to_db_datetime, to_utc, utcnow

logger = logging.getLogger(__name__)
DEFAULT_BACKUP_FILE_PREFIX = "dc_network_planner_data_backup_"
CRON_RANGES = (
    (0, 59, "分钟"),
    (0, 23, "小时"),
    (1, 31, "日期"),
    (1, 12, "月份"),
    (0, 7, "星期"),
)
MAX_CRON_LOOKAHEAD_MINUTES = 5 * 366 * 24 * 60


class ObjectStorageClient(Protocol):
    """S3-compatible client methods used by backup service."""

    def put_object(self, **kwargs: object) -> object:
        """Upload a small object used for target validation."""

    def delete_object(self, **kwargs: object) -> object:
        """Delete a target-validation probe object."""

    def upload_file(self, Filename: str, Bucket: str, Key: str) -> object:  # noqa: N803
        """Upload a generated backup file."""


def calculate_next_run(base_time: datetime, cron_expression: str) -> datetime:
    """根据五段式 cron 表达式计算下一次备份时间。

    Args:
        base_time: 计算基准时间。
        cron_expression: 五段式 cron 表达式，格式为 分 时 日 月 周，秒固定为 0。

    Returns:
        下一次应执行备份的 timezone-aware UTC 时间。

    Raises:
        BusinessError: cron 表达式不合法，或无法在允许范围内计算出下次运行时间。
    """
    cron = parse_cron_expression(cron_expression)
    tz = app_timezone()
    base_local = to_utc(base_time).astimezone(tz)
    candidate = base_local.replace(second=0, microsecond=0) + timedelta(minutes=1)

    for _ in range(MAX_CRON_LOOKAHEAD_MINUTES):
        if _cron_matches(candidate, cron):
            return candidate.astimezone(to_utc(base_time).tzinfo)
        candidate += timedelta(minutes=1)
    raise BusinessError("无法在未来 5 年内计算出下一次备份时间")


def parse_cron_expression(
    cron_expression: str,
) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """解析五段式 cron 表达式。

    支持 `*`、数字、列表、范围和步长，例如 `0 2 * * *`、`*/15 * * * *`、`30 3 * * 1-5`。

    Args:
        cron_expression: 五段式 cron 表达式，格式为 分 时 日 月 周。

    Returns:
        每个 cron 字段允许值的集合。

    Raises:
        BusinessError: cron 表达式不合法。
    """
    fields = cron_expression.strip().split()
    if len(fields) != 5:
        raise BusinessError("Cron 表达式必须是 5 段格式: 分 时 日 月 周")
    return (
        _parse_cron_field(fields[0], *CRON_RANGES[0]),
        _parse_cron_field(fields[1], *CRON_RANGES[1]),
        _parse_cron_field(fields[2], *CRON_RANGES[2]),
        _parse_cron_field(fields[3], *CRON_RANGES[3]),
        _parse_cron_field(fields[4], *CRON_RANGES[4]),
    )


def _parse_cron_field(field: str, min_value: int, max_value: int, label: str) -> set[int]:
    """解析 cron 单字段（如分钟、小时），支持列表、范围、步长。

    例如："1,3-5,*/15" 会解析为 {1, 3, 4, 5, 0, 15, 30, 45}。
    """
    values: set[int] = set()
    for part in field.split(","):
        values.update(_parse_cron_part(part.strip(), min_value, max_value, label))
    if not values:
        raise BusinessError(f"Cron {label}字段不能为空")
    return values


def _parse_cron_part(part: str, min_value: int, max_value: int, label: str) -> set[int]:
    """解析 cron 字段中的一个片段（不含逗号）。

    支持格式：`*`、`N`、`N-M`、`*/S`、`N-M/S`。
    """
    if not part:
        raise BusinessError(f"Cron {label}字段包含空片段")

    base, step = _split_step(part, label)
    if base == "*":
        start = min_value
        end = max_value
    elif "-" in base:
        start_text, end_text = base.split("-", 1)
        start = _parse_int(start_text, label)
        end = _parse_int(end_text, label)
        if start > end:
            raise BusinessError(f"Cron {label}范围起始值不能大于结束值")
    else:
        value = _parse_int(base, label)
        _validate_cron_value(value, min_value, max_value, label)
        return {value}

    _validate_cron_value(start, min_value, max_value, label)
    _validate_cron_value(end, min_value, max_value, label)
    return set(range(start, end + 1, step))


def _split_step(part: str, label: str) -> tuple[str, int]:
    """从 cron 片段中提取步长，例如 `*/15` -> (`*`, 15)。

    无步长时默认返回 1。
    """
    if "/" not in part:
        return part, 1
    base, step_text = part.split("/", 1)
    step = _parse_int(step_text, label)
    if step <= 0:
        raise BusinessError(f"Cron {label}步长必须大于 0")
    return base, step


def _parse_int(value: str, label: str) -> int:
    """将字符串解析为整数，非数字时抛出业务异常。"""
    if not value.isdigit():
        raise BusinessError(f"Cron {label}字段包含非数字值")
    return int(value)


def _validate_cron_value(value: int, min_value: int, max_value: int, label: str) -> None:
    """校验 cron 数值是否在允许范围内。"""
    if value < min_value or value > max_value:
        raise BusinessError(f"Cron {label}字段必须在 {min_value}-{max_value} 范围内")


def _cron_matches(candidate: datetime, cron: tuple[set[int], set[int], set[int], set[int], set[int]]) -> bool:
    """判断给定时间是否匹配已解析的 cron 表达式。

    日期和星期采用标准 cron 语义：
    - 若两者均为 `*`（全范围），则同时匹配（AND）；
    - 若任一被显式指定，则满足其一即可（OR）。
    星期中 0 和 7 均视为周日。
    """
    minute_values, hour_values, day_values, month_values, weekday_values = cron
    cron_weekday = (candidate.weekday() + 1) % 7
    weekday_match = cron_weekday in weekday_values or (cron_weekday == 0 and 7 in weekday_values)
    day_match = candidate.day in day_values
    if day_values != set(range(1, 32)) and weekday_values != set(range(0, 8)):
        day_match = day_match or weekday_match
    else:
        day_match = day_match and weekday_match
    return (
        candidate.minute in minute_values
        and candidate.hour in hour_values
        and day_match
        and candidate.month in month_values
    )


def ensure_backup_config(db: Session) -> BackupConfig:
    """确保全局备份配置存在，不存在时创建默认配置。

    应在应用启动时调用一次。

    Args:
        db: 数据库会话。

    Returns:
        全局备份配置。
    """
    config = db.query(BackupConfig).order_by(BackupConfig.created_at.asc()).first()
    if config:
        return config

    config = BackupConfig(
        enabled=False,
        cron_expression="0 2 * * *",
        backup_file_prefix=DEFAULT_BACKUP_FILE_PREFIX,
        method="local",
        local_path=settings.BACKUP_DEFAULT_LOCAL_PATH,
    )
    db.add(config)
    db.flush()
    return config


def get_backup_config(db: Session) -> BackupConfig:
    """获取全局备份配置。

    Args:
        db: 数据库会话。

    Returns:
        全局备份配置。

    Raises:
        BusinessError: 配置不存在。
    """
    config = db.query(BackupConfig).order_by(BackupConfig.created_at.asc()).first()
    if not config:
        raise BusinessError("备份配置不存在")
    return config


def update_backup_config(db: Session, data: BackupConfigUpdate, operator: str) -> BackupConfig:
    """更新全局备份配置。

    Args:
        db: 数据库会话。
        data: 新配置。
        operator: 操作者名称。

    Returns:
        更新后的备份配置。
    """
    _validate_backup_basic_format(data.cron_expression, data.backup_file_prefix)

    config = get_backup_config(db)
    old_value = _config_snapshot(config)

    config.enabled = data.enabled
    config.cron_expression = data.cron_expression.strip()
    config.backup_file_prefix = data.backup_file_prefix.strip()
    config.method = data.method
    config.local_path = data.local_path
    config.endpoint_url = data.endpoint_url
    config.access_key = data.access_key
    config.secret_key = data.secret_key or (  # 对象存储模式下不传则保留旧值；切回本地时清空
        config.secret_key if data.method == "object_storage" else None
    )
    config.bucket = data.bucket
    config.object_prefix = data.object_prefix
    _validate_storage_config(config)
    _validate_backup_target(config)
    config.next_run_at = to_db_datetime(_next_run_from_config(config, utcnow())) if data.enabled else None
    db.flush()

    log_change(
        db,
        entity_type="backup_config",
        entity_id=config.id,
        action="update",
        operator=operator,
        old_value=old_value,
        new_value=_config_snapshot(config),
    )
    return config


def list_backup_records(db: Session, skip: int = 0, limit: int = 20) -> tuple[list[BackupRecord], int]:
    """查询备份执行历史。

    Args:
        db: 数据库会话。
        skip: 分页偏移量。
        limit: 每页条数。

    Returns:
        (备份记录列表, 总数) 的元组。
    """
    query = db.query(BackupRecord)
    total = query.count()
    records = query.order_by(BackupRecord.started_at.desc()).offset(skip).limit(limit).all()
    return records, total


def run_backup(db: Session, operator: str = "system", scheduled: bool = False) -> BackupRecord:
    """执行一次数据库备份。

    Args:
        db: 数据库会话。
        operator: 操作者名称。
        scheduled: 是否由定时任务触发。

    Returns:
        备份执行记录。

    Raises:
        BusinessError: 配置不完整或对象存储依赖不可用。
    """
    config = get_backup_config(db)
    _validate_backup_basic_format(config.cron_expression, config.backup_file_prefix)
    _validate_storage_config(config)

    record = BackupRecord(
        status="running",
        method=config.method,
        operator=operator or "system",
        started_at=to_db_datetime(utcnow()),
    )
    db.add(record)
    db.flush()

    backup_file: Optional[Path] = None
    try:
        backup_file = _create_sqlite_backup(db, config)
        file_size = backup_file.stat().st_size
        if config.method == "local":
            target = str(backup_file)
        else:
            target = _upload_object_storage(config, backup_file)
            backup_file.unlink(missing_ok=True)

        record.status = "success"
        record.target = target
        record.file_size = file_size
        finished_at = to_db_datetime(utcnow())
        record.finished_at = finished_at
        if config.enabled:
            config.next_run_at = to_db_datetime(_next_run_from_config(config, finished_at))
        db.flush()

        log_change(
            db,
            entity_type="backup_config",
            entity_id=config.id,
            action="backup",
            operator=operator,
            new_value=target,
            comment="定时备份任务执行" if scheduled else "手动备份执行",
        )
    except Exception as exc:
        record.status = "failed"
        record.error_message = str(exc)
        finished_at = to_db_datetime(utcnow())
        record.finished_at = finished_at
        if config.enabled:
            config.next_run_at = to_db_datetime(_next_run_from_config(config, finished_at))
        db.flush()
        if isinstance(exc, BusinessError):
            raise
        logger.exception("Backup failed")
    return record


def run_due_backup(db: Session) -> Optional[BackupRecord]:
    """执行已到期的定时备份任务。

    Args:
        db: 数据库会话。

    Returns:
        已执行的备份记录；未到期时返回 None。
    """
    config = get_backup_config(db)
    now = utcnow()
    if not config.enabled:
        return None
    if config.next_run_at is None:
        config.next_run_at = to_db_datetime(_next_run_from_config(config, now))
        db.flush()
    if to_utc(config.next_run_at) > now:
        return None
    return run_backup(db, operator="system", scheduled=True)


def _validate_storage_config(config: BackupConfig) -> None:
    if config.method == "local" and not config.local_path:
        raise BusinessError("本地备份路径不能为空")
    if config.method == "object_storage":
        missing = []
        for field_name in ("endpoint_url", "access_key", "secret_key", "bucket"):
            if not getattr(config, field_name):
                missing.append(field_name)
        if missing:
            raise BusinessError(f"对象存储配置不完整: {', '.join(missing)}")


def _validate_backup_basic_format(cron_expression: str, backup_file_prefix: str) -> None:
    """校验备份调度和文件名前缀这类纯输入格式。"""
    parse_cron_expression(cron_expression.strip())
    backup_file_prefix = backup_file_prefix.strip()
    if not backup_file_prefix:
        raise BusinessError("备份文件名前缀不能为空")
    if "/" in backup_file_prefix or "\\" in backup_file_prefix:
        raise BusinessError("备份文件名前缀不能包含路径分隔符")


def _validate_backup_target(config: BackupConfig) -> None:
    if config.method == "local":
        _validate_local_backup_path(config)
    else:
        _validate_object_storage_target(config)


def _validate_local_backup_path(config: BackupConfig) -> None:
    target_dir = Path(config.local_path or settings.BACKUP_DEFAULT_LOCAL_PATH)
    probe_file = target_dir / f".dc_network_planner_backup_probe_{uuid.uuid4().hex}.tmp"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        probe_file.write_bytes(b"ok")
    except OSError as exc:
        raise BusinessError(f"本地备份路径不可写: {exc}") from exc
    finally:
        try:
            probe_file.unlink(missing_ok=True)
        except OSError:
            pass


def _validate_object_storage_target(config: BackupConfig) -> None:
    client = _create_object_storage_client(config)
    bucket = _required_object_storage_value(config.bucket, "bucket")
    prefix = (config.object_prefix or "").strip("/")
    object_key = f".dc_network_planner_backup_probe_{uuid.uuid4().hex}"
    if prefix:
        object_key = f"{prefix}/{object_key}"
    try:
        client.put_object(Bucket=bucket, Key=object_key, Body=b"")
    except Exception as exc:
        raise BusinessError(f"对象存储备份目标校验失败: {exc}") from exc
    try:
        client.delete_object(Bucket=bucket, Key=object_key)
    except Exception:
        logger.warning(
            "Failed to delete object storage backup probe: %s",
            object_key,
            exc_info=True,
        )


def _next_run_from_config(config: BackupConfig, base_time: datetime) -> datetime:
    return calculate_next_run(base_time, config.cron_expression)


def _create_sqlite_backup(db: Session, config: BackupConfig) -> Path:
    timestamp = utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{config.backup_file_prefix}{timestamp}"
    target_dir = Path(config.local_path or settings.BACKUP_DEFAULT_LOCAL_PATH)
    if config.method == "object_storage":
        target_dir = Path(tempfile.gettempdir()) / "dc_network_planner_backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / filename

    source = _get_sqlite_connection(db)
    dump_sql = "\n".join(source.iterdump())
    with sqlite3.connect(target_file) as target:
        target.executescript(dump_sql)
    return target_file


def _get_sqlite_connection(db: Session) -> sqlite3.Connection:
    raw_connection = db.connection().connection
    driver_connection = getattr(raw_connection, "driver_connection", raw_connection)
    if not isinstance(driver_connection, sqlite3.Connection):
        raise BusinessError("当前备份功能仅支持 SQLite 数据库")
    return driver_connection


def _upload_object_storage(config: BackupConfig, backup_file: Path) -> str:
    client = _create_object_storage_client(config)
    bucket = _required_object_storage_value(config.bucket, "bucket")
    prefix = (config.object_prefix or "").strip("/")
    object_key = f"{prefix}/{backup_file.name}" if prefix else backup_file.name
    client.upload_file(str(backup_file), bucket, object_key)
    return _build_object_storage_target(config, object_key)


def _build_object_storage_target(config: BackupConfig, object_key: str) -> str:
    endpoint = _required_object_storage_value(config.endpoint_url, "endpoint_url").rstrip("/")
    bucket = _required_object_storage_value(config.bucket, "bucket")
    return f"{endpoint}/{bucket}/{object_key.lstrip('/')}"


def _create_object_storage_client(config: BackupConfig) -> ObjectStorageClient:
    try:
        import boto3
    except ImportError as exc:
        raise BusinessError("对象存储备份需要安装 boto3 依赖") from exc

    return cast(
        ObjectStorageClient,
        boto3.client(
            "s3",
            endpoint_url=_required_object_storage_value(config.endpoint_url, "endpoint_url"),
            aws_access_key_id=_required_object_storage_value(config.access_key, "access_key"),
            aws_secret_access_key=_required_object_storage_value(config.secret_key, "secret_key"),
        ),
    )


def _required_object_storage_value(value: Optional[str], field_name: str) -> str:
    if not value:
        raise BusinessError(f"对象存储配置不完整: {field_name}")
    return value


def _config_snapshot(config: BackupConfig) -> str:
    """将备份配置序列化为字符串快照，用于变更日志记录。

    对 secret_key 仅记录存在状态（configured/empty），避免敏感信息泄露。
    """
    secret_state = "configured" if config.secret_key else "empty"
    return (
        f"enabled={config.enabled};cron_expression={config.cron_expression};"
        f"backup_file_prefix={config.backup_file_prefix};"
        f"method={config.method};"
        f"local_path={config.local_path or ''};endpoint_url={config.endpoint_url or ''};"
        f"access_key={config.access_key or ''};secret_key={secret_state};"
        f"bucket={config.bucket or ''};object_prefix={config.object_prefix or ''}"
    )
