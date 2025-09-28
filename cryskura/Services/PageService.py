"""
页面服务模块 | Page Service Module

该模块定义了用于提供静态页面服务的类。
This module defines the class for serving static page services.
"""

from typing import List, Dict, Tuple, Optional, Union
import os
from http import HTTPStatus

from . import BaseService, Route
from .. import Handler


class PageService(BaseService):
    """
    页面服务类，用于提供静态页面服务
    Page service class for serving static pages
    """

    def __init__(
        self,
        local_path: str,
        remote_path: Union[str, List[str]],
        index_pages: Tuple[str, ...] = ("index.html", "index.htm"),
        auth_func: Optional[callable] = None,
        host: Optional[Union[str, List[str]]] = None,
        port: Optional[Union[int, List[int]]] = None
    ) -> None:
        """
        初始化页面服务
        Initialize page service

        Args:
            local_path: 本地文件路径 | Local file path
            remote_path: 远程访问路径 | Remote access path
            index_pages: 默认索引页面列表 | Default index page list
            auth_func: 认证函数 | Authentication function
            host: 主机名限制 | Host name restriction
            port: 端口限制 | Port restriction
        """
        self.routes = [
            Route(remote_path, ["GET", "HEAD"], "prefix", host, port),
        ]
        self.local_path = os.path.abspath(local_path)
        self.index_pages = index_pages
        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path

    def calc_path(self, path: List[str]) -> Tuple[bool, str, str]:
        """
        计算实际文件路径
        Calculate actual file path

        Args:
            path: 请求路径段列表 | Request path segments list

        Returns:
            (是否有效, 根目录, 相对路径) | (is_valid, root_directory, relative_path)
        """
        sub_path = path[len(self.remote_path):]
        r_directory = os.path.abspath(self.local_path)
        r_path = '/' + '/'.join(sub_path)
        real_path = os.path.join(r_directory, '/'.join(sub_path))
        is_valid = False
        common_path = os.path.commonpath([real_path, self.local_path])

        if (os.path.exists(real_path) and
                os.path.samefile(common_path, self.local_path)):
            if os.path.isfile(real_path):
                is_valid = True
            else:
                # 检查是否有默认索引页面 | Check for default index pages
                for file in self.index_pages:
                    index_file_path = os.path.join(real_path, file)
                    if os.path.exists(index_file_path):
                        is_valid = True
                        r_path = os.path.join(r_path, file)
                        break

        return is_valid, r_directory, r_path

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
        # 验证身份认证 | Verify authentication
        if not self.auth_verify(request, path, args, "GET"):
            return

        # 计算文件路径 | Calculate file path
        is_valid, request.directory, request.path = self.calc_path(path)
        if not is_valid:
            request.errsvc.handle(
                request, path, args, "GET", HTTPStatus.NOT_FOUND
            )
            return

        # 发送文件内容 | Send file content
        f = request.send_head()
        if f:
            try:
                request.copyfile(f, request.wfile)
            except Exception as e:
                f.close()
                raise e
            f.close()

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
        # 验证身份认证 | Verify authentication
        if not self.auth_verify(request, path, args, "HEAD"):
            return

        # 计算文件路径 | Calculate file path
        is_valid, request.directory, request.path = self.calc_path(path)
        if not is_valid:
            request.errsvc.handle(
                request, path, args, "HEAD", HTTPStatus.NOT_FOUND
            )
            return

        # 只发送头部信息 | Send only headers
        f = request.send_head()
        if f:
            f.close()
