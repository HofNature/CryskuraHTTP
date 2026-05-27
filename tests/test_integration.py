"""Integration tests for proxy, CORS, and logging features."""
import os
import tempfile
import http.client

import pytest

from cryskura import Server
from cryskura.Services import FileService
from cryskura.CORSManager import CORSConfig


def _free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestCORSIntegration:
    """Integration tests for CORS headers in HTTP responses."""

    def test_cors_headers_on_get(self, temp_dir):
        port = _free_port()
        cors_cfg = CORSConfig(allow_origins=["https://example.com"])
        server = Server(
            interface="127.0.0.1", port=port,
            services=[FileService(temp_dir, "/")],
            cors=cors_cfg,
        )
        from tests.conftest import _run_server
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/hello.txt",
                         headers={"Origin": "https://example.com"})
            resp = conn.getresponse()
            resp.read()
            assert resp.getheader("Access-Control-Allow-Origin") == "https://example.com"
            assert resp.status == 200

    def test_cors_preflight_options(self, temp_dir):
        port = _free_port()
        cors_cfg = CORSConfig(allow_origins=["*"])
        server = Server(
            interface="127.0.0.1", port=port,
            services=[FileService(temp_dir, "/")],
            cors=cors_cfg,
        )
        from tests.conftest import _run_server
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("OPTIONS", "/hello.txt",
                         headers={"Origin": "http://app.com"})
            resp = conn.getresponse()
            resp.read()
            assert resp.getheader("Access-Control-Allow-Origin") is not None
            assert resp.getheader("Access-Control-Allow-Methods") is not None

    def test_no_cors_headers_when_not_configured(self, temp_dir):
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[FileService(temp_dir, "/")],
        )
        from tests.conftest import _run_server
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/hello.txt")
            resp = conn.getresponse()
            resp.read()
            assert resp.getheader("Access-Control-Allow-Origin") is None

    def test_no_duplicate_when_service_sets_own_cors(self, temp_dir):
        """Custom services that set CORS headers manually should not get duplicates."""
        from cryskura.Services import BaseService, Route
        from http import HTTPStatus

        class MyCorsService(BaseService):
            def __init__(self):
                self.routes = [Route("/custom", ["GET"], "exact")]
                super().__init__(self.routes)

            def handle_GET(self, request, path, args):
                request.send_response(200)
                request.send_header("Access-Control-Allow-Origin", "https://custom.com")
                request.send_header("Content-Type", "text/plain")
                request.send_header("Content-Length", "2")
                request.end_headers()
                request.wfile.write(b"OK")

        port = _free_port()
        cors_cfg = CORSConfig(allow_origins=["https://global.com"])
        server = Server(
            interface="127.0.0.1", port=port,
            services=[MyCorsService()],
            cors=cors_cfg,
        )
        from tests.conftest import _run_server
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/custom")
            resp = conn.getresponse()
            resp.read()
            # Should only have the custom origin, not the global one
            origins = resp.getheader("Access-Control-Allow-Origin")
            assert origins == "https://custom.com", f"Expected single origin, got: {origins!r}"


class TestLoggingIntegration:
    """Integration tests for file logging."""

    def test_access_log_written(self, temp_dir):
        with tempfile.TemporaryDirectory() as log_td:
            port = _free_port()
            log_dir = os.path.join(log_td, "logs")
            server = Server(
                interface="127.0.0.1", port=port,
                services=[FileService(temp_dir, "/")],
                log_dir=log_dir,
            )
            from tests.conftest import _run_server
            with _run_server(server):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", "/hello.txt")
                resp = conn.getresponse()
                resp.read()
                assert resp.status == 200
                conn.close()

            access_log = os.path.join(log_dir, "latest", "access.log")
            assert os.path.isfile(access_log)
            with open(access_log, "r") as f:
                content = f.read()
            assert "GET /hello.txt" in content

    def test_server_log_written(self, temp_dir):
        with tempfile.TemporaryDirectory() as log_td:
            port = _free_port()
            log_dir = os.path.join(log_td, "logs")
            server = Server(
                interface="127.0.0.1", port=port,
                services=[FileService(temp_dir, "/")],
                log_dir=log_dir,
            )
            from tests.conftest import _run_server
            with _run_server(server):
                pass

            server_log = os.path.join(log_dir, "latest", "server.log")
            assert os.path.isfile(server_log)
            with open(server_log, "r") as f:
                content = f.read()
            assert "Server started" in content
