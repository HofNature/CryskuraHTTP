"""文件上传处理（multipart/form-data），支持单次请求多文件，流式写入。"""
from __future__ import annotations

import os
import re
import json
import logging

from typing import TYPE_CHECKING
from http import HTTPStatus
from urllib.parse import quote, unquote

if TYPE_CHECKING:
    from ...Handler import HTTPRequestHandler

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────────────────────
_CHUNK = 64 * 1024          # 读取块大小 64KB
_READ_AHEAD = 128 * 1024    # 缓冲区预读上限 128KB
_MAX_HEAD_LEN = 8 * 1024    # part 头部最大长度 8KB（B3：防内存耗尽）

# 状态
_S_HEAD = 0   # 正在读取 part 头部
_S_BODY = 1   # 正在流式写入文件体
_S_DONE = 2   # 当前 part 结束，准备下一个


# ── 工具函数 ─────────────────────────────────────────────────────────────────
def _extract_boundary(content_type: str) -> str | None:
    """从 Content-Type 头中提取 multipart boundary。"""
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("boundary="):
            value = part.split("=", 1)[1].strip().strip('"')
            return value or None
    return None


_FILENAME_RE = re.compile(
    r"""filename\*\s*=\s*[^']+'\w*'([^;,\s]+)"""
    r"""|filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;,\s]+)""",
)


def _parse_filename(header_block: bytes) -> str | None:
    """从 part 头部字节中解析 filename。"""
    m = _FILENAME_RE.search(header_block.decode("utf-8", errors="replace"))
    if m:
        # B5: filename* (RFC 5987) 需要 URL 解码
        raw = m.group(1) or m.group(2) or m.group(3)
        return unquote(raw.strip('"')) or None
    return None


def _sanitize_filename(name: str) -> str | None:
    """清洗文件名，返回安全名称或 None（无效）。"""
    # B4: 拒绝空字节
    if "\x00" in name:
        return None
    # 只取 basename，防止路径穿越
    name = os.path.basename(name)
    if not name or name in (".", ".."):
        return None
    return name


# ── 流式 multipart 解析器 ────────────────────────────────────────────────────
def _read_multipart_upload(
    stream,
    length: int,
    boundary: bytes,
    dest_dir: str,
) -> tuple[list[str], list[str], bool]:
    """流式读取 multipart 请求体，逐文件写入磁盘。

    返回 (saved_files, errors, seen_file_part)。
    """
    start_boundary = b"--" + boundary          # 首 boundary：--boundary
    part_boundary  = b"\r\n--" + boundary      # 后续 boundary：\r\n--boundary
    bnd_len = len(part_boundary)

    buf = bytearray()
    remaining = length
    saved: list[str] = []          # B6: 存完整路径
    errors: list[str] = []
    seen_file = False

    # 当前 part 状态
    state = _S_HEAD
    fp = None
    cur_path = ""
    skip_body = False              # B1: 文件已存在时跳过 body 写入
    # 用于头部分块收集
    head_buf = bytearray()
    # 记录本次上传打开过的所有路径，用于异常时清理半成品文件
    opened_paths: set[str] = set()
    # 流是否已到末尾
    eof = False

    def _fill() -> None:
        """从 stream 读取数据填充 buffer，直到达到 _READ_AHEAD 或流耗尽。"""
        nonlocal remaining, eof
        if eof:
            return
        while len(buf) < _READ_AHEAD and remaining > 0:
            chunk = stream.read(min(_CHUNK, remaining))
            if not chunk:
                eof = True
                return
            buf.extend(chunk)
            remaining -= len(chunk)
        if remaining == 0:
            eof = True

    def _close_fp() -> None:
        nonlocal fp
        if fp:
            fp.close()
            fp = None

    def _cleanup_partial() -> None:
        """删除本次上传中写入一半的文件（仅删除未出现在 saved 中的）。"""
        _close_fp()
        saved_set = set(saved)  # B6: saved 已是完整路径
        for p in opened_paths:
            if p not in saved_set and os.path.exists(p):
                try:
                    os.remove(p)
                    logger.info("Cleaned up partial upload: %s", p)
                except OSError:
                    pass

    try:
        # ── 跳过请求体开头到首个 boundary 之间的 preamble ──────────────
        while True:
            _fill()
            idx = buf.find(start_boundary)
            if idx != -1:
                buf = buf[idx + len(start_boundary):]
                break
            if eof:
                return saved, errors, seen_file
            # buffer 过大但没找到 → 丢弃已扫描部分（保留尾部 bnd_len 字节）
            if len(buf) > bnd_len:
                buf = buf[-bnd_len:]

        state = _S_HEAD
        head_buf.clear()

        # ── 主循环 ──────────────────────────────────────────────────────
        while True:
            if state == _S_HEAD:
                _fill()
                # 在 buffer 中找 \r\n\r\n（头部结束标志）
                sep = buf.find(b"\r\n\r\n")
                if sep == -1:
                    if eof:
                        # 没有更多数据且头部不完整 → 截断
                        _cleanup_partial()
                        raise ConnectionError("Upload stream ended prematurely")
                    # B3: 检查头部长度限制
                    if len(head_buf) + len(buf) > _MAX_HEAD_LEN:
                        _cleanup_partial()
                        raise ValueError("Part header too large")
                    # 头部可能分块到达，把 buffer 暂存后继续读
                    head_buf.extend(buf)
                    buf.clear()
                    continue
                # 合并分块头部（也检查长度）
                if len(head_buf) + sep > _MAX_HEAD_LEN:
                    _cleanup_partial()
                    raise ValueError("Part header too large")
                head_buf.extend(buf[:sep])
                raw_name = _parse_filename(bytes(head_buf))
                buf = buf[sep + 4:]  # 跳过 \r\n\r\n
                head_buf.clear()

                if not raw_name:
                    errors.append("Missing filename in multipart part")
                    skip_body = True
                    state = _S_BODY
                    continue

                seen_file = True
                # B4: 清洗文件名（含 basename、null byte 检查）
                filename = _sanitize_filename(raw_name)
                if not filename:
                    errors.append(f"Invalid filename: {raw_name}")
                    skip_body = True
                    state = _S_BODY
                    continue

                cur_path = os.path.join(dest_dir, filename)
                try:
                    fp = open(cur_path, "xb")
                    opened_paths.add(cur_path)
                    skip_body = False
                except FileExistsError:
                    errors.append(f"{filename}: file already exists")
                    skip_body = True      # B1: 标记跳过，但仍需消费 body
                except OSError as e:
                    errors.append(f"{filename}: {e}")
                    skip_body = True      # B1: 同样跳过写入
                    state = _S_BODY
                    continue

                state = _S_BODY

            elif state == _S_BODY:
                _fill()
                safe = len(buf) - bnd_len
                if safe < 0:
                    safe = 0

                if safe == 0:
                    if eof:
                        # 流断开，数据不完整
                        _cleanup_partial()
                        raise ConnectionError("Upload stream ended prematurely")
                    # 数据不足，继续读
                    continue

                # 搜整个 buffer 找 boundary
                idx = buf.find(part_boundary)
                if idx == -1:
                    if eof:
                        # 流断开且无 boundary，数据不完整
                        _cleanup_partial()
                        raise ConnectionError("Upload stream ended prematurely")
                    # 没找到，写出 safe 区域的数据（这部分不可能是 boundary 起始）
                    if not skip_body:
                        fp.write(buf[:safe])
                    buf = buf[safe:]
                    continue

                # 找到了：boundary 前的数据写入文件
                if not skip_body:
                    fp.write(buf[:idx])
                    saved.append(cur_path)      # B6: 存完整路径
                _close_fp()
                buf = buf[idx + bnd_len:]
                state = _S_DONE

            elif state == _S_DONE:
                # 检查 boundary 后面的分隔符
                # part_boundary 匹配后 buf 已跳过 \r\n--boundary
                # 正常 part → buf 以 \r\n 开头
                # 结束     → buf 以 -- 开头 (--boundary-- 的 --\r\n)
                _fill()
                if eof and len(buf) == 0:
                    break
                if buf.startswith(b"\r\n"):
                    buf = buf[2:]
                    state = _S_HEAD
                    head_buf.clear()
                else:
                    # 以 -- 开头 = 结束边界；其他异常情况也视为结束
                    break

    except (OSError, ConnectionError):
        _cleanup_partial()
        raise
    finally:
        _close_fp()

    return saved, errors, seen_file


# ── 入口函数 ─────────────────────────────────────────────────────────────────
def handle_upload(
    request: HTTPRequestHandler,
    real_path: str,
    upload_limit: int,
) -> None:
    """处理文件上传 POST 请求，支持单次多文件。"""
    content_type = request.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return

    content_length = request.headers.get("Content-Length")
    if not content_length:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.LENGTH_REQUIRED)
        return

    # B2: 校验 Content-Length 合法性
    try:
        length = int(content_length)
    except ValueError:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return

    if upload_limit > 0 and length > upload_limit:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        return

    boundary = _extract_boundary(content_type)
    if not boundary:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return

    try:
        saved_files, errors, seen_file = _read_multipart_upload(
            request.rfile, length, boundary.encode(), real_path,
        )
    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
        raise
    except OSError as e:
        logger.error("Upload parse error: %s", e)
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return
    except ValueError as e:
        logger.error("Upload parse error: %s", e)
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return

    if not saved_files and not errors:
        request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        return

    if not saved_files and errors:
        if "already exists" in errors[0]:
            request.errsvc.handle(request, [], {}, "POST", HTTPStatus.CONFLICT)
        elif "Invalid filename" in errors[0] or "Missing filename" in errors[0]:
            request.errsvc.handle(request, [], {}, "POST", HTTPStatus.BAD_REQUEST)
        else:
            request.errsvc.handle(request, [], {}, "POST", HTTPStatus.INTERNAL_SERVER_ERROR)
        return

    # ── 返回结果 ────────────────────────────────────────────────────────
    if len(saved_files) == 1 and not errors:
        request.send_response(HTTPStatus.CREATED)
        loc = request.path + ("/" if request.path[-1] != "/" else "") + os.path.basename(saved_files[0])
        request.send_header("Location", quote(loc))
        request.send_header("Content-Length", "0")
        request.end_headers()
    else:
        result = {"saved": [os.path.basename(p) for p in saved_files], "count": len(saved_files)}
        if errors:
            result["errors"] = errors
        body = json.dumps(result, ensure_ascii=False).encode()
        status = HTTPStatus.CREATED if saved_files else HTTPStatus.INTERNAL_SERVER_ERROR
        if saved_files and errors:
            status = HTTPStatus.MULTI_STATUS
        request.send_response(status)
        request.send_header("Content-Type", "application/json; charset=utf-8")
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        request.wfile.write(body)
