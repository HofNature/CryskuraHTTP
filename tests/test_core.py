"""Route、Compression 等核心工具的单元测试。

纯逻辑测试，不启动服务器，速度极快。
"""
from __future__ import annotations

import io
import gzip

import pytest

from cryskura.compression import (
    GzipFileWrapper, is_compressible, accepts_gzip, COMPRESSIBLE_TYPES,
)
from cryskura.Services.base_service import Route


# ═══════════════════════════════════════════════════════════════
#  Route 匹配
# ═══════════════════════════════════════════════════════════════

class TestRoute:

    # ── exact 匹配 ─────────────────────────────────────────────

    def test_exact_match_hit(self):
        r = Route("/api/v1", ["GET"], "exact")
        assert r.match(["api", "v1"], "GET") == (True, True)

    def test_exact_match_wrong_path(self):
        r = Route("/api/v1", ["GET"], "exact")
        can, exists = r.match(["api", "v1", "users"], "GET")
        assert can is False
        assert exists is False

    def test_exact_match_wrong_method(self):
        r = Route("/api/v1", ["GET"], "exact")
        can, exists = r.match(["api", "v1"], "POST")
        assert can is False
        assert exists is True  # 路径存在，方法不对

    # ── prefix 匹配 ────────────────────────────────────────────

    def test_prefix_exact_length(self):
        r = Route("/api", ["GET"], "prefix")
        assert r.match(["api"], "GET") == (True, True)

    def test_prefix_longer_path(self):
        r = Route("/api", ["GET"], "prefix")
        assert r.match(["api", "users", "1"], "GET") == (True, True)

    def test_prefix_no_match(self):
        r = Route("/api", ["GET"], "prefix")
        assert r.match(["other"], "GET") == (False, False)

    def test_prefix_method_mismatch(self):
        r = Route("/api", ["GET"], "prefix")
        can, exists = r.match(["api"], "POST")
        assert can is False
        assert exists is True

    # ── host / port 过滤 ───────────────────────────────────────

    def test_host_match(self):
        r = Route("/api", ["GET"], "prefix", host="example.com")
        assert r.match(["api"], "GET", host="example.com") == (True, True)
        assert r.match(["api"], "GET", host="other.com") == (False, False)
        assert r.match(["api"], "GET") == (False, False)

    def test_port_match(self):
        r = Route("/api", ["GET"], "prefix", port=8080)
        assert r.match(["api"], "GET", port=8080) == (True, True)
        assert r.match(["api"], "GET", port=9090) == (False, False)

    def test_host_and_port_combined(self):
        r = Route("/api", ["GET"], "prefix", host="example.com", port=8080)
        assert r.match(["api"], "GET", host="example.com", port=8080) == (True, True)
        assert r.match(["api"], "GET", host="example.com", port=9090) == (False, False)
        assert r.match(["api"], "GET", host="other.com", port=8080) == (False, False)

    def test_host_list(self):
        r = Route("/api", ["GET"], "prefix", host=["a.com", "b.com"])
        assert r.match(["api"], "GET", host="a.com") == (True, True)
        assert r.match(["api"], "GET", host="b.com") == (True, True)
        assert r.match(["api"], "GET", host="c.com") == (False, False)

    def test_port_list(self):
        r = Route("/api", ["GET"], "prefix", port=[8080, 9090])
        assert r.match(["api"], "GET", port=8080) == (True, True)
        assert r.match(["api"], "GET", port=9090) == (True, True)
        assert r.match(["api"], "GET", port=3000) == (False, False)

    # ── 构造参数校验 ───────────────────────────────────────────

    def test_string_path_auto_split(self):
        r = Route("/api/v1/users", ["GET"], "exact")
        assert r.path == ["api", "v1", "users"]

    def test_invalid_route_type_raises(self):
        with pytest.raises(ValueError, match="not a valid type"):
            Route("/api", ["GET"], "regex")

    def test_invalid_host_raises(self):
        with pytest.raises((ValueError, TypeError)):
            Route("/api", ["GET"], "prefix", host=123)

    def test_invalid_port_raises(self):
        with pytest.raises(ValueError):
            Route("/api", ["GET"], "prefix", port="bad")

    def test_trailing_slash_stripped(self):
        r = Route("/api/v1/", ["GET"], "exact")
        assert r.path == ["api", "v1"]


# ═══════════════════════════════════════════════════════════════
#  Compression: is_compressible
# ═══════════════════════════════════════════════════════════════

class TestIsCompressible:

    @pytest.mark.parametrize("ct", [
        "text/html", "text/css", "text/javascript", "text/plain",
        "application/json", "application/xml", "image/svg+xml",
    ])
    def test_compressible_types(self, ct):
        assert is_compressible(ct) is True

    def test_compressible_with_charset(self):
        assert is_compressible("text/html; charset=utf-8") is True

    @pytest.mark.parametrize("ct", [
        None, "", "image/png", "application/octet-stream",
        "video/mp4", "audio/ogg",
    ])
    def test_incompressible_types(self, ct):
        assert is_compressible(ct) is False


# ═══════════════════════════════════════════════════════════════
#  Compression: accepts_gzip
# ═══════════════════════════════════════════════════════════════

class TestAcceptsGzip:

    def test_simple_gzip(self):
        assert accepts_gzip("gzip") is True

    def test_multiple_encodings(self):
        assert accepts_gzip("deflate, gzip, br") is True

    def test_gzip_with_quality(self):
        assert accepts_gzip("gzip;q=1.0") is True

    def test_gzip_disabled_q0(self):
        assert accepts_gzip("gzip;q=0") is False

    def test_empty_string(self):
        assert accepts_gzip("") is False

    def test_none(self):
        assert accepts_gzip(None) is False

    def test_no_gzip(self):
        assert accepts_gzip("deflate, br") is False


# ═══════════════════════════════════════════════════════════════
#  Compression: GzipFileWrapper
# ═══════════════════════════════════════════════════════════════

class TestGzipFileWrapper:

    def test_write_and_close(self):
        buf = io.BytesIO()
        wrapper = GzipFileWrapper(buf)
        wrapper.write(b"Hello, world!")
        wrapper.close()
        # 解压验证
        buf.seek(0)
        result = gzip.decompress(buf.read())
        assert result == b"Hello, world!"

    def test_writable(self):
        buf = io.BytesIO()
        wrapper = GzipFileWrapper(buf)
        assert wrapper.writable() is True
        wrapper.close()

    def test_double_close_safe(self):
        buf = io.BytesIO()
        wrapper = GzipFileWrapper(buf)
        wrapper.close()
        wrapper.close()  # 不应抛异常

    def test_write_after_close_raises(self):
        buf = io.BytesIO()
        wrapper = GzipFileWrapper(buf)
        wrapper.close()
        with pytest.raises(ValueError):
            wrapper.write(b"data")

    def test_large_data_triggers_flush(self):
        """超过 flush_threshold 应自动 flush。"""
        buf = io.BytesIO()
        wrapper = GzipFileWrapper(buf, compresslevel=1)
        # 写入超过 64KB 阈值
        wrapper.write(b"x" * 100_000)
        wrapper.close()
        buf.seek(0)
        result = gzip.decompress(buf.read())
        assert len(result) == 100_000
