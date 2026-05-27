"""Tests for CORSManager module."""
from unittest.mock import MagicMock

import pytest

from cryskura.CORSManager import CORSConfig, CORSManager


class TestCORSConfigDefaults:
    def test_default_origin(self):
        cfg = CORSConfig()
        headers = cfg.get_headers("GET")
        assert headers["Access-Control-Allow-Origin"] == "*"

    def test_default_methods(self):
        cfg = CORSConfig()
        headers = cfg.get_headers("OPTIONS")
        assert headers["Access-Control-Allow-Methods"] == "*"

    def test_default_headers(self):
        cfg = CORSConfig()
        headers = cfg.get_headers("OPTIONS")
        assert headers["Access-Control-Allow-Headers"] == "*"

    def test_default_no_credentials(self):
        cfg = CORSConfig()
        headers = cfg.get_headers("GET")
        assert "Access-Control-Allow-Credentials" not in headers

    def test_default_max_age(self):
        cfg = CORSConfig()
        headers = cfg.get_headers("OPTIONS")
        assert headers["Access-Control-Max-Age"] == "86400"


class TestCORSConfigCustom:
    def test_custom_origin(self):
        cfg = CORSConfig(allow_origins=["https://example.com"])
        headers = cfg.get_headers("GET")
        assert headers["Access-Control-Allow-Origin"] == "https://example.com"

    def test_credentials_enabled(self):
        cfg = CORSConfig(allow_credentials=True)
        headers = cfg.get_headers("GET")
        assert headers["Access-Control-Allow-Credentials"] == "true"

    def test_expose_headers(self):
        cfg = CORSConfig(expose_headers=["X-Custom", "X-Request-ID"])
        headers = cfg.get_headers("GET")
        assert "X-Custom, X-Request-ID" in headers["Access-Control-Expose-Headers"]

    def test_options_includes_preflight(self):
        cfg = CORSConfig(allow_origins=["https://app.com"])
        headers = cfg.get_headers("OPTIONS")
        assert "Access-Control-Allow-Methods" in headers
        assert "Access-Control-Allow-Headers" in headers
        assert "Access-Control-Max-Age" in headers

    def test_zero_max_age_suppresses_header(self):
        cfg = CORSConfig(max_age=0)
        h = cfg.get_headers("OPTIONS")
        assert "Access-Control-Max-Age" not in h


class TestCORSManager:
    def _make_handler(self, method="GET", origin=None):
        handler = MagicMock()
        handler.command = method
        handler.headers = {"Origin": origin} if origin else {}
        return handler

    def test_add_cors_headers_get(self):
        mgr = CORSManager(CORSConfig(allow_origins=["*"]))
        handler = self._make_handler("GET")
        mgr.add_cors_headers(handler, "GET")
        calls = {
            call.args[0]: call.args[1]
            for call in handler.send_header.call_args_list
        }
        assert "Access-Control-Allow-Origin" in calls

    def test_add_cors_headers_options(self):
        mgr = CORSManager()
        handler = self._make_handler("OPTIONS")
        mgr.add_cors_headers(handler, "OPTIONS")
        calls = {
            call.args[0]: call.args[1]
            for call in handler.send_header.call_args_list
        }
        assert "Access-Control-Allow-Methods" in calls
        assert "Access-Control-Max-Age" in calls

    def test_default_config_used(self):
        mgr = CORSManager()
        cfg = mgr._get_config_for_service(None)
        assert cfg.allow_origins == ["*"]

    def test_custom_default_config(self):
        cfg = CORSConfig(allow_origins=["https://myapp.com"])
        mgr = CORSManager(cfg)
        dcfg = mgr._get_config_for_service(None)
        assert dcfg.allow_origins == ["https://myapp.com"]
