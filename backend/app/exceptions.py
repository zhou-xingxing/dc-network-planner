"""应用异常定义。

Service 层通过自定义异常传递业务结果，
Router 层捕获后转为对应的 HTTPException。
"""


class BusinessError(Exception):
    """业务逻辑异常。

    Service 层在校验失败时抛出，Router 层捕获后转为 HTTP 409 响应。

    Args:
        message: 异常描述，将作为 HTTP 响应的 detail。
    """

    pass


class ResourceNotFoundError(Exception):
    """资源不存在异常。

    Service 层在明确的实体查找失败时抛出，Router 层捕获后转为 HTTP 404 响应。

    Args:
        message: 异常描述，将作为 HTTP 响应的 detail。
    """

    pass
