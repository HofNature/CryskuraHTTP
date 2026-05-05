"""公共类型定义。

Shared type aliases used across the cryskura package.
"""
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import http.client
    from .handler import HTTPRequestHandler

# 鉴权函数签名：(cookies, path, args, operation) -> bool
# Authentication function signature: (cookies, path, args, method) -> bool
AuthFunc = Callable[[dict[str, str], list[str], dict[str, str], str], bool]

# API 函数签名：(request, sub_path, args, headers, content, method) -> (code, headers, content)
# API handler function signature: (request, sub_path, args, headers, content, method) -> (status, headers, body)
APIFunc = Callable[
    ["HTTPRequestHandler", list[str], dict[str, str], "http.client.HTTPMessage", bytes, str],
    tuple[int, dict[str, str], bytes],
]

# 路径类型：URL 路径段列表 / URL path segments list
PathType = list[str]

# 查询参数类型：键值对 / Query-string key-value pairs
ArgsType = dict[str, str]
