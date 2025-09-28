"""
重定向服务模块 | Redirect Service Module

该模块定义了用于处理HTTP重定向请求的服务类。
This module defines the service class for handling HTTP redirect requests.
"""

from typing import List, Dict, Optional, Union
from http import HTTPStatus

from . import BaseService, Route
from .. import Handler


class RedirectService(BaseService):
    """
    重定向服务类，用于处理HTTP重定向
    Redirect service class for handling HTTP redirects
    """

    def __init__(
        self,
        remote_path: Union[str, List[str]],
        redirect_path: str,
        methods: List[str] = ["GET", "HEAD", "POST"],
        remote_type: str = "prefix",
        redirect_type: str = "prefix",
        auth_func: Optional[callable] = None,
        default_protocol: str = "http",
        host: Optional[Union[str, List[str]]] = None,
        port: Optional[Union[int, List[int]]] = None
    ) -> None:
        """
        初始化重定向服务
        Initialize redirect service

        Args:
            remote_path: 远程路径 | Remote path
            redirect_path: 重定向目标路径 | Redirect target path
            methods: 支持的HTTP方法列表 | List of supported HTTP methods
            remote_type: 远程路由匹配类型 | Remote route match type
            redirect_type: 重定向类型 | Redirect type
            auth_func: 认证函数 | Authentication function
            default_protocol: 默认协议 | Default protocol
            host: 主机名限制 | Host name restriction
            port: 端口限制 | Port restriction
        """
        self.routes = [
            Route(remote_path, methods, remote_type, host, port),
        ]
        self.redirect_path = redirect_path

        # 验证重定向类型 | Validate redirect type
        if redirect_type not in ["prefix", "exact"]:
            raise ValueError(f"Type {redirect_type} is not a valid type.")
        self.redirect_type = redirect_type
        self.default_protocol = default_protocol

        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path

    def calc_path(self, path: List[str], request: Handler) -> str:
        """
        计算重定向路径
        Calculate redirect path

        Args:
            path: 请求路径段列表 | Request path segments list
            request: HTTP请求处理器 | HTTP request handler

        Returns:
            计算出的重定向路径 | Calculated redirect path
        """
        sub_path = path[len(self.remote_path):]

        if self.redirect_type == "prefix":
            # 前缀匹配模式 | Prefix match mode
            if self.redirect_path[-1] == "/":
                r_path = self.redirect_path + '/'.join(sub_path)
            else:
                r_path = self.redirect_path + '/' + '/'.join(sub_path)

            # 处理协议 | Handle protocol
            if r_path[:2] == "//":
                r_path = self.default_protocol + ":" + r_path
            elif r_path[:1] == "/":
                request_host = request.headers.get("Host")
                r_path = self.default_protocol + "://" + request_host + r_path
        else:
            # 精确匹配模式 | Exact match mode
            r_path = self.redirect_path

        return r_path

    def handle_GET(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str]
    ) -> None:
        """
        处理GET请求的重定向
        Handle GET request redirect

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
        """
        # 验证身份认证 | Verify authentication
        if not self.auth_verify(request, path, args, "GET"):
            return

        # 计算重定向路径并发送响应 | Calculate redirect path and send response
        r_path = self.calc_path(path, request)
        request.send_response(HTTPStatus.MOVED_PERMANENTLY)
        request.send_header("Location", r_path)
        request.end_headers()

    def handle_HEAD(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str]
    ) -> None:
        """
        处理HEAD请求的重定向
        Handle HEAD request redirect

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
        """
        # 验证身份认证 | Verify authentication
        if not self.auth_verify(request, path, args, "HEAD"):
            return

        # 计算重定向路径并发送响应 | Calculate redirect path and send response
        r_path = self.calc_path(path, request)
        request.send_response(HTTPStatus.MOVED_PERMANENTLY)
        request.send_header("Location", r_path)
        request.end_headers()

    def handle_POST(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str]
    ) -> None:
        """
        处理POST请求的重定向
        Handle POST request redirect

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
        """
        # 验证身份认证 | Verify authentication
        if not self.auth_verify(request, path, args, "POST"):
            return

        # 计算重定向路径并发送响应 | Calculate redirect path and send response
        r_path = self.calc_path(path, request)
        request.send_response(HTTPStatus.PERMANENT_REDIRECT)
        request.send_header("Location", r_path)
        request.end_headers()
