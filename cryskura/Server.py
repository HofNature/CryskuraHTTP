"""CryskuraHTTP 服务器主类。"""
from __future__ import annotations

import logging
import os
import socket
import threading
from http.server import ThreadingHTTPServer
from typing import Optional

try:
    import ssl
except ImportError:
    logging.warning("SSL module not found. HTTPS is not supported.")
    ssl = None  # type: ignore[assignment]

from .Handler import HTTPRequestHandler as Handler
from .Services.BaseService import BaseService
from .Services.ErrorService import ErrorService
from .Services.FileService import FileService
from .uPnP import uPnPClient

logger = logging.getLogger(__name__)


class _CryskuraHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer 子类，支持在实例级设置 address_family。

    避免直接修改 ThreadingHTTPServer.address_family 类变量，
    保证多实例并发创建时的线程安全（Python 3.14t free-threaded 模式）。
    """

    def __init__(
        self,
        server_address,
        handler_class,
        address_family=socket.AF_INET,
        ipv6_v6only: Optional[bool] = None,
    ):
        self.address_family = address_family
        self._ipv6_v6only: Optional[bool] = ipv6_v6only
        super().__init__(server_address, handler_class)

    def server_bind(self) -> None:
        """在 bind 之前设置 IPV6_V6ONLY，确保双栈在所有平台生效。"""
        if (
            self._ipv6_v6only is not None
            and self.address_family == socket.AF_INET6
        ):
            try:
                self.socket.setsockopt(
                    socket.IPPROTO_IPV6,
                    socket.IPV6_V6ONLY,
                    int(self._ipv6_v6only),
                )
            except (OSError, AttributeError) as e:
                logger.warning("Failed to set IPV6_V6ONLY: %s", e)
        super().server_bind()


class _PlainHTTPRedirectHandler:
    """检测 plain HTTP 请求到达 HTTPS 端口，自动回复 301 跳转。

    用 MSG_PEEK 预读首字节区分 TLS（0x16）与明文 HTTP，
    避免 SSL 握手消费缓冲区数据导致请求丢失。
    """

    def __init__(self, raw_sock: socket.socket, ssl_ctx: ssl.SSLContext) -> None:
        self._raw = raw_sock
        self._ssl_ctx = ssl_ctx

    def handle(self) -> socket.socket:
        """返回最终可用的 socket（SSLSocket 或已关闭的 raw socket）。"""
        try:
            first_byte = self._raw.recv(1, socket.MSG_PEEK)
        except Exception:
            self._raw.close()
            raise

        if not first_byte:
            self._raw.close()
            raise ConnectionError("Empty connection")

        if first_byte[0] == 0x16:
            # TLS ClientHello → 正常 SSL 握手
            return self._ssl_ctx.wrap_socket(self._raw, server_side=True)

        # 明文 HTTP → 返回 301 跳转并关闭
        self._handle_plain_http()
        raise ConnectionError("Plain HTTP on HTTPS port — redirected")

    def _handle_plain_http(self) -> None:
        """读取明文请求并回复 HTTPS 重定向。"""
        try:
            self._raw.settimeout(5)
            data = b""
            while b"\r\n\r\n" not in data and len(data) < 8192:
                chunk = self._raw.recv(4096)
                if not chunk:
                    return
                data += chunk

            first_line = data.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
            parts = first_line.split()
            path = parts[1] if len(parts) >= 2 else "/"

            host = ""
            for line in data.split(b"\r\n")[1:]:
                if line.lower().startswith(b"host:"):
                    host = line[5:].decode("ascii", errors="replace").strip()
                    break

            if host:
                location = f"https://{host}{path}"
            else:
                location = f"https://localhost{path}"

            resp = (
                f"HTTP/1.1 301 Moved Permanently\r\n"
                f"Location: {location}\r\n"
                f"Content-Length: 0\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )
            self._raw.sendall(resp.encode("ascii"))
            # 确保数据发送完毕再关闭
            try:
                self._raw.shutdown(socket.SHUT_WR)
            except Exception:
                pass
        except Exception:
            pass
        finally:
            try:
                self._raw.close()
            except Exception:
                pass


class HTTPServer:
    def __init__(
        self,
        interface: str = "127.0.0.1",
        port: int = 8080,
        services: Optional[list[BaseService]] = None,
        error_service: Optional[BaseService] = None,
        server_name: str = "CryskuraHTTP/1.0",
        forcePort: bool = False,
        certfile: Optional[str] = None,
        uPnP: bool = False,
        max_request_body: int = 0,
        access_log: bool = False,
        ipv6_v6only: Optional[bool] = None,
    ) -> None:
        # 验证接口地址是否可用
        self._validate_interface(interface)

        # 检查端口是否被占用
        try:
            port_in_use = self._is_port_in_use(interface, port)
        except Exception as e:
            logger.error("Error checking port availability: %s, skipping check", e)
            port_in_use = False

        if port_in_use:
            if forcePort:
                logger.warning("Port %d is already in use. Forcing to use port %d.", port, port)
            else:
                raise ValueError(f"Port {port} is already in use.")
        self.interface: str = interface

        # 检查uPnP是否可用
        self.uPnP: Optional[uPnPClient]
        if uPnP:
            self.uPnP = uPnPClient(interface)
            if not self.uPnP.available:
                logger.info("Disabling uPnP port forwarding.")
                self.uPnP = None
        else:
            self.uPnP = None

        # Linux下端口小于1024需要root权限
        if os.name == "posix" and port < 1024 and os.geteuid() != 0:
            raise PermissionError(f"Port {port} requires root permission.")
        if port < 0 or port > 65535:
            raise ValueError(f"Port {port} is out of range.")
        self.port: int = port

        # 检查服务是否合法
        if services is None:
            self.services: list[BaseService] = [FileService(
                os.fspath(os.getcwd()), "/", server_name=server_name)]
        else:
            self.services = []
            for service in services:
                if isinstance(service, BaseService):
                    self.services.append(service)
                else:
                    raise ValueError(f"Service {service} is not a valid service.")

        # 检查错误服务是否合法
        if error_service is None:
            self.error_service: BaseService = ErrorService(server_name)
        else:
            if isinstance(error_service, BaseService):
                self.error_service = error_service
            else:
                raise ValueError(f"Service {error_service} is not a valid service.")

        # 检查证书是否合法
        self.certfile: Optional[str]
        if certfile is not None:
            if not os.path.exists(certfile):
                raise ValueError(f"Certfile {certfile} does not exist.")
            self.certfile = certfile
        else:
            self.certfile = None

        self.server_name: str = server_name
        self.server: Optional[_CryskuraHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.max_request_body: int = max_request_body
        self.access_log: bool = access_log
        self.ipv6_v6only: Optional[bool] = ipv6_v6only

    @staticmethod
    def _validate_interface(interface: str) -> None:
        """通过 socket.bind 验证接口地址是否可用。"""
        if interface in ("0.0.0.0", "::", ""):
            return
        af = socket.AF_INET6 if ":" in interface else socket.AF_INET
        test_sock = socket.socket(af, socket.SOCK_STREAM)
        try:
            test_sock.bind((interface, 0))
        except OSError as e:
            test_sock.close()
            raise ValueError(
                f"Interface {interface} is not available: {e}"
            ) from e
        test_sock.close()

    @staticmethod
    def _is_port_in_use(interface: str, port: int) -> bool:
        """通过 socket.bind 探测端口是否已被占用。"""
        af = socket.AF_INET6 if ":" in interface else socket.AF_INET
        test_sock = socket.socket(af, socket.SOCK_STREAM)
        try:
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_sock.bind((interface, port))
            test_sock.close()
            return False
        except OSError:
            test_sock.close()
            return True

    def start(self, threaded: bool = True) -> None:
        ready_event = threading.Event()

        def handler(*args, **kwargs):
            return Handler(
                *args, services=self.services, errsvc=self.error_service,
                max_request_body=self.max_request_body,
                access_log=self.access_log, **kwargs,
            )
        af = socket.AF_INET6 if ":" in self.interface else socket.AF_INET
        self.server = _CryskuraHTTPServer(
            (self.interface, self.port), handler, address_family=af,
            ipv6_v6only=self.ipv6_v6only,
        )
        if self.certfile is not None and ssl is not None:
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            try:
                ssl_ctx.load_cert_chain(certfile=self.certfile)
            except Exception as e:
                raise ValueError(
                    f"Error loading certificate: {e}\nPlease provide a valid certificate file.\nOnly PEM file with both certificate and private key is supported.") from e

            _orig_get_request = self.server.get_request

            def _get_request_with_redirect():
                sock, addr = _orig_get_request()
                try:
                    first_byte = sock.recv(1, socket.MSG_PEEK)
                except Exception:
                    sock.close()
                    raise

                if not first_byte:
                    sock.close()
                    raise ConnectionError("Empty connection")

                if first_byte[0] == 0x16:
                    return ssl_ctx.wrap_socket(sock, server_side=True), addr

                handler = _PlainHTTPRedirectHandler(sock, ssl_ctx)
                handler._handle_plain_http()
                raise ConnectionError("Plain HTTP on HTTPS port — redirected")

            def _handle_request_noblock_safe():
                try:
                    request, client_address = self.server.get_request()
                except (OSError, ConnectionError):
                    return
                except Exception:
                    return
                if self.server.verify_request(request, client_address):
                    self.server.process_request(request, client_address)
                else:
                    self.server.shutdown_request(request)

            self.server.get_request = _get_request_with_redirect  # type: ignore[assignment]
            self.server._handle_request_noblock = _handle_request_noblock_safe  # type: ignore[attr-defined]
        if ":" in self.interface:
            logger.info("Server started at [%s]:%d", self.interface, self.port)
        else:
            logger.info("Server started at %s:%d", self.interface, self.port)
        if self.uPnP is not None:
            res, port_maps = self.uPnP.add_port_mapping(
                self.port, self.port, "TCP", self.server_name)
            if res:
                for mapping in port_maps:
                    logger.info("Service is available at %s:%d", mapping[0], mapping[1])
        if threaded:
            self.thread = threading.Thread(
                target=self._serve_with_ready, args=(ready_event,))
            self.thread.start()
            ready_event.wait(timeout=10)
        else:
            self.serve_forever()

    def _serve_with_ready(self, ready_event: threading.Event) -> None:
        """在 serve_forever 前通知就绪。"""
        ready_event.set()
        self.serve_forever()

    def serve_forever(self) -> None:
        try:
            if self.server is not None:
                self.server.serve_forever()
        except KeyboardInterrupt:
            if self.uPnP is not None:
                self.uPnP.remove_port_mapping()
            logger.info("Server on port %d stopped.", self.port)
            self.stop()
        except Exception:
            if self.uPnP is not None:
                self.uPnP.remove_port_mapping()
            raise

    def stop(self) -> None:
        """优雅停机：等待在途请求完成后关闭。"""
        if self.server is not None:
            if self.uPnP is not None:
                self.uPnP.remove_port_mapping()
            if self.thread is not None:
                self.server.shutdown()
                self.thread.join(timeout=10)
                self.server.server_close()
                self.server = None
                self.thread = None
            else:
                self.server.shutdown()
                self.server.server_close()
                self.server = None
            logger.info("Server on port %d stopped.", self.port)
        else:
            raise ValueError("Server is not running.")
