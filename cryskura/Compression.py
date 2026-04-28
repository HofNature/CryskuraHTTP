"""Gzip 压缩响应包装器。"""
from __future__ import annotations

import io
import gzip
from typing import BinaryIO

# 可压缩的 MIME 类型
COMPRESSIBLE_TYPES: set[str] = {
    "text/html", "text/css", "text/javascript", "text/plain", "text/xml",
    "application/javascript", "application/json", "application/xml",
    "application/xhtml+xml", "application/rss+xml", "application/atom+xml",
    "application/wasm", "image/svg+xml", "application/x-javascript",
}


class GzipFileWrapper(io.RawIOBase):
    """包装原始 wfile，在写入时实时 gzip 压缩。

    每 64KB 自动 flush 一次，避免 gzip 缓冲区无限膨胀。
    """

    def __init__(self, wfile: BinaryIO, compresslevel: int = 5) -> None:
        self._wfile: BinaryIO = wfile
        self._gzip: gzip.GzipFile = gzip.GzipFile(
            mode="wb", fileobj=wfile, compresslevel=compresslevel
        )
        self._closed_gzip: bool = False
        self._bytes_written: int = 0
        self._flush_threshold: int = 65536  # 64KB

    def write(self, data: bytes) -> int:  # type: ignore[override]
        if self._closed_gzip:
            raise ValueError("write to closed gzip wrapper")
        n = self._gzip.write(data)
        self._bytes_written += n
        if self._bytes_written >= self._flush_threshold:
            self._gzip.flush()
            self._bytes_written = 0
        return n

    def flush(self) -> None:
        if not self._closed_gzip:
            self._gzip.flush()
            self._bytes_written = 0

    def close(self) -> None:
        if not self._closed_gzip:
            try:
                self._gzip.flush()
            except Exception:
                pass
            self._gzip.close()
            self._closed_gzip = True

    def writable(self) -> bool:
        return True

    def fileno(self) -> int:
        return self._wfile.fileno()


def is_compressible(content_type: str | None) -> bool:
    """判断 Content-Type 是否可压缩。"""
    if not content_type:
        return False
    base = content_type.split(";")[0].strip().lower()
    return base in COMPRESSIBLE_TYPES


def accepts_gzip(accept_encoding: str | None) -> bool:
    """判断客户端是否接受 gzip 编码。"""
    if not accept_encoding:
        return False
    for part in accept_encoding.split(","):
        part = part.strip()
        if part.startswith("gzip"):
            # 检查 q=0
            if "q=" in part:
                try:
                    q = float(part.split("q=")[1].split(";")[0].strip())
                    if q <= 0:
                        continue
                except (ValueError, IndexError):
                    pass
            return True
    return False
