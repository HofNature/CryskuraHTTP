"""健康检查端点。"""
from __future__ import annotations

import json
import time
from http import HTTPStatus
from typing import Optional, TYPE_CHECKING

from .base_service import BaseService, Route

if TYPE_CHECKING:
    from ..handler import HTTPRequestHandler as Handler

_start_time: float = time.time()


class HealthService(BaseService):
    """内置健康检查服务。

    用法：
        health = HealthService()  # 默认 /health
        server = Server(services=[health, fs, api])
    """

    def __init__(
        self,
        remote_path: str = "/health",
        methods: Optional[list[str]] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        if methods is None:
            methods = ["GET", "HEAD"]
        self.routes = [
            Route(remote_path, methods, "exact", host, port),
        ]
        super().__init__(self.routes)

    def handle_GET(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        uptime = time.time() - _start_time
        body = json.dumps({"status": "ok", "uptime": round(uptime, 2)}).encode()
        request.send_response(HTTPStatus.OK)
        request.send_header("Content-Type", "application/json")
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        request.wfile.write(body)

    def handle_HEAD(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        request.send_response(HTTPStatus.OK)
        request.send_header("Content-Type", "application/json")
        request.end_headers()
