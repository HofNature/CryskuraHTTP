# CryskuraHTTP

<div align="center">
    <img src="CryskuraHTTP.png" alt="CryskuraHTTP Logo" width="500">

帮助文档: [English](README.md) | [中文](README_zh.md)

CryskuraHTTP 是一个用 Python 实现的轻量级、可定制的 HTTP(s) 服务器，支持基本的 HTTP(s) 功能，包括文件服务和错误处理，并支持自定义服务、API 调用和鉴权。

</div>

## 特性

CryskuraHTTP 是 Python 内置 `http.server` 的扩展，零强制依赖。您可以利用它实现 Python HTTP 服务，而无需安装大型软件或库。它还可以用作文件共享工具，支持通过浏览器进行文件下载和上传，并可通过 Windows 右键菜单启动。

- **可定制服务**：通过扩展 `BaseService` 类轻松添加自定义服务，支持 `before_handle` / `after_handle` 中间件钩子。
- **可定制 API 调用**：使用 `APIService` 类定义自定义 API 调用。
- **API 路由装饰器**：使用 `APIRouter` 以装饰器方式注册多个 API 端点。
- **简化 API 装饰器**：使用 `SimpleAPIRouter` 自动处理 JSON 序列化，支持 URL 路径参数（`{param_name}` 语法）。
- **错误处理**：通过 `ErrorService` 类实现可定制的错误处理。
- **文件服务**：通过 `FileService` 类从指定目录提供文件服务。
- **文件上传**：通过 `FileService` 类处理通过 POST 请求的文件上传，支持上传大小限制。支持单次请求多文件上传。
- **网页服务**：通过 `PageService` 类提供网页服务，而不允许用户查看目录列表。
- **可定制路由**：使用 `Route` 类为您的服务定义自定义路由，支持主机名和端口过滤。
- **可定制身份验证**：为您的服务实现自定义身份验证。
- **CORS 跨域支持**：内置 `CORSService`，可配置允许的源、方法、请求头和 `expose_headers`。
- **健康检查**：内置 `HealthService`，用于监控和负载均衡器集成。
- **WebSocket 支持**：内置 `WebSocketService`，提供连接管理、帧协议、消息回调和可配置超时。
- **反向代理**：内置 `ReverseProxyService`，支持 HTTP 和 WebSocket 转发，路径重写，自动添加 `X-Forwarded-*` 请求头。
- **Gzip 压缩**：自动对文本类内容进行 gzip 响应压缩，64KB 自动 flush。
- **缓存支持**：自动为文件响应生成 ETag / Last-Modified 头，支持 304 Not Modified。
- **自动 uPnP 端口转发**：使用 uPnP 自动转发端口。
- **请求处理**：处理 GET、POST、HEAD、PUT、DELETE、PATCH、OPTIONS 请求。
- **可续传下载**：支持 Range 断点续传下载大文件，包括多段范围请求（multipart/byteranges）。
- **Zip 流式下载**：大文件 zip 通过 chunked 传输编码流式发送（HTTP/1.1），100MB 以下走内存（兼容 HTTP/1.0）。
- **重定向**：支持 301、302、307 和 308 重定向。
- **SSL 支持**：通过提供证书文件可选启用 SSL。明文 HTTP 请求到 HTTPS 端口时自动回复 301 重定向。
- **IPv6 支持**：完整 IPv6 支持，默认双栈模式（IPv6 socket 接受 IPv4 连接；使用 `--ipv6Only` 禁用）。
- **多线程服务器**：支持多线程请求处理以提高性能。
- **命令行界面**：通过命令行运行服务器并进行自定义设置。
- **右键支持**：支持在 Windows 上通过右键菜单启动服务器，提供三种模式：文件模式、网页模式和上传模式。
- **安全加固**：自动注入安全响应头（X-Content-Type-Options、X-Frame-Options、Referrer-Policy）、防符号链接穿越、防 HTTP 头注入、请求体大小限制等。
- **标准日志**：使用 Python `logging` 模块，便于日志管理，支持可选的访问日志。

该项目并非设计用于替代全规模、生产级 HTTP 服务器。它更适合小规模的 Web UI 开发或与 `pywebview` 和 `qtwebengine` 等工具一起使用。

## 要求

- Python 3.x（3.7+）
- 无强制依赖（可选：`upnpclient` 用于 uPnP）

## 安装

1. 使用 pip 安装包：

    ```sh
    pip install cryskura
    ```

2. 您也可以从 [GitHub Releases](https://github.com/HofNature/CryskuraHTTP/releases) 下载 whl 文件并使用 pip 安装：

    ```sh
    pip install cryskura-1.0-py3-none-any.whl
    ```

3. 如果您想修改源代码，可以克隆仓库并手动安装：

    ```sh
    git clone https://github.com/HofNature/CryskuraHTTP.git
    cd CryskuraHTTP
    python setup.py install
    ```

## 快速开始

### 启动服务器

使用默认设置启动服务器：

```python
from cryskura import Server
server = Server(interface="127.0.0.1", port=8080)
server.start()
```

这将在 `localhost` 上的端口 `8080` 启动服务器，并从当前目录提供文件服务。

或者，您可以从命令行运行服务器：

```sh
cryskura --interface 127.0.0.1 --port 8080 --path /path/to/serve
```

### 注册到右键菜单

您可以通过运行以下命令将服务器添加到 Windows 的右键菜单：

```sh
cryskura --addRightClick # 您也可以使用 -ar 作为简写
```

> **注意**：如果提供了 `--interface`、`--port`、`--browser` 等参数，当从右键菜单启动服务器时，将使用指定的设置。

如果您想从右键菜单中移除它，请运行：

```sh
cryskura --removeRightClick # 您也可以使用 -rr 作为简写
```

> **注意**：此功能仅在 Windows 上可用。对于 Windows 11 24h2 及以上版本，如果启用了 Sudo，它将自动调用；否则，您需要手动以管理员权限运行。

右键菜单提供三种模式：

- **网页模式**：提供网页服务，无目录列表（`-w` 参数）。
- **文件模式**：提供文件服务和目录列表，禁用上传。
- **上传模式**：提供文件服务和目录列表，启用上传（`-t` 参数）。

### 停止服务器

使用 Python API 时，您可以通过调用 `stop()` 方法停止服务器：

```python
server.stop()
```

> **注意**：只有多线程服务器可以使用此方法停止。非多线程服务器将阻塞线程，因此无法通过调用 `stop()` 方法停止。您可以通过在终端中按 `Ctrl+C` 停止非多线程服务器。

## 命令行界面

您可以通过运行以下命令获取命令行界面的帮助：

```sh
cryskura --help
```

| 参数 | 简写 | 说明 |
|------|------|------|
| `-h, --help` | | 显示帮助信息并退出 |
| `-i INTERFACE` | | 监听的接口（默认：`0.0.0.0`） |
| `-p PORT` | | 监听的端口（默认：`8080`） |
| `-d PATH` | | 要提供服务的目录路径 |
| `-n NAME` | | 服务器名称 |
| `-c CERTFILE` | | SSL 证书文件路径（PEM，需包含证书和私钥） |
| `-j PORT` | | HTTP 到 HTTPS 的重定向端口，需配合 `-c` 使用 |
| `-w` | `--webMode` | 启用 Web 模式（无目录列表） |
| `-r` | `--allowResume` | 允许可续传下载 |
| `-t` | `--allowUpload` | 允许文件上传 |
| `-f` | `--forcePort` | 强制使用被占用的端口 |
| `-b` | `--browser` | 启动后打开浏览器 |
| `-ba ADDR` | `--browserAddress` | 浏览器打开的地址 |
| `-u` | `--uPnP` | 启用 uPnP 端口转发 |
| `-al` | `--accessLog` | 启用访问日志 |
| `-6` | `--ipv6Only` | 禁用 IPv6 双栈（设置 `IPV6_V6ONLY=1`）。默认情况下，IPv6 socket 接受 IPv4 连接 |
| `-pf PATH` | `--pidFile` | PID 文件路径 |
| `-ar` | `--addRightClick` | 添加到 Windows 右键菜单 |
| `-rr` | `--removeRightClick` | 从 Windows 右键菜单移除 |
| `-v` | `--version` | 显示版本号 |

## 作为 Python 模块使用

### 自定义配置

您可以通过提供不同的参数来自定义服务器：

```python
from cryskura import Server
from cryskura.Services import FileService, PageService, RedirectService, APIService

# 创建服务
fs = FileService(r"/path/to/file", "/Files", allowResume=True, allowUpload=True)
rs = RedirectService("/Redirect", "https://www.google.com")
ps1 = PageService(r"/path/to/html/example.com", "/", host="example.com")
ps2 = PageService(r"/path/to/html/default", "/")

# 定义 API 函数
def APIFunc(request, path, args, headers, content, method):
    """
    用于处理 API 请求的示例函数。

    参数：
    - request：HTTP 请求对象。
    - path：API 端点之后的请求 URL 子路径。
    - args：URL 中的查询参数，字典形式。
    - headers：请求头（HTTPMessage）。
    - content：请求的主体内容，字节类型。
    - method：使用的 HTTP 方法（例如 "GET"、"POST"）。

    返回：
    - code：整数类型的 HTTP 状态码。
    - response_headers：要包含在响应中的头信息，字典形式。
    - response_content：响应的主体内容，字节类型。
    """
    code = 200
    response_headers = {"Content-Type": "text/plain"}
    response_content = b"API 调用"
    return code, response_headers, response_content

# 创建 API 服务
api = APIService("/API", func=APIFunc)

# 启动服务器
server = Server(services=[fs, rs, api, ps1, ps2], certfile="/path/to/cert.pem", uPnP=True)
server.start()
```

### 路由优先级

如果多个服务有冲突的路由，优先级由 `services` 参数中服务的顺序决定。列在前面的服务优先级最高，依此类推。

```python
from cryskura import Server
from cryskura.Services import FileService, PageService

fs = FileService(r"/path/to/files", "/files")
ps = PageService(r"/path/to/pages", "/")

server = Server(services=[fs, ps])
server.start()
```

在这种情况下，`FileService` 将优先处理冲突的路由。

### 身份验证

要实现自定义身份验证，您需要定义一个身份验证函数并将其传递给需要身份验证的服务：

```python
from cryskura import Server
from cryskura.Services import FileService

def AUTHFunc(cookies, path, args, operation):
    if args.get('passwd') == "passwd" and operation == "GET":
        return True
    elif args.get('passwd') == "admin" and operation == "POST":
        return True
    return False

fs = FileService(r"/path/to/files", "/files", allowResume=True, auth_func=AUTHFunc)
server = Server(services=[fs])
server.start()
```

### 自定义服务

要创建自定义服务，请扩展 `BaseService` 类并实现所需的方法：

```python
from cryskura.Services import BaseService, Route

class MyService(BaseService):
    def __init__(self):
        routes = [Route("/myservice", ["GET"], "exact")]
        super().__init__(routes)

    def handle_GET(self, request, path, args):
        request.send_response(200)
        request.send_header("Content-Type", "text/plain")
        request.end_headers()
        request.wfile.write(b"Hello from MyService!")
```

#### 中间件钩子

`BaseService` 提供 `before_handle` 和 `after_handle` 钩子：

```python
class MyService(BaseService):
    def before_handle(self, request, path, args, method):
        # 返回 int 可短路请求（作为状态码）
        # 返回 None 继续正常处理
        if not authorized(request):
            return 403  # 短路，返回 403
        return None

    def after_handle(self, request, path, args, method):
        # 在请求处理完成后调用
        pass  # 适用于日志、统计等场景
```

### 使用 APIRouter 装饰器

`APIRouter` 允许您以装饰器方式注册多个 API 端点：

```python
from cryskura import Server
from cryskura.Services import APIRouter

router = APIRouter()

@router.route("/hello", methods=["GET"])
def hello(request, path, args, headers, content, method):
    return 200, {"Content-Type": "text/plain"}, b"Hello!"

@router.route("/users", methods=["GET", "POST"])
def users(request, path, args, headers, content, method):
    return 200, {"Content-Type": "application/json"}, b'{"ok":true}'

@router.route("/files", methods=["GET"], prefix=True)
def files(request, path, args, headers, content, method):
    sub = "/".join(path)
    return 200, {}, f"Path: {sub}".encode()

# build() 生成服务列表，所有路由统一加 /api 前缀
server = Server(services=router.build("/api"))
server.start()
```

`@router.route()` 参数：

- `path`：路由路径（相对于 `build()` 的 base_path）。
- `methods`：允许的 HTTP 方法，默认 `["GET", "HEAD", "POST"]`。
- `prefix`：是否使用前缀匹配，默认 `False`（精确匹配）。
- `auth_func`：鉴权函数，同 `BaseService`。
- `length_limit`：请求体大小限制，默认 1MB。
- `host`：按请求 Host 头过滤，默认 `None`（匹配所有）。
- `port`：按请求端口过滤，默认 `None`（匹配所有）。

### 使用 SimpleAPIRouter（简化 JSON API）

`SimpleAPIRouter` 自动处理 JSON 序列化/反序列化，支持 URL 路径参数：

```python
from cryskura import Server
from cryskura.Services import SimpleAPIRouter

router = SimpleAPIRouter()

@router.get("/users/{user_id}")
def get_user(params, body):
    # params = {"user_id": "123"}
    return 200, {"user_id": params["user_id"], "name": "Alice"}

@router.post("/users")
def create_user(params, body):
    # body 已经是 JSON 解析后的对象
    return 201, {"created": body}

@router.put("/users/{user_id}")
def update_user(params, body):
    return 200, {"updated": params["user_id"], "data": body}

@router.delete("/users/{user_id}")
def delete_user(params, body):
    return 200, {"deleted": params["user_id"]}

# 注册所有路由，统一 /api 前缀
server = Server(services=router.build("/api"))
server.start()
```

**快捷装饰器：**

- `@router.get(path)` — GET + HEAD 端点
- `@router.post(path)` — POST 端点
- `@router.put(path)` — PUT 端点
- `@router.delete(path)` — DELETE 端点
- `@router.route(path, methods=[...])` — 通用，手动指定方法

**路径参数**使用 `{param_name}` 语法：`/users/{user_id}` → `params["user_id"]`

支持多个路径参数：`/users/{user_id}/posts/{post_id}` → `params["user_id"]`、`params["post_id"]`

**自动错误处理：**

- 无效 JSON 请求体 → 400 `{"error": "Invalid JSON body"}`
- 缺少路径参数 → 400 `{"error": "Missing path parameter(s): ..."}`
- 请求体过大 → 413 `{"error": "Request body too large"}`
- 处理函数抛出异常 → 500 `{"error": "..."}`
- 响应不可 JSON 序列化 → 500 `{"error": "Response is not JSON-serializable"}`

### WebSocket 服务

`WebSocketService` 提供完整的 WebSocket 支持：

```python
from cryskura import Server
from cryskura.Services import WebSocketService

def on_connect(conn, path, args):
    conn.send("欢迎连接 WebSocket 服务器！")

def on_message(conn, message):
    conn.send(f"回显: {message}")

def on_close(conn, code):
    print(f"连接关闭，代码: {code}")

ws = WebSocketService("/ws", on_connect=on_connect, on_message=on_message, on_close=on_close)
server = Server(services=[ws])
server.start()
```

`WebSocketConnection` 对象支持：

- `conn.send(data)` — 发送文本或二进制数据
- `conn.send_ping(data)` — 发送 ping 帧
- `conn.send_pong(data)` — 发送 pong 帧
- `conn.close(code, reason)` — 发起关闭握手
- `conn.recv()` — 接收完整消息（自动处理 ping/pong/close）
- `conn.timeout` — 设置读取超时（0 = 不设超时，默认值）

### 反向代理服务

`ReverseProxyService` 将请求转发到后端服务器，支持 HTTP 和 WebSocket：

```python
from cryskura import Server
from cryskura.Services import ReverseProxyService

# 将 /api 下的请求转发到后端
proxy = ReverseProxyService("/api", "http://localhost:3000")

# 转发 WebSocket 连接
ws_proxy = ReverseProxyService("/ws", "http://localhost:3000")

server = Server(services=[proxy, ws_proxy])
server.start()
```

参数：

- `remote_path`：路径前缀。
- `backend`：后端 URL（如 `http://localhost:3000`），支持 `https://` 协议。
- `methods`：允许的 HTTP 方法（默认：所有常见方法）。
- `timeout`：后端连接超时秒数（默认：30）。
- `preserve_host`：保留原始 Host 头（默认：False）。
- `max_request_body`：转发请求体最大大小（默认：10MB）。

代理会自动添加 `X-Forwarded-For`、`X-Forwarded-Host` 和 `X-Forwarded-Proto` 请求头。WebSocket 连接通过原始 socket 中继转发。

### FileService 参数说明

```python
FileService(local_path, remote_path, isFolder=True, allowResume=False,
            server_name="CryskuraHTTP", auth_func=None, allowUpload=False,
            host=None, port=None, upload_limit=0)
```

- `local_path`：本地目录或文件路径。
- `remote_path`：URL 路径前缀。
- `isFolder`：是否作为文件夹服务（前缀匹配）或单文件（精确匹配）。
- `allowResume`：启用 Range 断点续传下载。
- `server_name`：目录列表页面显示的服务器名称。
- `auth_func`：鉴权函数。
- `allowUpload`：启用 POST 文件上传。
- `host`：按请求 Host 头过滤。
- `port`：按请求端口过滤。
- `upload_limit`：上传文件大小限制（字节），`0` 表示不限制。超过限制返回 413。

### 服务器参数说明

```python
Server(interface="127.0.0.1", port=8080, services=None, error_service=None,
       server_name="CryskuraHTTP/1.0", forcePort=False, certfile=None,
       uPnP=False, max_request_body=0, access_log=False, ipv6_v6only=None)
```

- `interface`：监听的网络接口。
- `port`：监听的端口。
- `services`：服务实例列表。默认为 `FileService`，服务当前目录。
- `error_service`：自定义错误服务。默认为 `ErrorService`。
- `server_name`：响应中发送的服务器名称。
- `forcePort`：即使端口已被占用也强制使用。
- `certfile`：SSL 证书文件路径（PEM，需包含证书和私钥）。
- `uPnP`：启用 uPnP 端口转发。
- `max_request_body`：全局请求体大小限制（字节），`0` 表示不限制。超过限制返回 413，在请求到达服务之前生效。
- `access_log`：启用请求访问日志（默认：False）。
- `ipv6_v6only`：设置 socket 的 `IPV6_V6ONLY`。`True` 禁用双栈（仅 IPv6），`None` 保持系统默认（双栈）。

### CORS 跨域服务

使用 `CORSService` 处理跨域请求：

```python
from cryskura.Services import CORSService, FileService

cors = CORSService(
    allow_origins=["https://example.com"],  # 或 ["*"] 允许所有
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Custom-Header"],  # 可选
    allow_credentials=False,
    max_age=86400,
)

fs = FileService(r"/path/to/files", "/")
server = Server(services=[cors, fs])  # CORS 服务应放在最前面
server.start()
```

### 健康检查服务

使用 `HealthService` 提供监控端点：

```python
from cryskura.Services import HealthService, FileService

health = HealthService()  # 默认: GET /health
fs = FileService(r"/path/to/files", "/")
server = Server(services=[health, fs])
server.start()

# GET /health 返回: {"status": "ok", "uptime": 123.45}
```

参数：

- `remote_path`：端点路径（默认：`/health`）。
- `methods`：允许的方法（默认：`["GET", "HEAD"]`）。

### Zip 下载

在文件或目录路径后追加 `?zip` 即可以 zip 压缩包下载：

```
GET /documents?zip       → 下载 documents.zip
GET /report.pdf?zip      → 下载 report.pdf.zip
```

**内存优化：**

- 100MB 以下的压缩包读入内存发送 `Content-Length`（兼容 HTTP/1.0 和 HTTP/1.1）。
- 100MB 以上的压缩包在 HTTP/1.1 下通过 `Transfer-Encoding: chunked` 流式发送。
- HTTP/1.0 客户端请求超大压缩包时返回 `507 Insufficient Storage`。

### 文件信息端点

在路径后追加 `?info` 获取文件/目录元数据 JSON：

```
GET /documents/report.pdf?info
```

返回示例：

```json
{
    "name": "report.pdf",
    "path": "/documents/report.pdf",
    "size": 1048576,
    "modified": "2024-01-15T10:30:00+00:00",
    "created": "2024-01-15T10:30:00+00:00",
    "is_dir": false,
    "is_file": true,
    "is_symlink": false,
    "permissions": "0o644",
    "mime_type": "application/pdf"
}
```

对于目录，还会包含额外字段：

```json
{
    "name": "documents",
    "path": "/documents",
    "size": 4096,
    "is_dir": true,
    "is_file": false,
    "is_symlink": false,
    "permissions": "0o755",
    "mime_type": null,
    "item_count": 15,
    "file_count": 10,
    "dir_count": 5
}
```

## 使用 uPnP 客户端

CryskuraHTTP 包含一个内置的 uPnP 客户端，以便自动端口转发。这在路由器或防火墙后运行服务器时特别有用。

### 启用 uPnP

要启用 uPnP 端口转发，您可以在从命令行启动服务器时使用 `--uPnP` 标志：

```sh
cryskura --interface 0.0.0.0 --port 8080 --path /path/to/serve --uPnP
```

### 在 Python 中使用 uPnP

```python
from cryskura import Server

server = Server(interface="0.0.0.0", port=8080, uPnP=True)
server.start()
```

### 自定义 uPnP 配置

内置的 uPnP 客户端可以独立使用以满足自定义端口转发需求。

#### 初始化 uPnP 客户端

```python
from cryskura import uPnP

upnp_client = uPnP(interface="0.0.0.0")

if upnp_client.available:
    print("uPnP 客户端初始化成功。")
else:
    print("uPnP 客户端不可用。")
```

#### 添加端口映射

```python
if upnp_client.available:
    success, mappings = upnp_client.add_port_mapping(
        remote_port=8080,
        local_port=8080,
        protocol="TCP",
        description="CryskuraHTTP Server"
    )
    if success:
        for mapping in mappings:
            print(f"服务可用地址: {mapping[0]}:{mapping[1]}")
```

#### 移除所有端口映射

```python
if upnp_client.available:
    upnp_client.remove_port_mapping()
    print("端口映射已移除。")
```

### uPnP 故障排除

如果遇到 uPnP 问题，请确保：

- 您的路由器 **支持** uPnP 并且已 **启用**。
- 安装了 `upnpclient` 库：

    ```sh
    pip install upnpclient
    ```

    或者：

    ```sh
    pip install cryskura[upnp]
    ```

- 指定的网络接口是正确且可访问的。

## 许可证

本项目采用 MIT 许可证。有关详细信息，请参阅 [LICENSE](https://github.com/HofNature/CryskuraHTTP/blob/main/LICENSE) 文件。

## 贡献

欢迎贡献！请提交问题或拉取请求。

## 联系方式

如有任何问题或建议，请在 [GitHub](https://github.com/HofNature/CryskuraHTTP/issues) 上提交问题。

---

享受使用 CryskuraHTTP 吧！
