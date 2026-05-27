"""Tests for TrustedProxy module."""
from unittest.mock import MagicMock

import pytest

from cryskura.TrustedProxy import TrustedProxy


class TestTrustedProxyInit:
    def test_empty_default(self):
        tp = TrustedProxy()
        assert tp.enabled is False

    def test_none_disables(self):
        tp = TrustedProxy(None)
        assert tp.enabled is False

    def test_empty_list_disables(self):
        tp = TrustedProxy([])
        assert tp.enabled is False

    def test_single_ip(self):
        tp = TrustedProxy(["127.0.0.1"])
        assert tp.enabled is True

    def test_cidr(self):
        tp = TrustedProxy(["10.0.0.0/8"])
        assert tp.enabled is True

    def test_multiple_entries(self):
        tp = TrustedProxy(["127.0.0.1", "10.0.0.0/8", "::1"])
        assert tp.enabled is True

    def test_invalid_cidr_raises(self):
        with pytest.raises(ValueError, match="Invalid trusted IP"):
            TrustedProxy(["not-an-ip"])

    def test_ipv6_entry(self):
        tp = TrustedProxy(["::1", "fe80::/10"])
        assert tp.enabled is True


class TestTrustedProxyIsTrusted:
    def test_localhost_trusted(self):
        tp = TrustedProxy(["127.0.0.1"])
        assert tp.is_trusted("127.0.0.1") is True

    def test_localhost_not_trusted(self):
        tp = TrustedProxy(["10.0.0.0/8"])
        assert tp.is_trusted("127.0.0.1") is False

    def test_cidr_range_trusted(self):
        tp = TrustedProxy(["10.0.0.0/8"])
        assert tp.is_trusted("10.1.2.3") is True
        assert tp.is_trusted("10.255.255.255") is True

    def test_cidr_edge_not_trusted(self):
        tp = TrustedProxy(["10.0.0.0/8"])
        assert tp.is_trusted("11.0.0.1") is False

    def test_disabled_never_trusted(self):
        tp = TrustedProxy()
        assert tp.is_trusted("127.0.0.1") is False
        assert tp.is_trusted("10.0.0.1") is False

    def test_ipv6_trusted(self):
        tp = TrustedProxy(["::1"])
        assert tp.is_trusted("::1") is True
        assert tp.is_trusted("::2") is False

    def test_invalid_ip_not_trusted(self):
        tp = TrustedProxy(["127.0.0.1"])
        assert tp.is_trusted("not-an-ip") is False


class TestTrustedProxyGetClientIP:
    def _make_handler(self, client_ip, headers=None):
        handler = MagicMock()
        handler.client_address = (client_ip, 12345)
        handler.headers = headers or {}
        return handler

    def test_untrusted_returns_client_ip(self):
        tp = TrustedProxy(["10.0.0.0/8"])
        handler = self._make_handler("192.168.1.1",
                                      {"X-Forwarded-For": "1.2.3.4"})
        assert tp.get_client_ip(handler) == "192.168.1.1"

    def test_trusted_returns_forwarded_ip(self):
        tp = TrustedProxy(["127.0.0.1"])
        handler = self._make_handler("127.0.0.1",
                                      {"X-Forwarded-For": "1.2.3.4"})
        assert tp.get_client_ip(handler) == "1.2.3.4"

    def test_trusted_uses_leftmost_forwarded_ip(self):
        tp = TrustedProxy(["127.0.0.1"])
        handler = self._make_handler(
            "127.0.0.1",
            {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
        )
        assert tp.get_client_ip(handler) == "1.2.3.4"

    def test_trusted_no_forwarded_header(self):
        tp = TrustedProxy(["127.0.0.1"])
        handler = self._make_handler("127.0.0.1", {})
        assert tp.get_client_ip(handler) == "127.0.0.1"

    def test_strips_ipv4_mapped_ipv6(self):
        tp = TrustedProxy(["::ffff:127.0.0.1"])
        handler = self._make_handler(
            "::ffff:127.0.0.1",
            {"X-Forwarded-For": "::ffff:1.2.3.4"},
        )
        assert tp.get_client_ip(handler) == "1.2.3.4"

    def test_disabled_returns_client_ip(self):
        tp = TrustedProxy()
        handler = self._make_handler("192.168.1.1",
                                      {"X-Forwarded-For": "1.2.3.4"})
        assert tp.get_client_ip(handler) == "192.168.1.1"


class TestTrustedProxyGetScheme:
    def _make_handler(self, client_ip, headers=None):
        handler = MagicMock()
        handler.client_address = (client_ip, 12345)
        handler.headers = headers or {}
        handler.connection = None
        return handler

    def test_trusted_returns_forwarded_proto(self):
        tp = TrustedProxy(["127.0.0.1"])
        handler = self._make_handler(
            "127.0.0.1", {"X-Forwarded-Proto": "https"}
        )
        assert tp.get_scheme(handler) == "https"

    def test_untrusted_ignores_forwarded_proto(self):
        tp = TrustedProxy(["10.0.0.0/8"])
        handler = self._make_handler(
            "192.168.1.1", {"X-Forwarded-Proto": "https"}
        )
        assert tp.get_scheme(handler) == "http"

    def test_trusted_no_header_returns_http(self):
        tp = TrustedProxy(["127.0.0.1"])
        handler = self._make_handler("127.0.0.1", {})
        assert tp.get_scheme(handler) == "http"

    def test_disabled_returns_http(self):
        tp = TrustedProxy()
        handler = self._make_handler(
            "192.168.1.1", {"X-Forwarded-Proto": "https"}
        )
        assert tp.get_scheme(handler) == "http"


class TestTrustedProxyGetHostPort:
    def _make_handler(self, client_ip, headers=None, host=None, port=None):
        handler = MagicMock()
        handler.client_address = (client_ip, 12345)
        handler.headers = headers or {}
        handler.host = host
        handler.port = port
        return handler

    def test_trusted_returns_forwarded_host_port(self):
        tp = TrustedProxy(["127.0.0.1"])
        handler = self._make_handler(
            "127.0.0.1",
            {"X-Forwarded-Host": "example.com:8443"},
            host="localhost", port=8080,
        )
        h, p = tp.get_host_port(handler)
        assert h == "example.com"
        assert p == 8443

    def test_trusted_ipv6_forwarded_host(self):
        tp = TrustedProxy(["127.0.0.1"])
        handler = self._make_handler(
            "127.0.0.1",
            {"X-Forwarded-Host": "[::1]:9000"},
            host="localhost", port=8080,
        )
        h, p = tp.get_host_port(handler)
        assert h == "::1"
        assert p == 9000

    def test_untrusted_falls_back_to_handler(self):
        tp = TrustedProxy(["10.0.0.0/8"])
        handler = self._make_handler(
            "192.168.1.1",
            {"X-Forwarded-Host": "evil.com"},
            host="good.com", port=8080,
        )
        h, p = tp.get_host_port(handler)
        assert h == "good.com"
        assert p == 8080

    def test_trusted_no_header_falls_back(self):
        tp = TrustedProxy(["127.0.0.1"])
        handler = self._make_handler(
            "127.0.0.1", {},
            host="direct.com", port=8080,
        )
        h, p = tp.get_host_port(handler)
        assert h == "direct.com"
        assert p == 8080

    def test_disabled_falls_back(self):
        tp = TrustedProxy()
        handler = self._make_handler(
            "192.168.1.1",
            {"X-Forwarded-Host": "evil.com"},
            host="good.com", port=8080,
        )
        h, p = tp.get_host_port(handler)
        assert h == "good.com"
        assert p == 8080
