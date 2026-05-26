import os
try:
    import ssl
except ImportError:
    print("Warning: SSL module not found. HTTPS is not supported.")
    ssl = None
import socket
import threading
from http.server import ThreadingHTTPServer
from .uPnP import uPnPClient, _get_local_addresses
from .Handler import HTTPRequestHandler as Handler
from .Services import BaseService, FileService, ErrorService


class _BoundHTTPServer(ThreadingHTTPServer):
    """A ThreadingHTTPServer subclass that uses per-instance address_family
    to avoid class-variable races and supports dual-stack mode."""

    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass,
                 family=None, dual_stack=False, bind_and_activate=True):
        if family is not None:
            self.address_family = family
        self._family = family or self.address_family
        self._dual_stack = dual_stack
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)

    def server_bind(self):
        if self._family == socket.AF_INET6:
            try:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0 if self._dual_stack else 1)
            except OSError:
                pass
        super().server_bind()


class HTTPServer:
    def __init__(self, interface=None, port=8080, services=None,
                 error_service=None, server_name: str = "CryskuraHTTP/1.0",
                 forcePort: bool = False, certfile=None, uPnP=False,
                 dual_stack: bool = True):

        # --- Normalize bind addresses ---
        if interface is None:
            interface = "::1"
        if isinstance(interface, str):
            interfaces = [interface]
        else:
            interfaces = list(interface)
        if isinstance(port, int):
            ports = [port]
        else:
            ports = list(port)

        self.bind_addresses = []
        for iface in interfaces:
            for p in ports:
                self.bind_addresses.append((iface, p))

        self.dual_stack = dual_stack

        # --- Validate interfaces (lightweight, stdlib only) ---
        local_addrs = _get_local_addresses()
        local_addrs.update(['0.0.0.0', '::', '127.0.0.1', '::1'])
        for iface, _ in self.bind_addresses:
            if iface.startswith('127.'):
                continue
            if iface not in local_addrs:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    try:
                        s.bind((iface, 0))
                    finally:
                        s.close()
                except OSError:
                    available = sorted(
                        a for a in local_addrs
                        if not a.startswith('127.') and a != '::1' and not a == "::" and not a == "0.0.0.0"
                    )
                    nl = '\n - '
                    raise ValueError(
                        f"Interface {iface} not found.\n"
                        f"Available addresses: {nl}{nl.join(available) if available else 'none detected'}\n"
                        "Use '::1' for loopback, or '::' for all interfaces."
                    )

        # --- Validate port ranges and permissions ---
        for _, p in self.bind_addresses:
            if p < 0 or p > 65535:
                raise ValueError(f"Port {p} is out of range.")
            if os.name == "posix" and p < 1024 and os.geteuid() != 0:
                raise PermissionError(f"Port {p} requires root permission.")

        # Primary interface/port for backward compatibility
        self.interface = self.bind_addresses[0][0]
        self.port = self.bind_addresses[0][1]

        # --- uPnP ---
        if uPnP:
            self.uPnP = uPnPClient(self.interface)
            if not self.uPnP.available:
                print("Disabling uPnP port forwarding.")
                self.uPnP = None
        else:
            self.uPnP = None

        # --- Validate services ---
        if services is None:
            self.services = [FileService(
                os.fspath(os.getcwd()), "/", server_name=server_name)]
        else:
            self.services = []
            for service in services:
                if isinstance(service, BaseService):
                    self.services.append(service)
                else:
                    raise ValueError(
                        f"Service {service} is not a valid service.")

        # --- Validate error service ---
        if error_service is None:
            self.error_service = ErrorService(server_name)
        else:
            if isinstance(error_service, BaseService):
                self.error_service = error_service
            else:
                raise ValueError(
                    f"Service {error_service} is not a valid service.")

        # --- Validate certificate ---
        if certfile is not None:
            if not os.path.exists(certfile):
                raise ValueError(f"Certfile {certfile} does not exist.")
            self.certfile = certfile
        else:
            self.certfile = None

        self.server_name = server_name
        self.servers = []       # list of (server, thread)
        self._force_port = forcePort

    @staticmethod
    def _resolve_family(interface):
        try:
            info = socket.getaddrinfo(interface, None, type=socket.SOCK_STREAM,
                                       flags=socket.AI_PASSIVE)
            return info[0][0]
        except socket.gaierror:
            raise ValueError(f"Cannot resolve interface: {interface}")

    def start(self, threaded: bool = True):
        handler = lambda *args, **kwargs: Handler(
            *args, services=self.services, errsvc=self.error_service, **kwargs)

        for iface, port in self.bind_addresses:
            family = self._resolve_family(iface)

            try:
                server = _BoundHTTPServer(
                    (iface, port), handler,
                    family=family, dual_stack=self.dual_stack)
            except OSError as e:
                if e.errno == 98 or getattr(e, 'winerror', 0) == 10048:
                    msg = f"Port {port} on {iface} is already in use."
                    if self._force_port:
                        print(f"{msg} Forcing anyway (may fail).")
                        continue
                    raise ValueError(msg)
                raise ValueError(f"Failed to bind {iface}:{port}: {e}")

            if self.certfile is not None and ssl is not None:
                ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                try:
                    ssl_ctx.load_cert_chain(certfile=self.certfile)
                except Exception as e:
                    raise ValueError(
                        f"Error loading certificate: {e}\n"
                        "Please provide a valid certificate file.\n"
                        "Only PEM file with both certificate and private key is supported.")
                ssl_ctx.set_alpn_protocols(['http/1.1'])
                server.socket = ssl_ctx.wrap_socket(
                    server.socket, server_side=True)

            if family == socket.AF_INET6:
                print(f"Server started at [{iface}]:{port}")
            else:
                print(f"Server started at {iface}:{port}")

            thread = threading.Thread(target=server.serve_forever)
            thread.daemon = threaded
            thread.start()
            self.servers.append((server, thread))

        if not self.servers:
            raise RuntimeError("No servers could be started.")

        # --- uPnP port mappings (deduplicated by port) ---
        if self.uPnP is not None:
            seen_ports = set()
            for _, port in self.bind_addresses:
                if port not in seen_ports:
                    seen_ports.add(port)
                    res, mappings = self.uPnP.add_port_mapping(
                        port, port, "TCP", self.server_name)
                    if res:
                        for mapping in mappings:
                            print(f"Service is available at {mapping[0]}:{mapping[1]}")

        if not threaded:
            try:
                while any(t.is_alive() for _, t in self.servers):
                    for _, t in self.servers:
                        t.join(timeout=0.25)
            except KeyboardInterrupt:
                print(f"\nServer on port {self.port} stopped.")
                self.stop()

    def stop(self):
        if not self.servers:
            raise ValueError("Server is not running.")

        if self.uPnP is not None:
            self.uPnP.remove_port_mapping()

        for server, thread in self.servers:
            server.shutdown()
            thread.join()
            server.server_close()

        self.servers.clear()
