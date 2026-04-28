"""?zip 端点：zip 压缩下载（单文件 + 递归目录）。

优化策略：
- 小文件（< 100MB）：读入内存，Content-Length 发送，兼容所有 HTTP 版本。
- HTTP/1.1 + 大文件：流式 chunked 传输编码，零内存拷贝。
- HTTP/1.0 + 大文件：回退，返回 507 Insufficient Storage，提示用 HTTP/1.1。
"""
from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from typing import TYPE_CHECKING
from http import HTTPStatus
from urllib.parse import quote

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler

logger = logging.getLogger(__name__)

# 小于此阈值的 zip 读入内存发送（兼容 HTTP/1.0）；超过则回退到流式
_IN_MEMORY_LIMIT = 100 * 1024 * 1024  # 100 MB

# 每次流式读取的块大小
_CHUNK_SIZE = 256 * 1024  # 256 KB


def handle_zip(request: HTTPRequestHandler, real_path: str) -> None:
    """处理 ?zip 查询参数，以 zip 压缩包形式下载文件或目录。

    构建 zip 到临时文件后，根据文件大小和 HTTP 版本选择发送策略：
    - 小于 _IN_MEMORY_LIMIT：全部读入内存，Content-Length 发送。
    - HTTP/1.1 + 超过限制：流式 chunked 传输。
    - HTTP/1.0 + 超过限制：返回 507，提示客户端升级到 HTTP/1.1。
    """
    basename = os.path.basename(real_path) or "download"
    zip_name = basename + ".zip"

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="cryskura_")
    try:
        os.close(tmp_fd)
        _build_zip(tmp_path, real_path, basename)
        file_size = os.path.getsize(tmp_path)

        if file_size <= _IN_MEMORY_LIMIT:
            _send_in_memory(request, tmp_path, file_size, zip_name)
        else:
            _send_streamed(request, tmp_path, file_size, zip_name)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _build_zip(tmp_path: str, real_path: str, basename: str) -> None:
    """将文件或目录压缩为 zip 并写入临时文件。"""
    root_real = os.path.realpath(real_path)
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.isfile(real_path):
            zf.write(real_path, basename)
        elif os.path.isdir(real_path):
            for dirpath, _dirnames, filenames in os.walk(real_path):
                for fn in filenames:
                    fp = os.path.join(dirpath, fn)
                    # Issue 6: boundary-check resolved path to prevent symlink escape
                    resolved = os.path.realpath(fp)
                    if not (resolved == root_real or resolved.startswith(root_real + os.sep)):
                        logger.warning("Skipping out-of-tree path in zip: %s -> %s", fp, resolved)
                        continue
                    arcname = os.path.join(
                        basename, os.path.relpath(fp, real_path),
                    )
                    try:
                        zf.write(fp, arcname)
                    except (OSError, PermissionError) as e:
                        logger.warning("Skipping file %s in zip: %s", fp, e)
                        continue


def _send_in_memory(
    request: HTTPRequestHandler,
    tmp_path: str,
    file_size: int,
    zip_name: str,
) -> None:
    """读入内存发送（Content-Length），兼容 HTTP/1.0 和 HTTP/1.1。"""
    with open(tmp_path, "rb") as f:
        zip_data = f.read()
    request.send_response(HTTPStatus.OK)
    request.send_header("Content-Type", "application/zip")
    request.send_header(
        "Content-Disposition",
        f'attachment; filename="{quote(zip_name)}"',
    )
    request.send_header("Content-Length", str(len(zip_data)))
    request.end_headers()
    request.wfile.write(zip_data)


def _send_streamed(
    request: HTTPRequestHandler,
    tmp_path: str,
    file_size: int,
    zip_name: str,
) -> None:
    """流式发送大 zip 文件。

    HTTP/1.1 → 手动按 chunked 帧格式写入（Python http.server 不会自动
    做 chunked 编码，必须由应用层手动写 <hex-size>\\r\\n<data>\\r\\n）。
    HTTP/1.0 → 返回 507 Insufficient Storage，提示客户端用 HTTP/1.1。
    """
    # 判断 HTTP 版本
    is_http10 = (
        hasattr(request, "request_version")
        and request.request_version == "HTTP/1.0"
    )

    if is_http10:
        # HTTP/1.0 不支持 chunked 传输编码，无法流式发送大文件
        request.send_error(
            HTTPStatus.INSUFFICIENT_STORAGE,
            "Zip file is too large for HTTP/1.0. "
            "Please retry with HTTP/1.1 or download files individually.",
        )
        return

    # HTTP/1.1: 使用 Transfer-Encoding: chunked 流式发送
    # 必须手动写 chunked 帧格式，http.server 不会自动编码
    request.send_response(HTTPStatus.OK)
    request.send_header("Content-Type", "application/zip")
    request.send_header(
        "Content-Disposition",
        f'attachment; filename="{quote(zip_name)}"',
    )
    request.send_header("Transfer-Encoding", "chunked")
    request.end_headers()

    with open(tmp_path, "rb") as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            # 手动写 chunked 帧：<hex-size>\r\n<data>\r\n
            request.wfile.write(f"{len(chunk):x}\r\n".encode("ascii"))
            request.wfile.write(chunk)
            request.wfile.write(b"\r\n")
    # 结束帧
    request.wfile.write(b"0\r\n\r\n")
    request.wfile.flush()
