from __future__ import annotations

import html
import json
from http import HTTPStatus
from typing import TYPE_CHECKING

from ..pages import Error_Page, Cryskura_Icon
from .base_service import BaseService

if TYPE_CHECKING:
    from ..handler import HTTPRequestHandler as Handler


class ErrorService(BaseService):
    def __init__(self, server_name: str) -> None:
        super().__init__([])
        self.server_name: str = server_name

    def handle(
        self, request: Handler, path: list[str], args: dict[str, str],
        method: str, status: int,
    ) -> None:
        if method == "HEAD":
            request.send_response(status)
            request.end_headers()
            return
        request.send_response(status)
        request.send_header("Content-Type", "text/html")
        request.end_headers()
        status_str = HTTPStatus(status).phrase
        # Issue 12: HTML-escape server_name before embedding in page
        page = Error_Page.replace("CryskuraHTTP", html.escape(self.server_name))
        page = page.replace(
            'background: url("Cryskura.png");',
            f'background: url("{Cryskura_Icon}");',
        )
        error_msg = json.dumps(str(status) + ' ' + status_str)
        page = page.replace('let error = "";', f'let error = {error_msg};')
        request.wfile.write(page.encode())
