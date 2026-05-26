"""Tests for Server initialization, binding, and validation."""

import pytest

from cryskura import Server
from cryskura.Services import FileService


class TestServerInit:
    """Tests for Server constructor validation."""

    def test_default_server(self):
        """A default server should be constructable."""
        server = Server()
        assert server.port == 8080
        assert len(server.services) == 1
        assert server.certfile is None
        assert server.uPnP is None

    def test_custom_port(self, temp_dir):
        """Server should accept a custom port."""
        server = Server(
            interface="127.0.0.1", port=9999,
            services=[FileService(temp_dir, "/")],
        )
        assert server.port == 9999

    def test_multiple_ports(self, temp_dir):
        """Server should accept multiple ports."""
        server = Server(
            interface="127.0.0.1", port=[8080, 8081],
            services=[FileService(temp_dir, "/")],
        )
        assert len(server.bind_addresses) == 2

    def test_multiple_interfaces(self, temp_dir):
        """Server should accept multiple interfaces."""
        server = Server(
            interface=["127.0.0.1", "::1"], port=8080,
            services=[FileService(temp_dir, "/")],
        )
        assert len(server.bind_addresses) == 2

    def test_port_out_of_range_high(self):
        """Ports above 65535 should raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            Server(port=99999)

    def test_port_out_of_range_negative(self):
        """Negative ports should raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            Server(port=-1)

    def test_invalid_service(self):
        """Non-BaseService objects should raise ValueError."""
        with pytest.raises(ValueError, match="not a valid service"):
            Server(services=["not_a_service"])

    def test_certfile_not_found(self):
        """Non-existent certfile should raise ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            Server(certfile="/nonexistent/cert.pem")

    def test_force_port_flag(self, temp_dir):
        """forcePort flag should be accepted."""
        server = Server(
            interface="127.0.0.1", port=8080,
            services=[FileService(temp_dir, "/")],
            forcePort=True,
        )
        assert server._force_port is True

    def test_dual_stack_flag(self, temp_dir):
        """dual_stack flag should default to True."""
        server = Server(services=[FileService(temp_dir, "/")])
        assert server.dual_stack is True

    def test_custom_server_name(self, temp_dir):
        """Custom server_name should be stored."""
        server = Server(
            services=[FileService(temp_dir, "/")],
            server_name="TestServer/2.0",
        )
        assert server.server_name == "TestServer/2.0"

    def test_interface_not_found(self):
        """Non-existent interface should raise ValueError with suggestions."""
        with pytest.raises(ValueError, match="not found"):
            Server(interface="invalid-interface-name-that-does-not-exist")
