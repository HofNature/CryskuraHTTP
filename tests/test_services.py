"""CORS、ErrorService、PageService、APIService、APIRouter、SimpleAPIRouter、
HealthService、RedirectService、ReverseProxy 测试。
"""
from __future__ import annotations

import json
import os
import socket
import time
from http.client import HTTPResponse

import pytest

from cryskura import Server
from cryskura.Services import (
    BaseService, Route, ErrorService, FileService,
    PageService, RedirectService, APIService, APIRouter,
    SimpleAPIRouter, CORSService, HealthService,
)

from conftest import HTTPTestClient, start_server, stop_server, get_free_port


# ═══════════════════════════════════════════════════════════════
#  CORS
# ═══════════════════════════════════════════════════════════════

class TestCORS:

    def test_preflight_allowed(self):
        cors = CORSService(
            allow_origins=["https://example.com"],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"])
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[cors, fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "OPTIONS", "/",
                headers={"Origin": "https://example.com",
                          "Access-Control-Request-Method": "GET"})
            assert resp.status == 204
            assert resp.getheader("Access-Control-Allow-Origin") == "https://example.com"
            resp.read()
        finally:
            stop_server(server)

    def test_wrong_origin_403(self):
        cors = CORSService(allow_origins=["https://example.com"])
        server, port = start_server(services=[cors])
        try:
            resp = HTTPTestClient(port=port).request(
                "OPTIONS", "/", headers={"Origin": "https://evil.com"})
            assert resp.status == 403
            resp.read()
        finally:
            stop_server(server)

    def test_wildcard_origin(self):
        cors = CORSService(allow_origins=["*"])
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[cors, fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "OPTIONS", "/", headers={"Origin": "https://any.com"})
            assert resp.status == 204
            assert resp.getheader("Access-Control-Allow-Origin") == "*"
            resp.read()
        finally:
            stop_server(server)

    def test_cors_on_get(self):
        """非 OPTIONS 请求也应注入 CORS 头。"""
        cors = CORSService(allow_origins=["*"])
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[cors, fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "GET", "/", headers={"Origin": "https://any.com"})
            assert resp.status == 200
            assert resp.getheader("Access-Control-Allow-Origin") == "*"
            resp.read()
        finally:
            stop_server(server)

    def test_credentials_header(self):
        cors = CORSService(allow_origins=["https://a.com"], allow_credentials=True)
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[cors, fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "OPTIONS", "/", headers={"Origin": "https://a.com"})
            assert resp.getheader("Access-Control-Allow-Credentials") == "true"
            resp.read()
        finally:
            stop_server(server)

    def test_max_age_header(self):
        cors = CORSService(allow_origins=["*"], max_age=3600)
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[cors, fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "OPTIONS", "/", headers={"Origin": "https://a.com"})
            assert resp.getheader("Access-Control-Max-Age") == "3600"
            resp.read()
        finally:
            stop_server(server)

    def test_no_origin_header(self):
        """无 Origin 头的 OPTIONS 应被拒绝。"""
        cors = CORSService(allow_origins=["https://a.com"])
        server, port = start_server(services=[cors])
        try:
            resp = HTTPTestClient(port=port).request("OPTIONS", "/")
            assert resp.status == 403
            resp.read()
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  ErrorService
# ═══════════════════════════════════════════════════════════════

class TestErrorService:

    def test_404_page(self, sample_files):
        fs = FileService(sample_files, "/")
        errsvc = ErrorService("TestServer/1.0")
        server, port = start_server(services=[fs], error_service=errsvc)
        try:
            resp = HTTPTestClient(port=port).request("GET", "/nonexistent")
            assert resp.status == 404
            assert "TestServer/1.0" in resp.read().decode()
        finally:
            stop_server(server)

    def test_405_method_not_allowed(self, sample_files):
        fs = FileService(sample_files, "/", allowUpload=False)
        server, port = start_server(services=[fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "POST", "/", headers={"Content-Type": "text/plain"}, body=b"test")
            assert resp.status == 405
            resp.read()
        finally:
            stop_server(server)

    def test_head_error_returns_status_only(self, sample_files):
        fs = FileService(sample_files, "/")
        errsvc = ErrorService("Test/1.0")
        server, port = start_server(services=[fs], error_service=errsvc)
        try:
            resp = HTTPTestClient(port=port).request("HEAD", "/nonexistent")
            assert resp.status == 404
            assert resp.read() == b""
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  PageService（Web 模式）
# ═══════════════════════════════════════════════════════════════

class TestPageService:

    def test_index_and_file(self, sample_files):
        ps = PageService(sample_files, "/")
        server, port = start_server(services=[ps])
        try:
            c = HTTPTestClient(port=port)
            resp = c.request("GET", "/")
            assert resp.status == 200
            assert "Index" in resp.read().decode()

            resp = c.request("GET", "/hello.txt")
            assert resp.status == 200
            assert resp.read() == b"Hello, CryskuraHTTP!"
        finally:
            stop_server(server)

    def test_dir_without_index_404(self, sample_files):
        ps = PageService(sample_files, "/")
        server, port = start_server(services=[ps])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/subdir/")
            assert resp.status == 404
            resp.read()
        finally:
            stop_server(server)

    def test_head_request(self, sample_files):
        ps = PageService(sample_files, "/")
        server, port = start_server(services=[ps])
        try:
            resp = HTTPTestClient(port=port).request("HEAD", "/")
            assert resp.status == 200
            resp.read()
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  APIService
# ═══════════════════════════════════════════════════════════════

class TestAPIService:

    def test_simple_get(self):
        def handler(request, path, args, headers, content, method):
            return 200, {"Content-Type": "application/json"}, b'{"ok":true}'
        api = APIService("/api", func=handler)
        server, port = start_server(services=[api])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/api")
            assert resp.status == 200
            assert json.loads(resp.read()) == {"ok": True}
        finally:
            stop_server(server)

    def test_args_and_subpath(self):
        def handler(request, path, args, headers, content, method):
            name = args.get("name", "unknown")
            body = json.dumps({"name": name, "path": "/".join(path)}).encode()
            return 200, {"Content-Type": "application/json"}, body
        api = APIService("/api", func=handler)
        server, port = start_server(services=[api])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/api/users/123?name=test")
            data = json.loads(resp.read())
            assert data == {"name": "test", "path": "users/123"}
        finally:
            stop_server(server)

    def test_post(self):
        def handler(request, path, args, headers, content, method):
            return 201, {"Content-Type": "text/plain"}, b"Created"
        api = APIService("/api", func=handler, methods=["GET", "POST"])
        server, port = start_server(services=[api])
        try:
            resp = HTTPTestClient(port=port).request(
                "POST", "/api",
                headers={"Content-Type": "application/json"},
                body=b'{"data": 1}')
            assert resp.status == 201
            assert resp.read() == b"Created"
        finally:
            stop_server(server)

    def test_header_injection_blocked(self):
        """恶意 header 名应被过滤。"""
        def handler(request, path, args, headers, content, method):
            return 200, {"X-Evil\r\nInjected: bar": "value",
                          "X-Normal": "val\r\nue"}, b"ok"
        api = APIService("/api", func=handler)
        server, port = start_server(services=[api])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/api")
            # 恶意 header 不应出现
            assert resp.getheader("X-Evil") is None
            resp.read()
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  APIRouter
# ═══════════════════════════════════════════════════════════════

class TestAPIRouter:

    def test_basic_and_prefix(self):
        router = APIRouter()

        @router.route("/hello", methods=["GET"])
        def hello(request, path, args, headers, content, method):
            return 200, {"Content-Type": "text/plain"}, b"Hello!"

        @router.route("/files", methods=["GET"], prefix=True)
        def files(request, path, args, headers, content, method):
            return 200, {}, "/".join(path).encode()

        server, port = start_server(services=router.build("/api"))
        try:
            c = HTTPTestClient(port=port)
            assert c.request("GET", "/api/hello").read() == b"Hello!"
            assert c.request("GET", "/api/files/some/path").status == 200
        finally:
            stop_server(server)

    def test_multiple_routers(self):
        r1 = APIRouter()
        r2 = APIRouter()

        @r1.route("/a", methods=["GET"])
        def a(request, path, args, headers, content, method):
            return 200, {}, b"A"

        @r2.route("/b", methods=["GET"])
        def b(request, path, args, headers, content, method):
            return 200, {}, b"B"

        services = r1.build("/api") + r2.build("/api")
        server, port = start_server(services=services)
        try:
            c = HTTPTestClient(port=port)
            assert c.request("GET", "/api/a").read() == b"A"
            assert c.request("GET", "/api/b").read() == b"B"
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  SimpleAPIRouter
# ═══════════════════════════════════════════════════════════════

class TestSimpleAPIRouter:

    def test_get_and_post(self):
        router = SimpleAPIRouter()

        @router.get("/users/{user_id}")
        def get_user(params, body):
            return 200, {"user_id": params["user_id"]}

        @router.post("/items")
        def create_item(params, body):
            return 201, {"received": body}

        server, port = start_server(services=router.build("/api"))
        try:
            c = HTTPTestClient(port=port)
            resp = c.request("GET", "/api/users/42")
            assert json.loads(resp.read()) == {"user_id": "42"}

            resp = c.request("POST", "/api/items",
                             headers={"Content-Type": "application/json"},
                             body=json.dumps({"name": "test"}).encode())
            assert resp.status == 201
            assert json.loads(resp.read()) == {"received": {"name": "test"}}
        finally:
            stop_server(server)

    def test_invalid_json_400(self):
        router = SimpleAPIRouter()

        @router.post("/items")
        def create(params, body):
            return 201, {}

        server, port = start_server(services=router.build("/api"))
        try:
            resp = HTTPTestClient(port=port).request(
                "POST", "/api/items",
                headers={"Content-Type": "application/json"},
                body=b"not json{")
            assert resp.status == 400
            assert "error" in json.loads(resp.read())
        finally:
            stop_server(server)

    def test_multiple_path_params(self):
        router = SimpleAPIRouter()

        @router.get("/users/{user_id}/posts/{post_id}")
        def get_post(params, body):
            return 200, params

        server, port = start_server(services=router.build())
        try:
            resp = HTTPTestClient(port=port).request("GET", "/users/5/posts/42")
            assert json.loads(resp.read()) == {"user_id": "5", "post_id": "42"}
        finally:
            stop_server(server)

    def test_put_delete(self):
        router = SimpleAPIRouter()

        @router.put("/items/{id}")
        def update(params, body):
            return 200, {"updated": params["id"], "data": body}

        @router.delete("/items/{id}")
        def delete(params, body):
            return 204, None

        server, port = start_server(services=router.build())
        try:
            c = HTTPTestClient(port=port)
            resp = c.request("PUT", "/items/7",
                             headers={"Content-Type": "application/json"},
                             body=json.dumps({"name": "new"}).encode())
            assert resp.status == 200
            data = json.loads(resp.read())
            assert data["updated"] == "7"

            resp = c.request("DELETE", "/items/7")
            assert resp.status == 204
        finally:
            stop_server(server)

    def test_function_exception_500(self):
        router = SimpleAPIRouter()

        @router.get("/boom")
        def boom(params, body):
            raise RuntimeError("kaboom")

        server, port = start_server(services=router.build())
        try:
            resp = HTTPTestClient(port=port).request("GET", "/boom")
            assert resp.status == 500
            data = json.loads(resp.read())
            assert "error" in data
        finally:
            stop_server(server)

    def test_no_base_path(self):
        router = SimpleAPIRouter()

        @router.get("/ping")
        def ping(params, body):
            return 200, "pong"

        server, port = start_server(services=router.build())
        try:
            resp = HTTPTestClient(port=port).request("GET", "/ping")
            assert resp.status == 200
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  HealthService
# ═══════════════════════════════════════════════════════════════

class TestHealthService:

    def test_get(self):
        health = HealthService()
        server, port = start_server(services=[health])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/health")
            assert resp.status == 200
            data = json.loads(resp.read())
            assert data["status"] == "ok"
            assert "uptime" in data
        finally:
            stop_server(server)

    def test_head(self):
        health = HealthService()
        server, port = start_server(services=[health])
        try:
            resp = HTTPTestClient(port=port).request("HEAD", "/health")
            assert resp.status == 200
            assert resp.read() == b""
        finally:
            stop_server(server)

    def test_custom_path(self):
        health = HealthService("/status")
        server, port = start_server(services=[health])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/status")
            assert resp.status == 200
        finally:
            stop_server(server)


# ═══════════════════════════════════════════════════════════════
#  RedirectService
# ═══════════════════════════════════════════════════════════════

class TestRedirect:

    @pytest.mark.parametrize("status", [301, 302, 307])
    def test_redirect_statuses(self, status):
        rs = RedirectService("/old", "https://example.com/new", status=status)
        server, port = start_server(services=[rs])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/old")
            assert resp.status == status
            assert resp.getheader("Location") == "https://example.com/new"
            resp.read()
        finally:
            stop_server(server)

    def test_prefix_redirect(self):
        rs = RedirectService("/api", "http://localhost/new-api", redirect_type="prefix")
        server, port = start_server(services=[rs])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/api/v1/users")
            assert resp.status == 301
            loc = resp.getheader("Location")
            assert "/new-api/v1/users" in loc
            resp.read()
        finally:
            stop_server(server)

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            RedirectService("/old", "/new", status=404)


# ═══════════════════════════════════════════════════════════════
#  路由优先级 & 鉴权 & 请求体限制 & Host 路由
# ═══════════════════════════════════════════════════════════════

class TestRoutePriority:

    def test_specific_wins(self):
        def api_handler(request, path, args, headers, content, method):
            return 200, {}, b"API"
        api = APIService("/api", func=api_handler)
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[api, fs])
        try:
            resp = HTTPTestClient(port=port).request("GET", "/api")
            assert resp.status == 200
            assert resp.read() == b"API"
        finally:
            stop_server(server)


class TestAuthentication:

    def test_token_auth(self):
        def auth(cookies, path, args, operation):
            return args.get("token") == "secret"

        def handler(request, path, args, headers, content, method):
            return 200, {}, b"OK"
        api = APIService("/api", func=handler, auth_func=auth)
        server, port = start_server(services=[api])
        try:
            c = HTTPTestClient(port=port)
            assert c.request("GET", "/api?token=secret").status == 200
            assert c.request("GET", "/api?token=wrong").status == 401
        finally:
            stop_server(server)

    def test_cookie_auth(self):
        def auth(cookies, path, args, operation):
            return cookies.get("session") == "abc123"

        def handler(request, path, args, headers, content, method):
            return 200, {}, b"OK"
        api = APIService("/api", func=handler, auth_func=auth)
        server, port = start_server(services=[api])
        try:
            c = HTTPTestClient(port=port)
            assert c.request("GET", "/api", headers={"Cookie": "session=abc123"}).status == 200
            assert c.request("GET", "/api", headers={"Cookie": "session=bad"}).status == 401
        finally:
            stop_server(server)


class TestRequestBodyLimit:

    def test_rejected(self):
        def handler(request, path, args, headers, content, method):
            return 200, {}, b"OK"
        api = APIService("/api", func=handler)
        server, port = start_server(services=[api], max_request_body=10)
        try:
            body = b"x" * 100
            resp = HTTPTestClient(port=port).request(
                "POST", "/api",
                headers={"Content-Length": str(len(body))}, body=body)
            assert resp.status == 413
            resp.read()
        finally:
            stop_server(server)

    def test_accepted(self):
        def handler(request, path, args, headers, content, method):
            return 200, {}, b"OK"
        api = APIService("/api", func=handler)
        server, port = start_server(services=[api], max_request_body=1024)
        try:
            body = b"x" * 10
            resp = HTTPTestClient(port=port).request(
                "POST", "/api",
                headers={"Content-Length": str(len(body))}, body=body)
            assert resp.status == 200
        finally:
            stop_server(server)


class TestHostRouting:

    def test_host_specific(self):
        def handler(request, path, args, headers, content, method):
            return 200, {}, b"Host-specific"
        api = APIService("/", func=handler, host="example.com")
        fs = FileService("/tmp", "/")
        server, port = start_server(services=[api, fs])
        try:
            resp = HTTPTestClient(port=port).request(
                "GET", "/", headers={"Host": "example.com"})
            assert resp.status == 200
            assert resp.read() == b"Host-specific"
        finally:
            stop_server(server)
