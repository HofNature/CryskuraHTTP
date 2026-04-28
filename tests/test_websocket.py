"""WebSocket 帧协议和握手测试。

单元测试为主，不依赖真实网络连接。
"""
from __future__ import annotations

import io
import struct
import base64
import hashlib
import time

import pytest

from cryskura.Services.WebSocket import (
    WebSocketConnection, compute_accept_key, _WS_MAGIC,
)


# ═══════════════════════════════════════════════════════════════
#  compute_accept_key
# ═══════════════════════════════════════════════════════════════

class TestComputeAcceptKey:

    def test_rfc6455_example(self):
        """RFC 6455 §4.2.2 示例 key 的 Accept 值。"""
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        expected = "6O1QA00UvMxmLjOutqRJUnF/S0A="
        assert compute_accept_key(key) == expected

    def test_deterministic(self):
        assert compute_accept_key("abc") == compute_accept_key("abc")

    def test_different_keys_differ(self):
        assert compute_accept_key("aaa") != compute_accept_key("bbb")


# ═══════════════════════════════════════════════════════════════
#  WebSocketConnection 帧协议
# ═══════════════════════════════════════════════════════════════

class TestWebSocketConnection:

    def _make_conn(self) -> tuple[WebSocketConnection, io.BytesIO, io.BytesIO]:
        rbuf = io.BytesIO()
        wbuf = io.BytesIO()
        conn = WebSocketConnection(rbuf, wbuf)
        return conn, rbuf, wbuf

    def _encode_frame(self, opcode: int, payload: bytes, fin: bool = True, masked: bool = False) -> bytes:
        """编码一帧原始字节。"""
        header = bytearray()
        header.append((0x80 if fin else 0) | opcode)
        mask_bit = 0x80 if masked else 0
        length = len(payload)
        if length < 126:
            header.append(mask_bit | length)
        elif length < 65536:
            header.append(mask_bit | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack("!Q", length))
        if masked:
            mask_key = b"\x01\x02\x03\x04"
            header.extend(mask_key)
            masked_payload = bytearray(payload)
            for i in range(len(masked_payload)):
                masked_payload[i] ^= mask_key[i % 4]
            header.extend(masked_payload)
        return bytes(header)

    def test_send_text(self):
        conn, _, wbuf = self._make_conn()
        conn.send("hello")
        conn.close()
        # 验证输出包含文本帧
        wbuf.seek(0)
        data = wbuf.read()
        assert len(data) > 0

    def test_send_binary(self):
        conn, _, wbuf = self._make_conn()
        conn.send(b"\x00\x01\x02")
        conn.close()

    def test_send_after_close_raises(self):
        conn, _, _ = self._make_conn()
        conn.close()
        with pytest.raises(ConnectionError):
            conn.send("data")

    def test_recv_text_frame(self):
        """构造一个客户端文本帧，验证 conn.recv() 能正确解析。"""
        rbuf = io.BytesIO()
        wbuf = io.BytesIO()
        conn = WebSocketConnection(rbuf, wbuf)

        # 写入一个文本帧
        frame = self._encode_frame(WebSocketConnection.OP_TEXT, b"hello world", masked=True)
        rbuf.write(frame)
        rbuf.seek(0)

        opcode, payload = conn.recv()
        assert opcode == WebSocketConnection.OP_TEXT
        assert payload == "hello world"

    def test_recv_binary_frame(self):
        rbuf = io.BytesIO()
        wbuf = io.BytesIO()
        conn = WebSocketConnection(rbuf, wbuf)

        frame = self._encode_frame(WebSocketConnection.OP_BINARY, b"\x00\x01\x02", masked=True)
        rbuf.write(frame)
        rbuf.seek(0)

        opcode, payload = conn.recv()
        assert opcode == WebSocketConnection.OP_BINARY
        assert payload == b"\x00\x01\x02"

    def test_recv_ping_auto_pong(self):
        """Ping 应自动回复 Pong。"""
        rbuf = io.BytesIO()
        wbuf = io.BytesIO()
        conn = WebSocketConnection(rbuf, wbuf)

        frame = self._encode_frame(WebSocketConnection.OP_PING, b"ping!", masked=True)
        rbuf.write(frame)
        rbuf.seek(0)

        opcode, payload = conn.recv()
        assert opcode == WebSocketConnection.OP_PING
        assert payload == b"ping!"

        # 验证发送了 Pong
        wbuf.seek(0)
        wdata = wbuf.read()
        assert len(wdata) > 0  # 包含 Pong 帧

    def test_recv_close_frame(self):
        rbuf = io.BytesIO()
        wbuf = io.BytesIO()
        conn = WebSocketConnection(rbuf, wbuf)

        # Close 帧：code=1000
        close_payload = struct.pack("!H", 1000) + b"bye"
        frame = self._encode_frame(WebSocketConnection.OP_CLOSE, close_payload, masked=True)
        rbuf.write(frame)
        rbuf.seek(0)

        opcode, payload = conn.recv()
        assert opcode == WebSocketConnection.OP_CLOSE
        assert conn.closed is True
        assert conn.close_code == 1000

    def test_send_close(self):
        conn, _, wbuf = self._make_conn()
        conn.close(code=1001, reason="going away")
        assert conn.closed is True
        assert conn.close_code == 1001

    def test_double_close_safe(self):
        conn, _, _ = self._make_conn()
        conn.close()
        conn.close()  # 不应抛异常

    def test_fragmented_message(self):
        """分片消息应自动拼装。"""
        rbuf = io.BytesIO()
        wbuf = io.BytesIO()
        conn = WebSocketConnection(rbuf, wbuf)

        # 第一个分片：opcode=TEXT, fin=False
        f1 = self._encode_frame(WebSocketConnection.OP_TEXT, b"hel", fin=False, masked=True)
        # 后续分片：opcode=CONTINUATION, fin=True
        f2 = self._encode_frame(WebSocketConnection.OP_CONTINUATION, b"lo", fin=True, masked=True)
        rbuf.write(f1 + f2)
        rbuf.seek(0)

        opcode, payload = conn.recv()
        assert opcode == WebSocketConnection.OP_TEXT
        assert payload == "hello"

    def test_large_frame_126(self):
        """payload 长度 126 使用 16-bit 扩展长度。"""
        rbuf = io.BytesIO()
        wbuf = io.BytesIO()
        conn = WebSocketConnection(rbuf, wbuf)

        payload = b"x" * 200
        frame = self._encode_frame(WebSocketConnection.OP_BINARY, payload, masked=True)
        rbuf.write(frame)
        rbuf.seek(0)

        opcode, data = conn.recv()
        assert opcode == WebSocketConnection.OP_BINARY
        assert len(data) == 200

    def test_unexpected_close(self):
        """连接中断应抛 ConnectionError。"""
        rbuf = io.BytesIO()
        wbuf = io.BytesIO()
        conn = WebSocketConnection(rbuf, wbuf)
        # 空流 → 读取失败
        with pytest.raises(ConnectionError):
            conn.recv()


# ═══════════════════════════════════════════════════════════════
#  WebSocketService 集成测试（握手 + echo）
# ═══════════════════════════════════════════════════════════════

class TestWebSocketServiceIntegration:

    def test_echo(self):
        """完整的 WebSocket echo 测试。"""
        import socket
        from cryskura.Services.WebSocket import WebSocketService
        from conftest import start_server, stop_server, get_free_port

        messages = []

        def on_connect(conn, path, args):
            conn.send("welcome")

        def on_message(conn, msg):
            messages.append(msg)
            conn.send(f"echo: {msg}")

        ws = WebSocketService("/ws", on_connect=on_connect, on_message=on_message)
        server, port = start_server(services=[ws])
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=10)
            try:
                # 手动 WebSocket 握手
                key = base64.b64encode(b"test-key-1234567").decode()
                req = (
                    f"GET /ws HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{port}\r\n"
                    f"Upgrade: websocket\r\n"
                    f"Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Key: {key}\r\n"
                    f"Sec-WebSocket-Version: 13\r\n"
                    f"\r\n"
                )
                sock.sendall(req.encode())

                # 读取 101 响应
                resp = b""
                while b"\r\n\r\n" not in resp:
                    resp += sock.recv(4096)
                assert b"101" in resp

                # 提取 leftover：101 头之后可能已经包含了 welcome 帧字节
                header_end = resp.index(b"\r\n\r\n") + 4
                leftover = resp[header_end:]

                # 辅助函数：可靠地读取一帧（支持 leftover）
                def recv_ws_frame(s, leftover=b""):
                    def _read_n(n):
                        nonlocal leftover
                        data = b""
                        while len(data) < n:
                            if leftover:
                                take = leftover[:n - len(data)]
                                data += take
                                leftover = leftover[len(take):]
                            else:
                                chunk = s.recv(n - len(data))
                                if not chunk:
                                    raise ConnectionError("Connection closed")
                                data += chunk
                        return data

                    header = _read_n(2)
                    opcode = header[0] & 0x0F
                    length = header[1] & 0x7F
                    if length == 126:
                        ext = _read_n(2)
                        length = struct.unpack("!H", ext)[0]
                    elif length == 127:
                        ext = _read_n(8)
                        length = struct.unpack("!Q", ext)[0]
                    data = _read_n(length)
                    return opcode, data

                # 辅助函数：构造 masked 帧
                def make_frame(opcode, payload, mask=b"\xAA\xBB\xCC\xDD"):
                    frame = bytearray()
                    frame.append(0x80 | opcode)
                    frame.append(0x80 | len(payload))
                    frame.extend(mask)
                    for i in range(len(payload)):
                        frame.append(payload[i] ^ mask[i % 4])
                    return bytes(frame)

                # 读取 welcome 消息
                opcode, payload = recv_ws_frame(sock, leftover=leftover)
                assert opcode == 0x1
                assert payload == b"welcome"

                # 发送 hi 消息
                sock.sendall(make_frame(0x1, b"hi"))

                # 读取 echo 响应
                opcode, payload = recv_ws_frame(sock, leftover=b"")
                assert opcode == 0x1
                assert payload == b"echo: hi"

                # 发送 Close
                sock.sendall(make_frame(0x8, struct.pack("!H", 1000)))
                time.sleep(0.1)
            finally:
                sock.close()
        finally:
            stop_server(server)

        assert "hi" in messages
