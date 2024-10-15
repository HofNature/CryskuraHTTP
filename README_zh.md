# CryskuraHTTP

CryskuraHTTP 是一个用 Python 实现的轻量级、可定制的 HTTP(s) 服务器。  
它支持基本的 HTTP(s) 功能，包括文件服务和错误处理，并可选支持 SSL。

帮助文档: [English](README.md) | [中文](README_zh.md)

## 功能

CryskuraHTTP 是 Python 内置 `http.server` 的扩展，依赖性极小。您可以利用它来实现 Python HTTP 服务，而无需安装大型软件或库。

- **可定制服务**：通过扩展 `BaseService` 类轻松添加自定义服务。
- **可定制 API 调用**：使用 `APIService` 类定义自定义 API 调用。
- **错误处理**：通过 `ErrorService` 类实现可定制的错误处理。
- **文件服务**：从指定目录提供文件服务。
- **网页服务**：提供网页服务，不允许目录列表。
- **可定制路由**：为您的服务定义自定义路由。
- **请求处理**：处理 GET、POST、HEAD 请求。
- **可恢复下载**：在提供文件服务时支持大文件的可恢复下载。
- **重定向**：支持 301 和 308 重定向。
- **SSL 支持**：通过提供证书文件可选启用 SSL。
- **线程服务器**：支持多线程请求处理以提高性能。
- **命令行界面**：通过命令行运行服务器并进行自定义设置。

该项目并非旨在取代全规模、生产级的 HTTP 服务器。相反，它非常适合小规模的 Web UI 开发或与 `pywebview` 和 `qtwebengine` 等工具一起使用。因此，不要期望它能处理数千个并发连接或具有负载均衡或缓存等高级功能。

## 要求

- Python 3.x
- `psutil` 库

## 安装

1. 从 [GitHub Releases](https://github.com/HofNature/CryskuraHTTP/releases) 下载 whl 文件并使用 pip 安装：

    ```sh
    pip install cryskura-1.0-py3-none-any.wh
    ```

2. 您也可以克隆仓库并手动安装：

    ```sh
    git clone https://github.com/HofNature/CryskuraHTTP.git
    cd CryskuraHTTP
    python setup.py install
    ```

## 使用

### 基本使用

使用默认设置启动服务器：

```python
from cryskura import Server
server = HTTPServer(interface="127.0.0.1", port=8080)
server.start()
```

这将在 `localhost` 上的端口 `8080` 启动服务器，并从当前目录提供文件服务。

或者，您可以从命令行运行服务器：

```sh
cryskura --interface 127.0.0.1 --port 8080 --path /path/to/serve
```

这将在 `localhost` 上的端口 `8080` 启动服务器，并从 `/path/to/serve` 提供文件服务。

### 停止服务器

使用 Python API 时，可以通过调用 `stop()` 方法停止服务器：

```python
server.stop()
```
> **注意**：只有线程服务器可以使用此方法停止。非线程服务器将阻塞线程，因此无法通过调用 `stop()` 方法停止。您可以通过在终端中按 `Ctrl+C` 停止非线程服务器。

使用命令行时，可以通过在终端中按 `Ctrl+C` 停止服务器。

### 命令行界面

您可以通过运行以下命令获取命令行界面的帮助：

```sh
cryskura --help
```

这将显示可用选项：

- `-h, --help`：显示帮助信息并退出。
- `-b, --browser`：启动服务器后打开浏览器。
- `-w, --webMode`：启用 Web 模式，这意味着只能访问文件，不能访问目录。
- `-f, --forcePort`：即使指定端口已被占用，也强制使用该端口。
- `-r, --allowResume`：允许恢复下载。

- `-d PATH, --path PATH`：要提供服务的目录路径。
- `-n NAME, --name NAME`：服务器名称。
- `-p PORT, --port PORT`：监听端口。
- `-c CERTFILE, --certfile CERTFILE`：证书文件路径。
- `-i INTERFACE, --interface INTERFACE`：监听接口。

### 自定义配置

您可以通过提供不同的参数来自定义服务器：

```python
from cryskura import Server
from cryskura.Services import FileService,PageService,RedirectService,APIService

# 创建服务
fs=FileService(r"/path/to/video","/Videos",allowResume=True)
rs=RedirectService("/Redirect","https://www.google.com")
ps=PageService(r"/path/to/html","/")

# 定义 API 函数
def APIFunc(request, path, args, method):
    print(f"API {method} {path} {args}")
    request.send_response(200)
    request.send_header("Content-Type", "text/plain")
    request.end_headers()
    request.wfile.write(b"API Call")

# 创建 API 服务
api=APIService("/API",func=APIFunc)

# 启动服务器
server=Server(services=[fs,rs,api,ps],certfile="/path/to/cert.pem")
server.start()
```

这将启动具有以下服务的服务器：

- FileService：在 `/Videos` 端点提供来自 `/path/to/video` 的文件服务，并支持可恢复下载。
- RedirectService：将 `/Redirect` 的请求重定向到 `https://www.google.com`。
- PageService：在根端点 `/` 提供来自 `/path/to/html` 的网页服务。
- APIService：在 `/API` 端点处理 API 调用，打印请求详情并响应纯文本消息。
- SSL 支持：使用位于 `/path/to/cert.pem` 的证书文件进行 SSL 加密。

### 路由优先级

如果多个服务具有冲突的路由，则优先级由 `services` 参数中列出的顺序决定。首先列出的服务将具有最高优先级，依此类推。

例如：

```python
from cryskura import Server
from cryskura.Services import FileService, PageService

fs = FileService(r"/path/to/files", "/files")
ps = PageService(r"/path/to/pages", "/")

server = Server(services=[fs,ps])
server.start()
```

在这种情况下，对于 `FileService` 和 `PageService` 之间冲突的路由，`FileService` 将具有优先级。因此，如果请求 `/files/index.html`，将由 `FileService` 处理，而不是 `PageService`。

## 自定义服务

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

## 许可证

该项目使用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 贡献

欢迎贡献！请提交 issue 或 pull request。

## 联系

如有任何问题或建议，请在 [GitHub](https://github.com/HofNature/CryskuraHTTP/issues) 上提交 issue。

---

享受使用 CryskuraHTTP 吧！