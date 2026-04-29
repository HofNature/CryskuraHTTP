from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING
from .api_service import APIService

if TYPE_CHECKING:
    pass


class APIRouter:
    """API 路由装饰器，支持以装饰器方式注册多个 API 端点。

    用法：
        router = APIRouter()

        @router.route("/hello", methods=["GET"])
        def hello(request, path, args, headers, content, method):
            return 200, {"Content-Type": "text/plain"}, b"hello"

        @router.route("/echo", methods=["POST"])
        def echo(request, path, args, headers, content, method):
            return 200, {"Content-Type": "application/octet-stream"}, content

        # 注册到服务器，base_path 为统一前缀
        server = Server(services=router.build("/api"))
    """

    def __init__(self) -> None:
        self._routes: list[dict] = []

    def route(
        self,
        path: str,
        methods: Optional[list[str]] = None,
        prefix: bool = False,
        auth_func: Optional[object] = None,
        length_limit: int = 1024 * 1024,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> Callable:
        """装饰器：注册一个 API 端点。"""
        if methods is None:
            methods = ["GET", "HEAD", "POST"]

        def decorator(func: Callable) -> Callable:
            self._routes.append({
                "path": path,
                "func": func,
                "methods": methods,
                "prefix": prefix,
                "auth_func": auth_func,
                "length_limit": length_limit,
                "host": host,
                "port": port,
            })
            return func

        return decorator

    def build(self, base_path: str = "") -> list[APIService]:
        """根据注册的路由构建 APIService 列表。"""
        if base_path:
            if not base_path.startswith("/"):
                base_path = "/" + base_path
            base_parts = [p for p in base_path.split("/") if p]
        else:
            base_parts = []

        services: list[APIService] = []
        for route in self._routes:
            route_path = route["path"]
            if route_path.startswith("/"):
                route_path = route_path[1:]
            full_path = base_parts + [p for p in route_path.split("/") if p]

            services.append(APIService(
                remote_path=full_path,
                func=route["func"],
                methods=route["methods"],
                route_type="prefix" if route["prefix"] else "exact",
                auth_func=route["auth_func"],
                length_limit=route["length_limit"],
                host=route["host"],
                port=route["port"],
            ))

        return services
