"""系统日志能力测试。"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.exceptions import BusinessError, ResourceNotFoundError
from app.logging_config import ConsoleFormatter, setup_logging, shutdown_logging
from app.main import app


@pytest.fixture
def system_log_file(tmp_path: Path) -> Iterator[Path]:
    """使用临时日志目录，避免测试写入真实运行日志。"""
    old_values = {
        "LOG_DIR": settings.LOG_DIR,
        "LOG_FILE_NAME": settings.LOG_FILE_NAME,
        "LOG_MAX_BYTES": settings.LOG_MAX_BYTES,
        "LOG_BACKUP_COUNT": settings.LOG_BACKUP_COUNT,
    }
    settings.LOG_DIR = str(tmp_path)
    settings.LOG_FILE_NAME = "app.log"
    settings.LOG_MAX_BYTES = 2048
    settings.LOG_BACKUP_COUNT = 2
    setup_logging()
    try:
        yield tmp_path / "app.log"
    finally:
        shutdown_logging()
        for key, value in old_values.items():
            setattr(settings, key, value)


@pytest.fixture(scope="module", autouse=True)
def register_logging_test_routes() -> None:
    """注册只在测试中使用的异常路由，验证全局异常日志行为。"""

    @app.get("/__test__/unexpected-error", include_in_schema=False)
    def unexpected_error() -> None:
        raise RuntimeError("boom for logging test")

    @app.get("/__test__/explicit-500", include_in_schema=False)
    def explicit_500() -> None:
        raise HTTPException(status_code=500, detail="explicit 500 for logging test")

    @app.get("/__test__/leaked-business-error", include_in_schema=False)
    def leaked_business_error() -> None:
        raise BusinessError("leaked business error for logging test")

    @app.get("/__test__/leaked-not-found", include_in_schema=False)
    def leaked_not_found() -> None:
        raise ResourceNotFoundError("leaked resource not found for logging test")


def test_request_id_is_returned_and_written_to_access_log(
    client: TestClient,
    system_log_file: Path,
    admin_headers: dict[str, str],
) -> None:
    """访问日志应记录 request_id、请求上下文、状态码和认证用户名。"""
    request_id = "req-test-001"
    response = client.get("/api/regions", headers={**admin_headers, "X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id

    entries = _read_log_entries(system_log_file)
    access_entry = _find_entry(entries, logger="app.access", request_id=request_id)
    assert access_entry["method"] == "GET"
    assert access_entry["path"] == "/api/regions"
    assert access_entry["status_code"] == 200
    assert access_entry["username"] == "admin"
    assert isinstance(access_entry["duration_ms"], float)


def test_invalid_request_id_is_replaced(client: TestClient, admin_headers: dict[str, str]) -> None:
    """过长或无效的客户端 request_id 应被后端生成的新 ID 替换。"""
    response = client.get("/api/regions", headers={**admin_headers, "X-Request-ID": "x" * 200})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "x" * 200
    assert len(response.headers["X-Request-ID"]) <= 128


def test_health_check_is_not_written_to_access_log(client: TestClient, system_log_file: Path) -> None:
    """健康检查不写访问日志，避免定时探活产生噪声。"""
    request_id = "req-health-check"
    response = client.get("/api/health", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    entries = _read_log_entries(system_log_file)
    matching_entries = [
        entry for entry in entries if entry.get("logger") == "app.access" and entry.get("request_id") == request_id
    ]
    assert not matching_entries


def test_http_business_error_is_warning_without_stack_trace(
    client: TestClient,
    system_log_file: Path,
    admin_headers: dict[str, str],
) -> None:
    """4xx 业务错误只记录 WARNING 访问日志，不额外写异常日志。"""
    request_id = "req-business-error"
    response = client.get(
        "/api/lookup",
        params={"q": "not-an-ip"},
        headers={**admin_headers, "X-Request-ID": request_id},
    )

    assert response.status_code == 400
    entries = _read_log_entries(system_log_file)
    access_entry = _find_entry(entries, logger="app.access", request_id=request_id)
    assert access_entry["level"] == "WARNING"
    assert access_entry["status_code"] == 400
    matching_exceptions = [
        entry for entry in entries if entry.get("logger") == "app.exceptions" and entry.get("request_id") == request_id
    ]
    assert not matching_exceptions


def test_leaked_business_error_is_logged_as_router_conversion_gap(system_log_file: Path) -> None:
    """漏到全局处理器的 BusinessError 应记录 Router 漏转提示日志。"""
    request_id = "req-leaked-business-error"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test__/leaked-business-error", headers={"X-Request-ID": request_id})

    assert response.status_code == 409
    entries = _read_log_entries(system_log_file)
    error_entry = _find_entry(entries, logger="app.exceptions", request_id=request_id)
    assert error_entry["level"] == "WARNING"
    assert error_entry["message"] == "未被 Router 转换的 BusinessError"
    assert error_entry["status_code"] == 409
    assert "exception" not in error_entry

    access_entry = _find_entry(entries, logger="app.access", request_id=request_id)
    assert access_entry["level"] == "WARNING"
    assert access_entry["status_code"] == 409


def test_leaked_resource_not_found_is_logged_as_router_conversion_gap(system_log_file: Path) -> None:
    """漏到全局处理器的 ResourceNotFoundError 应记录 Router 漏转提示日志。"""
    request_id = "req-leaked-not-found"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test__/leaked-not-found", headers={"X-Request-ID": request_id})

    assert response.status_code == 404
    entries = _read_log_entries(system_log_file)
    error_entry = _find_entry(entries, logger="app.exceptions", request_id=request_id)
    assert error_entry["level"] == "WARNING"
    assert error_entry["message"] == "未被 Router 转换的 ResourceNotFoundError"
    assert error_entry["status_code"] == 404
    assert "exception" not in error_entry

    access_entry = _find_entry(entries, logger="app.access", request_id=request_id)
    assert access_entry["level"] == "WARNING"
    assert access_entry["status_code"] == 404


def test_unexpected_error_logs_stack_trace_and_returns_request_id(system_log_file: Path) -> None:
    """未预期异常应记录 ERROR 堆栈，并在 500 响应中返回 request_id。"""
    request_id = "req-unexpected-error"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test__/unexpected-error", headers={"X-Request-ID": request_id})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == request_id
    assert response.json()["request_id"] == request_id

    entries = _read_log_entries(system_log_file)
    error_entry = _find_entry(entries, logger="app.exceptions", request_id=request_id)
    assert error_entry["level"] == "ERROR"
    assert error_entry["status_code"] == 500
    exception_text = str(error_entry["exception"])
    assert "RuntimeError: boom for logging test" in exception_text


def test_http_500_error_logs_stack_trace(system_log_file: Path) -> None:
    """显式 5xx HTTPException 应记录 ERROR 堆栈，便于排查服务端故障。"""
    request_id = "req-explicit-500"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test__/explicit-500", headers={"X-Request-ID": request_id})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == request_id

    entries = _read_log_entries(system_log_file)
    error_entry = _find_entry(entries, logger="app.exceptions", request_id=request_id)
    assert error_entry["level"] == "ERROR"
    assert error_entry["status_code"] == 500
    exception_text = str(error_entry["exception"])
    assert "HTTPException" in exception_text
    assert "explicit 500 for logging test" in exception_text


def test_access_log_query_params_are_recorded_and_masked(
    client: TestClient,
    system_log_file: Path,
    admin_headers: dict[str, str],
) -> None:
    """访问日志应记录查询参数，并按 key 脱敏其中的敏感值。"""
    request_id = "req-query-params-mask"
    response = client.get(
        "/api/lookup",
        params={"q": "10.0.0.1", "token": "query-token"},
        headers={**admin_headers, "X-Request-ID": request_id},
    )

    assert response.status_code == 200
    entries = _read_log_entries(system_log_file)
    access_entry = _find_entry(entries, logger="app.access", request_id=request_id)
    query_params = cast(dict[str, object], access_entry["query_params"])
    assert query_params["q"] == "10.0.0.1"
    assert query_params["token"] == "***"


def test_log_extra_fields_are_masked(system_log_file: Path) -> None:
    """JSON 文件日志应脱敏结构化字段和常见非结构化凭据文本。"""
    logger = logging.getLogger("app.security_test")
    logger.info(
        "sensitive payload password=message-password authorization: Bearer message-token",
        extra={
            "authorization": "Bearer secret-token",
            "error_detail": 'secret_key="detail-secret" access_key=detail-access-key',
            "payload": {
                "password": "plain-password",
                "nested": {"access_key": "ak"},
            },
        },
    )

    entries = _read_log_entries(system_log_file)
    entry = _find_entry(entries, logger="app.security_test")
    assert entry["message"] == "sensitive payload password=*** authorization: ***"
    assert entry["authorization"] == "***"
    assert entry["error_detail"] == 'secret_key="***" access_key=***'
    payload = cast(dict[str, object], entry["payload"])
    nested = cast(dict[str, object], payload["nested"])
    assert payload["password"] == "***"
    assert nested["access_key"] == "***"
    assert str(entry["source_file"]).endswith("test_system_logging.py")
    assert isinstance(entry["source_line"], int)
    assert entry["source_func"] == "test_log_extra_fields_are_masked"


def test_console_log_message_is_masked() -> None:
    """控制台日志 message 中的常见凭据文本也应被脱敏。"""
    formatter = ConsoleFormatter("%(levelname)s [request_id=%(request_id)s] %(message)s")
    record = logging.makeLogRecord(
        {
            "name": "app.console_security_test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "console token=console-token cookie: session-id",
            "args": (),
        }
    )

    output = formatter.format(record)

    assert output == "INFO [request_id=-] console token=*** cookie: ***"


def test_log_rotation_is_configured(system_log_file: Path) -> None:
    """文件日志超过配置大小后应产生轮转备份文件。"""
    logger = logging.getLogger("app.rotation_test")
    for index in range(80):
        logger.info("rotation line %s %s", index, "x" * 80)

    rotated_files = list(system_log_file.parent.glob("app.log.*"))
    assert rotated_files


def _read_log_entries(log_file: Path) -> list[dict[str, object]]:
    """读取当前日志及轮转文件中的 JSON 日志条目。"""
    for handler in logging.getLogger().handlers:
        handler.flush()
    entries: list[dict[str, object]] = []
    for path in sorted(log_file.parent.glob("app.log*")):
        for line in path.read_text(encoding="utf-8").splitlines():
            entries.append(json.loads(line))
    return entries


def _find_entry(
    entries: list[dict[str, object]],
    *,
    logger: str,
    request_id: str | None = None,
    status_code: int | None = None,
) -> dict[str, object]:
    """按 logger、request_id、状态码查找最近一条匹配日志。"""
    for entry in reversed(entries):
        if entry.get("logger") != logger:
            continue
        if request_id is not None and entry.get("request_id") != request_id:
            continue
        if status_code is not None and entry.get("status_code") != status_code:
            continue
        return entry
    raise AssertionError(f"未找到日志: logger={logger}, request_id={request_id}")
