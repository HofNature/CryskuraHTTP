"""HTTP 请求处理器：路径解析、服务分发、安全头、gzip、缓存、访问日志。"""
from __future__ import annotations

import time
import uuid
import logging
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from typing import Optional, TYPE_CHECKING
from urllib.parse import unquote

try:
    import ssl
    _SSL_EOF: type = ssl.SSLEOFError
except ImportError:
    logging.warning("SSL module not found. HTTPS is not supported.")
    ssl = None  # type: ignore[assignment]
    _SSL_EOF = OSError

from . import __version__
from .compression import GzipFileWrapper, is_compressible, accepts_gzip
from .handlers.cache import check_cache, add_cache_headers

if TYPE_CHECKING:
    from .Services.base_service import BaseService

logger = logging.getLogger(__name__)


class HTTPRequestHandler(SimpleHTTPRequestHandler):
    server_version = "CryskuraHTTP/" + __version__
    index_pages = ()

    services: list[BaseService]
    errsvc: BaseService
    max_request_body: int
    access_log: bool

    # ── 安全响应头 ────────────────────────────────────────────

    def send_response(self, code: int, message: Optional[str] = None) -> None:
        super().send_response(code, message)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        # Issue 9: Content-Security-Policy — pages use inline scripts/styles and data: URIs
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'",
        )
        # Issue 8: HSTS for TLS connections
        try:
            import ssl as _ssl
            if isinstance(self.request, _ssl.SSLSocket):
                self.send_header(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )
        except (ImportError, AttributeError):
            pass

    # ── 初始化 ────────────────────────────────────────────────

    def __init__(
        self,
        *args: object,
        services: list[BaseService],
        errsvc: BaseService,
        max_request_body: int = 0,
        access_log: bool = False,
        directory: Optional[str] = None,
        **kwargs: object,
    ) -> None:
        self.services = services
        self.errsvc = errsvc
        self.max_request_body = max_request_body
        self.access_log = access_log
        self._cors_service: Optional[BaseService] = None
        self._request_id: str = ""
        self._gzip_active: bool = False
        self._ws_upgrade_complete: bool = False
        directory = "/dev/null"
        super().__init__(*args, directory=directory, **kwargs)  # type: ignore[arg-type]

    # ── CORS 注入 ──────────────────────────────────────────────

    def _inject_cors_headers(self) -> None:
        """遍历 services，找到 CORSService 并注入响应头。"""
        if self._cors_service is not None:
            if hasattr(self._cors_service, "inject_headers"):
                self._cors_service.inject_headers(self)
            return
        for svc in self.services:
            if type(svc).__name__ == "CORSService":
                self._cors_service = svc
                if hasattr(svc, "inject_headers"):
                    svc.inject_headers(self)
                return

    def end_headers(self) -> None:
        """在响应头发送完毕前注入 CORS 头和文件缓存头。"""
        self._inject_cors_headers()
        # 文件响应注入缓存头（send_head 已调用 send_response 清空了缓冲区，
        # 必须在 end_headers 之前注入才能写入响应头）
        if hasattr(self, "directory") and hasattr(self, "path"):
            from .handlers.cache import check_and_inject_file_headers
            check_and_inject_file_headers(self)
        super().end_headers()

    # ── 缓存 ──────────────────────────────────────────────────

    def _check_cache(self) -> bool:
        return check_cache(self)

    def _add_cache_headers(self) -> None:
        add_cache_headers(self)

    # ── Gzip ──────────────────────────────────────────────────

    def _try_setup_gzip(self) -> None:
        """如果客户端接受 gzip 且响应体可压缩，包装 wfile。"""
        if self._gzip_active:
            return
        if self._get_sent_header("Content-Length") is not None:
            return
        ae = self.headers.get("Accept-Encoding", "")
        if not accepts_gzip(ae):
            return
        ct = self._get_sent_header("Content-Type")
        if not is_compressible(ct):
            return
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Vary", "Accept-Encoding")
        self.wfile = GzipFileWrapper(self.wfile)  # type: ignore[assignment,arg-type]
        self._gzip_active = True

    def _get_sent_header(self, name: str) -> Optional[str]:
        """从已发送的响应头中取值。"""
        try:
            buf = self._headers_buffer  # type: ignore[attr-defined]
        except AttributeError:
            return None
        if not buf:
            return None
        name_lower = name.lower()
        for line in buf:
            try:
                line_str = line.decode("latin-1") if isinstance(line, bytes) else line
            except (UnicodeDecodeError, AttributeError):
                continue
            if ":" in line_str:
                k, _, v = line_str.partition(":")
                if k.strip().lower() == name_lower:
                    return v.strip()
        return None

    # ── Access Log ─────────────────────────────────────────────

    def _log_access(self, status: int, duration_ms: float) -> None:
        if not self.access_log:
            return
        rid = getattr(self, "_request_id", "-")
        client = self.client_address[0] if self.client_address else "-"
        logger.info(
            '%s - %s "%s %s %s" %d %.1fms',
            client, rid, self.command, self.path, self.request_version,
            status, duration_ms,
        )

    # ── 路径解析 ──────────────────────────────────────────────

    def split_Path(self) -> tuple[list[str], dict[str, str]]:
        path = unquote(self.path).split("?", 1)
        path_str, args_str = (path[0], path[1]) if len(path) == 2 else (path[0], "")
        path_list = path_str.replace("\\", "/").split("/")
        if path_list and path_list[0] == "":
            path_list.pop(0)
        if path_list and path_list[-1] == "":
            path_list.pop(-1)
        processed_args: dict[str, str] = {}
        for arg in args_str.split("&"):
            if "=" not in arg:
                if arg:
                    processed_args[arg] = ""
            else:
                key, _, value = arg.partition("=")
                processed_args[key] = value
        return path_list, processed_args

    # ── 主请求处理 ────────────────────────────────────────────

    def handle_one_request(self) -> None:
        start_time = time.time()
        status_code = 500

        # WebSocket 连接已升级：不再读取 HTTP 请求
        if getattr(self, "_ws_upgrade_complete", False):
            self.close_connection = True
            return

        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                return

            self._request_id = uuid.uuid4().hex[:12]

            # 全局请求体大小限制
            if self.max_request_body > 0:
                content_length = self.headers.get("Content-Length")
                if content_length:
                    try:
                        if int(content_length) > self.max_request_body:
                            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                            status_code = 413
                            return
                    except ValueError:
                        self.send_error(HTTPStatus.BAD_REQUEST)
                        status_code = 400
                        return

            path, args = self.split_Path()
            host, port = self._parse_host()

            status_code = self._dispatch(path, args, host, port)

            # WebSocket 连接已升级：跳过 HTTP 清理和日志
            if not getattr(self, "_ws_upgrade_complete", False):
                self.wfile.flush()
                self._cleanup_gzip()

        except TimeoutError as e:
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return
        finally:
            if not getattr(self, "_ws_upgrade_complete", False):
                self._log_access(status_code, (time.time() - start_time) * 1000)

    def _parse_host(self) -> tuple[Optional[str], Optional[int]]:
        """解析 Host 头，返回 (host, port)。"""
        host_header = self.headers.get('Host')
        if host_header is None:
            return None, None
        host: Optional[str] = host_header
        port: Optional[int] = None
        try:
            if host_header.startswith('['):
                if ']' in host_header:
                    host, _, port_str = host_header[1:].partition(']')
                    if port_str.startswith(':'):
                        port = int(port_str[1:])
                else:
                    host = None
            else:
                host, _, port_str = host_header.partition(':')
                if port_str:
                    port = int(port_str)
        except (ValueError, Exception) as e:
            logger.warning("Invalid host header %r: %s", host_header, e)
            host, port = None, None
        return host, port

    def _dispatch(
        self,
        path: list[str],
        args: dict[str, str],
        host: Optional[str],
        port: Optional[int],
    ) -> int:
        """将请求分发到匹配的服务，返回状态码。"""
        path_exists = False

        for service in self.services:
            if self.command != "OPTIONS" and type(service).__name__ == "CORSService":
                continue
            for route in service.routes:
                can_handle, path_ok = route.match(path, self.command, host, port)
                if path_ok:
                    path_exists = True
                if can_handle:
                    return self._handle_with_service(service, path, args)

        if path_exists:
            self.errsvc.handle(self, path, args, self.command, HTTPStatus.METHOD_NOT_ALLOWED)
            return 405
        # favicon 自动回退：无匹配路由时返回 cryskura.ico
        if self._try_favicon(path):
            return 200
        self.errsvc.handle(self, path, args, self.command, HTTPStatus.NOT_FOUND)
        return 404

    # ── Favicon 回退 ──────────────────────────────────────────

    def _try_favicon(self, path: list[str]) -> bool:
        """如果是 favicon 请求且无服务处理，返回默认图标。"""
        import os
        import mimetypes
        if not path or len(path) != 1:
            return False
        name_lower = path[0].lower()
        if not (name_lower == "favicon.ico" or name_lower == "favicon.png"
                or name_lower == "favicon" or name_lower == "apple-touch-icon.png"):
            return False
        icon_path = os.path.join(os.path.dirname(__file__), "Icons", "cryskura.ico")
        if not os.path.isfile(icon_path):
            return False
        try:
            with open(icon_path, "rb") as f:
                data = f.read()
            mime = mimetypes.guess_type(icon_path)[0] or "image/x-icon"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
            return True
        except Exception:
            return False

    def _handle_with_service(
        self,
        service: BaseService,
        path: list[str],
        args: dict[str, str],
    ) -> int:
        """用指定服务处理请求，返回状态码。"""
        try:
            before_result = service.before_handle(self, path, args, self.command)
            if before_result is not None:
                return before_result

            method_name = "handle_" + self.command
            if not hasattr(service, method_name):
                raise ValueError(
                    f"Service to handle {path} does not have a "
                    f"{self.command} handler, but a route for it exists."
                )
            getattr(service, method_name)(self, path, args)

            # 后置钩子
            service.after_handle(self, path, args, self.command)
            # CORS 和 gzip 由 end_headers() / _cleanup_gzip 处理
            self._try_setup_gzip()
            return 200

        except (ConnectionAbortedError, ConnectionResetError, _SSL_EOF) as e:  # type: ignore[misc]
            logger.warning(
                "Client disconnected while handling %s request for /%s: %s",
                self.command, '/'.join(path), e,
            )
            return 500
        except Exception as e:
            logger.error(
                "Error while handling %s request for /%s: %s",
                self.command, '/'.join(path), e,
            )
            self.errsvc.handle(self, path, args, self.command, HTTPStatus.INTERNAL_SERVER_ERROR)
            return 500

    def _cleanup_gzip(self) -> None:
        """刷新并关闭 gzip 包装器。"""
        if self._gzip_active:
            try:
                self.wfile.close()  # type: ignore[union-attr]
            except Exception:
                pass
            self._gzip_active = False

    # ── WebSocket 生命周期 ─────────────────────────────────────

    def finish(self) -> None:
        """处理 WebSocket 连接结束：跳过 flush 避免写已关闭的 socket。"""
        if getattr(self, "_ws_upgrade_complete", False):
            # WebSocket 连接由服务器 shutdown_request 负责关闭 socket
            return
        try:
            self.wfile.flush()
        except Exception:
            pass
