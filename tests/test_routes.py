"""Tests for Route matching logic."""

from unittest.mock import MagicMock

import pytest

from cryskura.Services.BaseService import BaseService, Route


def _make_request(method="GET", host=None, port=None):
    """Create a mock request with the given command."""
    req = MagicMock()
    req.command = method
    req.host = host
    req.port = port
    return req


class TestRouteMatch:
    """Tests for Route.match()."""

    def test_exact_match_get(self):
        route = Route("/api/test", ["GET"], "exact")
        req = _make_request("GET")
        can_handle, path_ok = route.match(req, ["api", "test"])
        assert can_handle is True
        assert path_ok is True

    def test_exact_match_wrong_method(self):
        route = Route("/api/test", ["GET"], "exact")
        req = _make_request("POST")
        can_handle, path_ok = route.match(req, ["api", "test"])
        assert can_handle is False
        assert path_ok is True

    def test_exact_match_wrong_path(self):
        route = Route("/api/test", ["GET"], "exact")
        req = _make_request("GET")
        can_handle, path_ok = route.match(req, ["api", "other"])
        assert can_handle is False
        assert path_ok is False

    def test_prefix_match(self):
        route = Route("/api", ["GET"], "prefix")
        req = _make_request("GET")
        can_handle, path_ok = route.match(req, ["api", "test", "sub"])
        assert can_handle is True
        assert path_ok is True

    def test_prefix_match_exact(self):
        route = Route("/api", ["GET"], "prefix")
        req = _make_request("GET")
        can_handle, path_ok = route.match(req, ["api"])
        assert can_handle is True
        assert path_ok is True

    def test_prefix_match_wrong_prefix(self):
        route = Route("/api", ["GET"], "prefix")
        req = _make_request("GET")
        can_handle, path_ok = route.match(req, ["other"])
        assert can_handle is False
        assert path_ok is False

    def test_host_match(self):
        route = Route("/api", ["GET"], "prefix", host="localhost")
        req = _make_request("GET")
        can_handle, _ = route.match(req, ["api"], host="localhost")
        assert can_handle is True

    def test_host_mismatch(self):
        route = Route("/api", ["GET"], "prefix", host="localhost")
        req = _make_request("GET")
        can_handle, _ = route.match(req, ["api"], host="otherhost")
        assert can_handle is False

    def test_port_match(self):
        route = Route("/api", ["GET"], "prefix", port=8080)
        req = _make_request("GET")
        can_handle, _ = route.match(req, ["api"], port=8080)
        assert can_handle is True

    def test_port_mismatch(self):
        route = Route("/api", ["GET"], "prefix", port=8080)
        req = _make_request("GET")
        can_handle, _ = route.match(req, ["api"], port=9090)
        assert can_handle is False

    def test_multiple_methods(self):
        route = Route("/api", ["GET", "POST", "HEAD"], "prefix")
        for method in ["GET", "POST", "HEAD"]:
            req = _make_request(method)
            can_handle, _ = route.match(req, ["api"])
            assert can_handle is True

    def test_invalid_route_type(self):
        with pytest.raises(ValueError, match="not a valid type"):
            Route("/api", ["GET"], "invalid")

    def test_route_from_string_path(self):
        route = Route("/a/b/c", ["GET"], "exact")
        assert route.path == ["a", "b", "c"]

    def test_route_from_list_path(self):
        route = Route(["a", "b", "c"], ["GET"], "exact")
        assert route.path == ["a", "b", "c"]

    def test_empty_path_segments_stripped(self):
        """Leading/trailing slashes are stripped; interior empty segments remain."""
        route = Route("/a//b/", ["GET"], "exact")
        assert route.path == ["a", "", "b"]

    def test_multiple_hosts(self):
        route = Route("/api", ["GET"], "prefix", host=["a", "b"])
        req = _make_request("GET")
        can_handle, _ = route.match(req, ["api"], host="b")
        assert can_handle is True

    def test_multiple_ports(self):
        route = Route("/api", ["GET"], "prefix", port=[80, 443])
        req = _make_request("GET")
        can_handle, _ = route.match(req, ["api"], port=443)
        assert can_handle is True


class TestBaseService:
    """Tests for BaseService."""

    def test_constructor_validates_routes(self):
        """BaseService should only accept Route objects."""
        with pytest.raises(ValueError, match="not a valid route"):
            BaseService(["not_a_route"])

    def test_constructor_with_valid_routes(self):
        """BaseService should accept a list of Route objects."""
        routes = [Route("/a", ["GET"], "prefix")]
        svc = BaseService(routes)
        assert svc.routes == routes

    def test_default_handlers_raise_not_implemented(self):
        """Default handlers should raise NotImplementedError."""
        svc = BaseService([Route("/a", ["GET"], "prefix")])
        req = MagicMock()
        with pytest.raises(NotImplementedError):
            svc.handle_GET(req, [], {})
        with pytest.raises(NotImplementedError):
            svc.handle_POST(req, [], {})
        with pytest.raises(NotImplementedError):
            svc.handle_HEAD(req, [], {})
