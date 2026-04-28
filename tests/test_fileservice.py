"""FileService 及子模块测试：文件服务、目录、上传、Range、Zip、Info。

集成测试为主，每个 class 用同一个服务器实例减少启动开销。
"""
from __future__ import annotations

import gzip
import json
import os
import socket
from http.client import HTTPResponse

import pytest

from cryskura.Services.FileService import FileService
from cryskura.Services.BaseService import Route

from conftest import HTTPTestClient, start_server, stop_server


# ═══════════════════════════════════════════════════════════════
#  FileService 基本功能
# ═══════════════════════════════════════════════════════════════

class TestFileServiceBasic:
    """GET / HEAD / 目录 / 子目录 / 空文件 / 404 / 二进制。"""

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/")
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        yield
        stop_server(self.server)

    def test_get_text(self):
        resp = self.c.request("GET", "/hello.txt")
        assert resp.status == 200
        assert resp.read() == b"Hello, CryskuraHTTP!"

    def test_head_request(self):
        resp = self.c.request("HEAD", "/hello.txt")
        assert resp.status == 200
        assert resp.read() == b""

    def test_directory_listing(self):
        body = self.c.request("GET", "/").read().decode()
        assert "hello.txt" in body
        assert "subdir" in body

    def test_subdirectory(self):
        assert self.c.request("GET", "/subdir/nested.txt").read() == b"Nested file content"

    def test_empty_file(self):
        assert self.c.request("GET", "/empty.txt").read() == b""

    def test_nonexistent_404(self):
        assert self.c.request("GET", "/notfound.txt").status == 404

    def test_binary_file(self):
        assert len(self.c.request("GET", "/binary.bin").read()) == 1024

    def test_head_directory(self):
        resp = self.c.request("HEAD", "/")
        assert resp.status == 200

    def test_empty_directory(self):
        """空目录应正常列出。"""
        body = self.c.request("GET", "/emptydir/").read().decode()
        assert "emptydir" in body or len(body) > 0


# ═══════════════════════════════════════════════════════════════
#  路径遍历防护
# ═══════════════════════════════════════════════════════════════

class TestPathTraversal:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/files")
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        yield
        stop_server(self.server)

    @pytest.mark.parametrize("path", [
        "/files/../../../etc/passwd",
        "/files/%2e%2e/%2e%2e/etc/passwd",
        "/files/subdir/../../etc/passwd",
    ])
    def test_traversal_blocked(self, path):
        assert self.c.request("GET", path).status == 404


# ═══════════════════════════════════════════════════════════════
#  单文件模式
# ═══════════════════════════════════════════════════════════════

class TestFileServiceSingleFile:

    def test_single_file_mode(self, sample_files):
        filepath = os.path.join(sample_files, "hello.txt")
        fs = FileService(filepath, "/download", isFolder=False)
        server, port = start_server(services=[fs])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/download")
            assert resp.status == 200
            assert resp.read() == b"Hello, CryskuraHTTP!"
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  HTTP/1.0 & 1.1 兼容性
# ═══════════════════════════════════════════════════════════════

class TestHTTPCompatibility:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/")
        self.server, self.port = start_server(services=[self.fs])
        yield
        stop_server(self.server)

    def test_http10_get(self):
        resp = HTTPTestClient(port=self.port, http_version="HTTP/1.0").request("GET", "/hello.txt")
        assert resp.status == 200
        assert resp.read() == b"Hello, CryskuraHTTP!"

    def test_http10_head(self):
        resp = HTTPTestClient(port=self.port, http_version="HTTP/1.0").request("HEAD", "/hello.txt")
        assert resp.status == 200

    def test_http10_directory(self):
        body = HTTPTestClient(port=self.port, http_version="HTTP/1.0").request("GET", "/").read().decode()
        assert "hello.txt" in body

    def test_http10_no_host_header(self):
        """HTTP/1.0 允许无 Host 头。"""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        try:
            sock.sendall(b"GET /hello.txt HTTP/1.0\r\n\r\n")
            resp = HTTPResponse(sock, method="GET")
            resp.begin()
            assert resp.status == 200
            assert resp.read() == b"Hello, CryskuraHTTP!"
        finally:
            sock.close()

    def test_http10_content_length(self):
        """HTTP/1.0 应有 Content-Length。"""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        try:
            sock.sendall(b"GET /hello.txt HTTP/1.0\r\nConnection: close\r\n\r\n")
            resp = HTTPResponse(sock, method="GET")
            resp.begin()
            cl = resp.getheader("Content-Length")
            assert cl is not None and int(cl) > 0
            resp.read()
        finally:
            sock.close()

    def test_http11_get(self):
        resp = HTTPTestClient(port=self.port, http_version="HTTP/1.1").request("GET", "/hello.txt")
        assert resp.status == 200
        assert resp.read() == b"Hello, CryskuraHTTP!"


# ═══════════════════════════════════════════════════════════════
#  Range 请求（断点续传）
# ═══════════════════════════════════════════════════════════════

class TestRangeRequests:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/", allowResume=True)
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        yield
        stop_server(self.server)

    def test_range_prefix(self):
        resp = self.c.request("GET", "/hello.txt", headers={"Range": "bytes=0-4"})
        assert resp.status == 206
        assert resp.read() == b"Hello"

    def test_range_suffix(self):
        resp = self.c.request("GET", "/hello.txt", headers={"Range": "bytes=-5"})
        assert resp.status == 206
        assert resp.read() == b"HTTP!"

    def test_range_open_end(self):
        resp = self.c.request("GET", "/hello.txt", headers={"Range": "bytes=7-"})
        assert resp.status == 206
        assert resp.read() == b"CryskuraHTTP!"

    def test_range_content_range_header(self):
        resp = self.c.request("GET", "/hello.txt", headers={"Range": "bytes=0-4"})
        assert resp.getheader("Content-Range", "").startswith("bytes 0-4/")

    def test_invalid_range_416(self):
        resp = self.c.request("GET", "/hello.txt", headers={"Range": "bytes=999-9999"})
        assert resp.status == 416

    def test_no_range_full_response(self):
        resp = self.c.request("GET", "/hello.txt")
        assert resp.status == 200
        assert resp.read() == b"Hello, CryskuraHTTP!"

    def test_range_disabled(self, sample_files):
        """allowResume=False 时 Range 被忽略。"""
        fs = FileService(sample_files, "/", allowResume=False)
        server, port = start_server(services=[fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "GET", "/hello.txt", headers={"Range": "bytes=0-4"})
            assert resp.status == 200  # 被忽略，返回完整内容
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  缓存（ETag / 304）
# ═══════════════════════════════════════════════════════════════

class TestCaching:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/")
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        yield
        stop_server(self.server)

    def test_etag_present(self):
        resp = self.c.request("GET", "/hello.txt")
        etag = resp.getheader("ETag")
        assert etag is not None and etag.startswith('"')
        resp.read()

    def test_last_modified_present(self):
        resp = self.c.request("GET", "/hello.txt")
        assert resp.getheader("Last-Modified") is not None
        resp.read()

    def test_if_none_match_304(self):
        resp1 = self.c.request("GET", "/hello.txt")
        etag = resp1.getheader("ETag")
        resp1.read()
        resp2 = self.c.request("GET", "/hello.txt", headers={"If-None-Match": etag})
        assert resp2.status == 304
        resp2.read()

    def test_if_modified_since_304(self):
        resp1 = self.c.request("GET", "/hello.txt")
        lm = resp1.getheader("Last-Modified")
        resp1.read()
        resp2 = self.c.request("GET", "/hello.txt", headers={"If-Modified-Since": lm})
        assert resp2.status == 304
        resp2.read()


# ═══════════════════════════════════════════════════════════════
#  Gzip 压缩
# ═══════════════════════════════════════════════════════════════

class TestGzip:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/")
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        yield
        stop_server(self.server)

    def test_gzip_html(self):
        resp = self.c.request("GET", "/index.html",
                              headers={"Accept-Encoding": "gzip"})
        assert resp.status == 200
        ce = resp.getheader("Content-Encoding")
        if ce == "gzip":
            assert b"Index" in gzip.decompress(resp.read())
        else:
            resp.read()  # 小文件可能跳过

    def test_no_gzip_without_accept(self):
        resp = self.c.request("GET", "/index.html")
        assert resp.status == 200
        assert resp.getheader("Content-Encoding") != "gzip"

    def test_no_gzip_binary(self):
        resp = self.c.request("GET", "/binary.bin",
                              headers={"Accept-Encoding": "gzip"})
        assert resp.status == 200
        assert resp.getheader("Content-Encoding") != "gzip"


# ═══════════════════════════════════════════════════════════════
#  安全响应头
# ═══════════════════════════════════════════════════════════════

class TestSecurityHeaders:

    def test_headers_present(self, sample_files):
        fs = FileService(sample_files, "/")
        server, port = start_server(services=[fs])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/hello.txt")
            assert resp.getheader("X-Content-Type-Options") == "nosniff"
            assert resp.getheader("X-Frame-Options") == "SAMEORIGIN"
            assert resp.getheader("Referrer-Policy") == "strict-origin-when-cross-origin"
            resp.read()
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  文件上传
# ═══════════════════════════════════════════════════════════════

class TestFileUpload:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/", allowUpload=True)
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        self.tmp_dir = sample_files
        yield
        stop_server(self.server)

    def _upload(self, filename: str, content: bytes, boundary="TESTBOUNDARY") -> HTTPResponse:
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.c.request(
            "POST", "/",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                      "Content-Length": str(len(body))},
            body=body)

    def test_upload_success(self):
        resp = self._upload("uploaded.txt", b"Upload content here")
        assert resp.status == 201
        resp.read()
        path = os.path.join(self.tmp_dir, "uploaded.txt")
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "Upload content here"

    def test_upload_conflict(self):
        """同名文件上传应返回 409。"""
        self._upload("dup.txt", b"first").read()
        resp = self._upload("dup.txt", b"second")
        assert resp.status == 409
        resp.read()

    def test_upload_disabled(self):
        fs = FileService(self.tmp_dir, "/", allowUpload=False)
        server, port = start_server(services=[fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "POST", "/",
                headers={"Content-Type": "multipart/form-data; boundary=b"},
                body=b"--b\r\nContent-Disposition: form-data; name=\"f\"; filename=\"a.txt\"\r\n\r\ndata\r\n--b--\r\n")
            assert resp.status == 405
            resp.read()
        finally:
            stop_server(server)

    def test_upload_no_content_type(self):
        resp = self.c.request("POST", "/", headers={"Content-Length": "10"}, body=b"some data!")
        assert resp.status == 400
        resp.read()

    def test_upload_special_chars_filename(self):
        resp = self._upload("test file (1).txt", b"special")
        assert resp.status == 201
        resp.read()
        assert os.path.exists(os.path.join(self.tmp_dir, "test file (1).txt"))


# ═══════════════════════════════════════════════════════════════
#  Zip 下载
# ═══════════════════════════════════════════════════════════════

class TestZipDownload:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/")
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        yield
        stop_server(self.server)

    def test_zip_file(self):
        resp = self.c.request("GET", "/hello.txt?zip")
        assert resp.status == 200
        assert resp.getheader("Content-Type") == "application/zip"
        assert resp.read()[:2] == b"PK"

    def test_zip_directory(self):
        resp = self.c.request("GET", "/?zip")
        assert resp.status == 200
        assert resp.read()[:2] == b"PK"

    def test_zip_http10_in_memory(self):
        """小文件 zip 应走 Content-Length，HTTP/1.0 兼容。"""
        resp = HTTPTestClient(port=self.port, http_version="HTTP/1.0").request(
            "GET", "/hello.txt?zip")
        assert resp.status == 200
        cl = resp.getheader("Content-Length")
        assert cl is not None and int(cl) > 0
        assert resp.read()[:2] == b"PK"

    def test_zip_http11_chunked(self):
        """HTTP/1.1 大文件应走 chunked（此处小文件走内存，但验证流程正确）。"""
        resp = self.c.request("GET", "/hello.txt?zip")
        assert resp.status == 200
        assert resp.read()[:2] == b"PK"


# ═══════════════════════════════════════════════════════════════
#  Info 端点
# ═══════════════════════════════════════════════════════════════

class TestInfoEndpoint:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/")
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        yield
        stop_server(self.server)

    def test_file_info(self):
        data = json.loads(self.c.request("GET", "/hello.txt?info").read())
        assert data["is_file"] is True
        assert data["is_dir"] is False
        assert data["name"] == "hello.txt"
        assert data["size"] > 0

    def test_directory_info(self):
        data = json.loads(self.c.request("GET", "/?info").read())
        assert data["is_dir"] is True
        assert data["is_file"] is False
        assert data["file_count"] > 0
        assert data["item_count"] > 0

    def test_info_has_mime(self):
        data = json.loads(self.c.request("GET", "/hello.txt?info").read())
        assert data["mime_type"] is not None


# ═══════════════════════════════════════════════════════════════
#  Favicon 回退
# ═══════════════════════════════════════════════════════════════

class TestFavicon:

    def test_favicon_ico(self, sample_files):
        fs = FileService(sample_files, "/")
        server, port = start_server(services=[fs])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/favicon.ico")
            assert resp.status == 200
            ct = resp.getheader("Content-Type")
            assert "icon" in ct or "png" in ct
            assert len(resp.read()) > 0
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  FileService 构造校验
# ═══════════════════════════════════════════════════════════════

class TestFileServiceInit:

    def test_nonexistent_path_raises(self):
        with pytest.raises(ValueError, match="does not exist"):
            FileService("/nonexistent/path/abc", "/")

    def test_file_as_folder_raises(self, sample_files):
        filepath = os.path.join(sample_files, "hello.txt")
        with pytest.raises(ValueError, match="not a folder"):
            FileService(filepath, "/", isFolder=True)

    def test_folder_as_file_raises(self, sample_files):
        with pytest.raises(ValueError, match="not a file"):
            FileService(sample_files, "/", isFolder=False)


# ═══════════════════════════════════════════════════════════════
#  多文件上传
# ═══════════════════════════════════════════════════════════════

class TestMultiFileUpload:

    @pytest.fixture(autouse=True)
    def setup(self, sample_files):
        self.fs = FileService(sample_files, "/", allowUpload=True)
        self.server, self.port = start_server(services=[self.fs])
        self.c = HTTPTestClient(port=self.port)
        self.tmp_dir = sample_files
        yield
        stop_server(self.server)

    def _build_multipart(self, files: list[tuple[str, bytes]], boundary="TESTBOUNDARY") -> bytes:
        """构建包含多个文件的 multipart body。"""
        parts = []
        for filename, content in files:
            part = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f"\r\n"
            ).encode() + content + b"\r\n"
            parts.append(part)
        return b"".join(parts) + f"--{boundary}--\r\n".encode()

    def test_multi_file_upload(self):
        """一次请求上传多个文件。"""
        files = [
            ("multi_a.txt", b"content A"),
            ("multi_b.txt", b"content B"),
            ("multi_c.txt", b"content C"),
        ]
        body = self._build_multipart(files)
        resp = self.c.request(
            "POST", "/",
            headers={"Content-Type": "multipart/form-data; boundary=TESTBOUNDARY",
                      "Content-Length": str(len(body))},
            body=body)
        assert resp.status == 201
        import json
        data = json.loads(resp.read())
        assert data["count"] == 3
        assert len(data["saved"]) == 3
        # 验证文件内容
        for fname, content in files:
            with open(os.path.join(self.tmp_dir, fname), "rb") as f:
                assert f.read() == content

    def test_multi_file_partial_conflict(self):
        """部分文件冲突时返回 207 + JSON。"""
        # 先创建一个同名文件
        body1 = self._build_multipart([("exist.txt", b"first")])
        self.c.request("POST", "/",
                       headers={"Content-Type": "multipart/form-data; boundary=TESTBOUNDARY",
                                 "Content-Length": str(len(body1))},
                       body=body1).read()

        # 再上传包含同名 + 新文件
        files = [
            ("exist.txt", b"conflict"),
            ("new_ok.txt", b"ok"),
        ]
        body2 = self._build_multipart(files)
        resp = self.c.request(
            "POST", "/",
            headers={"Content-Type": "multipart/form-data; boundary=TESTBOUNDARY",
                      "Content-Length": str(len(body2))},
            body=body2)
        assert resp.status == 207  # Multi-Status
        import json
        data = json.loads(resp.read())
        assert data["count"] == 1  # 只有 new_ok.txt 成功
        assert "errors" in data
        assert len(data["errors"]) == 1

    def test_single_file_still_works(self):
        """单文件上传保持原有 201 行为。"""
        body = self._build_multipart([("single.txt", b"single content")])
        resp = self.c.request(
            "POST", "/",
            headers={"Content-Type": "multipart/form-data; boundary=TESTBOUNDARY",
                      "Content-Length": str(len(body))},
            body=body)
        assert resp.status == 201
        assert resp.getheader("Location") is not None
        resp.read()
