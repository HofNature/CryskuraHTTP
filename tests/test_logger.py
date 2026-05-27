"""Tests for LogManager module."""
import os
import tempfile
import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from cryskura.LogManager import LogManager


class TestLogManagerInit:
    def test_none_log_dir_disables_file_logging(self):
        lm = LogManager(log_dir=None)
        assert lm.log_dir is None
        # Should not raise
        lm.server_event("test message")
        lm.error("test error")
        lm.access("GET /", 200, "127.0.0.1", 1024)

    def test_log_dir_creates_latest(self):
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            lm = LogManager(log_dir=log_dir)
            try:
                latest = os.path.join(log_dir, "latest")
                assert os.path.isdir(latest)
                assert os.path.isfile(os.path.join(latest, "access.log"))
                assert os.path.isfile(os.path.join(latest, "server.log"))
            finally:
                lm.close()

    def test_rotate_on_start_renames_existing_latest(self):
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            # Create a first session
            lm1 = LogManager(log_dir=log_dir)
            lm1.server_event("session 1")
            lm1.close()

            # Start a second session
            lm2 = LogManager(log_dir=log_dir)
            try:
                # The old latest should be renamed
                dirs = [
                    d for d in os.listdir(log_dir)
                    if os.path.isdir(os.path.join(log_dir, d))
                ]
                latest_dirs = [d for d in dirs if d == "latest"]
                timestamped = [d for d in dirs if d != "latest"]
                assert len(latest_dirs) == 1
                assert len(timestamped) >= 1
            finally:
                lm2.close()


class TestLogManagerAccess:
    def test_access_writes_to_log(self):
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            lm = LogManager(log_dir=log_dir)
            try:
                lm.access("GET /hello.txt HTTP/1.1", 200, "127.0.0.1", 13)
                # Give file handler time to flush
                time.sleep(0.1)
                access_log = os.path.join(log_dir, "latest", "access.log")
                assert os.path.isfile(access_log)
                with open(access_log, "r") as f:
                    content = f.read()
                assert "GET /hello.txt" in content
                assert "200" in content
                assert "127.0.0.1" in content
            finally:
                lm.close()

    def test_access_noop_when_disabled(self):
        lm = LogManager(log_dir=None)
        lm.access("GET /", 200, "127.0.0.1", 0)


class TestLogManagerServerEvent:
    def test_server_event_writes_to_log(self):
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            lm = LogManager(log_dir=log_dir)
            try:
                lm.server_event("Server started")
                time.sleep(0.1)
                server_log = os.path.join(log_dir, "latest", "server.log")
                with open(server_log, "r") as f:
                    content = f.read()
                assert "Server started" in content
            finally:
                lm.close()


class TestLogManagerError:
    def test_error_writes_to_server_log(self):
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            lm = LogManager(log_dir=log_dir)
            try:
                lm.error("Something went wrong")
                time.sleep(0.1)
                server_log = os.path.join(log_dir, "latest", "server.log")
                with open(server_log, "r") as f:
                    content = f.read()
                assert "Something went wrong" in content
            finally:
                lm.close()


class TestLogManagerRotate:
    def test_rotate_renames_latest(self):
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            lm = LogManager(log_dir=log_dir)
            try:
                lm.server_event("before rotate")
                time.sleep(0.1)
                lm.rotate()
                # Old latest should be renamed
                dirs = os.listdir(log_dir)
                assert "latest" in dirs
                timestamped = [d for d in dirs if d != "latest"]
                assert len(timestamped) == 1
            finally:
                lm.close()

    def test_rotate_noop_when_disabled(self):
        lm = LogManager(log_dir=None)
        lm.rotate()


class TestMidnightRotation:
    def test_timer_scheduled_on_init(self):
        """Midnight timer should be created with a positive delay <= 86400."""
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            real_timer = threading.Timer
            with patch("threading.Timer") as mock_timer:
                lm = LogManager(log_dir=log_dir)
                try:
                    assert mock_timer.called
                    call_kwargs = mock_timer.call_args
                    delay = call_kwargs[0][0]
                    assert 0 < delay <= 86400
                    callback = call_kwargs[0][1]
                    assert callback == lm.rotate
                finally:
                    lm.close()

    def test_timer_rescheduled_after_rotate(self):
        """After rotate(), a new midnight timer should replace the old one."""
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            lm = LogManager(log_dir=log_dir)
            try:
                old_timer = lm._rotation_timer
                old_timer.cancel()
                lm.rotate()
                new_timer = lm._rotation_timer
                assert new_timer is not None
                assert new_timer is not old_timer
            finally:
                lm.close()

    def test_timer_fires_and_rotates(self):
        """When the timer fires, rotate() renames latest/."""
        with tempfile.TemporaryDirectory() as td:
            log_dir = os.path.join(td, "logs")
            lm = LogManager(log_dir=log_dir)
            try:
                lm.server_event("before midnight")
                time.sleep(0.1)
                # Cancel the real timer so it doesn't interfere
                lm._rotation_timer.cancel()
                # Fire rotate directly as the timer would
                lm.rotate()
                dirs = os.listdir(log_dir)
                assert "latest" in dirs
                timestamped = [d for d in dirs if d != "latest"]
                assert len(timestamped) == 1
                # Verify old log has the event
                old_dir = os.path.join(log_dir, timestamped[0])
                with open(os.path.join(old_dir, "server.log"), "r") as f:
                    assert "before midnight" in f.read()
                # Verify new latest is fresh
                lm.server_event("after midnight")
                time.sleep(0.1)
                with open(os.path.join(log_dir, "latest", "server.log"), "r") as f:
                    content = f.read()
                assert "after midnight" in content
                assert "before midnight" not in content
            finally:
                lm.close()
