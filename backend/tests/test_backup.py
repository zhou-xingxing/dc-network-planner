from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

import app.services.backup as backup_service
from app.exceptions import BusinessError
from app.models.backup import BackupConfig, BackupRecord
from app.models.region import Region
from app.schemas.backup import BackupConfigUpdate
from app.services.backup import calculate_next_run, run_due_backup, utcnow


class _NoQueryDB:
    """用于确认不依赖数据库的备份配置错误会先被拦截。"""

    def query(self, *args, **kwargs):
        raise AssertionError("invalid backup config should not touch database")


def test_get_backup_config_returns_default(client, admin_headers):
    response = client.get("/api/backup/config", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["cron_expression"] == "0 2 * * *"
    assert data["backup_file_prefix"] == "dc_network_planner_data_backup_"
    assert data["method"] == "local"
    assert data["secret_key_configured"] is False


def test_backup_read_endpoints_allow_normal_user(client, user_headers_factory):
    user_headers = user_headers_factory([])

    config_response = client.get("/api/backup/config", headers=user_headers)
    records_response = client.get("/api/backup/records", headers=user_headers)

    assert config_response.status_code == 200
    assert records_response.status_code == 200


def test_backup_write_endpoints_require_administrator(client, tmp_path, user_headers_factory):
    user_headers = user_headers_factory([])

    update_response = client.put(
        "/api/backup/config",
        headers=user_headers,
        json={
            "enabled": True,
            "cron_expression": "0 2 * * *",
            "method": "local",
            "local_path": str(tmp_path),
        },
    )
    run_response = client.post("/api/backup/run", headers=user_headers)

    assert update_response.status_code == 403
    assert run_response.status_code == 403


def test_update_backup_config(client, tmp_path, admin_headers):
    response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "15 23 * * 5",
            "backup_file_prefix": "dc_backup_",
            "method": "local",
            "local_path": str(tmp_path),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["cron_expression"] == "15 23 * * 5"
    assert data["backup_file_prefix"] == "dc_backup_"
    assert data["local_path"] == str(tmp_path)
    assert data["next_run_at"] is not None


def test_update_backup_config_validates_cron_expression(client, tmp_path, admin_headers):
    response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "60 2 * * *",
            "method": "local",
            "local_path": str(tmp_path),
        },
    )

    assert response.status_code == 409
    assert "分钟" in response.json()["detail"]


def test_update_backup_config_invalid_cron_is_rejected_before_database_query(tmp_path):
    """无效 cron 是纯输入错误，应在读取现有备份配置前返回。"""
    data = BackupConfigUpdate(
        enabled=True,
        cron_expression="60 2 * * *",
        backup_file_prefix="backup_",
        method="local",
        local_path=str(tmp_path),
    )

    with pytest.raises(BusinessError):
        backup_service.update_backup_config(_NoQueryDB(), data, "tester")


def test_update_backup_config_validates_backup_file_prefix(client, tmp_path, admin_headers):
    response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "0 2 * * *",
            "backup_file_prefix": "backup/",
            "method": "local",
            "local_path": str(tmp_path),
        },
    )

    assert response.status_code == 409
    assert "路径分隔符" in response.json()["detail"]


def test_update_backup_config_invalid_prefix_is_rejected_before_database_query(tmp_path):
    """备份文件名前缀格式错误不需要读取现有配置。"""
    data = BackupConfigUpdate(
        enabled=True,
        cron_expression="0 2 * * *",
        backup_file_prefix="backup/",
        method="local",
        local_path=str(tmp_path),
    )

    with pytest.raises(BusinessError):
        backup_service.update_backup_config(_NoQueryDB(), data, "tester")


def test_update_backup_config_validates_local_path_is_writable(client, tmp_path, admin_headers):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("occupied")

    response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "0 2 * * *",
            "backup_file_prefix": "backup_",
            "method": "local",
            "local_path": str(file_path),
        },
    )

    assert response.status_code == 409
    assert "本地备份路径不可写" in response.json()["detail"]


def test_update_backup_config_validates_object_storage_target(client, monkeypatch, admin_headers):
    calls = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

    def fake_client(*args, **kwargs):
        calls.append(("client", kwargs))
        return FakeS3Client()

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=fake_client))

    response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "0 2 * * *",
            "backup_file_prefix": "backup_",
            "method": "object_storage",
            "endpoint_url": "https://obs.example.com",
            "access_key": "ak",
            "secret_key": "sk",
            "bucket": "dc-network-planner-backup",
            "object_prefix": "dc-network-planner",
        },
    )

    assert response.status_code == 200
    assert calls[0] == (
        "client",
        {
            "endpoint_url": "https://obs.example.com",
            "aws_access_key_id": "ak",
            "aws_secret_access_key": "sk",
        },
    )
    assert calls[1][0] == "put"
    assert calls[1][1]["Bucket"] == "dc-network-planner-backup"
    assert calls[1][1]["Key"].startswith("dc-network-planner/.dc_network_planner_backup_probe_")
    assert calls[2][0] == "delete"


def test_update_backup_config_reuses_existing_object_storage_secret(client, monkeypatch, admin_headers):
    client_calls = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            pass

        def delete_object(self, **kwargs):
            pass

    def fake_client(*args, **kwargs):
        client_calls.append(kwargs)
        return FakeS3Client()

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=fake_client))

    first_response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "0 2 * * *",
            "backup_file_prefix": "backup_",
            "method": "object_storage",
            "endpoint_url": "https://obs.example.com",
            "access_key": "ak",
            "secret_key": "first-secret",
            "bucket": "dc-network-planner-backup",
        },
    )
    second_response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "15 3 * * *",
            "backup_file_prefix": "backup_",
            "method": "object_storage",
            "endpoint_url": "https://obs.example.com",
            "access_key": "ak",
            "bucket": "dc-network-planner-backup",
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["secret_key_configured"] is True
    assert client_calls[-1]["aws_secret_access_key"] == "first-secret"


def test_update_backup_config_rejects_invalid_object_storage_target(client, monkeypatch, admin_headers):
    class FakeS3Client:
        def put_object(self, **kwargs):
            raise RuntimeError("access denied")

    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(client=lambda *args, **kwargs: FakeS3Client()),
    )

    response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "0 2 * * *",
            "backup_file_prefix": "backup_",
            "method": "object_storage",
            "endpoint_url": "https://obs.example.com",
            "access_key": "ak",
            "secret_key": "sk",
            "bucket": "dc-network-planner-backup",
        },
    )

    assert response.status_code == 409
    assert "对象存储备份目标校验失败" in response.json()["detail"]


def test_update_backup_config_validates_local_path(client, admin_headers):
    response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": True,
            "cron_expression": "0 2 * * *",
            "method": "local",
            "local_path": "",
        },
    )

    assert response.status_code == 422


def test_run_backup_creates_sqlite_file(client, tmp_path, admin_headers):
    config_response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": False,
            "cron_expression": "30 2 * * *",
            "backup_file_prefix": "dc_",
            "method": "local",
            "local_path": str(tmp_path),
        },
    )
    assert config_response.status_code == 200

    response = client.post("/api/backup/run", headers=admin_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["method"] == "local"
    assert data["file_size"] > 0
    target = Path(data["target"])
    assert target.exists()
    assert target.parent == tmp_path
    assert re.fullmatch(r"dc_\d{14}", target.name)


def test_run_backup_records_object_storage_full_target(client, monkeypatch, admin_headers):
    calls = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

        def upload_file(self, filename, bucket, key):
            calls.append(("upload", filename, bucket, key))

    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(client=lambda *args, **kwargs: FakeS3Client()),
    )
    config_response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": False,
            "cron_expression": "30 2 * * *",
            "backup_file_prefix": "dc_",
            "method": "object_storage",
            "endpoint_url": "https://obs.example.com/",
            "access_key": "ak",
            "secret_key": "sk",
            "bucket": "dc-network-planner-backup",
            "object_prefix": "dc-network-planner",
        },
    )
    assert config_response.status_code == 200

    response = client.post("/api/backup/run", headers=admin_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert re.fullmatch(
        r"https://obs\.example\.com/dc-network-planner-backup/dc-network-planner/dc_\d{14}",
        data["target"],
    )
    upload_call = [call for call in calls if call[0] == "upload"][0]
    assert upload_call[2] == "dc-network-planner-backup"
    assert re.fullmatch(r"dc-network-planner/dc_\d{14}", upload_call[3])


def test_run_backup_records_failed_status_when_backup_creation_fails(client, tmp_path, monkeypatch, admin_headers):
    config_response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": False,
            "cron_expression": "30 2 * * *",
            "backup_file_prefix": "dc_",
            "method": "local",
            "local_path": str(tmp_path),
        },
    )
    assert config_response.status_code == 200

    def fail_create_sqlite_backup(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(backup_service, "_create_sqlite_backup", fail_create_sqlite_backup)

    response = client.post("/api/backup/run", headers=admin_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "disk full"
    assert data["finished_at"] is not None
    assert data["target"] is None
    assert data["file_size"] is None


def test_run_backup_records_failed_upload_and_refreshes_next_run(client, monkeypatch, admin_headers, test_db):
    calls = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

        def upload_file(self, filename, bucket, key):
            calls.append(("upload", filename, bucket, key))
            raise RuntimeError("upload failed")

    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(client=lambda *args, **kwargs: FakeS3Client()),
    )
    config_response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": False,
            "cron_expression": "*/5 * * * *",
            "backup_file_prefix": "dc_",
            "method": "object_storage",
            "endpoint_url": "https://obs.example.com",
            "access_key": "ak",
            "secret_key": "sk",
            "bucket": "dc-network-planner-backup",
            "object_prefix": "dc-network-planner",
        },
    )
    assert config_response.status_code == 200

    old_next_run_at = utcnow() - timedelta(days=1)
    session = Session(test_db)
    try:
        config = session.query(BackupConfig).first()
        config.enabled = True
        config.next_run_at = old_next_run_at
        session.commit()
    finally:
        session.close()

    response = client.post("/api/backup/run", headers=admin_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "upload failed"
    assert [call for call in calls if call[0] == "upload"]

    session = Session(test_db)
    try:
        config = session.query(BackupConfig).first()
        assert config.next_run_at is not None
        assert config.next_run_at > old_next_run_at.replace(tzinfo=None)
    finally:
        session.close()


def test_run_backup_returns_409_for_business_error(client, tmp_path, monkeypatch, admin_headers):
    config_response = client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": False,
            "cron_expression": "30 2 * * *",
            "backup_file_prefix": "dc_",
            "method": "local",
            "local_path": str(tmp_path),
        },
    )
    assert config_response.status_code == 200

    def fail_with_business_error(*args, **kwargs):
        raise BusinessError("当前备份功能仅支持 SQLite 数据库")

    monkeypatch.setattr(backup_service, "_create_sqlite_backup", fail_with_business_error)

    response = client.post("/api/backup/run", headers=admin_headers)

    assert response.status_code == 409
    assert "SQLite" in response.json()["detail"]


def test_run_backup_rejects_incomplete_object_storage_config(client, admin_headers, test_db):
    session = Session(test_db)
    try:
        config = session.query(BackupConfig).first()
        config.enabled = False
        config.cron_expression = "30 2 * * *"
        config.backup_file_prefix = "dc_"
        config.method = "object_storage"
        config.endpoint_url = "https://obs.example.com"
        config.access_key = "ak"
        config.secret_key = None
        config.bucket = "dc-network-planner-backup"
        session.commit()
    finally:
        session.close()

    response = client.post("/api/backup/run", headers=admin_headers)

    assert response.status_code == 409
    assert "secret_key" in response.json()["detail"]


def test_list_backup_records(client, tmp_path, admin_headers):
    client.put(
        "/api/backup/config",
        headers=admin_headers,
        json={
            "enabled": False,
            "cron_expression": "30 2 * * *",
            "method": "local",
            "local_path": str(tmp_path),
        },
    )
    client.post("/api/backup/run", headers=admin_headers)

    response = client.get("/api/backup/records", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "success"


def test_run_due_backup_only_when_enabled_and_due(test_db, tmp_path):
    session = Session(test_db)
    try:
        session.add(Region(name="cn-north-1", description="北京"))
        config = session.query(BackupConfig).first()
        config.enabled = True
        config.cron_expression = "30 2 * * *"
        config.method = "local"
        config.local_path = str(tmp_path)
        config.next_run_at = utcnow() - timedelta(minutes=1)
        session.commit()

        record = run_due_backup(session)
        session.commit()

        assert record is not None
        assert record.status == "success"
        assert session.query(BackupRecord).count() == 1
    finally:
        session.close()


def test_run_due_backup_skips_when_disabled(test_db, tmp_path):
    session = Session(test_db)
    try:
        config = session.query(BackupConfig).first()
        config.enabled = False
        config.cron_expression = "30 2 * * *"
        config.method = "local"
        config.local_path = str(tmp_path)
        config.next_run_at = utcnow() - timedelta(minutes=1)
        session.commit()

        record = run_due_backup(session)
        session.commit()

        assert record is None
        assert session.query(BackupRecord).count() == 0
    finally:
        session.close()


def test_run_due_backup_initializes_next_run_without_running(test_db, tmp_path):
    session = Session(test_db)
    try:
        config = session.query(BackupConfig).first()
        config.enabled = True
        config.cron_expression = "* * * * *"
        config.method = "local"
        config.local_path = str(tmp_path)
        config.next_run_at = None
        session.commit()

        record = run_due_backup(session)
        session.commit()

        assert record is None
        assert config.next_run_at is not None
        assert session.query(BackupRecord).count() == 0
    finally:
        session.close()


def test_run_due_backup_skips_when_not_due(test_db, tmp_path):
    session = Session(test_db)
    try:
        config = session.query(BackupConfig).first()
        config.enabled = True
        config.cron_expression = "30 2 * * *"
        config.method = "local"
        config.local_path = str(tmp_path)
        config.next_run_at = utcnow() + timedelta(hours=1)
        session.commit()

        record = run_due_backup(session)
        session.commit()

        assert record is None
        assert session.query(BackupRecord).count() == 0
    finally:
        session.close()


def test_calculate_next_run_daily_uses_configured_time():
    before_time = datetime(2026, 4, 25, 18, 10, tzinfo=timezone.utc)
    after_time = datetime(2026, 4, 25, 19, 10, tzinfo=timezone.utc)

    assert calculate_next_run(before_time, "30 2 * * *") == datetime(2026, 4, 25, 18, 30, tzinfo=timezone.utc)
    assert calculate_next_run(after_time, "30 2 * * *") == datetime(2026, 4, 26, 18, 30, tzinfo=timezone.utc)


def test_calculate_next_run_weekly_uses_weekday_and_time():
    sunday_before_time = datetime(2026, 4, 25, 18, 10, tzinfo=timezone.utc)
    sunday_after_time = datetime(2026, 4, 25, 19, 10, tzinfo=timezone.utc)

    assert calculate_next_run(sunday_before_time, "30 2 * * 0") == datetime(2026, 4, 25, 18, 30, tzinfo=timezone.utc)
    assert calculate_next_run(sunday_after_time, "30 2 * * 7") == datetime(2026, 5, 2, 18, 30, tzinfo=timezone.utc)
    assert calculate_next_run(sunday_after_time, "30 2 * * 1") == datetime(2026, 4, 26, 18, 30, tzinfo=timezone.utc)


def test_calculate_next_run_supports_steps_ranges_and_lists():
    base_time = datetime(2026, 4, 25, 18, 10, tzinfo=timezone.utc)

    assert calculate_next_run(base_time, "*/15 2-4 * * 0,1") == datetime(2026, 4, 25, 18, 15, tzinfo=timezone.utc)


def test_calculate_next_run_uses_cron_day_or_weekday_semantics():
    base_time = datetime(2026, 4, 30, 18, 10, tzinfo=timezone.utc)

    assert calculate_next_run(base_time, "30 2 2 * 1") == datetime(2026, 5, 1, 18, 30, tzinfo=timezone.utc)


def test_parse_cron_expression_rejects_invalid_formats():
    """解析层应拒绝格式错误的 cron 表达式。"""
    from app.services.backup import parse_cron_expression

    # 段数不足/过多
    with pytest.raises(Exception, match="5 段"):
        parse_cron_expression("0 2 * *")
    with pytest.raises(Exception, match="5 段"):
        parse_cron_expression("0 2 * * * *")

    # 越界值
    with pytest.raises(Exception, match="分钟"):
        parse_cron_expression("60 2 * * *")
    with pytest.raises(Exception, match="小时"):
        parse_cron_expression("0 24 * * *")
    with pytest.raises(Exception, match="日期"):
        parse_cron_expression("0 2 32 * *")
    with pytest.raises(Exception, match="月份"):
        parse_cron_expression("0 2 * 13 *")
    with pytest.raises(Exception, match="星期"):
        parse_cron_expression("0 2 * * 8")

    # 非数字
    with pytest.raises(Exception, match="非数字"):
        parse_cron_expression("abc 2 * * *")

    # 空片段（连续逗号导致）
    with pytest.raises(Exception, match="空片段"):
        parse_cron_expression("1,,2 * * * *")

    # 范围起始大于结束
    with pytest.raises(Exception, match="起始值不能大于结束值"):
        parse_cron_expression("5-1 * * * *")

    # 步长为 0
    with pytest.raises(Exception, match="步长必须大于 0"):
        parse_cron_expression("*/0 * * * *")


def test_parse_cron_expression_accepts_various_formats():
    """解析层应正确接受各种合法格式。"""
    from app.services.backup import parse_cron_expression

    # 通配符
    minute, hour, day, month, weekday = parse_cron_expression("* * * * *")
    assert minute == set(range(0, 60))
    assert hour == set(range(0, 24))
    assert day == set(range(1, 32))
    assert month == set(range(1, 13))
    assert weekday == set(range(0, 8))

    # 固定值
    minute, hour, day, month, weekday = parse_cron_expression("0 2 15 3 1")
    assert minute == {0}
    assert hour == {2}
    assert day == {15}
    assert month == {3}
    assert weekday == {1}

    # 列表
    minute, hour, day, month, weekday = parse_cron_expression("0,15,30 2 * * 1,5")
    assert minute == {0, 15, 30}
    assert weekday == {1, 5}

    # 范围
    minute, hour, day, month, weekday = parse_cron_expression("1-5 2-4 * * 0-3")
    assert minute == {1, 2, 3, 4, 5}
    assert hour == {2, 3, 4}
    assert weekday == {0, 1, 2, 3}

    # 步长
    minute, hour, day, month, weekday = parse_cron_expression("*/15 */3 * * *")
    assert minute == {0, 15, 30, 45}
    assert hour == {0, 3, 6, 9, 12, 15, 18, 21}

    # 范围+步长
    minute, hour, day, month, weekday = parse_cron_expression("1-10/2 * * * *")
    assert minute == {1, 3, 5, 7, 9}

    # 周日 0 和 7 等价（在 _cron_matches 中处理，解析层保留原始值）
    _, _, _, _, weekday_0 = parse_cron_expression("0 2 * * 0")
    _, _, _, _, weekday_7 = parse_cron_expression("0 2 * * 7")
    assert weekday_0 == {0}
    assert weekday_7 == {7}
