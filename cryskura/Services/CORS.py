"""CORS (Cross-Origin Resource Sharing) 服务。"""
from __future__ import annotations

from http import HTTPStatus
from typing import Optional, TYPE_CHECKING

from .BaseService import BaseService, Route

if TYPE_CHECKING:
    from ..Handler import HTTPRequestHandler as Handler


class CORSService(BaseService):
    """处理 CORS 预检请求和响应头注入。

    用法：
        cors = CORSService(
            allow_origins=["https://example.com"],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Authorization"],
            max_age=86400,
        )
        # 放在 services 列表最前面，优先处理 OPTIONS 预检
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
        self.routes = [
            Route(remote_path, ["OPTIONS"], "prefix", host, port),
        ]
        self.allow_origins: list[str] = allow_origins if allow_origins is not None else ["*"]
        self.allow_methods: list[str] = allow_methods if allow_methods is not None else ["GET", "HEAD", "POST", "OPTIONS"]
        self.allow_headers: list[str] = allow_headers if allow_headers is not None else ["Content-Type", "Authorization"]
        self.expose_headers: Optional[list[str]] = expose_headers
        self.allow_credentials: bool = allow_credentials
        self.max_age: int = max_age
        super().__init__(self.routes)

    def _origin_allowed(self, origin: Optional[str]) -> bool:
        if origin is None:
            return False
        return "*" in self.allow_origins or origin in self.allow_origins

    def _set_cors_headers(self, request: Handler, origin: str) -> None:
        if "*" in self.allow_origins and not self.allow_credentials:
            request.send_header("Access-Control-Allow-Origin", "*")
        else:
            request.send_header("Access-Control-Allow-Origin", origin)
        request.send_header("Access-Control-Allow-Methods", ", ".join(self.allow_methods))
        request.send_header("Access-Control-Allow-Headers", ", ".join(self.allow_headers))
        if self.allow_credentials:
            request.send_header("Access-Control-Allow-Credentials", "true")
        if self.expose_headers:
            request.send_header("Access-Control-Expose-Headers", ", ".join(self.expose_headers))
        request.send_header("Access-Control-Max-Age", str(self.max_age))

    def handle_OPTIONS(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        origin = request.headers.get("Origin")
        if not self._origin_allowed(origin):
            request.send_response(HTTPStatus.FORBIDDEN)
            request.end_headers()
            return
        request.send_response(HTTPStatus.NO_CONTENT)
        # CORS headers injected by end_headers() → inject_headers(), skip duplicate here
        request.end_headers()

    def inject_headers(self, request: Handler) -> None:
        """供 Handler 在非 OPTIONS 响应后调用，注入 CORS 头。"""
        origin = request.headers.get("Origin")
        if self._origin_allowed(origin):
            self._set_cors_headers(request, origin)  # type: ignore[arg-type]
