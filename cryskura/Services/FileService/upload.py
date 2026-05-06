"""文件上传处理（multipart/form-data），支持单次请求多文件。"""
from __future__ import annotations

import os
import re
import json
import logging
from typing import TYPE_CHECKING
from http import HTTPStatus
from urllib.parse import quote

_SSL_EOF: type
try:
    import ssl as _ssl_mod
    _SSL_EOF = _ssl_mod.SSLEOFError
except ImportError:
    _SSL_EOF = OSError

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler

logger = logging.getLogger(__name__)


def _parse_filename(content_disposition: str) -> str | None:
    """从 Content-Disposition 头解析 filename，兼容 RFC 各种写法。"""
    match = re.search(
        r"""filename\*\s*=\s*[^']+'\w*'([^;,\s]+)|filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;,\s]+)""",
        content_disposition,
    )
    if match:
        result = match.group(1) or match.group(2) or match.group(3)
        # 去除可能的外层引号
        if result and len(result) >= 2 and result[0] == '"' and result[-1] == '"':
            result = result[1:-1]
        return result
    return None


def _parse_multipart(body: bytes, boundary_bytes: bytes) -> list[dict]:
    """解析 multipart body，返回所有 part 的列表。

    每个 part: {"headers": str, "content": bytes}
    """
    delim = b'--' + boundary_bytes + b'\r\n'

    parts: list[dict] = []
    pos = 0

    # 找到第一个 delimiter
    start = body.find(delim, pos)
    if start == -1:
        return parts
    pos = start + len(delim)

    while True:
        # 找到此 part 的 \r\n\r\n（头结束）
        header_end = body.find(b'\r\n\r\n', pos)
        if header_end == -1:
            break

        headers = body[pos:header_end].decode('utf-8', errors='replace')
        content_start = header_end + 4

        # 找下一个 \r\n--boundary（可能是分隔符或结束符）
        next_boundary = body.find(b'\r\n--' + boundary_bytes, content_start)
        if next_boundary == -1:
            break

        content = body[content_start:next_boundary]
        parts.append({"headers": headers, "content": content})

        # 检查是结束符还是分隔符
        after = body[next_boundary + 2: next_boundary + 2 + len(b'--' + boundary_bytes) + 2]
        if after.startswith(b'--' + boundary_bytes + b'--'):
            break  # 结束
        # 否则是分隔符，跳过 \r\n--boundary\r\n
        pos = next_boundary + 2 + len(b'--' + boundary_bytes) + 2

    return parts


def handle_upload(
    request: HTTPRequestHandler,
    real_path: str,
    upload_limit: int,
) -> None:
    """处理文件上传 POST 请求，支持单次多文件。

    Args:
        request: HTTP 请求对象。
        real_path: 目标目录的绝对路径。
        upload_limit: 上传文件大小限制（字节），0 表示不限。
    """
    content_type = request.headers.get('Content-Type', '')
    if 'multipart/form-data' not in content_type:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return

    content_length = request.headers.get('Content-Length')
    if content_length:
        length = int(content_length)
        if upload_limit > 0 and length > upload_limit:
            request.errsvc.handle(request, [], {}, "POST", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
    else:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.LENGTH_REQUIRED)
        return

    # 解析 boundary
    boundary_match = re.search(r'boundary=(?:"([^"]+)"|([^\s;]+))', content_type)
    if not boundary_match:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return
    boundary_value = boundary_match.group(1) or boundary_match.group(2)
    boundary_bytes = boundary_value.encode()

    # 读取完整请求体
    body = request.rfile.read(length)

    # 解析所有 parts
    parts = _parse_multipart(body, boundary_bytes)
    if not parts:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return

    # 处理每个文件 part
    saved_files: list[str] = []
    errors: list[str] = []

    for part in parts:
        filename = _parse_filename(part["headers"])
        if not filename:
            continue  # 跳过非文件字段

        # 过滤路径分隔符，防止目录穿越
        filename = os.path.basename(filename)
        if not filename:
            continue

        local_filepath = os.path.join(real_path, filename)
        try:
            with open(local_filepath, 'xb') as f:
                f.write(part["content"])
            saved_files.append(filename)
        except FileExistsError:
            errors.append(f"{filename}: already exists")
        except Exception as e:
            if os.path.exists(local_filepath):
                os.remove(local_filepath)
            if isinstance(e, (ConnectionAbortedError, ConnectionResetError, _SSL_EOF)):
                raise
            logger.error("Upload error for %s: %s", filename, e)
            errors.append(f"{filename}: {e}")

    if not saved_files and errors:
        # 所有文件都失败
        if "already exists" in errors[0]:
            request.errsvc.handle(request, [], {}, "POST", HTTPStatus.CONFLICT)
        else:
            request.errsvc.handle(request, [], {}, "POST", HTTPStatus.INTERNAL_SERVER_ERROR)
        return

    # 返回结果
    if len(saved_files) == 1 and not errors:
        # 单文件成功：保持原有 201 行为
        request.send_response(HTTPStatus.CREATED)
        if request.path[-1] != "/":
            request.send_header("Location", quote(request.path + "/" + saved_files[0]))
        else:
            request.send_header("Location", quote(request.path + saved_files[0]))
        request.end_headers()
    else:
        # 多文件或部分成功：返回 JSON
        result = {
            "saved": saved_files,
            "count": len(saved_files),
        }
        if errors:
            result["errors"] = errors
        body_bytes = json.dumps(result, ensure_ascii=False).encode()
        status = HTTPStatus.CREATED if saved_files else HTTPStatus.INTERNAL_SERVER_ERROR
        if saved_files and errors:
            status = HTTPStatus.MULTI_STATUS  # 207 Multi-Status
        request.send_response(status)
        request.send_header("Content-Type", "application/json; charset=utf-8")
        request.send_header("Content-Length", str(len(body_bytes)))
        request.end_headers()
        request.wfile.write(body_bytes)
