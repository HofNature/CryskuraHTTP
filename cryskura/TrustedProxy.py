"""TrustedProxy: reverse proxy IP support via X-Forwarded-* headers."""
from __future__ import annotations

import ipaddress
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .Handler import HTTPRequestHandler


class TrustedProxy:
    """Resolve client connection info from X-Forwarded-* headers when
    the connecting IP is within a trusted range (e.g., nginx on localhost).
    """

    def __init__(self, trusted_ips: Optional[List[str]] = None) -> None:
        self._networks: List[ipaddress.IPv4Network] = []
        if trusted_ips:
            for entry in trusted_ips:
                entry = entry.strip()
                if not entry:
                    continue
                try:
                    net = ipaddress.ip_network(entry, strict=False)
                except ValueError:
                    raise ValueError(
                        f"Invalid trusted IP/CIDR: {entry!r}"
                    )
                self._networks.append(net)

    @property
    def enabled(self) -> bool:
        return bool(self._networks)

    def is_trusted(self, client_ip: str) -> bool:
        if not self._networks:
            return False
        try:
            addr = ipaddress.ip_address(client_ip)
        except ValueError:
            return False
        for net in self._networks:
            if addr in net:
                return True
        return False

    @staticmethod
    def _normalize_ip(ip: str) -> str:
        """Strip IPv4-mapped IPv6 prefix."""
        if ip.startswith("::ffff:"):
            return ip[7:]
        return ip

    def get_client_ip(self, handler: HTTPRequestHandler) -> str:
        raw = handler.client_address[0]
        if self.is_trusted(raw):
            forwarded = handler.headers.get("X-Forwarded-For", "")
            if forwarded:
                leftmost = forwarded.split(",")[0].strip()
                if leftmost:
                    return self._normalize_ip(leftmost)
        return self._normalize_ip(raw)

    def get_scheme(self, handler: HTTPRequestHandler) -> str:
        raw = handler.client_address[0]
        if self.is_trusted(raw):
            proto = handler.headers.get("X-Forwarded-Proto", "")
            if proto:
                return proto
        try:
            import ssl
            if isinstance(handler.connection, ssl.SSLSocket):
                return "https"
        except (ImportError, AttributeError):
            pass
        return "http"

    def get_host_port(
        self, handler: HTTPRequestHandler
    ) -> Tuple[Optional[str], Optional[int]]:
        raw = handler.client_address[0]
        if self.is_trusted(raw):
            fwd_host = handler.headers.get("X-Forwarded-Host", "")
            if fwd_host:
                host = None  # type: Optional[str]
                port = None  # type: Optional[int]
                if fwd_host.startswith("["):
                    if "]" in fwd_host:
                        host, _, rest = fwd_host[1:].partition("]")
                        if rest.startswith(":"):
                            try:
                                port = int(rest[1:])
                            except ValueError:
                                port = None
                    else:
                        host = None
                else:
                    host, _, port_str = fwd_host.partition(":")
                    if port_str:
                        try:
                            port = int(port_str)
                        except ValueError:
                            port = None
                if host is not None or port is not None:
                    return host, port

        return getattr(handler, "host", None), getattr(handler, "port", None)
