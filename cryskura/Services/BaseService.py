"""
基础服务模块 | Base Service Module

该模块定义了HTTP服务的基础类和路由机制。
This module defines the base classes and routing mechanism for HTTP services.
"""

from typing import List, Dict, Optional, Callable, Tuple, Union
from http import HTTPStatus

from .. import Handler


class Route:
    """
    路由类，用于定义HTTP路由规则
    Route class for defining HTTP routing rules
    """

    def __init__(
        self,
        path: Union[str, List[str]],
        methods: List[str],
        type: str,
        host: Optional[Union[str, List[str]]] = None,
        port: Optional[Union[int, List[int]]] = None
    ) -> None:
        """
        初始化路由对象
        Initialize route object

        Args:
            path: 路径字符串或路径段列表 | Path string or list of path segments
            methods: 支持的HTTP方法列表 | List of supported HTTP methods
            type: 匹配类型('prefix' 或 'exact') | Match type ('prefix' or 'exact')
            host: 主机名限制 | Host name restriction
            port: 端口限制 | Port restriction
        """
        # 处理主机名参数 | Handle host parameter
        if host is not None:
            if isinstance(host, str):
                host = [host]
            for h in host:
                if h is not None and not isinstance(h, str):
                    raise ValueError(f"Host {h} is not a valid host.")
        self.host = host

        # 处理端口参数 | Handle port parameter
        if port is not None:
            if isinstance(port, int):
                port = [port]
            for p in port:
                if p is not None and not isinstance(p, int):
                    raise ValueError(f"Port {p} is not a valid port.")
        self.port = port

        # 处理路径参数 | Handle path parameter
        if not isinstance(path, list):
            if isinstance(path, str):
                path = path.split("/")
                if path[0] == '':
                    path.pop(0)
                if path[-1] == '':
                    path.pop(-1)
            else:
                raise ValueError(f"Path {path} is not a valid path.")
        self.path = path

        # 设置HTTP方法 | Set HTTP methods
        self.methods = methods

        # 验证匹配类型 | Validate match type
        if type not in ["prefix", "exact"]:
            raise ValueError(f"Type {type} is not a valid type.")
        self.type = type

    def match(
        self,
        path: List[str],
        method: str,
        host: Optional[str] = None,
        port: Optional[int] = None
    ) -> Tuple[bool, bool]:
        """
        检查路由是否匹配请求
        Check if route matches the request

        Args:
            path: 请求路径段列表 | Request path segments list
            method: HTTP方法 | HTTP method
            host: 请求主机名 | Request hostname
            port: 请求端口 | Request port

        Returns:
            (匹配成功, 路径存在) | (match_success, path_exists)
        """
        path_exists = False

        # 检查主机名匹配 | Check host match
        if self.host is None:
            host_match = True
        else:
            host_match = host in self.host

        # 检查端口匹配 | Check port match
        if self.port is None:
            port_match = True
        else:
            port_match = port in self.port

        if not host_match or not port_match:
            return False, False

        # 检查路径匹配 | Check path match
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
    """
    基础服务类，所有HTTP服务的父类
    Base service class, parent class for all HTTP services
    """

    def __init__(
        self,
        routes: List[Route],
        auth_func: Optional[Callable] = None
    ) -> None:
        """
        初始化基础服务
        Initialize base service

        Args:
            routes: 路由列表 | List of routes
            auth_func: 认证函数(可选) | Authentication function (optional)
        """
        for r in routes:
            if not isinstance(r, Route):
                raise ValueError(f"Route {r} is not a valid route.")
        self.auth_func = auth_func
        self.routes = routes

    def auth_verify(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str],
        operation: str
    ) -> bool:
        """
        验证用户身份认证
        Verify user authentication

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
            operation: HTTP操作类型 | HTTP operation type

        Returns:
            认证是否成功 | Whether authentication succeeded
        """
        if self.auth_func is not None:
            origin_cookie = request.headers.get("Cookie")
            cookies: Dict[str, str] = {}
            if origin_cookie is not None:
                for cookie in origin_cookie.split(";"):
                    cookie_parts = cookie.split("=")
                    if len(cookie_parts) >= 2:
                        cookies[cookie_parts[0].strip()] = cookie_parts[1].strip()
            if not self.auth_func(cookies, path, args, operation):
                request.errsvc.handle(
                    request, path, args, operation, HTTPStatus.UNAUTHORIZED
                )
                return False
        return True

    def handle_GET(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str]
    ) -> None:
        """
        处理GET请求
        Handle GET request

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
        """
        raise NotImplementedError

    def handle_POST(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str]
    ) -> None:
        """
        处理POST请求
        Handle POST request

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
        """
        raise NotImplementedError

    def handle_HEAD(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str]
    ) -> None:
        """
        处理HEAD请求
        Handle HEAD request

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
        """
        raise NotImplementedError
