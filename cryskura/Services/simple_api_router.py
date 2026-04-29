"""SimpleAPIRouter：简化的 JSON API 装饰器。

与 APIRouter 相比，SimpleAPIRouter 自动处理 JSON 序列化/反序列化，
开发者只需关注业务逻辑，无需手动处理请求/响应对象。

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

from .base_service import BaseService, Route

if TYPE_CHECKING:
    from ..handler import HTTPRequestHandler as Handler

logger = logging.getLogger(__name__)

# 用户函数签名：(path_params: dict, body: Any) -> (int, Any)
SimpleAPIFunc = Callable[[dict[str, str], Any], tuple[int, Any]]


class SimpleAPIService(BaseService):
    """单个 JSON API 端点，自动处理 JSON 序列化。"""

    def __init__(
        self,
        remote_path: list[str],
        func: SimpleAPIFunc,
        methods: list[str],
        route_type: str,
        path_params: list[str],
        path_template: list[str],  # 完整路径模板段，如 ["users", "{user_id}", "posts", "{post_id}"]
        host: Optional[str],
        port: Optional[int],
        max_body: int = 1024 * 1024,
    ) -> None:
        self.routes = [
            Route(remote_path, methods, route_type, host, port),
        ]
        self.func: SimpleAPIFunc = func
        self.path_params: list[str] = path_params
        self.path_template: list[str] = path_template
        self.route_len: int = len(remote_path)
        self.max_body: int = max_body
        for method in methods:
            setattr(
                self, f"handle_{method}",
                lambda request, path, args, m=method: self._handle(request, path, args, m),
            )
        super().__init__(self.routes)
        self.remote_path_list: list[str] = remote_path

    def _extract_params(self, remaining: list[str]) -> dict[str, str]:
        """从 remaining 路径段中按照 path_template 提取参数。

        path_template 中的普通段作为锚点，{param} 段从 remaining 中取值。
        例如 template=["users", "{uid}", "posts", "{pid}"], remaining=["5", "posts", "42"]
        → {"uid": "5", "pid": "42"}
        """
        params: dict[str, str] = {}
        ri = 0  # remaining 中的当前位置
        for seg in self.path_template:
            if seg.startswith("{") and seg.endswith("}"):
                name = seg[1:-1]
                if ri < len(remaining):
                    params[name] = remaining[ri]
                    ri += 1
            else:
                # 普通段：在 remaining 中找到它并前进
                if ri < len(remaining) and remaining[ri] == seg:
                    ri += 1
        return params

    def _handle(
        self,
        request: Handler,
        path: list[str],
        args: dict[str, str],
        method: str,
    ) -> None:
        # 提取路径参数
        remaining = path[self.route_len:]
        params = self._extract_params(remaining)

        # 检查必需的路径参数是否齐全
        missing = [p for p in self.path_params if p not in params]
        if missing:
            request.send_response(HTTPStatus.BAD_REQUEST)
            request.send_header("Content-Type", "application/json")
            err = json.dumps({"error": f"Missing path parameter(s): {', '.join(missing)}"}).encode()
            request.send_header("Content-Length", str(len(err)))
            request.end_headers()
            request.wfile.write(err)
            return

        # 解析 JSON 请求体（POST / PUT / PATCH / DELETE）
        body: Any = None
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            content_length = int(request.headers.get("Content-Length", 0))
            if content_length > 0:
                if self.max_body > 0 and content_length > self.max_body:
                    request.send_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    request.send_header("Content-Type", "application/json")
                    err = json.dumps({"error": "Request body too large"}).encode()
                    request.send_header("Content-Length", str(len(err)))
                    request.end_headers()
                    request.wfile.write(err)
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
        try:
            status_code, result = self.func(params, body)
        except Exception as e:
            logger.error("SimpleAPI error: %s", e)
            request.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            request.send_header("Content-Type", "application/json")
            err = json.dumps({"error": str(e)}).encode()
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
        # 将 {param} 替换为通配路径匹配用的占位符
        clean_path = re.sub(r'\{[^}]+\}', '', path)
        # 保留分隔符位置用于前缀匹配
        self._routes.append({
            "path": path,
            "clean_path": clean_path,
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

        路径参数段（如 {user_id}）不参与 Route 匹配，
        而是作为前缀匹配后剩余段的提取依据。
        """
        if base_path:
            base_parts = [p for p in base_path.strip("/").split("/") if p]
        else:
            base_parts = []

        services: list[SimpleAPIService] = []
        for route in self._routes:
            full_path_str = route["path"]
            if full_path_str.startswith("/"):
                full_path_str = full_path_str[1:]
            path_segments = [p for p in full_path_str.split("/") if p]

            # 分离固定段和参数段：遇到第一个 {param} 就停止
            # 匹配路径 = base + 固定段，用 prefix 匹配
            fixed_segments: list[str] = []
            for seg in path_segments:
                if seg.startswith("{") and seg.endswith("}"):
                    break
                fixed_segments.append(seg)

            remote_path = base_parts + fixed_segments

            services.append(SimpleAPIService(
                remote_path=remote_path,
                func=route["func"],
                methods=route["methods"],
                route_type="prefix",
                path_params=route["path_params"],
                path_template=path_segments,  # 完整路径模板，含参数占位符
                host=host,
                port=port,
                max_body=self._max_body,
            ))

        return services
