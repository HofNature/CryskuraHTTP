"""
错误服务模块 | Error Service Module

该模块定义了HTTP错误响应的处理服务。
This module defines the service for handling HTTP error responses.
"""

from typing import List, Dict
from http import HTTPStatus

from ..Pages import Error_Page, Cryskura_Icon
from . import BaseService
from .. import Handler


class ErrorService(BaseService):
    """
    错误服务类，用于处理HTTP错误响应
    Error service class for handling HTTP error responses
    """

    def __init__(self, server_name: str) -> None:
        """
        初始化错误服务
        Initialize error service

        Args:
            server_name: 服务器名称 | Server name
        """
        self.server_name = server_name

    def handle(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str],
        method: str,
        status: int
    ) -> None:
        """
        处理HTTP错误响应
        Handle HTTP error response

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
            method: HTTP方法 | HTTP method
            status: HTTP状态码 | HTTP status code
        """
        # 对于HEAD请求，只发送头部信息 | For HEAD requests, send only headers
        if method == "HEAD":
            request.send_response(status)
            request.end_headers()
            return

        # 发送完整的错误页面 | Send complete error page
        request.send_response(status)
        request.send_header("Content-Type", "text/html")
        request.end_headers()

        # 获取状态描述 | Get status description
        status_str = HTTPStatus(status).phrase

        # 替换错误页面模板中的占位符 | Replace placeholders in error page template
        page = Error_Page.replace("CryskuraHTTP", self.server_name)
        page = page.replace(
            'background: url("Cryskura.png");',
            f'background: url("{Cryskura_Icon}");'
        )
        page = page.replace(
            "<script>",
            f"<script>let error='{str(status) + ' ' + status_str}';"
        )

        # 发送错误页面内容 | Send error page content
        request.wfile.write(page.encode())

