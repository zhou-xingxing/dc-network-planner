from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_name, require_administrator
from app.exceptions import BusinessError
from app.models.backup import BackupConfig, BackupRecord
from app.models.user import User
from app.schemas.backup import BackupConfigResponse, BackupConfigUpdate, BackupMethod, BackupRecordResponse
from app.schemas.common import PaginatedResponse
from app.services.backup import get_backup_config, list_backup_records, run_backup, update_backup_config
from app.utils.time_utils import format_datetime

router = APIRouter(prefix="/api/backup", tags=["Backup"], dependencies=[Depends(get_current_user)])


@router.get("/config", response_model=BackupConfigResponse)
def get_config_endpoint(db: Session = Depends(get_db)) -> BackupConfigResponse:
    """获取全局备份配置。"""
    try:
        config = get_backup_config(db)
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_config_response(config)


@router.put("/config", response_model=BackupConfigResponse)
def update_config_endpoint(
    data: BackupConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> BackupConfigResponse:
    """更新全局备份配置。"""
    try:
        config = update_backup_config(db, data, operator_name(current_user))
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_config_response(config)


@router.post("/run", response_model=BackupRecordResponse, status_code=201)
def run_backup_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_administrator),
) -> BackupRecordResponse:
    """立即执行一次备份。"""
    try:
        record = run_backup(db, operator=operator_name(current_user), scheduled=False)
    except BusinessError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_record_response(record)


@router.get("/records", response_model=PaginatedResponse[BackupRecordResponse])
def list_records_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[BackupRecordResponse]:
    """查询备份执行历史。"""
    records, total = list_backup_records(db, skip=skip, limit=limit)
    return PaginatedResponse(
        items=[_to_record_response(record) for record in records],
        total=total,
        skip=skip,
        limit=limit,
    )


def _to_config_response(config: BackupConfig) -> BackupConfigResponse:
    return BackupConfigResponse(
        id=config.id,
        enabled=config.enabled,
        cron_expression=config.cron_expression,
        backup_file_prefix=config.backup_file_prefix,
        method=_to_backup_method(config.method),
        local_path=config.local_path,
        endpoint_url=config.endpoint_url,
        access_key=config.access_key,
        secret_key_configured=bool(config.secret_key),
        bucket=config.bucket,
        object_prefix=config.object_prefix,
        next_run_at=format_datetime(config.next_run_at),
        created_at=format_datetime(config.created_at),
        updated_at=format_datetime(config.updated_at),
    )


def _to_backup_method(value: str) -> BackupMethod:
    if value == "local" or value == "object_storage":
        return value
    raise HTTPException(status_code=500, detail=f"Invalid backup method: {value}")


def _to_record_response(record: BackupRecord) -> BackupRecordResponse:
    return BackupRecordResponse(
        id=record.id,
        status=record.status,
        method=record.method,
        target=record.target,
        file_size=record.file_size,
        error_message=record.error_message,
        operator=record.operator,
        started_at=format_datetime(record.started_at),
        finished_at=format_datetime(record.finished_at),
    )
