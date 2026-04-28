"""WebSocket 支持：连接管理、帧协议、Service 集成。

用法：
    from cryskura.Services.WebSocket import WebSocketService

    def on_connect(conn, path, args):
        conn.send("Hello!")

    def on_message(conn, message):
        conn.send(f"Echo: {message}")

    ws = WebSocketService("/ws", on_connect=on_connect, on_message=on_message)
    server = HTTPServer(services=[ws])
"""
from __future__ import annotations

import base64
import hashlib
import logging
import socket
import struct
import threading
from typing import Callable, Optional, TYPE_CHECKING

from .BaseService import BaseService, Route

if TYPE_CHECKING:
    from ..Handler import HTTPRequestHandler as Handler

logger = logging.getLogger(__name__)

# WebSocket 握手用的 magic GUID (RFC 6455 §4.2.2)
_WS_MAGIC = b"258EAFA5-E914-47DA-95CA-5AB0DC85B911"

# Issue 4: 单帧载荷大小上限（16 MB），防止超大帧导致 OOM
_MAX_FRAME_PAYLOAD = 16 * 1024 * 1024  # 16 MB

# Issue 4: 分片消息累计大小上限（64 MB），防止无限分片消耗内存
_MAX_MESSAGE_SIZE = 64 * 1024 * 1024  # 64 MB


# ═══════════════════════════════════════════════════════════════
#  WebSocket Connection — 帧协议封装
# ═══════════════════════════════════════════════════════════════

class WebSocketConnection:
    """管理一条 WebSocket 连接，处理帧的发送与接收。

    支持文本 / 二进制 / 分片消息、ping/pong、关闭握手。
    """

    # 操作码
    OP_CONTINUATION = 0x0
    OP_TEXT = 0x1
    OP_BINARY = 0x2
    OP_CLOSE = 0x8
    OP_PING = 0x9
    OP_PONG = 0xA

    def __init__(self, rfile, wfile) -> None:
        self._rfile = rfile
        self._wfile = wfile
        self._lock = threading.Lock()
        self.closed: bool = False
        self.close_code: int = 1000
        self.timeout: float = 0  # 0 表示不设超时

    # ── 发送 ───────────────────────────────────────────────────

    def send(self, data: str | bytes) -> None:
        """发送文本或二进制消息。"""
        if self.closed:
            raise ConnectionError("WebSocket is closed")
        if isinstance(data, str):
            opcode = self.OP_TEXT
            payload = data.encode("utf-8")
        else:
            opcode = self.OP_BINARY
            payload = data
        self._send_frame(opcode, payload)

    def send_ping(self, data: bytes = b"") -> None:
        """发送 Ping 控制帧。"""
        if self.closed:
            raise ConnectionError("WebSocket is closed")
        self._send_frame(self.OP_PING, data)

    def send_pong(self, data: bytes = b"") -> None:
        """发送 Pong 控制帧。"""
        if self.closed:
            raise ConnectionError("WebSocket is closed")
        self._send_frame(self.OP_PONG, data)

    def close(self, code: int = 1000, reason: str = "") -> None:
        """发起关闭握手。"""
        if self.closed:
            return
        self.closed = True
        self.close_code = code
        payload = struct.pack("!H", code) + reason.encode("utf-8")
        try:
            self._send_frame(self.OP_CLOSE, payload)
        except Exception:
            pass
        try:
            self._wfile.flush()
        except Exception:
            pass

    # ── 接收 ───────────────────────────────────────────────────

    def recv(self) -> tuple[int, str | bytes | None]:
        """接收一条完整消息，返回 (opcode, payload)。

        opcode:
            0x1 — 文本 (payload 为 str)
            0x2 — 二进制 (payload 为 bytes)
            0x8 — 关闭 (payload 为 str 或 None，close_code 已设置)
            0x9 — Ping (payload 为 bytes，已自动回复 Pong)
            0xA — Pong (payload 为 bytes)

        分片消息自动拼装后以首个分片的 opcode 返回。
        Ping 自动回复 Pong 后仍返回给调用者。
        Close 帧自动回送 Close 后返回。
        """
        fragments: list[bytes] = []
        msg_opcode: int = 0
        total_size: int = 0  # Issue 4: track accumulated fragment size

        while True:
            opcode, payload, fin = self._recv_frame()

            # ── 控制帧 ──
            if opcode in (self.OP_PING, self.OP_PONG, self.OP_CLOSE):
                if opcode == self.OP_CLOSE:
                    if len(payload) >= 2:
                        self.close_code = struct.unpack("!H", payload[:2])[0]
                    self.close_code = self.close_code or 1000
                    # 回送 Close 帧
                    try:
                        resp = struct.pack("!H", self.close_code)
                        self._send_frame(self.OP_CLOSE, resp)
                        self._wfile.flush()
                    except Exception:
                        pass
                    self.closed = True
                    return opcode, payload.decode("utf-8", errors="replace") if payload else None
                if opcode == self.OP_PING:
                    # 自动回复 Pong
                    try:
                        self._send_frame(self.OP_PONG, payload)
                        self._wfile.flush()
                    except Exception:
                        pass
                    return opcode, payload
                return opcode, payload

            # ── 数据帧 ──
            if opcode != self.OP_CONTINUATION:
                msg_opcode = opcode

            # Issue 4: enforce cumulative message size limit
            total_size += len(payload)
            if total_size > _MAX_MESSAGE_SIZE:
                self.closed = True
                try:
                    self._send_frame(self.OP_CLOSE, struct.pack("!H", 1009))
                    self._wfile.flush()
                except Exception:
                    pass
                raise ConnectionError(
                    f"WebSocket message too large: {total_size} > {_MAX_MESSAGE_SIZE}"
                )

            fragments.append(payload)

            if fin:
                combined = b"".join(fragments)
                if msg_opcode == self.OP_TEXT:
                    return msg_opcode, combined.decode("utf-8", errors="replace")
                return msg_opcode, combined

    # ── 底层帧操作 ─────────────────────────────────────────────

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        """发送一帧（服务器端不掩码）。"""
        with self._lock:
            header = bytearray()
            header.append(0x80 | opcode)  # FIN + opcode

            length = len(payload)
            if length < 126:
                header.append(length)
            elif length < 65536:
                header.append(126)
                header.extend(struct.pack("!H", length))
            else:
                header.append(127)
                header.extend(struct.pack("!Q", length))

            self._wfile.write(bytes(header))
            if payload:
                self._wfile.write(payload)
            self._wfile.flush()

    def _recv_frame(self) -> tuple[int, bytes, bool]:
        """接收一帧，返回 (opcode, payload, fin)。"""
        first_byte = self._read_exact(1)
        second_byte = self._read_exact(1)

        fin = bool(first_byte[0] & 0x80)
        opcode = first_byte[0] & 0x0F
        masked = bool(second_byte[0] & 0x80)
        payload_len = second_byte[0] & 0x7F

        # Issue 13: RFC 6455 §5.1 — server MUST close connection on unmasked client frame.
        # Check immediately after reading the mask bit, before consuming any more frame data.
        if not masked:
            raise ConnectionError("Client WebSocket frame must be masked (RFC 6455 §5.1)")

        if payload_len == 126:
            payload_len = struct.unpack("!H", self._read_exact(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack("!Q", self._read_exact(8))[0]

        # 控制帧限制
        if opcode >= 0x8:
            if not fin:
                raise ConnectionError("Control frame must not be fragmented")
            if payload_len > 125:
                raise ConnectionError("Control frame payload too large")

        # Issue 4: reject frames that claim an impossibly large payload
        if payload_len > _MAX_FRAME_PAYLOAD:
            raise ConnectionError(
                f"WebSocket frame payload too large: {payload_len} > {_MAX_FRAME_PAYLOAD}"
            )

        # The unmasked-frame check above guarantees masked is True here.
        # Read the 4-byte masking key and XOR-decode the payload.
        mask_key = self._read_exact(4)
        raw = bytearray(self._read_exact(payload_len))
        for i, b in enumerate(raw):
            raw[i] = b ^ mask_key[i % 4]
        payload = bytes(raw)

        return opcode, payload, fin

    def _read_exact(self, n: int) -> bytes:
        """从流中精确读取 n 字节。"""
        if self.timeout > 0:
            try:
                self._rfile._sock.settimeout(self.timeout)  # type: ignore[union-attr]
            except (AttributeError, OSError):
                pass
        data = b""
        while len(data) < n:
            chunk = self._rfile.read(n - len(data))
            if not chunk:
                raise ConnectionError("WebSocket connection closed unexpectedly")
            data += chunk
        return data


# ═══════════════════════════════════════════════════════════════
#  WebSocket 握手工具
# ═══════════════════════════════════════════════════════════════

def compute_accept_key(key: str) -> str:
    """计算 Sec-WebSocket-Accept 值 (RFC 6455 §4.2.2)。"""
    raw = key.encode("ascii") + _WS_MAGIC
    return base64.b64encode(hashlib.sha1(raw).digest()).decode("ascii")


# ═══════════════════════════════════════════════════════════════
#  WebSocketService
# ═══════════════════════════════════════════════════════════════

# 回调类型别名
WSConnectFunc = Callable[[WebSocketConnection, list[str], dict[str, str]], None]
WSMessageFunc = Callable[[WebSocketConnection, str | bytes], None]
WSCloseFunc = Callable[[WebSocketConnection, int], None]


class WebSocketService(BaseService):
    """WebSocket 服务端点。

    自动处理 HTTP Upgrade 握手，并在独立线程中运行消息循环。

    用法：
        def on_connect(conn, path, args):
            conn.send("Welcome!")

        def on_message(conn, msg):
            conn.send(f"Echo: {msg}")

        def on_close(conn, code):
            print(f"Closed with {code}")

        ws = WebSocketService(
            "/ws",
            on_connect=on_connect,
            on_message=on_message,
            on_close=on_close,
        )
        server = HTTPServer(services=[ws])
    """

    def __init__(
        self,
        remote_path: str,
        on_connect: Optional[WSConnectFunc] = None,
        on_message: Optional[WSMessageFunc] = None,
        on_close: Optional[WSCloseFunc] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: float = 0,
    ) -> None:
        self.routes = [
            Route(remote_path, ["GET"], "prefix", host, port),
        ]
        self.on_connect = on_connect
        self.on_message = on_message
        self.on_close = on_close
        self.timeout: float = timeout
        super().__init__(self.routes)

    def handle_GET(self, request: Handler, path: list[str], args: dict[str, str]) -> None:
        upgrade = request.headers.get("Upgrade", "").lower()
        if upgrade != "websocket":
            request.errsvc.handle(request, path, args, "GET", 400)
            return

        ws_key = request.headers.get("Sec-WebSocket-Key")
        if not ws_key:
            request.errsvc.handle(request, path, args, "GET", 400)
            return

        ws_version = request.headers.get("Sec-WebSocket-Version")
        if ws_version and ws_version != "13":
            request.send_error(400, "Unsupported WebSocket version")
            return

        # ── 握手 ──
        accept = compute_accept_key(ws_key)

        # 关闭 Nagle 算法，确保 HTTP 101 和后续 WS 帧不会被合并
        try:
            request.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        request.send_response(101, "Switching Protocols")
        request.send_header("Upgrade", "websocket")
        request.send_header("Connection", "Upgrade")
        request.send_header("Sec-WebSocket-Accept", accept)
        request.end_headers()
        request.wfile.flush()

        # 标记：后续 handle_one_request 不再读取 HTTP 请求
        request._ws_upgrade_complete = True  # type: ignore[attr-defined]
        request.close_connection = True

        # ── 创建连接 & 消息循环 ──
        conn = WebSocketConnection(request.rfile, request.wfile)
        conn.timeout = self.timeout

        if self.on_connect:
            self.on_connect(conn, path, args)

        # 始终运行消息循环（即使无 on_message），以处理 ping/pong/close
        try:
            while not conn.closed:
                opcode, payload = conn.recv()
                if opcode == WebSocketConnection.OP_CLOSE:
                    break
                if opcode in (WebSocketConnection.OP_PING, WebSocketConnection.OP_PONG):
                    continue
                if self.on_message:
                    self.on_message(conn, payload)  # type: ignore[arg-type]
        except (ConnectionError, OSError, TimeoutError):
            pass
        except Exception as e:
            logger.error("WebSocket error: %s", e)

        if self.on_close:
            try:
                self.on_close(conn, conn.close_code)
            except Exception:
                pass

        try:
            conn.close()
        except Exception:
            pass
