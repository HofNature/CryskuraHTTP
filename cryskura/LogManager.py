"""LogManager: file-based logging with date rotation.

Writes logs to <log_dir>/latest/access.log and server.log.
On start and at midnight, renames latest/ to a timestamped directory.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime, timedelta
from typing import Optional


class LogManager:
    """Centralized logger that writes to a rotating log directory.

    Directory structure:
        <log_dir>/
            latest/
                access.log
                server.log
            2026-05-27T15-30-00/
                access.log
                server.log
    """

    def __init__(
        self, log_dir: Optional[str] = None, server_name: str = "cryskura"
    ) -> None:
        self._log_dir: Optional[str] = log_dir
        self._server_name: str = server_name
        self._access_logger: Optional[logging.Logger] = None
        self._server_logger: Optional[logging.Logger] = None
        self._rotation_timer: Optional[threading.Timer] = None
        self._lock: threading.Lock = threading.Lock()

        if log_dir is not None:
            self._rotate_on_start()
            self._setup_loggers()
            self._schedule_midnight_rotation()

    @property
    def log_dir(self) -> Optional[str]:
        return self._log_dir

    # ── directory helpers ──────────────────────────────────────────

    @staticmethod
    def _latest_dir(log_dir: str) -> str:
        return os.path.join(log_dir, "latest")

    @staticmethod
    def _timestamped_name() -> str:
        return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    # ── rotation ───────────────────────────────────────────────────

    def _rotate_on_start(self) -> None:
        assert self._log_dir is not None
        log_dir_real = os.path.realpath(self._log_dir)
        os.makedirs(log_dir_real, exist_ok=True)
        latest = self._latest_dir(log_dir_real)
        if os.path.isdir(latest):
            new_name = os.path.join(log_dir_real, self._timestamped_name())
            os.rename(latest, new_name)

    def rotate(self) -> None:
        """Rename latest/ to a timestamped directory, recreate latest/ loggers."""
        if self._log_dir is None:
            return
        with self._lock:
            log_dir_real = os.path.realpath(self._log_dir)
            latest = self._latest_dir(log_dir_real)
            if os.path.isdir(latest):
                new_name = os.path.join(log_dir_real, self._timestamped_name())
                os.rename(latest, new_name)
            self._setup_loggers()
        self._schedule_midnight_rotation()

    def _resolve_safe_latest(self) -> str:
        """Resolve the latest/ path and verify it stays within log_dir."""
        assert self._log_dir is not None
        log_dir_real = os.path.realpath(self._log_dir)
        latest = self._latest_dir(log_dir_real)
        os.makedirs(latest, exist_ok=True)
        latest_real = os.path.realpath(latest)
        if os.path.commonpath([latest_real, log_dir_real]) != log_dir_real:
            raise RuntimeError(
                f"Log directory symlink escape detected: {latest} -> {latest_real}"
            )
        return latest_real

    def _setup_loggers(self) -> None:
        assert self._log_dir is not None
        latest = self._resolve_safe_latest()

        file_fmt = logging.Formatter(
            "%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
        )
        console_fmt = logging.Formatter(
            "[%(asctime)s] %(message)s", datefmt="%d/%b/%Y %H:%M:%S"
        )

        # access log
        self._access_logger = logging.getLogger(
            f"cryskura.access.{id(self)}"
        )
        self._access_logger.handlers.clear()
        self._access_logger.propagate = False
        self._access_logger.setLevel(logging.DEBUG)
        afh = logging.FileHandler(
            os.path.join(latest, "access.log"), encoding="utf-8"
        )
        afh.setFormatter(file_fmt)
        self._access_logger.addHandler(afh)

        # server log
        self._server_logger = logging.getLogger(
            f"cryskura.server.{id(self)}"
        )
        self._server_logger.handlers.clear()
        self._server_logger.propagate = False
        self._server_logger.setLevel(logging.DEBUG)
        sfh = logging.FileHandler(
            os.path.join(latest, "server.log"), encoding="utf-8"
        )
        sfh.setFormatter(file_fmt)
        self._server_logger.addHandler(sfh)
        # Also echo server events to stderr (parent-class format)
        sh = logging.StreamHandler()
        sh.setFormatter(console_fmt)
        self._server_logger.addHandler(sh)

    def _schedule_midnight_rotation(self) -> None:
        now = datetime.now()
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        delay = (midnight - now).total_seconds()
        if delay < 0:
            delay = 60
        if self._rotation_timer is not None:
            self._rotation_timer.cancel()
        self._rotation_timer = threading.Timer(delay, self.rotate)
        self._rotation_timer.daemon = True
        self._rotation_timer.start()

    # ── logging methods ────────────────────────────────────────────

    def access(
        self, request_line: str, status: int, client_ip: str, size: int
    ) -> None:
        """Log an HTTP access entry (file only; console handled by parent class)."""
        if self._access_logger is not None:
            self._access_logger.info(
                '%s "%s" %d %d', client_ip, request_line, status, size
            )

    def server_event(self, message: str, level: str = "INFO") -> None:
        """Log a server-level event."""
        if self._server_logger is not None:
            log_func = getattr(
                self._server_logger, level.lower(), self._server_logger.info
            )
            log_func(message)
        else:
            print(message, file=sys.stderr)

    def error(self, message: str, exc_info: bool = False) -> None:
        """Log an error (always to server log, falls back to print)."""
        if self._server_logger is not None:
            self._server_logger.error(message, exc_info=exc_info)
        else:
            print(message, file=sys.stderr)

    def close(self) -> None:
        """Close all log handlers."""
        if self._rotation_timer is not None:
            self._rotation_timer.cancel()
            self._rotation_timer = None
        for logger in (self._access_logger, self._server_logger):
            if logger is not None:
                for handler in list(logger.handlers):
                    handler.close()
                    logger.removeHandler(handler)
