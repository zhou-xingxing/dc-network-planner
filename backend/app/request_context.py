from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass

REQUEST_ID_HEADER = "X-Request-ID"


@dataclass(frozen=True)
class RequestContext:
    request_id: str = ""
    username: str | None = None
    method: str | None = None
    path: str | None = None
    client_ip: str | None = None


# ContextVar 对象全局声明，但保存的值按当前 async task / 执行上下文隔离。
_ctx_var: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())


def get_request_context() -> RequestContext:
    """返回当前请求上下文；非 HTTP 入口会得到空上下文。"""
    return _ctx_var.get()


def set_current_username(username: str | None) -> None:
    """在认证依赖解析成功后写入当前用户名，供日志自动携带。"""
    ctx = _ctx_var.get()
    _ctx_var.set(
        RequestContext(
            request_id=ctx.request_id,
            username=username,
            method=ctx.method,
            path=ctx.path,
            client_ip=ctx.client_ip,
        )
    )


@contextmanager
def request_context(
    *,
    request_id: str,
    method: str,
    path: str,
    client_ip: str | None,
) -> Iterator[None]:
    # set 返回的 token 记录进入本请求前的上下文，便于 finally 中精确恢复。
    token: Token[RequestContext] = _ctx_var.set(
        RequestContext(
            request_id=request_id,
            method=method,
            path=path,
            client_ip=client_ip,
        )
    )
    try:
        yield
    finally:
        # 请求结束或异常退出时恢复旧上下文，避免 request_id 等信息串到其他请求。
        _ctx_var.reset(token)
