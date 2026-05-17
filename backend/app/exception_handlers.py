from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.exceptions import BusinessError, ResourceNotFoundError
from app.request_context import REQUEST_ID_HEADER, get_request_context

logger = logging.getLogger("app.exceptions")
INTERNAL_ERROR_DETAIL = "系统内部错误，请联系管理员"


async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
    """兜底处理未在 Router 转换的业务异常。"""
    logger.warning("未被 Router 转换的 BusinessError", extra={"status_code": 409, "error_detail": str(exc)})
    return _json_response(status_code=409, detail=str(exc))


async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    """兜底处理未在 Router 转换的资源不存在异常。"""
    logger.warning(
        "未被 Router 转换的 ResourceNotFoundError",
        extra={"status_code": 404, "error_detail": str(exc)},
    )
    return _json_response(status_code=404, detail=str(exc))


async def wrapped_http_exception_handler(request: Request, exc: HTTPException) -> Response:
    """包装 FastAPI 默认 HTTPException 处理器；仅 5xx 额外记录堆栈。"""
    if exc.status_code >= 500:
        logger.error(
            "HTTP error",
            extra={"status_code": exc.status_code, "error_detail": exc.detail},
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    response = await fastapi_http_exception_handler(request, exc)
    request_id = get_request_context().request_id
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """作为中间件异常兜底之外的第二道防线，记录未预期系统异常。"""
    log_unexpected_error()
    return internal_error_response()


def log_unexpected_error() -> None:
    """记录未预期系统异常，供中间件和全局异常处理器复用。"""
    logger.exception("Unexpected system error", extra={"status_code": 500})


def internal_error_response() -> JSONResponse:
    """构造统一 500 响应，并带上当前 request_id。"""
    return _json_response(status_code=500, detail=INTERNAL_ERROR_DETAIL)


def _json_response(status_code: int, detail: str, request_id: str | None = None) -> JSONResponse:
    current_request_id = request_id or get_request_context().request_id
    content: dict[str, str] = {"detail": detail}
    if status_code >= 500 and current_request_id:
        content["request_id"] = current_request_id
    response = JSONResponse(status_code=status_code, content=content)
    if current_request_id:
        response.headers[REQUEST_ID_HEADER] = current_request_id
    return response
