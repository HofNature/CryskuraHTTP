"""SimpleAPIRouter：简化的 JSON API 装饰器。

与 APIRouter 相比，SimpleAPIRouter 自动处理 JSON 序列化/反序列化，
开发者只需关注业务逻辑，无需手动处理请求/响应对象。

特性：
    - 自动解析 JSON 请求体并序列化响应体
    - 支持 /users/{user_id} 形式的路径参数
    - 严格匹配模板路径，避免固定段被误忽略
    - HEAD 请求返回相同状态码和响应头，但不返回响应体

用法：
    from cryskura.Services import SimpleAPIRouter

    router = SimpleAPIRouter()

    @router.get("/users/{user_id}")
    def get_user(params, body):
        # params = {"user_id": "123"}  — URL 路径参数
        # body = None                  — GET 无请求体
        return 200, {"user_id": params["user_id"], "name": "Alice"}

    @router.post("/users")
    def create_user(params, body):
        # params = {}                  — 无路径参数
        # body = {"name": "Bob"}      — JSON 解析后的请求体
        return 201, {"created": body}

    # 注册到服务器
    server = Server(services=router.build("/api"))
"""
from __future__ import annotations

import json
import logging
import re
from http import HTTPStatus
from typing import Callable, Optional, Any, TYPE_CHECKING

from .BaseService import BaseService, Route

if TYPE_CHECKING:
    from ..Handler import HTTPRequestHandler as Handler
    SimpleAPIFunc = Callable[..., tuple[int, Any]]

logger = logging.getLogger(__name__)


class SimpleAPIService(BaseService):
    """单个 JSON API 端点，自动处理 JSON 序列化。

    支持同一 remote_path 下的多个路由模板，按注册顺序匹配。
    """

    def __init__(
        self,
        remote_path: list[str],
        route_defs: list[dict],
        route_type: str,
        host: Optional[str],
        port: Optional[int],
        max_body: int = 1024 * 1024,
    ) -> None:
        all_methods: list[str] = []
        for rd in route_defs:
            for m in rd["methods"]:
                if m not in all_methods:
                    all_methods.append(m)

        self.routes = [
            Route(remote_path, all_methods, route_type, host, port),
        ]
        self.route_defs: list[dict] = route_defs
        self.route_len: int = len(remote_path)
        self.max_body: int = max_body
        for method in all_methods:
            setattr(
                self, f"handle_{method}",
                lambda request, path, args, m=method: self._handle(request, path, args, m),
            )
        super().__init__(self.routes)
        self.remote_path_list: list[str] = remote_path

    def handle_GET(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args, "GET")

    def handle_POST(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args, "POST")

    def handle_HEAD(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args, "HEAD")

    @staticmethod
    def _extract_params_template(
        remaining: list[str],
        path_template: list[str],
        template_offset: int,
    ) -> dict[str, str] | None:
        """从 remaining 路径段中按照给定模板提取参数。"""
        params: dict[str, str] = {}
        template = path_template[template_offset:]
        if len(remaining) != len(template):
            return None

        for seg, value in zip(template, remaining):
            if seg.startswith("{") and seg.endswith("}"):
                name = seg[1:-1]
                params[name] = value
            else:
                if value != seg:
                    return None
        return params

    def _find_route(
        self,
        remaining: list[str],
        method: str,
    ) -> tuple[dict | None, dict[str, str] | None]:
        """查找匹配 method 和剩余路径的路由定义。"""
        for rd in self.route_defs:
            if method not in rd["methods"]:
                continue
            params = self._extract_params_template(
                remaining,
                rd["path_template"],
                rd["template_offset"],
            )
            if params is not None:
                return rd, params
        return None, None

    def _handle(
        self,
        request: Handler,
        path: list[str],
        _args: dict[str, str],
        method: str,
    ) -> None:
        # 提取路径参数
        remaining = path[self.route_len:]
        matched_rd, params = self._find_route(remaining, method)

        if matched_rd is None:
            request.send_response(HTTPStatus.NOT_FOUND)
            request.send_header("Content-Type", "application/json")
            err = json.dumps({"error": "Route not found"}).encode()
            request.send_header("Content-Length", str(len(err)))
            request.end_headers()
            request.wfile.write(err)
            return

        # 解析 JSON 请求体（POST / PUT / PATCH / DELETE）
        body: Any = None
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                content_length = int(request.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                request.send_response(HTTPStatus.BAD_REQUEST)
                request.send_header("Content-Type", "application/json")
                err = json.dumps({"error": "Invalid Content-Length"}).encode()
                request.send_header("Content-Length", str(len(err)))
                request.end_headers()
                request.wfile.write(err)
                return

            if content_length < 0:
                request.send_response(HTTPStatus.BAD_REQUEST)
                request.send_header("Content-Type", "application/json")
                err = json.dumps({"error": "Invalid Content-Length"}).encode()
                request.send_header("Content-Length", str(len(err)))
                request.end_headers()
                request.wfile.write(err)
                return

            if content_length > 0:
                if self.max_body > 0 and content_length > self.max_body:
                    request.send_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    request.send_header("Content-Type", "application/json")
                    err = json.dumps({"error": "Request body too large"}).encode()
                    request.send_header("Content-Length", str(len(err)))
                    request.end_headers()
                    request.wfile.write(err)
                    try:
                        request.rfile.read(content_length)
                    except Exception:
                        pass
                    return
                raw = request.rfile.read(content_length)
                try:
                    body = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    request.send_response(HTTPStatus.BAD_REQUEST)
                    request.send_header("Content-Type", "application/json")
                    err = json.dumps({"error": "Invalid JSON body"}).encode()
                    request.send_header("Content-Length", str(len(err)))
                    request.end_headers()
                    request.wfile.write(err)
                    return
        # 调用用户函数
        func = matched_rd["func"]
        try:
            try:
                argcount = func.__code__.co_argcount
            except AttributeError:
                argcount = 2
            if argcount == 1:
                status_code, result = func(params)
            else:
                status_code, result = func(params, body)
        except Exception as e:
            logger.error("SimpleAPI error: %s", e)
            request.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            request.send_header("Content-Type", "application/json")
            err = json.dumps({"error": "Internal server error"}).encode()
            request.send_header("Content-Length", str(len(err)))
            request.end_headers()
            request.wfile.write(err)
            return
    
        # 序列化响应
        try:
            resp_body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as e:
            logger.error("SimpleAPI response serialization error: %s", e)
            request.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            request.send_header("Content-Type", "application/json")
            err = json.dumps({"error": "Response is not JSON-serializable"}).encode()
            request.send_header("Content-Length", str(len(err)))
            request.end_headers()
            request.wfile.write(err)
            return

        request.send_response(status_code)
        request.send_header("Content-Type", "application/json; charset=utf-8")
        request.send_header("Content-Length", str(len(resp_body)))
        request.end_headers()
        if method != "HEAD":
            request.wfile.write(resp_body)


class SimpleAPIRouter:
    """简化的 JSON API 装饰器路由器。

    自动处理 JSON 序列化/反序列化，支持 URL 路径参数。
    路径参数用 {param_name} 表示，例如 "/users/{user_id}"。

    用法：
        router = SimpleAPIRouter()

        @router.get("/users/{user_id}")
        def get_user(params, body):
            return 200, {"id": params["user_id"]}

        @router.post("/items")
        def create_item(params, body):
            return 201, {"received": body}

        server = Server(services=router.build("/api"))
    """

    def __init__(self, max_body: int = 1024 * 1024) -> None:
        self._routes: list[dict] = []
        self._max_body: int = max_body

    def route(
        self,
        path: str,
        methods: Optional[list[str]] = None,
    ) -> Callable:
        """通用装饰器：指定路径和方法。"""
        if methods is None:
            methods = ["GET"]

        def decorator(func: SimpleAPIFunc) -> SimpleAPIFunc:
            self._register(path, methods, func)
            return func

        return decorator

    def get(self, path: str) -> Callable:
        """快捷装饰器：GET 端点。"""
        return self.route(path, methods=["GET", "HEAD"])

    def post(self, path: str) -> Callable:
        """快捷装饰器：POST 端点。"""
        return self.route(path, methods=["POST"])

    def put(self, path: str) -> Callable:
        """快捷装饰器：PUT 端点。"""
        return self.route(path, methods=["PUT"])

    def delete(self, path: str) -> Callable:
        """快捷装饰器：DELETE 端点。"""
        return self.route(path, methods=["DELETE"])

    def _register(
        self,
        path: str,
        methods: list[str],
        func: SimpleAPIFunc,
    ) -> None:
        path_params = re.findall(r'\{(\w+)\}', path)
        self._routes.append({
            "path": path,
            "func": func,
            "methods": methods,
            "path_params": path_params,
        })

    def build(
        self,
        base_path: str = "",
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> list[SimpleAPIService]:
        """构建 SimpleAPIService 列表。

        相同 fixed_prefix 的多个路由会合并到同一个 SimpleAPIService 中，
        避免前缀匹配时的路由遮蔽问题。路径参数段（如 {user_id}）不参与
        Route 匹配，而是作为前缀匹配后剩余段的提取依据。
        """
        if base_path:
            base_parts = [p for p in base_path.strip("/").split("/") if p]
        else:
            base_parts = []

        # 按 remote_path 分组，保留注册顺序
        groups: dict[tuple[str, ...], list[dict]] = {}
        group_order: list[tuple[str, ...]] = []

        for route in self._routes:
            full_path_str = route["path"]
            if full_path_str.startswith("/"):
                full_path_str = full_path_str[1:]
            path_segments = [p for p in full_path_str.split("/") if p]

            fixed_segments: list[str] = []
            for seg in path_segments:
                if seg.startswith("{") and seg.endswith("}"):
                    break
                fixed_segments.append(seg)

            remote_path = base_parts + fixed_segments
            key = tuple(remote_path)

            route_def = {
                "func": route["func"],
                "methods": route["methods"],
                "path_params": route["path_params"],
                "path_template": path_segments,
                "template_offset": len(fixed_segments),
            }

            if key not in groups:
                groups[key] = []
                group_order.append(key)
            groups[key].append(route_def)

        services: list[SimpleAPIService] = []
        for key in group_order:
            route_defs = groups[key]
            services.append(SimpleAPIService(
                remote_path=list(key),
                route_defs=route_defs,
                route_type="prefix",
                host=host,
                port=port,
                max_body=self._max_body,
            ))

        return services
