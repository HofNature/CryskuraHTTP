"""CryskuraHTTP 服务器主类。

CryskuraHTTP main server class.
"""
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

from .handler import HTTPRequestHandler as Handler
from .Services.base_service import BaseService
from .Services.error_service import ErrorService
from .Services.file_service import FileService
from .upnp import UPnPClient

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
    """CryskuraHTTP 高层服务器：封装 ThreadingHTTPServer，管理生命周期。

    CryskuraHTTP high-level server: wraps ThreadingHTTPServer and manages lifecycle.
    """

    def __init__(
        self,
        interface: str = "127.0.0.1",
        port: int = 8080,
        services: Optional[list[BaseService]] = None,
        error_service: Optional[BaseService] = None,
        server_name: str = "CryskuraHTTP/1.0",
        force_port: bool = False,
        certfile: Optional[str] = None,
        upnp: bool = False,
        max_request_body: int = 0,
        access_log: bool = False,
        ipv6_v6only: Optional[bool] = None,
        # 向后兼容参数 / Backward-compatible aliases.
        forcePort: bool = False,
        uPnP: bool = False,
    ) -> None:
        """初始化 HTTP 服务器。

        Initialise the HTTP server.

        Args:
            interface: 监听地址（默认 "127.0.0.1"）。
                       Bind address (default "127.0.0.1").
            port: 监听端口（默认 8080）。
                  Listen port (default 8080).
            services: 服务列表。 / List of services.
            error_service: 错误处理服务。 / Error handler service.
            server_name: 服务器名称。 / Server name string.
            force_port: 强制使用端口（忽略占用）。
                        Force use of the port even if already in use.
            certfile: PEM 证书文件路径（启用 HTTPS）。
                      Path to PEM certificate (enables HTTPS).
            upnp: 是否启用 UPnP 端口映射。 / Enable UPnP port forwarding.
            max_request_body: 请求体大小限制（0 表示不限）。
                              Max request body size in bytes (0 = unlimited).
            access_log: 是否记录访问日志。 / Enable access logging.
            ipv6_v6only: 设置 IPV6_V6ONLY socket 选项。
                         Set the IPV6_V6ONLY socket option.
            forcePort: 已弃用，请使用 force_port。 / Deprecated; use force_port.
            uPnP: 已弃用，请使用 upnp。 / Deprecated; use upnp.
        """
        # 处理向后兼容参数 / Handle backward-compatible aliases.
        force_port = force_port or forcePort
        upnp = upnp or uPnP

        # 验证接口地址是否可用 / Validate that the interface address is usable.
        self._validate_interface(interface)

        # 检查端口是否被占用 / Check if the port is already in use.
        try:
            port_in_use = self._is_port_in_use(interface, port)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error checking port availability: %s, skipping check", e)
            port_in_use = False

        if port_in_use:
            if force_port:
                logger.warning(
                    "Port %d is already in use. Forcing to use port %d.", port, port
                )
            else:
                raise ValueError(f"Port {port} is already in use.")
        self.interface: str = interface

        # 检查 UPnP 是否可用 / Check if UPnP is available.
        self.upnp: Optional[UPnPClient]
        if upnp:
            self.upnp = UPnPClient(interface)
            if not self.upnp.available:
                logger.info("Disabling uPnP port forwarding.")
                self.upnp = None
        else:
            self.upnp = None

        # Linux 下端口小于 1024 需要 root 权限。
        # On Linux, ports below 1024 require root privileges.
        if os.name == "posix" and port < 1024 and os.geteuid() != 0:
            raise PermissionError(f"Port {port} requires root permission.")
        if port < 0 or port > 65535:
            raise ValueError(f"Port {port} is out of range.")
        self.port: int = port

        # 检查服务是否合法 / Validate and assign services.
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

        # 检查错误服务是否合法 / Validate and assign the error service.
        if error_service is None:
            self.error_service: BaseService = ErrorService(server_name)
        else:
            if isinstance(error_service, BaseService):
                self.error_service = error_service
            else:
                raise ValueError(
                    f"Service {error_service} is not a valid service."
                )

        # 检查证书是否合法 / Validate the certificate file.
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
        """通过 socket.bind 验证接口地址是否可用。

        Validate that the interface address is usable via socket.bind.
        """
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
        """通过 socket.bind 探测端口是否已被占用。

        Probe whether a port is already in use via socket.bind.
        """
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
        """启动服务器。

        Start the server.

        Args:
            threaded: True 表示在后台线程中运行，False 表示阻塞直到停止。
                      True to run in a background thread; False to block until stopped.
        """
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
                    f"Error loading certificate: {e}\n"
                    "Please provide a valid certificate file.\n"
                    "Only PEM file with both certificate and private key is supported."
                ) from e

            _orig_get_request = self.server.get_request

            def _get_request_with_redirect():
                sock, addr = _orig_get_request()
                try:
                    first_byte = sock.recv(1, socket.MSG_PEEK)
                except Exception:  # pylint: disable=broad-exception-caught
                    sock.close()
                    raise

                if not first_byte:
                    sock.close()
                    raise ConnectionError("Empty connection")

                if first_byte[0] == 0x16:
                    return ssl_ctx.wrap_socket(sock, server_side=True), addr

                plain_handler = _PlainHTTPRedirectHandler(sock, ssl_ctx)
                plain_handler._handle_plain_http()
                raise ConnectionError("Plain HTTP on HTTPS port — redirected")

            def _handle_request_noblock_safe():
                try:
                    request, client_address = self.server.get_request()
                except (OSError, ConnectionError):
                    return
                except Exception:  # pylint: disable=broad-exception-caught
                    return
                if self.server.verify_request(request, client_address):
                    self.server.process_request(request, client_address)
                else:
                    self.server.shutdown_request(request)

            self.server.get_request = _get_request_with_redirect  # type: ignore[assignment]
            self.server._handle_request_noblock = (  # type: ignore[attr-defined]
                _handle_request_noblock_safe
            )
        if ":" in self.interface:
            logger.info("Server started at [%s]:%d", self.interface, self.port)
        else:
            logger.info("Server started at %s:%d", self.interface, self.port)
        if self.upnp is not None:
            res, port_maps = self.upnp.add_port_mapping(
                self.port, self.port, "TCP", self.server_name)
            if res:
                for mapping in port_maps:
                    logger.info(
                        "Service is available at %s:%d", mapping[0], mapping[1]
                    )
        if threaded:
            self.thread = threading.Thread(
                target=self._serve_with_ready, args=(ready_event,))
            self.thread.start()
            ready_event.wait(timeout=10)
        else:
            self.serve_forever()

    def _serve_with_ready(self, ready_event: threading.Event) -> None:
        """在 serve_forever 前通知就绪。

        Signal readiness before entering serve_forever.
        """
        ready_event.set()
        self.serve_forever()

    def serve_forever(self) -> None:
        """阻塞地运行服务器，直到 KeyboardInterrupt 或异常。

        Run the server in a blocking loop until KeyboardInterrupt or exception.
        """
        try:
            if self.server is not None:
                self.server.serve_forever()
        except KeyboardInterrupt:
            if self.upnp is not None:
                self.upnp.remove_port_mapping()
            logger.info("Server on port %d stopped.", self.port)
            self.stop()
        except Exception:
            if self.upnp is not None:
                self.upnp.remove_port_mapping()
            raise

    def stop(self) -> None:
        """优雅停机：等待在途请求完成后关闭。

        Graceful shutdown: wait for in-flight requests before closing.
        """
        if self.server is not None:
            if self.upnp is not None:
                self.upnp.remove_port_mapping()
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
