"""
API服务模块 | API Service Module

该模块定义了用于处理API请求的服务类。
This module defines the service class for handling API requests.
"""

from typing import List, Dict, Callable, Optional, Union

from . import BaseService, Route
from .. import Handler


class APIService(BaseService):
    """
    API服务类，用于处理API请求
    API service class for handling API requests
    """

    def __init__(
        self,
        remote_path: Union[str, List[str]],
        func: Callable,
        methods: List[str] = ["GET", "HEAD", "POST"],
        type: str = "prefix",
        auth_func: Optional[Callable] = None,
        length_limit: int = 1024 * 1024,
        host: Optional[Union[str, List[str]]] = None,
        port: Optional[Union[int, List[int]]] = None
    ) -> None:
        """
        初始化API服务
        Initialize API service

        Args:
            remote_path: 远程路径 | Remote path
            func: API处理函数 | API handler function
            methods: 支持的HTTP方法列表 | List of supported HTTP methods
            type: 路由匹配类型 | Route match type
            auth_func: 认证函数 | Authentication function
            length_limit: 请求内容长度限制 | Request content length limit
            host: 主机名限制 | Host name restriction
            port: 端口限制 | Port restriction
        """
        self.routes = [
            Route(remote_path, methods, type, host, port),
        ]
        self.func = func
        self.length_limit = length_limit

        # 为每个HTTP方法动态创建处理器 | Dynamically create handlers for each HTTP method
        for method in methods:
            setattr(
                self,
                f"handle_{method}",
                lambda request, path, args, method=method: self.handle_API(
                    request, path, args, method
                )
            )

        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path

    def handle_API(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str],
        method: str
    ) -> None:
        """
        处理API请求的核心逻辑
        Core logic for handling API requests

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
            method: HTTP方法 | HTTP method
        """
        # 验证身份认证 | Verify authentication
        if not self.auth_verify(request, path, args, method):
            return

        # 提取子路径 | Extract sub-path
        sub_path = path[len(self.remote_path):]

        # 获取请求头和内容 | Get request headers and content
        headers = request.headers
        content_length = int(headers.get("Content-Length", 0))
        content = request.rfile.read(min(content_length, self.length_limit))

        # 调用用户提供的API处理函数 | Call user-provided API handler function
        code, response_headers, response_content = self.func(
            request, sub_path, args, headers, content, method
        )

        # 发送响应 | Send response
        request.send_response(code)
        for key, value in response_headers.items():
            request.send_header(key, value)
        request.end_headers()
        request.wfile.write(response_content)
