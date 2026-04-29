"""反向代理服务：将请求转发到后端服务器，支持 HTTP 和 WebSocket。"""
from __future__ import annotations

import logging
import select
import socket
import ssl as _ssl
from http import HTTPStatus
from http.client import HTTPConnection, HTTPSConnection
from typing import Optional, TYPE_CHECKING
from urllib.parse import urlparse, urlencode

from .base_service import BaseService, Route

if TYPE_CHECKING:
    from ..handler import HTTPRequestHandler as Handler
    from .._types import AuthFunc

logger = logging.getLogger(__name__)

# 跳过这些逐跳头（RFC 7230 §6.1）
_HOP_BY_HOP: set[str] = {
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailer",
    "transfer-encoding", "upgrade",
}


class ReverseProxyService(BaseService):
    """反向代理：将匹配的请求转发到指定后端。

    支持 HTTP 和 WebSocket（自动检测 Upgrade 请求）。

    用法：
        # 代理 /api 下所有请求到后端
        proxy = ReverseProxyService("/api", "http://localhost:3000")

        # 代理 WebSocket
        proxy = ReverseProxyService("/ws", "http://localhost:3000")

        # 路径重写
        proxy = ReverseProxyService("/v1", "http://localhost:8000/v2")

        server = HTTPServer(services=[proxy])
    """

    def __init__(
        self,
        remote_path: str,
        backend: str,
        methods: Optional[list[str]] = None,
        auth_func: Optional[AuthFunc] = None,
        timeout: float = 30.0,
        host: Optional[str] = None,
        port: Optional[int] = None,
        preserve_host: bool = False,
        max_request_body: int = 10 * 1024 * 1024,  # 10MB
    ) -> None:
        if methods is None:
            methods = ["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        self.routes = [
            Route(remote_path, methods, "prefix", host, port),
        ]
        self.timeout = timeout
        self.preserve_host = preserve_host
        self.max_request_body = max_request_body

        parsed = urlparse(backend)
        self._backend_scheme: str = parsed.scheme or "http"
        self._backend_host: str = parsed.hostname or "localhost"
        self._backend_port: int = parsed.port or (443 if self._backend_scheme == "https" else 80)
        self._backend_path: str = parsed.path.rstrip("/")
        self._use_ssl: bool = self._backend_scheme == "https"

        super().__init__(self.routes, auth_func)
        self.remote_path: list[str] = self.routes[0].path

    # ── 路径构建 ─────────────────────────────────────────────

    def _backend_url(self, path: list[str], args: dict[str, str]) -> str:
        sub_path_parts = path[len(self.remote_path):]
        sub_path = "/" + "/".join(sub_path_parts) if sub_path_parts else "/"
        if args:
            return f"{self._backend_path}{sub_path}?{urlencode(args, doseq=True)}"
        return f"{self._backend_path}{sub_path}"

    def _build_headers(self, request: Handler) -> dict[str, str]:
        fwd: dict[str, str] = {}
        for key in request.headers:
            key_lower = key.lower()
            if key_lower in _HOP_BY_HOP:
                continue
            if key_lower == "host" and not self.preserve_host:
                continue
            fwd[key] = request.headers[key]
        if not self.preserve_host:
            if self._backend_port in (80, 443):
                fwd["Host"] = self._backend_host
            else:
                fwd["Host"] = f"{self._backend_host}:{self._backend_port}"
        client_ip = request.client_address[0] if request.client_address else "unknown"
        fwd["X-Forwarded-For"] = client_ip
        fwd["X-Forwarded-Host"] = request.headers.get("Host", "")
        fwd["X-Forwarded-Proto"] = "http"
        return fwd

    # ── WebSocket 代理 ───────────────────────────────────────

    def _proxy_websocket(
        self,
        request: Handler,
        path: list[str],
        args: dict[str, str],
    ) -> None:
        """WebSocket 反向代理：建立到后端的 WS 连接，双向中继帧。"""
        backend_url = self._backend_url(path, args)
        # 构造后端 HTTP Upgrade 请求
        fwd_headers = self._build_headers(request)
        # 确保 Upgrade / Connection 头在原始请求中
        ws_key = request.headers.get("Sec-WebSocket-Key", "")
        ws_version = request.headers.get("Sec-WebSocket-Version", "13")
        ws_protocols = request.headers.get("Sec-WebSocket-Protocol", "")
        ws_extensions = request.headers.get("Sec-WebSocket-Extensions", "")

        # 连接后端（用 raw socket 因为需要升级到 WebSocket）
        backend_sock = None
        try:
            backend_sock = socket.create_connection(
                (self._backend_host, self._backend_port),
                timeout=self.timeout,
            )
            if self._use_ssl:
                ctx = _ssl.create_default_context()
                backend_sock = ctx.wrap_socket(
                    backend_sock, server_hostname=self._backend_host,
                )

            # 发送 Upgrade 请求
            req_lines = [f"GET {backend_url} HTTP/1.1"]
            # 重建 Host
            if self._backend_port in (80, 443):
                req_lines.append(f"Host: {self._backend_host}")
            else:
                req_lines.append(f"Host: {self._backend_host}:{self._backend_port}")
            req_lines.append("Upgrade: websocket")
            req_lines.append("Connection: Upgrade")
            if ws_key:
                req_lines.append(f"Sec-WebSocket-Key: {ws_key}")
            req_lines.append(f"Sec-WebSocket-Version: {ws_version}")
            if ws_protocols:
                req_lines.append(f"Sec-WebSocket-Protocol: {ws_protocols}")
            if ws_extensions:
                req_lines.append(f"Sec-WebSocket-Extensions: {ws_extensions}")
            # 转发其他非 hop-by-hop 头
            for k, v in fwd_headers.items():
                kl = k.lower()
                if kl not in ("host", "upgrade", "connection",
                              "sec-websocket-key", "sec-websocket-version",
                              "sec-websocket-protocol", "sec-websocket-extensions"):
                    req_lines.append(f"{k}: {v}")
            req_lines.append("")
            req_lines.append("")
            backend_sock.sendall("\r\n".join(req_lines).encode("utf-8"))

            # 读取后端响应头
            resp_data = b""
            while b"\r\n\r\n" not in resp_data:
                chunk = backend_sock.recv(4096)
                if not chunk:
                    raise ConnectionError("Backend closed during WS handshake")
                resp_data += chunk

            header_end = resp_data.index(b"\r\n\r\n") + 4
            resp_head = resp_data[:header_end]
            leftover = resp_data[header_end:]  # 可能包含后端发来的 WS 帧

            resp_line = resp_head.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
            if "101" not in resp_line:
                # 后端拒绝了升级 — 返回错误页面
                status_code = 502
                try:
                    status_code = int(resp_line.split()[1])
                except (IndexError, ValueError):
                    pass
                request.errsvc.handle(request, path, args, "GET", status_code)
                return

            # 通知客户端升级成功
            request.send_response(101, "Switching Protocols")
            request.send_header("Upgrade", "websocket")
            request.send_header("Connection", "Upgrade")
            # 转发后端的响应头（Sec-WebSocket-Accept 等）
            for line in resp_head.decode("ascii", errors="replace").split("\r\n")[1:]:
                if ":" in line:
                    k, _, v = line.partition(":")
                    k = k.strip()
                    kl = k.lower()
                    if kl not in _HOP_BY_HOP and kl not in ("upgrade", "connection"):
                        request.send_header(k, v.strip())
            request.end_headers()
            request.wfile.flush()

            # 标记 WebSocket 升级完成
            request._ws_upgrade_complete = True  # type: ignore[attr-defined]
            request.close_connection = True

            # 双向帧中继
            client_sock = request.connection  # type: ignore[attr-defined]
            self._relay_frames(client_sock, backend_sock, leftover)

        except ConnectionRefusedError:
            request.errsvc.handle(request, path, args, "GET", HTTPStatus.BAD_GATEWAY)
        except TimeoutError:
            request.errsvc.handle(request, path, args, "GET", HTTPStatus.GATEWAY_TIMEOUT)
        except Exception as e:
            logger.error("WS proxy error for %s: %s", backend_url, e)
            request.errsvc.handle(request, path, args, "GET", HTTPStatus.BAD_GATEWAY)
        finally:
            if backend_sock is not None:
                try:
                    backend_sock.close()
                except Exception:
                    pass

    @staticmethod
    def _relay_frames(
        client_sock: socket.socket,
        backend_sock: socket.socket,
        initial_data: bytes = b"",
    ) -> None:
        """双向中继 WebSocket 帧（零拷贝，直接转发原始字节）。"""
        # 设置为非阻塞以支持 select
        client_sock.setblocking(False)
        backend_sock.setblocking(False)
        pending_backend = initial_data

        try:
            while True:
                readable = [client_sock, backend_sock]
                try:
                    rlist, _, _ = select.select(readable, [], [], 30.0)
                except (ValueError, OSError):
                    break

                if not rlist:
                    # 超时，连接空闲，继续等待
                    continue

                for src, dst in [(client_sock, backend_sock), (backend_sock, client_sock)]:
                    if src not in rlist:
                        continue
                    try:
                        if src is backend_sock and pending_backend:
                            data = pending_backend
                            pending_backend = b""
                        else:
                            data = src.recv(65536)
                        if not data:
                            return  # 连接关闭
                        dst.sendall(data)
                    except BlockingIOError:
                        continue
                    except (ConnectionError, OSError):
                        return
        finally:
            client_sock.setblocking(True)
            backend_sock.setblocking(True)

    # ── HTTP 连接 ────────────────────────────────────────────

    def _build_conn(self):
        """创建到后端的 HTTP 连接。"""
        if self._use_ssl:
            ctx = _ssl.create_default_context()
            return HTTPSConnection(
                self._backend_host, self._backend_port,
                timeout=self.timeout, context=ctx,
            )
        return HTTPConnection(
            self._backend_host, self._backend_port,
            timeout=self.timeout,
        )

    # ── HTTP 代理 ────────────────────────────────────────────

    def _forward(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        """转发 HTTP 请求到后端并回写响应。"""
        # WebSocket 升级请求走专用通道
        upgrade = request.headers.get("Upgrade", "").lower()
        if upgrade == "websocket":
            self._proxy_websocket(request, path, args)
            return

        backend_url = self._backend_url(path, args)
        fwd_headers = self._build_headers(request)

        body: bytes = b""
        cl = request.headers.get("Content-Length")
        if cl:
            try:
                body = request.rfile.read(min(int(cl), self.max_request_body))
            except (ValueError, OSError):
                pass

        conn = None
        try:
            conn = self._build_conn()
            conn.request(request.command, backend_url, body=body or None, headers=fwd_headers)
            resp = conn.getresponse()
            resp_body = resp.read()

            request.send_response(resp.status)
            for key, value in resp.getheaders():
                key_lower = key.lower()
                if key_lower in _HOP_BY_HOP:
                    continue
                if key_lower == "content-length":
                    request.send_header(key, str(len(resp_body)))
                    continue
                request.send_header(key, value)
            request.end_headers()
            request.wfile.write(resp_body)

        except ConnectionRefusedError:
            request.errsvc.handle(request, path, args, request.command, HTTPStatus.BAD_GATEWAY)
        except TimeoutError:
            request.errsvc.handle(request, path, args, request.command, HTTPStatus.GATEWAY_TIMEOUT)
        except Exception as e:
            logger.error("Reverse proxy error for %s %s: %s", request.command, backend_url, e)
            request.errsvc.handle(request, path, args, request.command, HTTPStatus.BAD_GATEWAY)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    # ── 请求分发 ─────────────────────────────────────────────

    def _handle(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        if not self.auth_verify(request, path, args, request.command):
            return
        self._forward(request, path, args)

    def handle_GET(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args)

    def handle_HEAD(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args)

    def handle_POST(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args)

    def handle_PUT(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args)

    def handle_DELETE(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args)

    def handle_PATCH(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args)

    def handle_OPTIONS(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        self._handle(request, path, args)
