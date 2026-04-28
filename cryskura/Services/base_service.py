from __future__ import annotations

from http import HTTPStatus
from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..Handler import HTTPRequestHandler as Handler
    from .._types import AuthFunc


class Route:
    def __init__(
        self,
        path: Union[str, list[str]],
        methods: list[str],
        route_type: str,
        host: Optional[Union[str, list[str]]] = None,
        port: Optional[Union[int, list[int]]] = None,
    ) -> None:
        if host is not None:
            if isinstance(host, str):
                host = [host]
            for h in host:
                if h is not None and not isinstance(h, str):
                    raise ValueError(f"Host {h} is not a valid host.")
        self.host: Optional[list[str]] = host
        if port is not None:
            if isinstance(port, int):
                port = [port]
            for p in port:
                if p is not None and not isinstance(p, int):
                    raise ValueError(f"Port {p} is not a valid port.")
        self.port: Optional[list[int]] = port

        if not isinstance(path, list):
            if isinstance(path, str):
                path = path.split("/")
                if path[0] == '':
                    path.pop(0)
                if path[-1] == '':
                    path.pop(-1)
            else:
                raise ValueError(f"Path {path} is not a valid path.")
        self.path: list[str] = path
        self.methods: list[str] = methods
        if route_type not in ["prefix", "exact"]:
            raise ValueError(f"Type {route_type} is not a valid type.")
        self.type: str = route_type

    def match(
        self,
        path: list[str],
        method: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> tuple[bool, bool]:
        path_exists = False
        if self.host is None:
            host_match = True
        else:
            host_match = host in self.host
        if self.port is None:
            port_match = True
        else:
            port_match = port in self.port
        if not host_match or not port_match:
            return False, False

        if self.type == "exact":
            if path == self.path:
                path_exists = True
                if method in self.methods:
                    return True, True
        elif self.type == "prefix":
            if path[:len(self.path)] == self.path:
                path_exists = True
                if method in self.methods:
                    return True, True
        return False, path_exists


class BaseService:
    def __init__(self, routes: list[Route], auth_func: Optional[AuthFunc] = None) -> None:
        for r in routes:
            if not isinstance(r, Route):
                raise ValueError(f"Route {r} is not a valid route.")
        self.auth_func: Optional[AuthFunc] = auth_func
        self.routes: list[Route] = routes

    def auth_verify(
        self,
        request: Handler,
        path: list[str],
        args: dict[str, str],
        operation: str,
    ) -> bool:
        if self.auth_func is not None:
            origin_cookie = request.headers.get("Cookie")
            cookies: dict[str, str] = {}
            if origin_cookie is not None:
                for cookie in origin_cookie.split(";"):
                    if "=" in cookie:
                        key, _, value = cookie.partition("=")
                        cookies[key.strip()] = value.strip()
            if not self.auth_func(cookies, path, args, operation):
                request.errsvc.handle(request, path, args, operation, HTTPStatus.UNAUTHORIZED)
                return False
        return True

    # ── 中间件钩子 ─────────────────────────────────────────────

    def before_handle(
        self,
        request: Handler,
        path: list[str],
        args: dict[str, str],
        method: str,
    ) -> Optional[int]:
        """请求处理前钩子。返回 int 则短路请求（作为状态码），返回 None 继续正常处理。"""
        return None

    def after_handle(
        self,
        request: Handler,
        path: list[str],
        args: dict[str, str],
        method: str,
    ) -> None:
        """请求处理后钩子。可用于日志、统计等。"""
        pass

    # ── 错误处理（由 ErrorService 覆盖）────────────────────────

    def handle(self, request: Handler, path: list[str], args: dict[str, str], method: str, status: int) -> None:
        """默认错误处理，子类（如 ErrorService）应覆盖此方法。"""
        raise NotImplementedError

    # ── 请求处理方法（子类重写）─────────────────────────────────

    def handle_GET(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        raise NotImplementedError

    def handle_POST(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        raise NotImplementedError

    def handle_HEAD(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        raise NotImplementedError
