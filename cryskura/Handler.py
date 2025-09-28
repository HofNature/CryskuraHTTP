"""
HTTP请求处理器模块 | HTTP Request Handler Module

该模块定义了用于处理HTTP请求的核心处理器类。
This module defines the core handler class for processing HTTP requests.
"""

from typing import List, Dict, Tuple, Optional, Any

# SSL模块导入处理，兼容不含ssl库的Python版本
# SSL module import handling, compatible with Python versions without ssl library
try:
    import ssl
except ImportError:
    ssl = None  # type: ignore

from urllib.parse import unquote
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler

from . import __version__


class HTTPRequestHandler(SimpleHTTPRequestHandler):
    """
    HTTP请求处理器类，继承自SimpleHTTPRequestHandler
    HTTP request handler class, inheriting from SimpleHTTPRequestHandler
    """

    server_version = "CryskuraHTTP/" + __version__
    index_pages: Tuple[str, ...] = ()

    def __init__(
        self,
        *args: Any,
        services: List[Any],
        errsvc: Any,
        directory: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        初始化HTTP请求处理器
        Initialize HTTP request handler

        Args:
            *args: 位置参数 | Positional arguments
            services: 服务列表 | List of services
            errsvc: 错误服务 | Error service
            directory: 目录路径 | Directory path
            **kwargs: 关键字参数 | Keyword arguments
        """
        self.services = services
        self.errsvc = errsvc
        # 设置默认目录以避免文件系统访问 | Set default directory to avoid filesystem access
        directory = "/dev/null"
        super().__init__(*args, directory=directory, **kwargs)

    def split_Path(self) -> Tuple[List[str], Dict[str, str]]:
        """
        分割URL路径和查询参数
        Split URL path and query parameters

        Returns:
            (路径段列表, 参数字典) | (path_segments_list, parameters_dict)
        """
        # 将路径分割为路径和参数 | Split path into path and parameters
        path_parts = unquote(self.path).split("?", 1)
        if len(path_parts) == 1:
            path, args = path_parts[0], ""
        else:
            path, args = path_parts

        # 处理路径 | Process path
        path = path.replace("\\", "/").split("/")
        if path[0] == "":
            path.pop(0)
        if path and path[-1] == "":
            path.pop(-1)

        # 处理查询参数 | Process query parameters
        args_list = args.split("&")
        processed_args: Dict[str, str] = {}
        for arg in args_list:
            if "=" not in arg:
                if arg != "":
                    processed_args[arg] = ""
            else:
                arg_parts = arg.split("=", 1)
                processed_args[arg_parts[0]] = arg_parts[1]

        return path, processed_args

    def _parse_host_port(self, host_header: str) -> Tuple[Optional[str], Optional[int]]:
        """
        解析Host头部中的主机名和端口
        Parse hostname and port from Host header

        Args:
            host_header: Host头部值 | Host header value

        Returns:
            (主机名, 端口号) | (hostname, port_number)
        """
        try:
            if host_header.startswith('['):  # IPv6 address
                if ']' in host_header:
                    host, _, port_str = host_header[1:].partition(']')
                    if port_str.startswith(':'):
                        port_str = port_str[1:]
                    else:
                        port_str = None
                else:
                    return None, None
            else:  # IPv4 or hostname
                host, _, port_str = host_header.partition(':')

            if port_str:
                try:
                    port = int(port_str)
                except ValueError:
                    print(f"Invalid port number {port_str!r}")
                    return None, None
            else:
                port = None

            return host, port
        except Exception:
            print(f"Invalid host {host_header!r}")
            return None, None

    def handle_one_request(self) -> None:
        """
        处理单个HTTP请求
        Handle a single HTTP request
        """
        try:
            # 读取请求行 | Read request line
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
                return

            if not self.raw_requestline:
                self.close_connection = True
                return

            if not self.parse_request():
                # 已发送错误码，直接退出 | Error code sent, just exit
                return

            # 解析路径和参数 | Parse path and parameters
            path, args = self.split_Path()
            host_header = self.headers.get('Host', None)

            # 解析主机名和端口 | Parse hostname and port
            if host_header is None:
                host, port = None, None
            else:
                host, port = self._parse_host_port(host_header)

            # 查找合适的服务处理请求 | Find appropriate service to handle request
            path_exists = False
            handled = False

            for service in self.services:
                for route in service.routes:
                    can_handle, path_ok = route.match(path, self.command, host, port)
                    if path_ok:
                        path_exists = True
                    if can_handle:
                        try:
                            # 检查服务是否有对应的处理方法
                            # Check if service has corresponding handler method
                            if not hasattr(service, "handle_" + self.command):
                                raise ValueError(
                                    f"Service to handle {path} does not have a "
                                    f"{self.command} handler, but a route exists."
                                )

                            # 调用处理方法 | Call handler method
                            method = getattr(service, "handle_" + self.command)
                            method(self, path, args)
                            handled = True
                            break
                        except Exception as e:
                            # 处理连接异常 | Handle connection exceptions
                            # 构建SSL异常元组，兼容无SSL环境
                            # Build SSL exception tuple, compatible with no SSL env
                            ssl_exceptions = (
                                ssl.SSLEOFError,) if ssl is not None else ()
                            connection_exceptions = (
                                ConnectionAbortedError, ConnectionResetError
                            ) + ssl_exceptions

                            if isinstance(e, connection_exceptions):
                                print(
                                    f"Client disconnected while handling "
                                    f"{self.command} request for "
                                    f"/{'/'.join(path)}: {e}"
                                )
                                return

                            # 处理其他异常 | Handle other exceptions
                            print(
                                f"Error while handling {self.command} request for "
                                f"/{'/'.join(path)}: {e}"
                            )
                            self.errsvc.handle(
                                self, path, args, self.command,
                                HTTPStatus.INTERNAL_SERVER_ERROR
                            )
                            handled = True
                            break

                if handled:
                    break

            # 如果没有找到合适的处理器 | If no suitable handler found
            if not handled:
                if path_exists:
                    self.errsvc.handle(
                        self, path, args, self.command,
                        HTTPStatus.METHOD_NOT_ALLOWED
                    )
                else:
                    self.errsvc.handle(
                        self, path, args, self.command, HTTPStatus.NOT_FOUND
                    )

            # 刷新输出缓冲区 | Flush output buffer
            self.wfile.flush()

        except TimeoutError as e:
            # 读取或写入超时，丢弃此连接 | Read or write timed out, discard connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return
