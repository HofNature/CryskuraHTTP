"""公共类型定义。"""
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import http.client
    from .Handler import HTTPRequestHandler

# 鉴权函数签名：(cookies, path, args, operation) -> bool
AuthFunc = Callable[[dict[str, str], list[str], dict[str, str], str], bool]

# API 函数签名：(request, sub_path, args, headers, content, method) -> (code, headers, content)
APIFunc = Callable[
    ["HTTPRequestHandler", list[str], dict[str, str], "http.client.HTTPMessage", bytes, str],
    tuple[int, dict[str, str], bytes],
]

# 路径类型
PathType = list[str]

# 查询参数类型
ArgsType = dict[str, str]
