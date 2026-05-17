from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from app.exception_handlers import internal_error_response, log_unexpected_error
from app.request_context import REQUEST_ID_HEADER, request_context, set_current_username

MAX_REQUEST_ID_LENGTH = 128
HEALTH_CHECK_PATH = "/api/health"
access_logger = logging.getLogger("app.access")


async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """维护请求级日志上下文，并记录 HTTP 访问摘要。

    负责生成或透传 request_id、写入请求上下文、统计耗时并输出 app.access。
    未预期异常会在这里优先兜底，记录堆栈后返回统一 500 响应。
    """
    request_id = _normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
    client_ip = request.client.host if request.client else None
    start_time = time.perf_counter()
    status_code = 500

    with request_context(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_ip=client_ip,
    ):
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            log_unexpected_error()
            response = internal_error_response()
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if request.url.path != HEALTH_CHECK_PATH:
                # 认证依赖写入 request.state.username；访问日志输出前同步回 ContextVar，确保 formatter 能取到用户名。
                set_current_username(getattr(request.state, "username", None))
                access_logger.log(
                    _level_for_status(status_code),
                    "HTTP request completed",
                    extra={
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "query_params": dict(request.query_params) or None,
                    },
                )

        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _normalize_request_id(raw_request_id: str | None) -> str:
    """校验客户端传入的 request_id，无效时生成新的 UUID。"""
    if not raw_request_id:
        return str(uuid.uuid4())
    request_id = raw_request_id.strip()
    if not request_id or len(request_id) > MAX_REQUEST_ID_LENGTH:
        return str(uuid.uuid4())
    return request_id


def _level_for_status(status_code: int) -> int:
    """根据 HTTP 状态码选择访问日志级别。"""
    if status_code >= 500:
        return logging.ERROR
    if status_code >= 400:
        return logging.WARNING
    return logging.INFO
