"""
文件服务模块 | File Service Module

该模块定义了用于提供文件服务的类，支持文件下载、目录浏览和文件上传功能。
This module defines the class for file services, supporting file downloads,
directory browsing, and file upload functionality.
"""

from typing import List, Dict, Tuple, Optional, Union
import os
import ssl
import json
import random
from http import HTTPStatus
from urllib.parse import quote

from . import BaseService, Route
from .. import Handler
from ..Pages import Directory_Page, Cryskura_Icon


class FileService(BaseService):
    """
    文件服务类，用于提供文件和目录服务
    File service class for providing file and directory services
    """

    def __init__(
        self,
        local_path: str,
        remote_path: Union[str, List[str]],
        is_folder: bool = True,
        allow_resume: bool = False,
        server_name: str = "CryskuraHTTP",
        auth_func: Optional[callable] = None,
        allow_upload: bool = False,
        host: Optional[Union[str, List[str]]] = None,
        port: Optional[Union[int, List[int]]] = None
    ) -> None:
        """
        初始化文件服务
        Initialize file service

        Args:
            local_path: 本地文件或目录路径 | Local file or directory path
            remote_path: 远程访问路径 | Remote access path
            is_folder: 是否为文件夹服务 | Whether it's a folder service
            allow_resume: 是否允许断点续传 | Whether to allow resume downloads
            server_name: 服务器名称 | Server name
            auth_func: 认证函数 | Authentication function
            allow_upload: 是否允许文件上传 | Whether to allow file uploads
            host: 主机名限制 | Host name restriction
            port: 端口限制 | Port restriction
        """
        # 根据功能设置支持的HTTP方法 | Set supported HTTP methods based on features
        methods = ["GET", "HEAD"]
        if allow_upload:
            methods.append("POST")

        self.routes = [
            Route(
                remote_path,
                methods,
                "prefix" if is_folder else "exact",
                host,
                port
            ),
        ]

        # 设置实例属性 | Set instance attributes
        self.allow_upload = allow_upload
        self.is_folder = is_folder
        self.allow_resume = allow_resume
        self.local_path = os.path.abspath(local_path)
        self.server_name = server_name

        # 验证路径的有效性 | Validate path validity
        if not os.path.exists(local_path):
            raise ValueError(f"Path {local_path} does not exist.")
        if is_folder and not os.path.isdir(local_path):
            raise ValueError(f"Path {local_path} is not a folder.")
        if not is_folder and not os.path.isfile(local_path):
            raise ValueError(f"Path {local_path} is not a file.")

        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path

    def calc_path(self, path: List[str]) -> Tuple[bool, str, str, str]:
        """
        计算实际文件路径
        Calculate actual file path

        Args:
            path: 请求路径段列表 | Request path segments list

        Returns:
            (是否有效, 根目录, 相对路径, 实际路径) |
            (is_valid, root_directory, relative_path, real_path)
        """
        if self.is_folder:
            # 文件夹模式：处理子路径 | Folder mode: handle sub-paths
            sub_path = path[len(self.remote_path):]
            r_directory = os.path.abspath(self.local_path)
            r_path = '/' + '/'.join(sub_path)
            real_path = os.path.join(r_directory, '/'.join(sub_path))
        else:
            # 单文件模式 | Single file mode
            r_directory = os.path.dirname(self.local_path)
            r_path = os.path.basename(self.local_path)
            real_path = self.local_path

        # 验证路径安全性 | Validate path security
        common_path = os.path.commonpath([real_path, self.local_path])
        is_valid = (os.path.exists(real_path) and
                    os.path.samefile(common_path, self.local_path))

        return is_valid, r_directory, r_path, real_path

    def _handle_range_request(
        self,
        request: Handler,
        real_path: str,
        range_header: str
    ) -> None:
        """
        处理HTTP Range请求（断点续传）
        Handle HTTP Range requests (resume downloads)

        Args:
            request: HTTP请求处理器 | HTTP request handler
            real_path: 实际文件路径 | Actual file path
            range_header: Range头部内容 | Range header content
        """
        range_h = range_header.strip("bytes=").split(",")
        file_size = os.path.getsize(real_path)
        ranges = []

        # 解析Range头部 | Parse Range header
        for r in range_h:
            if '-' in r:
                start_str, end_str = r.split('-')
                if start_str == '':
                    start = file_size - int(end_str)
                    end = file_size - 1
                elif end_str == '':
                    start = int(start_str)
                    end = file_size - 1
                else:
                    start = int(start_str)
                    end = min(int(end_str), file_size - 1)
            else:
                start = int(r)
                end = file_size - 1
            ranges.append((start, end))

        if len(ranges) == 1:
            # 单一范围请求 | Single range request
            start, end = ranges[0]
            length = end - start + 1
            request.send_response(HTTPStatus.PARTIAL_CONTENT)
            request.send_header(
                "Content-Range", f"bytes {start}-{end}/{file_size}"
            )
            request.send_header("Content-Length", length)
            request.send_header("Accept-Ranges", "bytes")
            request.send_header(
                "Content-Type", request.guess_type(request.path)
            )
            request.end_headers()

            # 发送文件片段 | Send file segment
            with open(real_path, 'rb') as f:
                f.seek(start)
                chunk_size = 8192
                while length > 0:
                    chunk = f.read(min(chunk_size, length))
                    request.wfile.write(chunk)
                    length -= len(chunk)
        else:
            # 多范围请求 | Multiple range request
            boundary = (f"CRYSKURA_BOUNDARY_"
                        f"{random.randint(int(1e10), int(1e11) - 1)}")
            request.send_response(HTTPStatus.PARTIAL_CONTENT)
            request.send_header(
                "Content-Type",
                f"multipart/byteranges; boundary={boundary}"
            )
            request.end_headers()

            with open(real_path, 'rb') as f:
                for start, end in ranges:
                    length = end - start + 1
                    request.wfile.write(f"--{boundary}\r\n".encode())
                    request.wfile.write(
                        f"Content-Type: "
                        f"{request.guess_type(request.path)}\r\n".encode()
                    )
                    request.wfile.write(
                        f"Content-Range: bytes "
                        f"{start}-{end}/{file_size}\r\n".encode()
                    )
                    request.wfile.write("\r\n".encode())
                    f.seek(start)
                    chunk_size = 8192
                    while length > 0:
                        chunk = f.read(min(chunk_size, length))
                        request.wfile.write(chunk)
                        length -= len(chunk)
                    request.wfile.write("\r\n".encode())
            request.wfile.write(f"--{boundary}--\r\n".encode())

    def _handle_directory_listing(
        self,
        request: Handler,
        real_path: str
    ) -> None:
        """
        处理目录列表显示
        Handle directory listing display

        Args:
            request: HTTP请求处理器 | HTTP request handler
            real_path: 实际目录路径 | Actual directory path
        """
        request.send_response(HTTPStatus.OK)
        request.send_header("Content-Type", "text/html")
        request.end_headers()

        # 替换页面模板 | Replace page template
        page = Directory_Page.replace("CryskuraHTTP", self.server_name)
        page = page.replace(
            'background: url("Cryskura.png");',
            f'background: url("{Cryskura_Icon}");'
        )

        # 列出目录下的文件和文件夹 | List files and folders in directory
        dirs, files = [], []
        for file in os.listdir(real_path):
            if os.path.isdir(os.path.join(real_path, file)):
                dirs.append(file)
            else:
                files.append(file)
        dirs.sort()
        files.sort()

        # 注入JavaScript数据 | Inject JavaScript data
        page = page.replace(
            "<script>",
            f"<script>let subfolders='{json.dumps(dirs, ensure_ascii=True)}';"
            f"let files='{json.dumps(files, ensure_ascii=True)}';"
            f"let allowUpload={self.allow_upload * 1};"
        )
        request.wfile.write(page.encode())

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
        is_valid, request.directory, request.path, real_path = \
            self.calc_path(path)
        if not is_valid:
            request.errsvc.handle(
                request, path, args, "GET", HTTPStatus.NOT_FOUND
            )
            return

        # 处理断点续传请求 | Handle resume download requests
        if (self.allow_resume and 'Range' in request.headers and
                os.path.isfile(real_path)):
            range_header = request.headers["Range"]
            self._handle_range_request(request, real_path, range_header)
        elif os.path.isdir(real_path):
            # 处理目录浏览 | Handle directory browsing
            self._handle_directory_listing(request, real_path)
        else:
            # 处理普通文件下载 | Handle normal file download
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
        is_valid, request.directory, request.path, real_path = \
            self.calc_path(path)
        if not is_valid:
            request.errsvc.handle(
                request, path, args, "HEAD", HTTPStatus.NOT_FOUND
            )
            return

        if os.path.isdir(real_path):
            # 目录的HEAD请求 | HEAD request for directory
            request.send_response(HTTPStatus.OK)
            request.send_header("Content-Type", "text/html")
            request.end_headers()
        else:
            # 文件的HEAD请求 | HEAD request for file
            f = request.send_head()
            if f:
                f.close()

    def handle_POST(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str]
    ) -> None:
        """
        处理POST请求（文件上传）
        Handle POST request (file upload)

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
        """
        # 验证身份认证 | Verify authentication
        if not self.auth_verify(request, path, args, "POST"):
            return

        # 检查是否允许上传 | Check if upload is allowed
        if not self.allow_upload:
            request.errsvc.handle(
                request, path, args, "POST", HTTPStatus.METHOD_NOT_ALLOWED
            )
            return

        # 计算路径并验证是否为有效目录 | Calculate path and validate directory
        is_valid, request.directory, request.path, real_path = \
            self.calc_path(path)
        if not is_valid or not os.path.isdir(real_path):
            request.errsvc.handle(
                request, path, args, "POST", HTTPStatus.NOT_FOUND
            )
            return

        # 获取内容长度 | Get content length
        content_length = int(request.headers.get('Content-Length', 0))
        if content_length <= 0:
            request.errsvc.handle(
                request, path, args, "POST", HTTPStatus.LENGTH_REQUIRED
            )
            return

        try:
            self._handle_file_upload(request, path, args, real_path,
                                     content_length)
        except Exception as e:
            # 处理上传过程中的异常 | Handle exceptions during upload
            if isinstance(e, (ConnectionAbortedError, ConnectionResetError,
                              ssl.SSLEOFError)):
                raise e
            else:
                request.errsvc.handle(
                    request, path, args, "POST",
                    HTTPStatus.INTERNAL_SERVER_ERROR
                )
                raise e

    def _handle_file_upload(
        self,
        request: Handler,
        path: List[str],
        args: Dict[str, str],
        real_path: str,
        content_length: int
    ) -> None:
        """
        处理文件上传的核心逻辑
        Core logic for handling file uploads

        Args:
            request: HTTP请求处理器 | HTTP request handler
            path: 路径段列表 | Path segments list
            args: 查询参数字典 | Query parameters dictionary
            real_path: 实际目录路径 | Actual directory path
            content_length: 内容长度 | Content length
        """
        split_length = 1024 * 1024  # 1MB chunks
        first_part = request.rfile.read(min(content_length, split_length))

        # 解析multipart/form-data | Parse multipart/form-data
        content_type = request.headers.get('Content-Type', '')
        boundary = content_type.split('boundary=')[-1].encode()
        boundary = b'--' + boundary + b'\r\n'
        head_part = first_part.split(boundary)

        if len(head_part) < 2:
            request.errsvc.handle(
                request, path, args, "POST", HTTPStatus.BAD_REQUEST
            )
            return

        # 提取文件信息 | Extract file information
        file_start = head_part[1].find(b'\r\n\r\n') + 4
        fileinfo = head_part[1][:file_start].decode('utf-8')

        try:
            filename = fileinfo.split("filename=")[1].split('"')[1]
        except (IndexError, ValueError):
            request.errsvc.handle(
                request, path, args, "POST", HTTPStatus.BAD_REQUEST
            )
            return

        if filename == "":
            request.errsvc.handle(
                request, path, args, "POST", HTTPStatus.BAD_REQUEST
            )
            return

        # 检查文件是否已存在 | Check if file already exists
        local_filepath = os.path.join(real_path, filename)
        if os.path.exists(local_filepath):
            request.errsvc.handle(
                request, path, args, "POST", HTTPStatus.CONFLICT
            )
            return

        # 保存文件 | Save file
        this_part = head_part[1][file_start:]
        remaining_length = content_length - len(boundary) - 4

        try:
            if remaining_length <= split_length:
                # 小文件：一次性写入 | Small file: write all at once
                with open(local_filepath, 'wb') as f:
                    f.write(head_part[1][file_start:-len(boundary) - 4])
            else:
                # 大文件：分块写入 | Large file: write in chunks
                remaining_length -= split_length
                with open(local_filepath, 'wb') as f:
                    f.write(this_part)
                    while remaining_length > 0:
                        chunk = request.rfile.read(
                            min(remaining_length, split_length)
                        )
                        remaining_length -= min(remaining_length, split_length)
                        if chunk == b'':
                            request.errsvc.handle(
                                request, path, args, "POST",
                                HTTPStatus.BAD_REQUEST
                            )
                            os.remove(local_filepath)
                            return
                        f.write(chunk)

            # 发送成功响应 | Send success response
            request.send_response(HTTPStatus.CREATED)
            if request.path[-1] != "/":
                request.send_header(
                    "Location", request.path + "/" + quote(filename)
                )
            else:
                request.send_header(
                    "Location", request.path + quote(filename)
                )
            request.end_headers()

        except Exception as e:
            # 清理失败的上传文件 | Clean up failed upload file
            if os.path.exists(local_filepath):
                os.remove(local_filepath)
            raise e
