"""Tests for SimpleAPIRouter JSON API."""

import json
import threading
import time
from contextlib import contextmanager

import pytest

from cryskura import Server
from cryskura.Services import SimpleAPIRouter


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


import http.client


class TestSimpleAPIRouter:
    """Tests for SimpleAPIRouter JSON API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.router = SimpleAPIRouter()

        @self.router.get("/users/{user_id}")
        def get_user(params, body):
            return 200, {"user_id": params["user_id"], "name": "Alice"}

        @self.router.post("/users")
        def create_user(params, body):
            return 201, {"received": body}

        @self.router.get("/items")
        def list_items(params, body):
            return 200, {"items": ["a", "b"]}

        @self.router.get("/status")
        def status(params):
            return 200, {"ok": True}

        self.services = self.router.build("/api")
        port = _free_port()
        self.server = Server(
            interface="127.0.0.1", port=port,
            services=self.services,
        )
        self.host = "127.0.0.1"
        self.port = port

    def _get(self, path):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    def _post(self, path, data):
        body = json.dumps(data).encode()
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("POST", path, body=body,
                     headers={"Content-Type": "application/json",
                              "Content-Length": str(len(body))})
        resp = conn.getresponse()
        resp_body = resp.read()
        conn.close()
        return resp, resp_body

    def test_get_with_path_params(self):
        with _run_server(self.server):
            resp, body = self._get("/api/users/123")
            assert resp.status == 200
            data = json.loads(body)
            assert data["user_id"] == "123"
            assert data["name"] == "Alice"

    def test_get_static_route(self):
        with _run_server(self.server):
            resp, body = self._get("/api/items")
            assert resp.status == 200
            data = json.loads(body)
            assert data["items"] == ["a", "b"]

    def test_post_with_body(self):
        with _run_server(self.server):
            resp, body = self._post("/api/users", {"name": "Bob"})
            assert resp.status == 201
            data = json.loads(body)
            assert data["received"]["name"] == "Bob"

    def test_head_request(self):
        with _run_server(self.server):
            conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
            conn.request("HEAD", "/api/items")
            resp = conn.getresponse()
            body = resp.read()
            conn.close()
            assert resp.status == 200
            assert body == b""

    def test_route_not_found(self):
        """Unmatched path falls through to ErrorService HTML page."""
        with _run_server(self.server):
            resp, body = self._get("/api/nonexistent")
            assert resp.status == 404
            # Falls through to ErrorService (no matching Route prefix)
            assert b"Not Found" in body or b"404" in body

    def test_template_not_matched_returns_json_error(self):
        """Prefix matches but template does not → JSON error from SimpleAPI."""
        with _run_server(self.server):
            # /api/users matches the prefix ["api","users"] but has no
            # remaining segments to bind to {user_id}
            resp, body = self._get("/api/users")
            assert resp.status == 404
            data = json.loads(body)
            assert data.get("error") == "Route not found"

    def test_post_large_body_rejected(self):
        """Body larger than max_body should be rejected."""
        # Create a router with a very small max_body
        router2 = SimpleAPIRouter(max_body=10)

        @router2.post("/data")
        def handle_data(params, body):
            return 200, {"ok": True}

        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=router2.build("/api"),
        )
        with _run_server(server):
            big_data = {"key": "x" * 100}
            body = json.dumps(big_data).encode()
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/api/data", body=body,
                         headers={"Content-Type": "application/json",
                                  "Content-Length": str(len(body))})
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 413

    def test_single_param_function(self):
        """Functions with 1 arg should work (receives only params)."""
        with _run_server(self.server):
            resp, body = self._get("/api/status")
            assert resp.status == 200
            data = json.loads(body)
            assert data["ok"] is True

    def test_content_type_json(self):
        with _run_server(self.server):
            resp, _ = self._get("/api/items")
            ctype = resp.getheader("Content-Type", "")
            assert "application/json" in ctype

    def test_nested_path_params(self):
        router2 = SimpleAPIRouter()

        @router2.get("/a/{a_id}/b/{b_id}")
        def nested(params, body):
            return 200, {"a": params["a_id"], "b": params["b_id"]}

        port = _free_port()
        server = Server(
            interface="127.0.0.1", port=port,
            services=router2.build("/api"),
        )
        with _run_server(server):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/api/a/1/b/2")
            resp = conn.getresponse()
            data = json.loads(resp.read())
            assert resp.status == 200
            assert data["a"] == "1"
            assert data["b"] == "2"
