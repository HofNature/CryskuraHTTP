"""CORS (Cross-Origin Resource Sharing) 服务。

CORS preflight handler and response-header injection service.
"""
from __future__ import annotations

from http import HTTPStatus
from typing import Optional, TYPE_CHECKING

from .base_service import BaseService, Route

if TYPE_CHECKING:
    from ..handler import HTTPRequestHandler as Handler


class CORSService(BaseService):
    """处理 CORS 预检请求和响应头注入。

    Handles CORS preflight (OPTIONS) requests and injects CORS headers into
    all other responses via :py:meth:`inject_headers`.

    用法 / Usage::

        cors = CORSService(
            allow_origins=["https://example.com"],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Authorization"],
            max_age=86400,
        )
        # 放在 services 列表最前面，优先处理 OPTIONS 预检
        # Place at the front of the services list to intercept OPTIONS first
        server = Server(services=[cors, fs, api])
    """

    def __init__(
        self,
        remote_path: str = "/",
        allow_origins: Optional[list[str]] = None,
        allow_methods: Optional[list[str]] = None,
        allow_headers: Optional[list[str]] = None,
        expose_headers: Optional[list[str]] = None,
        allow_credentials: bool = False,
        max_age: int = 86400,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        """初始化 CORS 服务。

        Initialise the CORS service.

        Args:
            remote_path: 匹配路径前缀（默认 "/"）。 / URL prefix to match (default "/").
            allow_origins: 允许的源列表；None 表示 ["*"]。
                           Allowed origins; None means ["*"].
            allow_methods: 允许的 HTTP 方法；None 使用默认列表。
                           Allowed HTTP methods; None uses sensible defaults.
            allow_headers: 允许的请求头；None 使用默认列表。
                           Allowed request headers; None uses sensible defaults.
            expose_headers: 暴露给客户端的响应头（可选）。
                            Response headers to expose to the client (optional).
            allow_credentials: 是否允许携带凭证（Cookie、Authorization 等）。
                                Whether to allow credentials (Cookie, Authorization, etc.).
            max_age: 预检结果缓存秒数（默认 86400）。
                     Max-age for preflight cache in seconds (default 86400).
            host: 限制匹配的虚拟主机名（可选）。 / Optional virtual-host filter.
            port: 限制匹配的端口（可选）。 / Optional port filter.
        """
        self.routes = [
            Route(remote_path, ["OPTIONS"], "prefix", host, port),
        ]
        self.allow_origins: list[str] = allow_origins if allow_origins is not None else ["*"]
        self.allow_methods: list[str] = (
            allow_methods if allow_methods is not None else ["GET", "HEAD", "POST", "OPTIONS"]
        )
        self.allow_headers: list[str] = (
            allow_headers if allow_headers is not None else ["Content-Type", "Authorization"]
        )
        self.expose_headers: Optional[list[str]] = expose_headers
        self.allow_credentials: bool = allow_credentials
        self.max_age: int = max_age
        super().__init__(self.routes)

    def _origin_allowed(self, origin: Optional[str]) -> bool:
        """检查请求来源是否在允许列表中。

        Return True if *origin* is on the allow-list.

        Args:
            origin: 请求的 Origin 头值（可为 None）。
                    Value of the incoming Origin header (may be None).
        """
        if origin is None:
            return False
        return "*" in self.allow_origins or origin in self.allow_origins

    def _set_cors_headers(self, request: Handler, origin: str) -> None:
        """向响应中写入 CORS 相关响应头。

        Write CORS-related response headers into *request*.

        Args:
            request: 当前请求处理器。 / The current request handler.
            origin: 已验证的请求来源。 / The validated request origin.
        """
        if "*" in self.allow_origins and not self.allow_credentials:
            request.send_header("Access-Control-Allow-Origin", "*")
        else:
            request.send_header("Access-Control-Allow-Origin", origin)
            # Issue 10: add Vary: Origin when responding with a specific origin
            # so caches don't serve a response for one Origin to a different Origin
            request.send_header("Vary", "Origin")
        request.send_header("Access-Control-Allow-Methods", ", ".join(self.allow_methods))
        request.send_header("Access-Control-Allow-Headers", ", ".join(self.allow_headers))
        if self.allow_credentials:
            request.send_header("Access-Control-Allow-Credentials", "true")
        if self.expose_headers:
            request.send_header("Access-Control-Expose-Headers", ", ".join(self.expose_headers))
        request.send_header("Access-Control-Max-Age", str(self.max_age))

    def handle_OPTIONS(
        self, request: Handler, path: list[str], args: dict[str, str],
    ) -> None:
        """处理 CORS 预检请求（OPTIONS）。

        Handle a CORS preflight (OPTIONS) request.

        Args:
            request: HTTP 请求处理器。 / HTTP request handler instance.
            path: 已解析的 URL 路径段。 / Parsed URL path segments.
            args: 查询参数字典。 / Query-string parameters.
        """
        origin = request.headers.get("Origin")
        if not self._origin_allowed(origin):
            request.send_response(HTTPStatus.FORBIDDEN)
            request.end_headers()
            return
        request.send_response(HTTPStatus.NO_CONTENT)
        # CORS headers injected by end_headers() → inject_headers(), skip duplicate here
        request.end_headers()

    def inject_headers(self, request: Handler) -> None:
        """供 Handler 在非 OPTIONS 响应后调用，注入 CORS 头。

        Called by the Handler after sending any non-OPTIONS response to
        inject the appropriate CORS headers.

        Args:
            request: HTTP 请求处理器。 / HTTP request handler instance.
        """
        origin = request.headers.get("Origin")
        if self._origin_allowed(origin):
            self._set_cors_headers(request, origin)  # type: ignore[arg-type]
