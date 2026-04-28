"""断点续传 / Range 请求处理。"""
from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING
from http import HTTPStatus

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler


def handle_range_request(
    request: HTTPRequestHandler,
    real_path: str,
    args: dict[str, str],
) -> bool:
    """处理 Range 请求头，支持单段和多段范围请求。

    Returns:
        True 如果处理了 Range 请求（包括错误），False 如果没有 Range 头。
    """
    if 'Range' not in request.headers:
        return False

    range_header = request.headers["Range"]
    range_h = range_header.strip("bytes=").split(",")
    file_size = os.path.getsize(real_path)
    ranges: list[tuple[int, int]] = []

    for r in range_h:
        if '-' in r:
            start_str, end_str = r.split('-', 1)
            try:
                if start_str == '':
                    end = int(end_str)
                    start = max(file_size - end, 0)
                    end = file_size - 1
                elif end_str == '':
                    start = int(start_str)
                    end = file_size - 1
                else:
                    start = int(start_str)
                    end = min(int(end_str), file_size - 1)
            except ValueError:
                request.errsvc.handle(request, [], args, "GET", HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return True
        else:
            try:
                start = int(r)
            except ValueError:
                request.errsvc.handle(request, [], args, "GET", HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return True
            end = file_size - 1

        if start < 0 or start > end:
            request.errsvc.handle(request, [], args, "GET", HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            return True
        ranges.append((start, end))

    if len(ranges) == 1:
        _send_single_range(request, real_path, ranges[0], file_size)
    else:
        _send_multi_range(request, real_path, ranges, file_size)

    return True


def _send_single_range(
    request: HTTPRequestHandler,
    real_path: str,
    range_tuple: tuple[int, int],
    file_size: int,
) -> None:
    """发送单段 Range 响应 (206 Partial Content)。"""
    start, end = range_tuple
    length = end - start + 1
    request.send_response(HTTPStatus.PARTIAL_CONTENT)
    request.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
    request.send_header("Content-Length", str(length))
    request.send_header("Accept-Ranges", "bytes")
    request.send_header("Content-Type", request.guess_type(request.path))
    request.end_headers()
    with open(real_path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(8192, remaining))
            request.wfile.write(chunk)
            remaining -= len(chunk)


def _send_multi_range(
    request: HTTPRequestHandler,
    real_path: str,
    ranges: list[tuple[int, int]],
    file_size: int,
) -> None:
    """发送多段 Range 响应 (multipart/byteranges)。"""
    boundary = "CRYSKURA_BOUNDARY_" + str(random.randint(int(1e10), int(1e11) - 1))
    request.send_response(HTTPStatus.PARTIAL_CONTENT)
    request.send_header("Content-Type", f"multipart/byteranges; boundary={boundary}")
    request.end_headers()
    with open(real_path, 'rb') as f:
        for start, end in ranges:
            length = end - start + 1
            request.wfile.write(f"--{boundary}\r\n".encode())
            request.wfile.write(f"Content-Type: {request.guess_type(request.path)}\r\n".encode())
            request.wfile.write(f"Content-Range: bytes {start}-{end}/{file_size}\r\n".encode())
            request.wfile.write(b"\r\n")
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(8192, remaining))
                request.wfile.write(chunk)
                remaining -= len(chunk)
            request.wfile.write(b"\r\n")
    request.wfile.write(f"--{boundary}--\r\n".encode())
