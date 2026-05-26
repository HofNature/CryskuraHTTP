"""Integration tests for services via HTTP."""

import http.client
import json
import os
import tempfile
import threading
import time
from io import BytesIO
from contextlib import contextmanager

import pytest

from cryskura import Server
from cryskura.Services import (
    FileService, PageService, RedirectService, AuthService, AuthVerify,
    ErrorService,
)


def _free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _run_server(server, timeout=5.0):
    started = threading.Event()
    error = [None]

    def _run():
        try:
            started.set()
            server.start(threaded=False)
        except Exception as e:
            error[0] = e
            started.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    if not started.wait(timeout):
        server.stop()
        raise RuntimeError("Server did not start")
    if error[0] is not None:
        raise error[0]
    time.sleep(0.1)
    try:
        yield server
    finally:
        server.stop()
        t.join(timeout=2.0)


# ── FileService tests ──────────────────────────────────────────────────

class TestFileService:
    """Tests for FileService (GET, HEAD, directory listing)."""

    @pytest.fixture(autouse=True)
    def setup(self, file_server):
        self.base_url, self.server = file_server
        self.host = "127.0.0.1"
        _, port_str = self.base_url.rsplit(":", 1)
        self.port = int(port_str)

    def _get(self, path):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp, resp.read()

    def _head(self, path):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("HEAD", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    def test_get_file(self):
        resp, body = self._get("/hello.txt")
        assert resp.status == 200
        assert body == b"Hello, World!"

    def test_get_file_content_type(self):
        resp, _ = self._get("/hello.txt")
        assert "text/plain" in resp.getheader("Content-Type", "")

    def test_get_nonexistent_file(self):
        resp, _ = self._get("/nonexistent.txt")
        assert resp.status == 404

    def test_head_file(self):
        resp, body = self._head("/hello.txt")
        assert resp.status == 200
        assert body == b""

    def test_head_directory(self):
        resp, body = self._head("/subdir")
        assert resp.status == 200
        assert body == b""

    def test_directory_listing(self):
        resp, body = self._get("/")
        assert resp.status == 200
        html = body.decode()
        assert "hello.txt" in html
        assert "subdir" in html

    def test_subdirectory_listing(self):
        resp, body = self._get("/subdir")
        assert resp.status == 200
        html = body.decode()
        assert "data.txt" in html

    def test_path_traversal_blocked(self):
        # %2e%2e%2f is URL-encoded ../ which should be normalized away by the
        # handler-based path split. Any attempt that reaches a path outside
        # the root should yield 404 via calc_path's commonpath check.
        resp, _ = self._get("/subdir/../../../etc/passwd")
        assert resp.status == 404

    def test_file_info_endpoint(self):
        resp, body = self._get("/hello.txt?info")
        assert resp.status == 200
        info = json.loads(body)
        assert info["name"] == "hello.txt"
        assert info["size"] == len(b"Hello, World!")
        assert info["is_file"] is True

    def test_directory_info_endpoint(self):
        resp, body = self._get("/subdir?info")
        assert resp.status == 200
        info = json.loads(body)
        assert info["is_dir"] is True
        assert "item_count" in info

    def test_zip_download(self):
        resp, body = self._get("/hello.txt?zip")
        assert resp.status == 200
        assert resp.getheader("Content-Type") == "application/zip"
        # body should be a valid zip file with hello.txt inside
        import zipfile
        bio = BytesIO(body)
        with zipfile.ZipFile(bio) as zf:
            names = zf.namelist()
            assert "hello.txt" in names

    def test_zip_directory(self):
        resp, body = self._get("/subdir?zip")
        assert resp.status == 200
        assert resp.getheader("Content-Type") == "application/zip"
        import zipfile
        bio = BytesIO(body)
        with zipfile.ZipFile(bio) as zf:
            names = zf.namelist()
            assert any("data.txt" in n for n in names)


class TestRangeRequests:
    """Tests for Range (resumable download) support."""

    @pytest.fixture(autouse=True)
    def setup(self, resume_server):
        self.base_url, self.server = resume_server
        self.host = "127.0.0.1"
        _, port_str = self.base_url.rsplit(":", 1)
        self.port = int(port_str)

    def _get(self, path, headers=None):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        if headers is None:
            headers = {}
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        return resp, resp.read()

    def test_single_range(self):
        resp, body = self._get("/range.txt", headers={"Range": "bytes=0-9"})
        assert resp.status == 206
        assert body == b"0123456789"
        assert "bytes 0-9/1000" in resp.getheader("Content-Range", "")

    def test_range_suffix(self):
        resp, body = self._get("/range.txt", headers={"Range": "bytes=-10"})
        assert resp.status == 206
        assert len(body) == 10

    def test_range_open_end(self):
        resp, body = self._get("/range.txt", headers={"Range": "bytes=990-"})
        assert resp.status == 206
        assert len(body) == 10

    def test_multi_range(self):
        resp, body = self._get(
            "/range.txt",
            headers={"Range": "bytes=0-4,10-14"},
        )
        assert resp.status == 206
        ctype = resp.getheader("Content-Type", "")
        assert "multipart/byteranges" in ctype
        assert b"01234" in body

    def test_no_range_header_returns_full_file(self):
        resp, body = self._get("/range.txt")
        assert resp.status == 200
        assert len(body) == 1000


class TestFileUpload:
    """Tests for file upload (POST)."""

    @pytest.fixture(autouse=True)
    def setup(self, upload_server):
        self.base_url, self.server = upload_server
        self.host = "127.0.0.1"
        _, port_str = self.base_url.rsplit(":", 1)
        self.port = int(port_str)

    def test_upload_single_file(self):
        boundary = "----TestBoundary123"
        body = (
            f"------TestBoundary123\r\n"
            f'Content-Disposition: form-data; name="file"; filename="uploaded.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
            f"uploaded content\r\n"
            f"------TestBoundary123--\r\n"
        )
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request(
            "POST", "/",
            body=body.encode(),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status in (201, 207)

    def test_upload_without_content_type(self):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("POST", "/", body=b"raw data")
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 400

    def test_upload_to_disabled_server(self, temp_dir):
        """POST to a server without upload enabled should return 405."""
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[FileService(temp_dir, "/", allowUpload=False)],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/", body=b"data")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 405


# ── PageService tests ───────────────────────────────────────────────────

class TestPageService:
    """Tests for PageService (web mode, no directory listing)."""

    @pytest.fixture(autouse=True)
    def setup(self, page_server):
        self.base_url, self.server = page_server
        self.host = "127.0.0.1"
        _, port_str = self.base_url.rsplit(":", 1)
        self.port = int(port_str)

    def _get(self, path):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp, resp.read()

    def test_get_index_html(self):
        resp, body = self._get("/index.html")
        assert resp.status == 200
        assert b"Hello" in body

    def test_get_via_directory_with_index(self):
        """Access '/' should serve index.html."""
        resp, body = self._get("/")
        assert resp.status == 200
        assert b"Hello" in body

    def test_get_nonexistent(self):
        resp, _ = self._get("/nonexistent.html")
        assert resp.status == 404

    def test_no_directory_listing(self):
        """PageService should not produce directory listings."""
        # Create a subdir with no index - should 404
        resp, _ = self._get("/subdir")
        assert resp.status == 404


# ── RedirectService tests ───────────────────────────────────────────────

class TestRedirectService:
    """Tests for RedirectService."""

    def test_get_redirect(self, temp_dir):
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[RedirectService("/old", "/new")],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/old")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 301
            assert "/new" in resp.getheader("Location", "")

    def test_post_redirect(self, temp_dir):
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[RedirectService("/old", "/new")],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/old")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 308


# ── AuthService tests ───────────────────────────────────────────────────

class TestAuthService:
    """Tests for AuthService authentication."""

    def test_login_page(self, temp_dir):
        verify = AuthVerify({"admin": "admin123"})
        auth = AuthService("/login", verify, "/protected")
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[auth, FileService(temp_dir, "/protected")],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/login")
            resp = conn.getresponse()
            body = resp.read()
            assert resp.status == 200
            assert b"login" in body.lower() or b"Login" in body

    def test_login_success(self, temp_dir):
        verify = AuthVerify({"admin": "admin123"}, expire_time=3600)
        auth = AuthService("/login", verify, "/protected")
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[auth, FileService(temp_dir, "/protected")],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            body = json.dumps({"username": "admin", "password": "admin123"})
            conn.request(
                "POST", "/login",
                body=body,
                headers={"Content-Type": "application/json",
                         "Content-Length": str(len(body))},
            )
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert "Authentication successful" in data.get("message", "")
            # Should receive a Set-Cookie header
            set_cookie = resp.getheader("Set-Cookie", "")
            assert "Cryskura_AUTH_" in set_cookie

    def test_login_failure(self, temp_dir):
        verify = AuthVerify({"admin": "admin123"})
        auth = AuthService("/login", verify, "/protected")
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[auth, FileService(temp_dir, "/protected")],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            body = json.dumps({"username": "admin", "password": "wrong"})
            conn.request(
                "POST", "/login",
                body=body,
                headers={"Content-Type": "application/json",
                         "Content-Length": str(len(body))},
            )
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 401
            assert "Authentication failed" in data.get("message", "")

    def test_protected_redirect(self, temp_dir):
        """Access protected resource without auth should redirect to login."""
        verify = AuthVerify({"admin": "admin123"})
        auth = AuthService("/login", verify, "/protected")
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[auth, FileService(temp_dir, "/protected")],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/protected/hello.txt")
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 307
            location = resp.getheader("Location", "")
            assert "/login" in location


# ── ErrorService tests ──────────────────────────────────────────────────

class TestErrorService:
    """Tests for ErrorService error handling."""

    def test_custom_error_service_404(self, temp_dir):
        port = _free_port()
        errsvc = ErrorService("TestError/1.0")
        server = Server(
            interface="127.0.0.1", port=port,
            error_service=errsvc,
            services=[FileService(temp_dir, "/")],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/nonexistent")
            resp = conn.getresponse()
            body = resp.read()
            assert resp.status == 404
            assert b"TestError/1.0" in body or b"404" in body

    def test_error_service_head(self, temp_dir):
        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=[FileService(temp_dir, "/")],
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("HEAD", "/nonexistent")
            resp = conn.getresponse()
            body = resp.read()
            assert resp.status == 404
            assert body == b""
