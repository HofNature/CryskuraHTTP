"""APIRouter：装饰器风格的多端点 API 路由器。

APIRouter: decorator-based multi-endpoint API router.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, TYPE_CHECKING
from .api_service import APIService

if TYPE_CHECKING:
    pass


class APIRouter:
    """API 路由装饰器，支持以装饰器方式注册多个 API 端点。

    Decorator-based API router for registering multiple endpoints.

    用法 / Usage::

        router = APIRouter()

        @router.route("/hello", methods=["GET"])
        def hello(request, path, args, headers, content, method):
            return 200, {"Content-Type": "text/plain"}, b"hello"

        @router.route("/echo", methods=["POST"])
        def echo(request, path, args, headers, content, method):
            return 200, {"Content-Type": "application/octet-stream"}, content

        # 注册到服务器，base_path 为统一前缀
        # Register with the server; base_path is the common URL prefix
        server = Server(services=router.build("/api"))
    """

    def __init__(self) -> None:
        """初始化路由列表。 / Initialise the empty route registry."""
        self._routes: list[dict[str, Any]] = []

    def route(
        self,
        path: str,
        methods: Optional[list[str]] = None,
        prefix: bool = False,
        auth_func: Optional[object] = None,
        length_limit: int = 1024 * 1024,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> Callable[..., Any]:
        """装饰器：注册一个 API 端点。

        Decorator: register an API endpoint at *path*.

        Args:
            path: URL 路径（相对于 build() 的 base_path）。
                  URL path relative to build()'s base_path.
            methods: 允许的 HTTP 方法列表，默认 GET/HEAD/POST。
                     Allowed HTTP methods; defaults to GET/HEAD/POST.
            prefix: True 表示前缀匹配；False 表示精确匹配（默认）。
                    True for prefix matching; False for exact match (default).
            auth_func: 可选的鉴权函数。 / Optional authentication function.
            length_limit: 请求体最大字节数（默认 1 MB）。
                          Maximum request body size in bytes (default 1 MB).
            host: 限制匹配的虚拟主机名（可选）。 / Optional virtual-host filter.
            port: 限制匹配的端口（可选）。 / Optional port filter.

        Returns:
            Callable: 返回原函数（不修改）。 / The original function, unchanged.
        """
        if methods is None:
            methods = ["GET", "HEAD", "POST"]

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
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
        """根据注册的路由构建 APIService 列表。

        Build a list of APIService instances from the registered routes.

        Args:
            base_path: 所有端点共享的 URL 前缀（如 "/api"）。
                       Shared URL prefix for all endpoints (e.g. "/api").

        Returns:
            list[APIService]: 可直接传给 HTTPServer 的服务实例列表。
                              List of service instances ready for HTTPServer.
        """
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
