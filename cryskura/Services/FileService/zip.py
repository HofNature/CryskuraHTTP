"""?zip 端点：zip 压缩下载（单文件 + 递归目录）。

"""
from __future__ import annotations

import io
import logging
import os
import zipfile
from typing import TYPE_CHECKING
from http import HTTPStatus
from urllib.parse import quote

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler

logger = logging.getLogger(__name__)

# 小于此阈值的 zip 读入内存发送
_IN_MEMORY_LIMIT = 10 * 1024 * 1024  # 10 MB

# 每次流式读取的块大小
_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


class _ChunkedWriter:
    """文件对象接口，供 zipfile 写入时使用。
    """

    def __init__(self, request):
        self.request = request
        self._buffer = bytearray()
        self._pos = 0

    def write(self, b: bytes) -> int:
        self._buffer.extend(b)
        written = len(b)
        # 当缓冲达到阈值时刷新为一个 chunk 帧
        if len(self._buffer) >= _CHUNK_SIZE:
            self.flush()
        self._pos += written
        return written

    def flush(self) -> None:
        if not self._buffer:
            return
        data = bytes(self._buffer)
        self.request.wfile.write(data)
        self._buffer.clear()

    def close(self) -> None:
        self.flush()
        self.request.wfile.flush()


def handle_zip(request: HTTPRequestHandler, real_path: str) -> None:
    """处理 ?zip 查询参数，以 zip 压缩包形式下载文件或目录。

    策略：
    - 单个小文件：在内存中构建 zip 并发送。
    - 其他实时压缩并发送（不占用磁盘/大量内存）。
    """
    basename = os.path.basename(real_path) or "download"
    zip_name = basename + ".zip"

    # 单文件且小于阈值时：在内存中构建 zip 并发送 Content-Length
    if os.path.isfile(real_path) and os.path.getsize(real_path) <= _IN_MEMORY_LIMIT:
        _send_in_memory_single_file(request, real_path, basename, zip_name)
        return

    # 否则采用流式实时压缩并发送
    _send_streamed_on_the_fly(request, real_path, basename, zip_name)

def _send_in_memory_single_file(
    request: HTTPRequestHandler,
    file_path: str,
    basename: str,
    zip_name: str,
) -> None:
    """针对单个小文件，直接在内存中构建 zip 并发送（带 Content-Length）。"""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_path, basename)
    data = bio.getvalue()

    request.send_response(HTTPStatus.OK)
    request.send_header("Content-Type", "application/zip")
    request.send_header(
        "Content-Disposition",
        f'attachment; filename="{quote(zip_name)}"',
    )
    request.send_header("Content-Length", str(len(data)))
    request.end_headers()
    request.wfile.write(data)


def _send_streamed_on_the_fly(
    request: HTTPRequestHandler,
    real_path: str,
    basename: str,
    zip_name: str,
) -> None:
    """实时分段压缩并流式发送 zip（仅支持 HTTP/1.1）。

    使用 zipfile 写入到自定义的 `_ChunkedWriter`，它会把数据直接写入 `request.wfile`。此方法不会在磁盘或一次性内存中构建完整 zip 文件，适用于目录或大文件集合。
    """
    is_http10 = (
        hasattr(request, "request_version")
        and request.request_version == "HTTP/1.0"
    )

    if is_http10:
        request.send_error(
            HTTPStatus.INSUFFICIENT_STORAGE,
            "Zip file is too large for HTTP/1.0. Please retry with HTTP/1.1.",
        )
        return

    request.send_response(HTTPStatus.OK)
    request.send_header("Content-Type", "application/zip")
    request.send_header(
        "Content-Disposition",
        f'attachment; filename="{quote(zip_name)}"',
    )
    request.end_headers()

    writer = _ChunkedWriter(request)

    root_real = os.path.realpath(real_path)

    try:
        with zipfile.ZipFile(writer, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(real_path):
                zf.write(real_path, basename)
            elif os.path.isdir(real_path):
                for dirpath, _dirnames, filenames in os.walk(real_path):
                    for fn in filenames:
                        fp = os.path.join(dirpath, fn)
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
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
        # 在写入过程中，如果发生任何异常（例如客户端断开），直接终止
        try:
            request.connection.close()
        except OSError:
            pass
