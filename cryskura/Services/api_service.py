from __future__ import annotations

import re
from typing import Callable, Optional, Union, TYPE_CHECKING

from .base_service import BaseService, Route

if TYPE_CHECKING:
    from ..handler import HTTPRequestHandler as Handler
    from .._types import AuthFunc


APIFuncType = Callable[
    ["Handler", list[str], dict[str, str], object, bytes, str],
    tuple[int, dict[str, str], bytes],
]


class APIService(BaseService):
    def __init__(
        self,
        remote_path: Union[str, list[str]],
        func: APIFuncType,
        methods: Optional[list[str]] = None,
        route_type: str = "prefix",
        auth_func: Optional[AuthFunc] = None,
        length_limit: int = 1024 * 1024,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        if methods is None:
            methods = ["GET", "HEAD", "POST"]
        self.routes = [
            Route(remote_path, methods, route_type, host, port),
        ]
        self.func: APIFuncType = func
        self.length_limit: int = length_limit
        for method in methods:
            setattr(
                self, f"handle_{method}",
                lambda request, path, args, method=method: self.handle_API(request, path, args, method),
            )
        super().__init__(self.routes, auth_func)
        self.remote_path: list[str] = self.routes[0].path

    def handle_API(self, request: Handler, path: list[str], args: dict[str, str], method: str) -> None:
        if not self.auth_verify(request, path, args, method):
            return
        sub_path = path[len(self.remote_path):]
        headers = request.headers
        content = request.rfile.read(min(int(headers.get("Content-Length", 0)), self.length_limit))
        code, resp_headers, content = self.func(request, sub_path, args, headers, content, method)
        request.send_response(code)
        for key in resp_headers:
            # 防止 HTTP 头注入
            if not re.match(r'^[a-zA-Z0-9_-]+$', key):
                continue
            val = resp_headers[key]
            if '\r' in val or '\n' in val:
                continue
            request.send_header(key, val)
        request.end_headers()
        request.wfile.write(content)
