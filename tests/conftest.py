"""公共 fixtures 和测试工具。"""
from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
from http.client import HTTPResponse

import pytest

from cryskura import Server
from cryskura.Services.FileService import FileService


# ═══════════════════════════════════════════════════════════════
#  端口分配
# ═══════════════════════════════════════════════════════════════

_port_counter = 9000
_port_lock = threading.Lock()


def get_free_port() -> int:
    global _port_counter
    with _port_lock:
        _port_counter += 1
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", _port_counter))
            s.close()
            return _port_counter
        except OSError:
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            s.close()
            _port_counter = max(_port_counter, port)
            return port


# ═══════════════════════════════════════════════════════════════
#  HTTP 测试客户端
# ═══════════════════════════════════════════════════════════════

class HTTPTestClient:
    """轻量级 HTTP 测试客户端，支持 HTTP/1.0 和 HTTP/1.1。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080,
                 http_version: str = "HTTP/1.1"):
        self.host = host
        self.port = port
        self.http_version = http_version

    def request(self, method: str, path: str,
                headers: dict[str, str] | None = None,
                body: bytes | None = None) -> HTTPResponse:
        sock = socket.create_connection((self.host, self.port), timeout=5)
        try:
            request_line = f"{method} {path} {self.http_version}\r\n"
            data = request_line.encode("ascii")
            hdrs = headers or {}
            if "Host" not in hdrs:
                hdrs["Host"] = f"{self.host}:{self.port}"
            if body is not None and "Content-Length" not in hdrs:
                hdrs["Content-Length"] = str(len(body))
            for k, v in hdrs.items():
                data += f"{k}: {v}\r\n".encode("ascii")
            data += b"\r\n"
            if body:
                data += body
            sock.sendall(data)
            resp = HTTPResponse(sock, method=method)
            resp.begin()
            return resp
        except Exception:
            sock.close()
            raise


# ═══════════════════════════════════════════════════════════════
#  服务器启停辅助
# ═══════════════════════════════════════════════════════════════

def start_server(interface="127.0.0.1", port=None, **kwargs) -> tuple[Server, int]:
    if port is None:
        port = get_free_port()
    server = Server(interface=interface, port=port, forcePort=True, **kwargs)
    server.start(threaded=True)
    time.sleep(0.15)
    return server, port


def stop_server(server: Server) -> None:
    try:
        server.stop()
    except Exception:
        pass
    time.sleep(0.05)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="cryskura_test_")
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_files(tmp_dir):
    """创建一组标准测试文件。"""
    with open(os.path.join(tmp_dir, "hello.txt"), "w") as f:
        f.write("Hello, CryskuraHTTP!")
    with open(os.path.join(tmp_dir, "index.html"), "w") as f:
        f.write("<html><body>Index</body></html>")
    with open(os.path.join(tmp_dir, "data.json"), "w") as f:
        f.write('{"key": "value"}')
    with open(os.path.join(tmp_dir, "binary.bin"), "wb") as f:
        f.write(os.urandom(1024))
    with open(os.path.join(tmp_dir, "large.bin"), "wb") as f:
        f.write(os.urandom(100 * 1024))
    os.makedirs(os.path.join(tmp_dir, "subdir"))
    with open(os.path.join(tmp_dir, "subdir", "nested.txt"), "w") as f:
        f.write("Nested file content")
    with open(os.path.join(tmp_dir, "empty.txt"), "w") as f:
        pass
    os.makedirs(os.path.join(tmp_dir, "emptydir"))
    return tmp_dir
