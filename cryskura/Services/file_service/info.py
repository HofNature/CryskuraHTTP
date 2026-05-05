"""?info 端点：返回文件/目录详细信息 JSON。"""
from __future__ import annotations

import os
import json
import datetime
from typing import TYPE_CHECKING
from http import HTTPStatus

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler


def handle_info(
    request: HTTPRequestHandler,
    real_path: str,
    expose_details: bool = True,
) -> None:
    """处理 ?info 查询参数，返回文件/目录的详细信息 JSON。

    Args:
        request: HTTP 请求对象。
        real_path: 目标文件/目录的绝对路径。
        expose_details: Issue 11 — 是否在响应中包含 permissions 和 is_symlink 字段。
                        默认为 True（保持原有行为），可在敏感环境中设为 False。
    """
    try:
        st = os.stat(real_path)
    except OSError:
        request.errsvc.handle(request, [], {}, "GET", HTTPStatus.NOT_FOUND)
        return

    info: dict = {
        "name": os.path.basename(real_path),
        "path": request.path,
        "size": st.st_size,
        "modified": datetime.datetime.fromtimestamp(
            st.st_mtime, tz=datetime.timezone.utc
        ).isoformat(),
        "created": datetime.datetime.fromtimestamp(
            getattr(st, "st_ctime", st.st_mtime), tz=datetime.timezone.utc
        ).isoformat(),
        "is_dir": os.path.isdir(real_path),
        "is_file": os.path.isfile(real_path),
    }

    # Issue 11: conditionally include sensitive fields
    if expose_details:
        info["is_symlink"] = os.path.islink(real_path)
        info["permissions"] = oct(st.st_mode & 0o777)

    if os.path.isdir(real_path):
        try:
            entries = os.listdir(real_path)
            info["item_count"] = len(entries)
            info["file_count"] = sum(
                1 for e in entries if os.path.isfile(os.path.join(real_path, e))
            )
            info["dir_count"] = sum(1 for e in entries if os.path.isdir(os.path.join(real_path, e)))
        except PermissionError:
            info["item_count"] = -1

    info["mime_type"] = request.guess_type(request.path) if os.path.isfile(real_path) else None

    body = json.dumps(info, ensure_ascii=False).encode()
    request.send_response(HTTPStatus.OK)
    request.send_header("Content-Type", "application/json; charset=utf-8")
    request.send_header("Content-Length", str(len(body)))
    request.end_headers()
    request.wfile.write(body)
