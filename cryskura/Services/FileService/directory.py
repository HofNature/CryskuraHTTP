"""目录列表页面渲染。"""
from __future__ import annotations

import html
import os
import json
import re
from typing import TYPE_CHECKING
from http import HTTPStatus
from ...Pages import Directory_Page, Cryskura_Icon

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler


def _html_safe_json(obj) -> str:
    """将对象序列化为 JSON 字符串，并将 <、>、/、& 替换为 Unicode 转义，
    避免在 HTML <script> 块中被浏览器解析为标签或提前结束脚本。"""
    raw = json.dumps(obj, ensure_ascii=True)
    return re.sub(r'[<>/&]', lambda m: f'\\u{ord(m.group()):04x}', raw)


def handle_directory(
    request: HTTPRequestHandler,
    real_path: str,
    server_name: str,
    allow_upload: bool,
) -> None:
    """渲染目录列表 HTML 页面。"""
    request.send_response(HTTPStatus.OK)
    request.send_header("Content-Type", "text/html")
    request.end_headers()

    # Issue 12: HTML-escape server_name before inserting into page
    page = Directory_Page.replace("CryskuraHTTP", html.escape(server_name))
    page = page.replace(
        'background: url("Cryskura.png");',
        f'background: url("{Cryskura_Icon}");',
    )

    dirs, files = [], []
    for entry in os.listdir(real_path):
        if os.path.isdir(os.path.join(real_path, entry)):
            dirs.append(entry)
        else:
            files.append(entry)
    dirs.sort()
    files.sort()

    # Issue 1: use HTML-safe JSON to prevent </script> injection in <script> block
    script_vars = (
        f"let subfolders={_html_safe_json(dirs)};"
        f"let files={_html_safe_json(files)};"
        f"let allowUpload={int(allow_upload)};"
    )
    page = page.replace("<script>", f"<script>{script_vars}")
    request.wfile.write(page.encode())
