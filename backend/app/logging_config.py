from __future__ import annotations

import copy
import json
import logging
import re
from logging import LogRecord
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, settings
from app.request_context import get_request_context

# 标记由本应用创建的 handler，重复初始化时只清理自己的日志输出器。
MANAGED_HANDLER_ATTR = "_dc_network_planner_managed"

# 需要按字段名或文本 key 脱敏的常见凭据关键字。
SENSITIVE_KEYS = ("password", "token", "authorization", "secret", "secret_key", "access_key", "jwt", "cookie")
SENSITIVE_KEY_PATTERN = "|".join(re.escape(key) for key in SENSITIVE_KEYS)

# 匹配 password="xxx"、token: 'xxx' 等带引号的凭据片段，保留原始引号。
SENSITIVE_QUOTED_TEXT_PATTERN_TEXT = rf"""(?ix)
    (["']?\b(?:{SENSITIVE_KEY_PATTERN})\b["']?\s*[:=]\s*)
    (["'])
    .*?
    \2
    """
SENSITIVE_QUOTED_TEXT_PATTERN = re.compile(SENSITIVE_QUOTED_TEXT_PATTERN_TEXT)

# 匹配 password=xxx、authorization: Bearer xxx 等未加引号的凭据片段。
SENSITIVE_UNQUOTED_TEXT_PATTERN_TEXT = rf"""(?ix)
    (["']?\b(?:{SENSITIVE_KEY_PATTERN})\b["']?\s*[:=]\s*)
    (Bearer\s+[^\s,;"']+|[^\s,;"']+)
    """
SENSITIVE_UNQUOTED_TEXT_PATTERN = re.compile(SENSITIVE_UNQUOTED_TEXT_PATTERN_TEXT)


class ConsoleFormatter(logging.Formatter):
    """控制台输出日志格式器，自动补齐 request_id。"""

    def format(self, record: LogRecord) -> str:
        """为控制台日志补齐 request_id 后交给标准 Formatter 输出。"""
        safe_record = copy.copy(record)
        context = get_request_context()
        if not hasattr(safe_record, "request_id"):
            safe_record.request_id = context.request_id or "-"
        safe_record.msg = mask_sensitive(record.getMessage())
        safe_record.args = ()
        return super().format(safe_record)


class JsonLineFormatter(logging.Formatter):
    """把系统日志格式化为便于搜索和采集的 JSON Lines。"""

    def format(self, record: LogRecord) -> str:
        """把单条日志记录转换为脱敏后的 JSON 字符串。"""
        context = get_request_context()
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": context.request_id or None,
            "username": context.username,
            "method": context.method,
            "path": context.path,
            "client_ip": context.client_ip,
            "source_file": record.pathname,
            "source_line": record.lineno,
            "source_func": record.funcName,
        }
        payload.update(_record_extra(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(mask_sensitive(payload), ensure_ascii=False, default=str)


def setup_logging() -> None:
    """按应用配置初始化控制台日志和轮转文件日志。"""
    log_level = _resolve_log_level(settings.LOG_LEVEL)
    log_dir = _resolve_log_dir(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 配置 root logger 作为统一出口，让应用模块和第三方库日志共用同一套 handler。
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    _remove_managed_handlers(root_logger)

    # 配置控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        ConsoleFormatter("%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s")
    )
    setattr(console_handler, MANAGED_HANDLER_ATTR, True)
    root_logger.addHandler(console_handler)

    # 配置轮转文件日志；轮转后命名为 app.log.1、app.log.2 等，数字越小越新。
    file_handler = RotatingFileHandler(
        log_dir / settings.LOG_FILE_NAME,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JsonLineFormatter())
    setattr(file_handler, MANAGED_HANDLER_ATTR, True)
    root_logger.addHandler(file_handler)


def shutdown_logging() -> None:
    """移除本应用托管的日志 handler，供测试隔离等非运行态场景使用。"""
    _remove_managed_handlers(logging.getLogger())


def mask_sensitive(value: Any) -> Any:
    """递归脱敏结构化字段，并兜底处理常见文本凭据模式。"""
    if isinstance(value, dict):
        return {key: "***" if _is_sensitive_key(str(key)) else mask_sensitive(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_sensitive(item) for item in value)
    if isinstance(value, str):
        return _mask_sensitive_text(value)
    return value


def _record_extra(record: LogRecord) -> dict[str, Any]:
    """提取业务通过 logging extra 传入的非标准字段。"""
    standard_keys = set(logging.makeLogRecord({}).__dict__) | {
        "message",
        "asctime",
        "request_id",
        "username",
        "method",
        "path",
        "client_ip",
        "log_extra",
        "source_file",
        "source_line",
        "source_func",
    }
    extra: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in standard_keys or key.startswith("_"):
            continue
        extra[key] = value
    return extra


def _remove_managed_handlers(logger: logging.Logger) -> None:
    """移除并关闭本应用创建的日志 handler，避免重复初始化。"""
    for handler in list(logger.handlers):
        if getattr(handler, MANAGED_HANDLER_ATTR, False):
            logger.removeHandler(handler)
            handler.close()


def _mask_sensitive_text(value: str) -> str:
    """脱敏 message、异常文本中的常见 key=value 或 key: value 凭据片段。"""

    def replace_quoted(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}***{match.group(2)}"

    value = SENSITIVE_QUOTED_TEXT_PATTERN.sub(replace_quoted, value)
    return SENSITIVE_UNQUOTED_TEXT_PATTERN.sub(r"\1***", value)


def _resolve_log_dir(log_dir: str) -> Path:
    """解析日志目录，相对路径固定落在 backend 目录下。"""
    path = Path(log_dir)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


def _resolve_log_level(log_level: str) -> int:
    """把配置中的日志级别名称转换为 logging 使用的整数级别。"""
    level = logging.getLevelNamesMapping().get(log_level.upper())
    if isinstance(level, int):
        return level
    logging.getLogger(__name__).warning("无效的 LOG_LEVEL %r，已回退为 INFO", log_level)
    return logging.INFO


def _is_sensitive_key(key: str) -> bool:
    """判断字段名是否命中需要脱敏的敏感关键字。"""
    lowered = key.lower()
    return any(sensitive in lowered for sensitive in SENSITIVE_KEYS)
