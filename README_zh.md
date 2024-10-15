# CryskuraHTTP

CryskuraHTTP 是一个用 Python 实现的轻量级、可定制的 HTTP(s) 服务器。  
它支持基本的 HTTP(s) 功能，包括文件服务和错误处理，并可选支持 SSL。

帮助文档: [English](README.md) | [中文](README_zh.md)

## 特性

CryskuraHTTP 是 Python 内置 `http.server` 的扩展，依赖最小。您可以利用它来实现 Python HTTP 服务，而无需安装大型软件或库。

- **可定制服务**：通过扩展 `BaseService` 类轻松添加自定义服务。
- **可定制 API 调用**：使用 `APIService` 类定义自定义 API 调用。
- **错误处理**：通过 `ErrorService` 类实现可定制的错误处理。
- **文件服务**：从指定目录提供文件服务。
- **文件上传**：通过 POST 请求处理文件上传。
- **网页服务**：在不允许目录列表的情况下提供网页服务。
- **可定制路由**：为您的服务定义自定义路由。
- **可定制身份验证**：为您的服务实现自定义身份验证。
- **自动 uPnP 端口转发**：使用 uPnP 自动转发端口。
- **请求处理**：处理 GET、POST、HEAD 请求。
- **可续传下载**：在提供文件时支持大文件的可续传下载。
- **重定向**：支持 301 和 308 重定向。
- **SSL 支持**：通过提供证书文件可选启用 SSL。
- **多线程服务器**：支持多线程请求处理以提高性能。
- **命令行界面**：通过命令行运行服务器并进行自定义设置。

该项目并非旨在取代全规模、生产级 HTTP 服务器。相反，它非常适合小规模的 Web UI 开发或与 `pywebview` 和 `qtwebengine` 等工具一起使用。因此，不要期望它能处理数千个并发连接或具有负载均衡或缓存等高级功能。

## 要求

- Python 3.x
- `psutil` 库

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
server = HTTPServer(interface="127.0.0.1", port=8080)
server.start()
```

这将在 `localhost` 的 `8080` 端口启动服务器，并从当前目录提供文件服务。

或者，您可以从命令行运行服务器：

```sh
cryskura --interface 127.0.0.1 --port 8080 --path /path/to/serve
```

这将在 `localhost` 的 `8080` 端口启动服务器，并从 `/path/to/serve` 提供文件服务。

### 停止服务器

使用 Python API 时，可以通过调用 `stop()` 方法停止服务器：

```python
server.stop()
```

> **注意**：只有多线程服务器可以通过此方法停止。非多线程服务器将阻塞线程，因此无法通过调用 `stop()` 方法停止。您可以通过在终端中按 `Ctrl+C` 停止非多线程服务器。

使用命令行时，可以通过在终端中按 `Ctrl+C` 停止服务器。

## 命令行界面

您可以通过运行以下命令获取命令行界面的帮助：

```sh
cryskura --help
```

这将显示可用选项：

- `-h, --help`：显示帮助信息并退出。
- `-u, --uPnP`：启用 uPnP 端口转发。
- `-v, --version`：显示程序的版本号并退出。
- `-b, --browser`：启动服务器后打开浏览器。
- `-w, --webMode`：启用 Web 模式，这意味着只能访问文件，不能访问目录。
- `-f, --forcePort`：强制使用指定端口，即使该端口已被占用。
- `-t, --allowUpload`：允许文件上传。
- `-r, --allowResume`：允许续传下载。
- `-d PATH, --path PATH`：要提供服务的目录路径。
- `-n NAME, --name NAME`：服务器名称。
- `-p PORT, --port PORT`：监听端口。
- `-c CERTFILE, --certfile CERTFILE`：证书文件路径。
- `-i INTERFACE, --interface INTERFACE`：监听接口。
- `-j HTTP_TO_HTTPS, --http_to_https HTTP_TO_HTTPS`：将 HTTP 请求重定向到 HTTPS 的端口。

## 作为 Python 模块使用

### 自定义配置

您可以通过提供不同的参数来自定义服务器：

```python
from cryskura import Server
from cryskura.Services import FileService, PageService, RedirectService, APIService

# 创建服务
fs = FileService(r"/path/to/file", "/Files", allowResume=True, allowUpload=True)
rs = RedirectService("/Redirect", "https://www.google.com")
ps = PageService(r"/path/to/html", "/")

# 定义 API 函数
def APIFunc(request, path, args, method):
    print(f"API {method} {path} {args}")
    request.send_response(200)
    request.send_header("Content-Type", "text/plain")
    request.end_headers()
    request.wfile.write(b"API Call")

# 创建 API 服务
api = APIService("/API", func=APIFunc)

# 启动服务器
server = Server(services=[fs, rs, api, ps], certfile="/path/to/cert.pem", uPnP=True)
server.start()
```

这将启动具有以下服务的服务器：

- FileService：在 `/Files` 端点提供 `/path/to/file` 的文件服务，允许续传下载和文件上传。
- RedirectService：将 `/Redirect` 的请求重定向到 `https://www.google.com`。
- PageService：在根端点 `/` 提供 `/path/to/html` 的网页服务。
- APIService：在 `/API` 端点处理 API 调用，打印请求详情并响应纯文本消息。

以及以下设置：

- SSL 支持：使用位于 `/path/to/cert.pem` 的证书文件进行 SSL 加密。
- uPnP 端口转发：使用 uPnP 自动转发端口。

### 路由优先级

如果多个服务有冲突的路由，优先级由 `services` 参数中列出的顺序决定。首先列出的服务具有最高优先级，依此类推。

例如：

```python
from cryskura import Server
from cryskura.Services import FileService, PageService

fs = FileService(r"/path/to/files", "/files")
ps = PageService(r"/path/to/pages", "/")

server = Server(services=[fs, ps])
server.start()
```

在这种情况下，对于 `FileService` 和 `PageService` 之间冲突的路由，`FileService` 将具有优先级。因此，如果请求 `/files/index.html`，它将由 `FileService` 处理，而不是 `PageService`。

### 身份验证

要实现自定义身份验证，您需要定义一个身份验证函数并将其传递给需要身份验证的服务。身份验证函数应接受四个参数：`cookies`、`path`、`args` 和 `operation`。如果身份验证成功，应返回 `True`，否则返回 `False`。

以下是如何实现自定义身份验证的示例：

```python
from cryskura import Server
from cryskura.Services import FileService

# 定义身份验证函数
def AUTHFunc(cookies, path, args, operation):
    print(f"AUTH {operation} {path} {args}")
    if args.get('passwd') == "passwd" and operation == "GET":
        return True
    elif args.get('passwd') == "admin" and operation == "POST":
        return True
    return False

# 创建带有身份验证的文件服务
fs = FileService(r"/path/to/files", "/files", allowResume=True, auth_func=AUTHFunc)

# 启动服务器
server = Server(services=[fs])
server.start()
```

在此示例中，`AUTHFunc` 函数检查请求参数中的 `passwd` 参数以验证 GET 和 POST 请求。如果 `passwd` 参数为 GET 请求的 `passwd` 或 POST 请求的 `admin`，则身份验证成功。否则，身份验证失败。

您可以自定义 `AUTHFunc` 函数以实现自己的身份验证逻辑，例如检查 cookies、headers 或其他请求参数。

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

## 使用 uPnP 客户端

CryskuraHTTP 包含一个内置的 uPnP 客户端，以便自动端口转发。这在路由器或防火墙后运行服务器时特别有用。

### 启用 uPnP

要启用 uPnP 端口转发，可以在从命令行启动服务器时使用 `--uPnP` 标志：

```sh
cryskura --interface 0.0.0.0 --port 8080 --path /path/to/serve --uPnP
```

### 在 Python 中使用 uPnP

您还可以在使用 Python API 启动服务器时启用 uPnP 端口转发：

```python
from cryskura import Server

server = Server(interface="0.0.0.0", port=8080, uPnP=True)
server.start()
```

### 自定义 uPnP 配置

内置的 uPnP 客户端可以独立用于自定义端口转发需求。以下是如何在 Python 代码中直接使用 `uPnPClient` 类：

#### 初始化 uPnP 客户端

首先，您需要使用所需的网络接口初始化 `uPnPClient`：

```python
from cryskura import uPnP

# 为特定接口初始化 uPnP 客户端
upnp_client = uPnP(interface="0.0.0.0")
# 使用 0.0.0.0 表示所有 IPv4 接口

if upnp_client.available:
    print("uPnP 客户端初始化成功。")
else:
    print("uPnP 客户端不可用。")
```

#### 添加端口映射

要添加端口映射，请使用 `add_port_mapping` 方法：

```python
if upnp_client.available:
    success, mappings = upnp_client.add_port_mapping(
        remote_port=8080, 
        local_port=8080, 
        protocol="TCP", 
        description="CryskuraHTTP Server"
    )
    if success:
        print("端口映射添加成功。")
        for mapping in mappings:
            print(f"服务可在 {mapping[0]}:{mapping[1]} 访问")
    else:
        print("添加端口映射失败。")
```

这将在远程设备的 `8080` 端口到本地设备的 `8080` 端口添加一个使用 TCP 协议的端口映射。描述只是映射的标签，可以用于稍后识别它。

#### 移除所有端口映射

要移除端口映射，请使用 `remove_port_mapping` 方法：

```python
if upnp_client.available:
    upnp_client.remove_port_mapping()
    print("端口映射已移除。")
```

这将移除客户端添加的所有端口映射。最好在不再需要端口映射时将其移除。您可以将此代码放在脚本的清理部分或异常处理程序中，以确保即使发生错误也能移除映射。例如：

```python
try:
    Your code here...
except Exception as exception:
    upnp_client.remove_port_mapping()
    raise exception
```

这将确保即使在执行代码期间发生异常，也能移除端口映射。

### uPnP 故障排除

如果遇到 uPnP 问题，请确保：

- 您的路由器 **支持** uPnP 并且已 **启用**。
- 安装了 `upnpclient` 库。您可以使用以下命令安装：

    ```sh
    pip install upnpclient
    ```

    或者安装带有 `upnp` 额外功能的 `cryskura` 包：

    ```sh
    pip install cryskura[upnp]
    ```

- 指定的网络接口是正确且可访问的。

有关 `uPnPClient` 类及其方法的详细信息，请参阅 `uPnP.py` 文件中的源代码。

## 许可证

本项目采用 MIT 许可证。有关详细信息，请参阅 [LICENSE](https://github.com/HofNature/CryskuraHTTP/blob/main/LICENSE) 文件。

## 贡献

欢迎贡献！请打开一个 issue 或提交 pull request。

## 联系方式

如有任何问题或建议，请在 [GitHub](https://github.com/HofNature/CryskuraHTTP/issues) 上打开一个 issue。

---

享受使用 CryskuraHTTP 吧！