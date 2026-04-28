"""HTTP 缓存逻辑：ETag、Last-Modified、304 Not Modified。"""
from __future__ import annotations

import os
from typing import Optional, TYPE_CHECKING
from http import HTTPStatus

if TYPE_CHECKING:
    from ..Handler import HTTPRequestHandler


def _real_path(request: HTTPRequestHandler) -> Optional[str]:
    """从 request.directory / request.path 计算本地真实路径。"""
    if not hasattr(request, "directory") or not hasattr(request, "path"):
        return None
    # request.path 以 '/' 开头，os.path.join 会将其视为绝对路径丢弃前半部分
    path_component = request.path.lstrip('/') if request.path else ""
    if path_component:
        return os.path.join(request.directory, path_component)
    return request.directory


def check_cache(request: HTTPRequestHandler) -> bool:
    """尝试返回 304 Not Modified。返回 True 表示已处理。"""
    real = _real_path(request)
    if real is None or not os.path.isfile(real):
        return False
    try:
        st = os.stat(real)
    except OSError:
        return False

    etag = f'"{int(st.st_mtime):x}-{st.st_size:x}"'
    mtime = st.st_mtime

    # If-None-Match
    inm = request.headers.get("If-None-Match")
    if inm and etag in inm.split(","):
        request.send_response(HTTPStatus.NOT_MODIFIED)
        request.send_header("ETag", etag)
        request.end_headers()
        return True

    # If-Modified-Since
    ims = request.headers.get("If-Modified-Since")
    if ims:
        from email.utils import parsedate_to_datetime
        try:
            ims_time = parsedate_to_datetime(ims).timestamp()
            if mtime <= ims_time:
                request.send_response(HTTPStatus.NOT_MODIFIED)
                request.send_header("ETag", etag)
                request.send_header("Last-Modified", request.date_time_string(int(mtime)))
                request.end_headers()
                return True
        except Exception:
            pass
    return False


def add_cache_headers(request: HTTPRequestHandler) -> None:
    """给文件响应添加 ETag / Last-Modified / Cache-Control 头。"""
    real = _real_path(request)
    if real is None or not os.path.isfile(real):
        return
    try:
        st = os.stat(real)
    except OSError:
        return
    etag = f'"{int(st.st_mtime):x}-{st.st_size:x}"'
    request.send_header("ETag", etag)
    request.send_header("Last-Modified", request.date_time_string(int(st.st_mtime)))
    request.send_header("Cache-Control", "public, max-age=0, must-revalidate")


def check_and_inject_file_headers(request: HTTPRequestHandler) -> None:
    """在 end_headers() 之前调用：如果响应对应本地文件，注入缓存头。"""
    real = _real_path(request)
    if real is None or not os.path.isfile(real):
        return
    try:
        st = os.stat(real)
    except OSError:
        return
    etag = f'"{int(st.st_mtime):x}-{st.st_size:x}"'
    request.send_header("ETag", etag)
    request.send_header("Last-Modified", request.date_time_string(int(st.st_mtime)))
    request.send_header("Cache-Control", "public, max-age=0, must-revalidate")
