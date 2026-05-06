"""FileService：文件服务，支持目录列表、文件下载、断点续传、上传。

子模块：
    info     — ?info 端点（文件信息 JSON）
    zip      — ?zip 端点（压缩下载）
    range    — 断点续传 Range 请求
    upload   — 文件上传（multipart/form-data）
    directory — 目录列表 HTML 渲染
"""
from __future__ import annotations

import logging
import os
import mimetypes
from http import HTTPStatus
from typing import Optional, TYPE_CHECKING

from ..BaseService import BaseService, Route
from .directory import handle_directory
from .info import handle_info
from .range import handle_range_request
from .upload import handle_upload
from .zip import handle_zip

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler as Handler

logger = logging.getLogger(__name__)


class FileService(BaseService):
    def __init__(
        self,
        local_path: str,
        remote_path: str,
        isFolder: bool = True,
        allowResume: bool = False,
        server_name: str = "CryskuraHTTP",
        auth_func: Optional[function] = None,
        allowUpload: bool = False,
        host: Optional[str] = None,
        port: Optional[int] = None,
        upload_limit: int = 0,
        expose_details: bool = True,
    ) -> None:
        methods = ["GET", "HEAD"]
        if allowUpload:
            methods.append("POST")
        self.routes = [
            Route(remote_path, methods, "prefix" if isFolder else "exact", host, port),
        ]
        self.allowUpload = allowUpload
        self.isFolder = isFolder
        self.allowResume = allowResume
        self.upload_limit = upload_limit
        # Issue 11: expose_details controls whether ?info includes permissions/is_symlink
        self.expose_details: bool = expose_details
        self.local_path = os.path.abspath(local_path)
        if not os.path.exists(local_path):
            raise ValueError(f"Path {local_path} does not exist.")
        if isFolder and not os.path.isdir(local_path):
            raise ValueError(f"Path {local_path} is not a folder.")
        if not isFolder and not os.path.isfile(local_path):
            raise ValueError(f"Path {local_path} is not a file.")
        self.server_name = server_name
        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path

    def calc_path(self, path: list) -> tuple[bool, str, str, str]:
        """解析请求路径到本地文件路径，返回 (is_valid, r_directory, r_path, real_path)。"""
        if self.isFolder:
            sub_path = path[len(self.remote_path):]
            r_directory = os.path.abspath(self.local_path)
            real_path = os.path.realpath(os.path.join(r_directory, '/'.join(sub_path)))
            r_path = '/' + '/'.join(sub_path)
        else:
            r_directory = os.path.dirname(self.local_path)
            r_path = os.path.basename(self.local_path)
            real_path = os.path.realpath(self.local_path)
        try:
            common_path = os.path.commonpath([real_path, os.path.realpath(self.local_path)])
        except ValueError:
            return False, r_directory, r_path, real_path
        is_valid = os.path.exists(real_path) and os.path.samefile(common_path, os.path.realpath(self.local_path))
        return is_valid, r_directory, r_path, real_path

    # ── GET ────────────────────────────────────────────────────

    def handle_GET(self, request: Handler, path: list, args: dict) -> None:
        if not self.auth_verify(request, path, args, "GET"):
            return

        is_valid, request.directory, request.path, real_path = self.calc_path(path)
        if not is_valid:
            request.errsvc.handle(request, path, args, "GET", HTTPStatus.NOT_FOUND)
            return

        # ?info: 文件信息
        if "info" in args:
            handle_info(request, real_path, self.expose_details)
            return

        # ?zip: 压缩下载
        if "zip" in args:
            handle_zip(request, real_path)
            return

        # Range: 断点续传
        if self.allowResume and os.path.isfile(real_path):
            if handle_range_request(request, real_path, args):
                return

        # 目录列表
        if os.path.isdir(real_path):
            handle_directory(request, real_path, self.server_name, self.allowUpload)
            return

        # 304 Not Modified 检查（send_head 内部也检查，但依赖 self.etag 属性）
        try:
            st = os.stat(real_path)
            etag = f'"{int(st.st_mtime):x}-{st.st_size:x}"'
            inm = request.headers.get("If-None-Match")
            if inm and etag in inm.split(","):
                request.send_response(HTTPStatus.NOT_MODIFIED)
                request.send_header("ETag", etag)
                request.send_header("Last-Modified", request.date_time_string(int(st.st_mtime)))
                request.end_headers()
                return
        except OSError:
            pass

        # 普通文件
        f = request.send_head()  # type: ignore[assignment]
        if f:
            try:
                request.copyfile(f, request.wfile)
            finally:
                f.close()

    # ── HEAD ───────────────────────────────────────────────────

    def handle_HEAD(self, request: Handler, path: list, args: dict) -> None:
        if not self.auth_verify(request, path, args, "HEAD"):
            return
        is_valid, request.directory, request.path, real_path = self.calc_path(path)
        if not is_valid:
            request.errsvc.handle(request, path, args, "HEAD", HTTPStatus.NOT_FOUND)
            return
        if os.path.isdir(real_path):
            request.send_response(HTTPStatus.OK)
            request.send_header("Content-Type", "text/html")
            request.end_headers()
        else:
            f = request.send_head()
            if f:
                f.close()

    # ── POST (上传) ────────────────────────────────────────────

    def handle_POST(self, request: Handler, path: list, args: dict) -> None:
        if not self.auth_verify(request, path, args, "POST"):
            return
        if not self.allowUpload:
            request.errsvc.handle(request, path, args, "POST", HTTPStatus.METHOD_NOT_ALLOWED)
            return
        is_valid, request.directory, request.path, real_path = self.calc_path(path)
        if not is_valid or not os.path.isdir(real_path):
            request.errsvc.handle(request, path, args, "POST", HTTPStatus.NOT_FOUND)
            return
        handle_upload(request, real_path, self.upload_limit)
