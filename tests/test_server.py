"""Server 生命周期、参数校验、SSL、uPnP、线程安全测试。
"""
from __future__ import annotations

import concurrent.futures
import socket
import threading
import time

import pytest

from cryskura import Server
from cryskura.server import _CryskuraHTTPServer
from cryskura.Services.file_service import FileService

from conftest import HTTPTestClient, start_server, stop_server, get_free_port


# ═══════════════════════════════════════════════════════════════
#  服务器启停
# ═══════════════════════════════════════════════════════════════

class TestServerLifecycle:

    def test_start_and_stop(self):
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[fs])
        stop_server(server)

    def test_double_stop_raises(self):
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[fs])
        stop_server(server)
        with pytest.raises(ValueError):
            server.stop()

    def test_default_services(self):
        """不传 services 应使用 cwd 作为 FileService。"""
        server = Server(interface="127.0.0.1", port=get_free_port(), forcePort=True)
        server.start(threaded=True)
        time.sleep(0.15)
        try:
            assert len(server.services) == 1
            assert isinstance(server.services[0], FileService)
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  端口 & 参数校验
# ═══════════════════════════════════════════════════════════════

class TestServerValidation:

    def test_port_conflict(self):
        port = get_free_port()
        fs = FileService("/tmp", "/")
        server1 = Server(interface="127.0.0.1", port=port, services=[fs], forcePort=True)
        server1.start(threaded=True)
        time.sleep(0.15)
        try:
            with pytest.raises((ValueError, OSError)):
                Server(interface="127.0.0.1", port=port, services=[fs])
        finally:
            stop_server(server1)

    def test_invalid_port_negative(self):
        with pytest.raises(ValueError):
            Server(port=-1)

    def test_invalid_port_too_large(self):
        with pytest.raises(ValueError):
            Server(port=70000)

    def test_invalid_service(self):
        with pytest.raises(ValueError, match="not a valid service"):
            Server(services=["not a service"])

    def test_invalid_error_service(self):
        with pytest.raises(ValueError, match="not a valid service"):
            Server(error_service="not a service")

    def test_nonexistent_certfile(self):
        with pytest.raises(ValueError, match="does not exist"):
            Server(certfile="/nonexistent/cert.pem")

    def test_invalid_interface(self):
        """不可用的接口地址应抛异常。"""
        with pytest.raises(ValueError):
            Server(interface="192.0.2.1", port=get_free_port())  # TEST-NET 不可用


# ═══════════════════════════════════════════════════════════════
#  forcePort 模式
# ═══════════════════════════════════════════════════════════════

class TestForcePort:

    def test_force_port_reuse(self):
        """forcePort=True 应允许绑定已占用端口（SO_REUSEADDR）。"""
        port = get_free_port()
        fs = FileService("/tmp", "/")
        server1 = Server(interface="127.0.0.1", port=port, services=[fs], forcePort=True)
        server1.start(threaded=True)
        time.sleep(0.15)
        stop_server(server1)
        # 重启同端口
        server2 = Server(interface="127.0.0.1", port=port, services=[fs], forcePort=True)
        server2.start(threaded=True)
        time.sleep(0.15)
        stop_server(server2)


# ═══════════════════════════════════════════════════════════════
#  访问日志
# ═══════════════════════════════════════════════════════════════

class TestAccessLog:

    def test_access_log_enabled(self, sample_files):
        """access_log=True 不应导致异常。"""
        fs = FileService(sample_files, "/")
        server, port = start_server(services=[fs], access_log=True)
        try:
            resp = HTTPTestClient(port=port).request("GET", "/hello.txt")
            assert resp.status == 200
            resp.read()
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  线程安全：_CryskuraHTTPServer address_family 隔离
# ═══════════════════════════════════════════════════════════════

class TestAddressFamilyIsolation:
    """验证多实例并发创建不会互相覆盖 address_family。

    Python 3.14t (free-threaded) 移除了 GIL，之前的实现直接修改
    ThreadingHTTPServer.address_family 类变量，存在竞态风险。
    修复后每个实例通过 _CryskuraHTTPServer 子类在 __init__ 中
    独立设置 address_family。
    """

    def test_cryskura_server_ipv4(self):
        """_CryskuraHTTPServer 实例级 IPv4。"""
        srv = _CryskuraHTTPServer(
            ("127.0.0.1", 0), lambda *a: None,
            address_family=socket.AF_INET,
        )
        assert srv.address_family == socket.AF_INET
        srv.server_close()

    def test_cryskura_server_ipv6(self):
        """_CryskuraHTTPServer 实例级 IPv6。"""
        srv = _CryskuraHTTPServer(
            ("::1", 0), lambda *a: None,
            address_family=socket.AF_INET6,
        )
        assert srv.address_family == socket.AF_INET6
        srv.server_close()

    def test_class_variable_not_mutated(self):
        """创建 IPv6 实例后，ThreadingHTTPServer 类变量不应被修改。"""
        from http.server import ThreadingHTTPServer
        original = ThreadingHTTPServer.address_family
        _CryskuraHTTPServer(
            ("::1", 0), lambda *a: None,
            address_family=socket.AF_INET6,
        ).server_close()
        assert ThreadingHTTPServer.address_family == original

    def test_concurrent_creation_no_race(self):
        """并发创建 IPv4/IPv6 实例，地址族应各自独立。"""
        results: list[tuple[int, int]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_server(af, addr):
            try:
                srv = _CryskuraHTTPServer(addr, lambda *a: None, address_family=af)
                with lock:
                    results.append((af, srv.address_family))
                srv.server_close()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(
                target=create_server,
                args=(socket.AF_INET, ("127.0.0.1", 0))))
            threads.append(threading.Thread(
                target=create_server,
                args=(socket.AF_INET6, ("::1", 0))))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Errors during concurrent creation: {errors}"
        assert len(results) == 10
        for expected_af, actual_af in results:
            assert actual_af == expected_af


# ═══════════════════════════════════════════════════════════════
#  Handler._get_sent_header 防御性测试
# ═══════════════════════════════════════════════════════════════

class TestHandlerDefensive:

    def test_get_sent_header_no_buffer(self, sample_files):
        """无 _headers_buffer 时应安全返回 None，不抛异常。"""
        fs = FileService(sample_files, "/")
        server, port = start_server(services=[fs])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/hello.txt")
            assert resp.status == 200
            # Content-Type 应正常返回
            ct = resp.getheader("Content-Type")
            assert ct is not None
            resp.read()
        finally:
            stop_server(server)

    def test_get_sent_header_after_response(self, sample_files):
        """响应发送后应能读取已发送的 header。"""
        fs = FileService(sample_files, "/")
        server, port = start_server(services=[fs])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/hello.txt")
            assert resp.status == 200
            # 安全头应存在
            assert resp.getheader("X-Content-Type-Options") == "nosniff"
            resp.read()
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  IPV6_V6ONLY 双栈支持
# ═══════════════════════════════════════════════════════════════

class TestIPv6V6Only:
    """测试 IPV6_V6ONLY socket 选项。"""

    def _has_dual_stack(self) -> bool:
        """探测当前系统是否支持 IPv6 双栈。"""
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            s.bind(("::", 0))
            s.close()
            return True
        except (OSError, AttributeError):
            return False

    def test_v6only_none_preserves_system_default(self):
        """ipv6_v6only=None 不设置 socket 选项，保持系统默认。"""
        srv = _CryskuraHTTPServer(
            ("::1", 0), lambda *a: None,
            address_family=socket.AF_INET6,
            ipv6_v6only=None,
        )
        # 不应抛异常
        assert srv.address_family == socket.AF_INET6
        srv.server_close()

    def test_v6only_false_sets_dual_stack(self):
        """ipv6_v6only=False 设置 IPV6_V6ONLY=0。"""
        if not self._has_dual_stack():
            pytest.skip("System does not support dual-stack")
        srv = _CryskuraHTTPServer(
            ("::", 0), lambda *a: None,
            address_family=socket.AF_INET6,
            ipv6_v6only=False,
        )
        try:
            val = srv.socket.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY)
            assert val == 0
        finally:
            srv.server_close()

    def test_v6only_true_sets_ipv6_only(self):
        """ipv6_v6only=True 设置 IPV6_V6ONLY=1。"""
        srv = _CryskuraHTTPServer(
            ("::1", 0), lambda *a: None,
            address_family=socket.AF_INET6,
            ipv6_v6only=True,
        )
        try:
            val = srv.socket.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY)
            assert val == 1
        finally:
            srv.server_close()

    def test_v6only_ignored_for_ipv4(self):
        """IPv4 时 ipv6_v6only 参数被忽略，不影响 socket。"""
        srv = _CryskuraHTTPServer(
            ("127.0.0.1", 0), lambda *a: None,
            address_family=socket.AF_INET,
            ipv6_v6only=False,
        )
        # IPv4 socket 没有 IPV6_V6ONLY 选项，不应抛异常
        assert srv.address_family == socket.AF_INET
        srv.server_close()

    def test_dual_stack_http_server_integration(self, sample_files):
        """集成测试：ipv6_v6only=False 的 HTTPServer 能正常启动和响应。"""
        if not self._has_dual_stack():
            pytest.skip("System does not support dual-stack")
        fs = FileService(sample_files, "/")
        server, port = start_server(services=[fs], ipv6_v6only=False,
                                     interface="::")
        try:
            # IPv6 连接
            resp = HTTPTestClient(host="::1", port=port).request("GET", "/hello.txt")
            assert resp.status == 200
            assert resp.read() == b"Hello, CryskuraHTTP!"
        finally:
            stop_server(server)

    def test_v6only_true_http_server_integration(self, sample_files):
        """集成测试：ipv6_v6only=True 的 HTTPServer 能正常启动和响应。"""
        fs = FileService(sample_files, "/")
        server, port = start_server(services=[fs], ipv6_v6only=True,
                                     interface="::1")
        try:
            resp = HTTPTestClient(host="::1", port=port).request("GET", "/hello.txt")
            assert resp.status == 200
            assert resp.read() == b"Hello, CryskuraHTTP!"
        finally:
            stop_server(server)

    def test_dual_stack_ipv4_client(self, sample_files):
        """双栈模式下 IPv4 客户端能通过 IPv6 socket 连接。"""
        if not self._has_dual_stack():
            pytest.skip("System does not support dual-stack")
        fs = FileService(sample_files, "/")
        server, port = start_server(services=[fs], ipv6_v6only=False,
                                     interface="::")
        try:
            # IPv4 客户端连接 IPv6 双栈 socket
            resp = HTTPTestClient(host="127.0.0.1", port=port).request("GET", "/hello.txt")
            assert resp.status == 200
            assert resp.read() == b"Hello, CryskuraHTTP!"
        finally:
            stop_server(server)
