"""Handler 辅助模块：缓存、范围请求等。"""
from .cache import check_cache, add_cache_headers, check_and_inject_file_headers

__all__ = ["check_cache", "add_cache_headers", "check_and_inject_file_headers"]
