"""Shared test fixtures for CryskuraHTTP."""

import os
import socket
import tempfile
import threading
import time
from contextlib import contextmanager

import pytest

from cryskura import Server
from cryskura.Services import FileService, PageService, RedirectService


def _free_port():
    """Return an available TCP port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _run_server(server, timeout=5.0):
    """Context manager that starts a server in a thread and stops it on exit."""
    started = threading.Event()
    error = [None]

    def _run():
        try:
            # Signal that the thread is about to start serve_forever
            started.set()
            server.start(threaded=False)
        except Exception as e:
            error[0] = e
            started.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    # Wait for the server to start
    if not started.wait(timeout):
        server.stop()
        raise RuntimeError("Server did not start within timeout")

    if error[0] is not None:
        raise error[0]

    # Give the server a moment to actually bind
    time.sleep(0.1)

    try:
        yield server
    finally:
        server.stop()
        t.join(timeout=2.0)


@pytest.fixture
def temp_dir():
    """Create a temporary directory with test files, cleaned up after the test."""
    with tempfile.TemporaryDirectory() as td:
        # Create a test file
        with open(os.path.join(td, "hello.txt"), "w") as f:
            f.write("Hello, World!")

        # Create a subdirectory with a file
        os.makedirs(os.path.join(td, "subdir"))
        with open(os.path.join(td, "subdir", "data.txt"), "w") as f:
            f.write("nested data")

        # Create a larger file for range testing
        with open(os.path.join(td, "range.txt"), "w") as f:
            f.write("0123456789" * 100)  # 1000 bytes

        yield td


@pytest.fixture
def http_port():
    """Get a free port number."""
    return _free_port()


@pytest.fixture
def file_server(temp_dir, http_port):
    """Start a FileServer on a temp directory and return (base_url, server)."""
    server = Server(
        interface="127.0.0.1",
        port=http_port,
        services=[FileService(temp_dir, "/")],
    )
    with _run_server(server) as srv:
        yield f"http://127.0.0.1:{http_port}", srv


@pytest.fixture
def upload_server(temp_dir, http_port):
    """Start a FileServer with upload enabled."""
    server = Server(
        interface="127.0.0.1",
        port=http_port,
        services=[FileService(temp_dir, "/", allowUpload=True)],
    )
    with _run_server(server) as srv:
        yield f"http://127.0.0.1:{http_port}", srv


@pytest.fixture
def resume_server(temp_dir, http_port):
    """Start a FileServer with range/resume support."""
    server = Server(
        interface="127.0.0.1",
        port=http_port,
        services=[FileService(temp_dir, "/", allowResume=True)],
    )
    with _run_server(server) as srv:
        yield f"http://127.0.0.1:{http_port}", srv


@pytest.fixture
def page_server(temp_dir, http_port):
    """Start a PageServer (no directory listing)."""
    # Create an index.html for PageService to find
    with open(os.path.join(temp_dir, "index.html"), "w") as f:
        f.write("<html><body>Hello</body></html>")
    server = Server(
        interface="127.0.0.1",
        port=http_port,
        services=[PageService(temp_dir, "/")],
    )
    with _run_server(server) as srv:
        yield f"http://127.0.0.1:{http_port}", srv
