from __future__ import annotations

import os
from http import HTTPStatus
from typing import Optional, TYPE_CHECKING

from .base_service import BaseService, Route

if TYPE_CHECKING:
    from ..handler import HTTPRequestHandler
    from .._types import AuthFunc


class PageService(BaseService):
    def __init__(
        self,
        local_path: str,
        remote_path: str,
        index_pages: tuple[str, ...] = ("index.html", "index.htm"),
        auth_func: Optional[AuthFunc] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        self.routes = [
            Route(remote_path, ["GET", "HEAD"], "prefix", host, port),
        ]
        self.local_path: str = os.path.abspath(local_path)
        self.index_pages: tuple[str, ...] = index_pages
        super().__init__(self.routes, auth_func)
        self.remote_path: list[str] = self.routes[0].path

    def calc_path(self, path: list[str]) -> tuple[bool, str, str]:
        sub_path = path[len(self.remote_path):]
        r_directory = os.path.abspath(self.local_path)
        real_path = os.path.realpath(os.path.join(r_directory, '/'.join(sub_path)))
        r_path = '/' + '/'.join(sub_path)
        is_valid = False
        try:
            common_path = os.path.commonpath([real_path, os.path.realpath(self.local_path)])
        except ValueError:
            return False, r_directory, r_path
        if os.path.exists(real_path) and os.path.samefile(common_path, os.path.realpath(self.local_path)):
            if os.path.isfile(real_path):
                is_valid = True
            else:
                for file in self.index_pages:
                    if os.path.exists(os.path.join(real_path, file)):
                        is_valid = True
                        r_path = os.path.join(r_path, file)
                        break
        return is_valid, r_directory, r_path

    def handle_GET(self, request: HTTPRequestHandler, path: list[str], args: dict[str, str]) -> None:
        if not self.auth_verify(request, path, args, "GET"):
            return
        is_valid, request.directory, request.path = self.calc_path(path)
        if not is_valid:
            request.errsvc.handle(request, path, args, "GET", HTTPStatus.NOT_FOUND)
            return
        f = request.send_head()
        if f:
            try:
                request.copyfile(f, request.wfile)
            except Exception as e:
                f.close()
                raise e
            f.close()

    def handle_HEAD(self, request: HTTPRequestHandler, path: list[str], args: dict[str, str]) -> None:
        if not self.auth_verify(request, path, args, "HEAD"):
            return
        is_valid, request.directory, request.path = self.calc_path(path)
        if not is_valid:
            request.errsvc.handle(request, path, args, "HEAD", HTTPStatus.NOT_FOUND)
            return
        f = request.send_head()
        if f:
            f.close()
