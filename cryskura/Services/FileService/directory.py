"""目录列表页面渲染。"""
from __future__ import annotations

import os
import json
from typing import TYPE_CHECKING
from http import HTTPStatus
from ...Pages import Directory_Page, Cryskura_Icon

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler


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

    page = Directory_Page.replace("CryskuraHTTP", server_name)
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

    script_vars = (
        f"let subfolders={json.dumps(dirs, ensure_ascii=True)};"
        f"let files={json.dumps(files, ensure_ascii=True)};"
        f"let allowUpload={int(allow_upload)};"
    )
    page = page.replace("<script>", f"<script>{script_vars}")
    request.wfile.write(page.encode())
