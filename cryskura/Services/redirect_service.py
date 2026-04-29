from __future__ import annotations

import re
from http import HTTPStatus
from typing import Optional, TYPE_CHECKING

from .base_service import BaseService, Route

if TYPE_CHECKING:
    from ..handler import HTTPRequestHandler
    from .._types import AuthFunc


class RedirectService(BaseService):
    def __init__(
        self,
        remote_path: str,
        redirect_path: str,
        methods: Optional[list[str]] = None,
        remote_type: str = "prefix",
        redirect_type: str = "prefix",
        auth_func: Optional[AuthFunc] = None,
        default_protocol: str = "http",
        status: int = 301,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        if methods is None:
            methods = ["GET", "HEAD", "POST"]
        if status not in (301, 302, 307, 308):
            raise ValueError(f"Redirect status {status} not supported. Use 301, 302, 307, or 308.")
        self.routes = [
            Route(remote_path, methods, remote_type, host, port),
        ]
        self.redirect_path: str = redirect_path
        if redirect_type not in ["prefix", "exact"]:
            raise ValueError(f"Type {redirect_type} is not a valid type.")
        self.redirect_type: str = redirect_type
        self.default_protocol: str = default_protocol
        self.redirect_status: int = status
        super().__init__(self.routes, auth_func)
        self.remote_path: list[str] = self.routes[0].path

    @staticmethod
    def _is_valid_host(host: Optional[str]) -> bool:
        """校验 Host 头是否为合法的域名或 IP"""
        if not host:
            return False
        host_only = host.split(':')[0].strip('[]')
        return bool(re.match(r'^[a-zA-Z0-9._-]+$|^[0-9a-fA-F:]+$', host_only))

    def calc_path(self, path: list[str], request: HTTPRequestHandler) -> Optional[str]:
        sub_path = path[len(self.remote_path):]
        if self.redirect_type == "prefix":
            joined = '/'.join(sub_path)
            if self.redirect_path[-1] == "/":
                r_path = self.redirect_path + joined
            else:
                if joined:
                    r_path = self.redirect_path + "/" + joined
                else:
                    r_path = self.redirect_path
            if r_path[:2] == "//":
                r_path = self.default_protocol + ":" + r_path
            elif r_path[:1] == "/":
                request_host = request.headers.get("Host")
                if not self._is_valid_host(request_host):
                    return None
                assert request_host is not None  # guaranteed by _is_valid_host
                r_path = self.default_protocol + "://" + request_host + r_path
        else:
            r_path = self.redirect_path
        return r_path

    def handle_GET(self, request: HTTPRequestHandler, path: list[str], args: dict[str, str]) -> None:
        if not self.auth_verify(request, path, args, "GET"):
            return
        r_path = self.calc_path(path, request)
        if r_path is None:
            request.send_error(HTTPStatus.BAD_REQUEST)
            return
        request.send_response(self.redirect_status)
        request.send_header("Location", r_path)
        request.end_headers()

    def handle_HEAD(self, request: HTTPRequestHandler, path: list[str], args: dict[str, str]) -> None:
        if not self.auth_verify(request, path, args, "HEAD"):
            return
        r_path = self.calc_path(path, request)
        if r_path is None:
            request.send_error(HTTPStatus.BAD_REQUEST)
            return
        request.send_response(self.redirect_status)
        request.send_header("Location", r_path)
        request.end_headers()

    def handle_POST(self, request: HTTPRequestHandler, path: list[str], args: dict[str, str]) -> None:
        if not self.auth_verify(request, path, args, "POST"):
            return
        r_path = self.calc_path(path, request)
        if r_path is None:
            request.send_error(HTTPStatus.BAD_REQUEST)
            return
        request.send_response(self.redirect_status)
        request.send_header("Location", r_path)
        request.end_headers()
