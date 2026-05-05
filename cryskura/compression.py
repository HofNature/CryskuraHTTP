"""Gzip 压缩响应包装器。

Gzip-compressed response wrapper for HTTP responses.
"""
from __future__ import annotations

import io
import gzip
from typing import BinaryIO

# 可压缩的 MIME 类型 / MIME types eligible for gzip compression
COMPRESSIBLE_TYPES: set[str] = {
    "text/html", "text/css", "text/javascript", "text/plain", "text/xml",
    "application/javascript", "application/json", "application/xml",
    "application/xhtml+xml", "application/rss+xml", "application/atom+xml",
    "application/wasm", "image/svg+xml", "application/x-javascript",
}


class GzipFileWrapper(io.RawIOBase):
    """包装原始 wfile，在写入时实时 gzip 压缩。

    Wraps the raw socket wfile and compresses data on-the-fly with gzip.

    每 64KB 自动 flush 一次，避免 gzip 缓冲区无限膨胀。
    Automatically flushes every 64 KB to prevent unbounded buffer growth.
    """

    def __init__(self, wfile: BinaryIO, compresslevel: int = 5) -> None:
        """初始化 gzip 包装器。

        Initialise the gzip wrapper.

        Args:
            wfile: 底层套接字写入流。 / Underlying socket write stream.
            compresslevel: gzip 压缩级别（1–9）。 / Gzip compression level (1–9).
        """
        self._wfile: BinaryIO = wfile
        self._gzip: gzip.GzipFile = gzip.GzipFile(
            mode="wb", fileobj=wfile, compresslevel=compresslevel
        )
        self._closed_gzip: bool = False
        self._bytes_written: int = 0
        self._flush_threshold: int = 65536  # 64KB

    def write(self, data: bytes) -> int:  # type: ignore[override]
        """写入数据并实时压缩，超过阈值时自动 flush。

        Write data through the gzip compressor; auto-flush when the threshold is hit.

        Args:
            data: 要写入的原始字节。 / Raw bytes to compress and write.

        Returns:
            int: 已写入的原始字节数。 / Number of raw bytes written.
        """
        if self._closed_gzip:
            raise ValueError("write to closed gzip wrapper")
        n = self._gzip.write(data)
        self._bytes_written += n
        if self._bytes_written >= self._flush_threshold:
            self._gzip.flush()
            self._bytes_written = 0
        return n

    def flush(self) -> None:
        """刷新 gzip 内部缓冲区到底层流。

        Flush the gzip internal buffer to the underlying stream.
        """
        if not self._closed_gzip:
            self._gzip.flush()
            self._bytes_written = 0

    def close(self) -> None:
        """关闭 gzip 流并写入结尾标记。

        Close the gzip stream and write the final trailer bytes.
        """
        if not self._closed_gzip:
            try:
                self._gzip.flush()
            except Exception:
                pass
            self._gzip.close()
            self._closed_gzip = True

    def writable(self) -> bool:
        """返回 True，表示此流可写。 / Return True; this stream is always writable."""
        return True

    def fileno(self) -> int:
        """返回底层文件描述符。 / Return the underlying file descriptor."""
        return self._wfile.fileno()


def is_compressible(content_type: str | None) -> bool:
    """判断 Content-Type 是否可用 gzip 压缩。

    Return True if the given Content-Type header value is gzip-compressible.

    Args:
        content_type: HTTP Content-Type 头值（可含参数）。
                      HTTP Content-Type header value (may include parameters).

    Returns:
        bool: 是否可压缩。 / Whether the content type is compressible.
    """
    if not content_type:
        return False
    base = content_type.split(";")[0].strip().lower()
    return base in COMPRESSIBLE_TYPES


def accepts_gzip(accept_encoding: str | None) -> bool:
    """判断客户端是否接受 gzip 编码（q > 0）。

    Return True if the client's Accept-Encoding header accepts gzip (q > 0).

    Args:
        accept_encoding: HTTP Accept-Encoding 头值。 / HTTP Accept-Encoding header value.

    Returns:
        bool: 客户端是否接受 gzip。 / Whether the client accepts gzip encoding.
    """
    if not accept_encoding:
        return False
    for part in accept_encoding.split(","):
        part = part.strip()
        if part.startswith("gzip"):
            # 检查 q=0 / Skip if explicitly disabled (q=0)
            if "q=" in part:
                try:
                    q = float(part.split("q=")[1].split(";")[0].strip())
                    if q <= 0:
                        continue
                except (ValueError, IndexError):
                    pass
            return True
    return False
