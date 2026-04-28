# CryskuraHTTP

<div align="center">
    <img src="CryskuraHTTP.png" alt="CryskuraHTTP Logo" width="500">

README: [English](README.md) | [中文](README_zh.md)

CryskuraHTTP is a lightweight, customizable HTTP(s) server implemented in Python that supports basic HTTP(s) functionalities, including serving files and handling errors, with support for custom services, API calls, and authentication.

</div>

## Features

CryskuraHTTP is an extension of Python's built-in `http.server`, with zero mandatory dependencies. You can leverage it to implement Python HTTP services without needing to install large software or libraries. It can also be used as a file sharing tool, supporting file serving and uploading through the browser, and can be launched from the Windows right-click menu.

- **Customizable Services**: Easily add custom services by extending the `BaseService` class, with `before_handle` / `after_handle` middleware hooks.
- **Customizable API Calls**: Define custom API calls with the `APIService` class.
- **API Router Decorator**: Register multiple API endpoints with `APIRouter` using decorators.
- **Simple API Router**: Simplified JSON API decorator with automatic JSON serialization and URL path parameters (`{param_name}` syntax).
- **Error Handling**: Customizable error handling via the `ErrorService` class.
- **File Serving**: Serve files from a specified directory via the `FileService` class.
- **File Uploading**: Handle file uploads via POST requests with the `FileService` class, with upload size limits. Supports multi-file upload in a single request.
- **WebPage Serving**: Serve web pages without allowing directory listing via the `PageService` class.
- **Customizable Routes**: Define custom routes for your services with the `Route` class. Supports host and port filtering.
- **Customizable Authentication**: Implement custom authentication for your services.
- **CORS Support**: Built-in `CORSService` for cross-origin resource sharing with configurable origins, methods, headers, and `expose_headers`.
- **Health Check**: Built-in `HealthService` for monitoring and load balancer integration.
- **WebSocket Support**: Built-in `WebSocketService` with connection management, frame protocol, message callbacks, and configurable timeout.
- **Reverse Proxy**: Built-in `ReverseProxyService` with HTTP and WebSocket forwarding, path rewriting, and `X-Forwarded-*` headers.
- **Gzip Compression**: Automatic gzip response compression for text-based content types with 64KB auto-flush.
- **Caching**: Automatic ETag / Last-Modified generation and 304 Not Modified handling for file responses.
- **Auto uPnP Port Forwarding**: Automatically forward ports using uPnP.
- **Request Handling**: Handle GET, POST, HEAD, PUT, DELETE, PATCH, OPTIONS requests.
- **Resumable Downloads**: Supports Range-based resumable downloads for large files, including multi-range (multipart/byteranges) requests.
- **Zip Streaming**: Zip downloads stream large archives via chunked transfer (HTTP/1.1), with HTTP/1.0 in-memory fallback for files under 100 MB.
- **Redirects**: Supports 301, 302, 307, and 308 redirects.
- **SSL Support**: Optionally enable SSL by providing a certificate file. Plain HTTP requests to the HTTPS port are automatically redirected with 301.
- **IPv6 Support**: Full IPv6 support with optional dual-stack mode (IPv6 sockets accept IPv4 by default; use `--ipv6Only` to disable).
- **Threaded Server**: Supports multi-threaded request handling for better performance.
- **Command-Line Interface**: Run the server from the command line with custom settings.
- **Right Click Support**: Supports right-click context menu for launching the server on Windows with three modes: File Mode, Web Mode, and Upload Mode.
- **Security Hardening**: Auto-injected security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy), symlink traversal protection, HTTP header injection prevention, request body size limits, and more.
- **Standard Logging**: Uses Python `logging` module for log management, with optional access logging.

This project is not designed to replace full-scale, production-grade HTTP servers. Instead, it is ideal for small-scale web UI development or for use alongside tools like `pywebview` and `qtwebengine`.

## Requirements

- Python 3.x (3.7+)
- No mandatory dependencies (optional: `upnpclient` for uPnP)

## Installation

1. Install the package using pip:

    ```sh
    pip install cryskura
    ```

2. You can also download whl file from [GitHub Releases](https://github.com/HofNature/CryskuraHTTP/releases) and install it using pip:

    ```sh
    pip install cryskura-1.0-py3-none-any.whl
    ```

3. Clone the repository and install manually if you want to modify the source code:

    ```sh
    git clone https://github.com/HofNature/CryskuraHTTP.git
    cd CryskuraHTTP
    python setup.py install
    ```

## Quick Start

### Starting the Server

To start the server with default settings:

```python
from cryskura import Server
server = Server(interface="127.0.0.1", port=8080)
server.start()
```

This will start the server on `localhost` at port `8080` and serve files from the current directory.

Or you can run the server from the command line:

```sh
cryskura --interface 127.0.0.1 --port 8080 --path /path/to/serve
```

This will start the server on `localhost` at port `8080` and serve files from `/path/to/serve`.

### Register to Right-Click Menu

You can add the server to the right-click context menu on Windows by running:

```sh
cryskura --addRightClick # You can also use -ar as a short form
```

> **Note**: If arguments like `--interface`, `--port`, `--browser`, etc., are provided, the server will start with the specified settings when launched from the right-click menu.

If you want to remove it from the right-click menu, run:

```sh
cryskura --removeRightClick # You can also use -rr as a short form
```

> **Note**: This feature is only available on Windows. For Windows 11 24h2 and above, if Sudo is enabled, it will be called automatically; otherwise, you need to run it manually with administrator privileges.

The right-click menu provides three modes:

- **Web Mode**: Serves web pages without directory listing (`-w` flag).
- **File Mode**: Serves files with directory listing, upload disabled.
- **Upload Mode**: Serves files with directory listing and upload enabled (`-t` flag).

### Stopping the Server

When using the Python API, you can stop the server by calling the `stop()` method:

```python
server.stop()
```

> **Note**: Only the threaded server can be stopped using this method. The non-threaded server will block the thread, so it cannot be stopped by calling the `stop()` method. You can stop the non-threaded server by pressing `Ctrl+C` in the terminal.

When using the command line, you can stop the server by pressing `Ctrl+C` in the terminal.

## Command-Line Interface

You can get help on the command-line interface by running:

```sh
cryskura --help
```

This will show the available options:

| Flag | Short | Description |
|------|-------|-------------|
| `-h, --help` | | Show help message and exit. |
| `-i INTERFACE` | | The interface to listen on (default: `0.0.0.0`). |
| `-p PORT` | | The port to listen on (default: `8080`). |
| `-d PATH` | | The path to the directory to serve. |
| `-n NAME` | | The name of the server. |
| `-c CERTFILE` | | Path to the SSL certificate file (PEM, must include both certificate and private key). |
| `-j PORT` | | Port to redirect HTTP requests to HTTPS. Requires `-c` to be set. |
| `-w` | `--webMode` | Enable web mode (no directory listing). |
| `-r` | `--allowResume` | Allow resumable (Range) downloads. |
| `-t` | `--allowUpload` | Allow file upload. |
| `-f` | `--forcePort` | Force use of port even if in use. |
| `-b` | `--browser` | Open the browser after starting. |
| `-ba ADDR` | `--browserAddress` | The address to open in the browser. |
| `-u` | `--uPnP` | Enable uPnP port forwarding. |
| `-al` | `--accessLog` | Enable access logging. |
| `-6` | `--ipv6Only` | Disable IPv6 dual-stack (set `IPV6_V6ONLY=1`). By default, IPv6 sockets accept IPv4 connections. |
| `-pf PATH` | `--pidFile` | Path to PID file. |
| `-ar` | `--addRightClick` | Add to Windows right-click menu. |
| `-rr` | `--removeRightClick` | Remove from Windows right-click menu. |
| `-v` | `--version` | Show version number. |

## Using as a Python Module

### Custom Configuration

You can customize the server by providing different parameters:

```python
from cryskura import Server
from cryskura.Services import FileService, PageService, RedirectService, APIService

# Create services
fs = FileService(r"/path/to/file", "/Files", allowResume=True, allowUpload=True)
rs = RedirectService("/Redirect", "https://www.google.com")
ps1 = PageService(r"/path/to/html/example.com", "/", host="example.com")
ps2 = PageService(r"/path/to/html/default", "/")

# Define the API function
def APIFunc(request, path, args, headers, content, method):
    """
    A sample API function for handling API requests.

    Parameters:
    - request: The HTTP request object.
    - path: The sub-path of the request URL after the API endpoint.
    - args: The query parameters from the URL as a dictionary.
    - headers: The headers from the request as an HTTPMessage.
    - content: The body content of the request as bytes.
    - method: The HTTP method used (e.g., "GET", "POST").

    Returns:
    - code: An integer HTTP status code (e.g., 200 for success).
    - response_headers: A dictionary of headers to include in the response.
    - response_content: The body content to send in the response as bytes.
    """
    code = 200
    response_headers = {"Content-Type": "text/plain"}
    response_content = b"API Call"
    return code, response_headers, response_content

# Create API service
api = APIService("/API", func=APIFunc)

# Start the server
server = Server(services=[fs, rs, api, ps1, ps2], certfile="/path/to/cert.pem", uPnP=True)
server.start()
```

This will start the server with the following services:

- **FileService**: Serves files from `/path/to/file` at the `/Files` endpoint, allowing resumable downloads and file uploads.
- **RedirectService**: Redirects requests from `/Redirect` to `https://www.google.com`.
- **PageService 1**: Hosts web pages located in `/path/to/html/example.com` and serves them at the root endpoint `/` only when the user requests with domain `example.com`.
- **PageService 2**: Hosts default web pages located in `/path/to/html/default` and serves them at the root endpoint `/` for all other requests.
- **APIService**: Handles API calls at the `/API` endpoint.

And with the following settings:

- **SSL Support**: Uses the certificate file located at `/path/to/cert.pem` for SSL encryption.
- **uPnP Port Forwarding**: Automatically forwards ports using uPnP.

### Route Priority

If multiple services have conflicting routes, the priority is determined by the order in which the services are listed in the `services` parameter. The service listed first will have the highest priority, and so on.

For example:

```python
from cryskura import Server
from cryskura.Services import FileService, PageService

fs = FileService(r"/path/to/files", "/files")
ps = PageService(r"/path/to/pages", "/")

server = Server(services=[fs, ps])
server.start()
```

In this case, `FileService` will have priority over `PageService` for routes that conflict between the two services.

### Authentication

To implement custom authentication, you need to define an authentication function and pass it to the service that requires authentication. The authentication function should accept four parameters: `cookies`, `path`, `args`, and `operation`. It should return `True` if the authentication is successful, and `False` otherwise.

```python
from cryskura import Server
from cryskura.Services import FileService

# Define authentication function
def AUTHFunc(cookies, path, args, operation):
    if args.get('passwd') == "passwd" and operation == "GET":
        return True
    elif args.get('passwd') == "admin" and operation == "POST":
        return True
    return False

# Create a file service with authentication
fs = FileService(r"/path/to/files", "/files", allowResume=True, auth_func=AUTHFunc)

# Start the server
server = Server(services=[fs])
server.start()
```

### Custom Services

To create a custom service, extend the `BaseService` class and implement the required methods:

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

#### Middleware Hooks

`BaseService` provides `before_handle` and `after_handle` hooks:

```python
class MyService(BaseService):
    def before_handle(self, request, path, args, method):
        # Return an int to short-circuit the request (used as status code)
        # Return None to continue normal processing
        if not authorized(request):
            return 403  # short-circuit with 403
        return None

    def after_handle(self, request, path, args, method):
        # Called after the request handler completes
        pass  # useful for logging, metrics, etc.
```

### Using the APIRouter Decorator

`APIRouter` allows you to register multiple API endpoints using decorators for cleaner code:

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
    # prefix=True matches /api/files/a/b/c and sub-paths
    sub = "/".join(path)
    return 200, {}, f"Path: {sub}".encode()

# build() generates service list, all routes share /api prefix
server = Server(services=router.build("/api"))
server.start()
```

`@router.route()` parameters:

- `path`: Route path (relative to the `build()` base_path).
- `methods`: Allowed HTTP methods, default `["GET", "HEAD", "POST"]`.
- `prefix`: Use prefix matching, default `False` (exact match).
- `auth_func`: Authentication function, same as `BaseService`.
- `length_limit`: Request body size limit, default 1MB.
- `host`: Filter by request Host header, default `None` (matches all).
- `port`: Filter by request port, default `None` (matches all).

### Using the SimpleAPIRouter (Simplified JSON API)

`SimpleAPIRouter` automatically handles JSON serialization/deserialization. Your function only needs to accept `(params, body)` and return `(status_code, response_dict)`:

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
    # body is already JSON-parsed
    return 201, {"created": body}

@router.put("/users/{user_id}")
def update_user(params, body):
    return 200, {"updated": params["user_id"], "data": body}

@router.delete("/users/{user_id}")
def delete_user(params, body):
    return 200, {"deleted": params["user_id"]}

# Register all routes with /api prefix
server = Server(services=router.build("/api"))
server.start()
```

**Quick decorator methods:**

- `@router.get(path)` — GET + HEAD endpoint
- `@router.post(path)` — POST endpoint
- `@router.put(path)` — PUT endpoint
- `@router.delete(path)` — DELETE endpoint
- `@router.route(path, methods=[...])` — Generic, specify methods manually

**Path parameters** use `{param_name}` syntax: `/users/{user_id}` → `params["user_id"]`

Multiple path parameters are supported: `/users/{user_id}/posts/{post_id}` → `params["user_id"]`, `params["post_id"]`

**Automatic error handling:**

- Invalid JSON body → 400 `{"error": "Invalid JSON body"}`
- Missing path parameter → 400 `{"error": "Missing path parameter(s): ..."}`
- Request body too large → 413 `{"error": "Request body too large"}`
- Handler exception → 500 `{"error": "..."}`
- Non-serializable response → 500 `{"error": "Response is not JSON-serializable"}`

### WebSocket Service

`WebSocketService` provides full WebSocket support with connection management and message callbacks:

```python
from cryskura import Server
from cryskura.Services import WebSocketService

def on_connect(conn, path, args):
    conn.send("Welcome to the WebSocket server!")

def on_message(conn, message):
    conn.send(f"Echo: {message}")

def on_close(conn, code):
    print(f"Connection closed with code {code}")

ws = WebSocketService("/ws", on_connect=on_connect, on_message=on_message, on_close=on_close)
server = Server(services=[ws])
server.start()
```

The `WebSocketConnection` object supports:

- `conn.send(data)` — Send text or binary data
- `conn.send_ping(data)` — Send a ping frame
- `conn.send_pong(data)` — Send a pong frame
- `conn.close(code, reason)` — Initiate close handshake
- `conn.recv()` — Receive a complete message (auto-handles ping/pong/close)
- `conn.timeout` — Set read timeout (0 = no timeout, default)

### Reverse Proxy Service

`ReverseProxyService` forwards requests to a backend server, supporting both HTTP and WebSocket:

```python
from cryskura import Server
from cryskura.Services import ReverseProxyService

# Forward all /api requests to a backend
proxy = ReverseProxyService("/api", "http://localhost:3000")

# Forward WebSocket connections
ws_proxy = ReverseProxyService("/ws", "http://localhost:3000")

server = Server(services=[proxy, ws_proxy])
server.start()
```

Parameters:

- `remote_path`: The path prefix to match.
- `backend`: The backend URL (e.g., `http://localhost:3000`). Supports `https://` scheme.
- `methods`: Allowed HTTP methods (default: all common methods).
- `timeout`: Backend connection timeout in seconds (default: 30).
- `preserve_host`: Keep the original Host header (default: False).
- `max_request_body`: Max request body size to forward (default: 10MB).

The proxy automatically adds `X-Forwarded-For`, `X-Forwarded-Host`, and `X-Forwarded-Proto` headers. WebSocket connections are proxied via raw socket relay.

### FileService Parameters

```python
FileService(local_path, remote_path, isFolder=True, allowResume=False,
            server_name="CryskuraHTTP", auth_func=None, allowUpload=False,
            host=None, port=None, upload_limit=0)
```

- `local_path`: Local directory or file path to serve.
- `remote_path`: URL path prefix.
- `isFolder`: Whether to serve as a folder (prefix match) or single file (exact match).
- `allowResume`: Enable Range-based resumable downloads.
- `server_name`: Server name shown in directory listing pages.
- `auth_func`: Authentication function.
- `allowUpload`: Enable file upload via POST.
- `host`: Filter by request Host header.
- `port`: Filter by request port.
- `upload_limit`: Upload file size limit in bytes, `0` means unlimited. Returns 413 when exceeded.

### Server Parameters

```python
Server(interface="127.0.0.1", port=8080, services=None, error_service=None,
       server_name="CryskuraHTTP/1.0", forcePort=False, certfile=None,
       uPnP=False, max_request_body=0, access_log=False, ipv6_v6only=None)
```

- `interface`: Network interface to listen on.
- `port`: Port to listen on.
- `services`: List of service instances. Defaults to a `FileService` serving the current directory.
- `error_service`: Custom error service. Defaults to `ErrorService`.
- `server_name`: Server name sent in responses.
- `forcePort`: Force use of port even if already in use.
- `certfile`: Path to SSL certificate file (PEM, must include both certificate and private key).
- `uPnP`: Enable uPnP port forwarding.
- `max_request_body`: Global request body size limit in bytes, `0` means unlimited. Returns 413 before the request reaches any service.
- `access_log`: Enable request access logging (default: False).
- `ipv6_v6only`: Set `IPV6_V6ONLY` on the socket. `True` disables dual-stack (IPv6 only), `None` keeps the OS default (dual-stack).

### CORS Service

Use `CORSService` to handle cross-origin requests:

```python
from cryskura.Services import CORSService, FileService

cors = CORSService(
    allow_origins=["https://example.com"],  # or ["*"] for all
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Custom-Header"],  # optional
    allow_credentials=False,
    max_age=86400,
)

fs = FileService(r"/path/to/files", "/")
server = Server(services=[cors, fs])  # CORS service should be first
server.start()
```

### Health Check Service

Use `HealthService` for monitoring endpoints:

```python
from cryskura.Services import HealthService, FileService

health = HealthService()  # Default: GET /health
fs = FileService(r"/path/to/files", "/")
server = Server(services=[health, fs])
server.start()

# GET /health returns: {"status": "ok", "uptime": 123.45}
```

Parameters:

- `remote_path`: Endpoint path (default: `/health`).
- `methods`: Allowed methods (default: `["GET", "HEAD"]`).

### Zip Downloads

Append `?zip` to any file or directory path to download it as a zip archive:

```
GET /documents?zip       → downloads documents.zip
GET /report.pdf?zip      → downloads report.pdf.zip
```

**Memory optimization:**

- Archives under 100 MB are read into memory with `Content-Length` (compatible with HTTP/1.0 and HTTP/1.1).
- Archives over 100 MB are streamed via `Transfer-Encoding: chunked` on HTTP/1.1.
- HTTP/1.0 clients requesting oversized archives receive a `507 Insufficient Storage` response.

### File Info Endpoint

Append `?info` to get file/directory metadata as JSON:

```
GET /documents/report.pdf?info
```

Returns:

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

For directories, additional fields are included:

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

## Using the uPnP Client

CryskuraHTTP includes a built-in uPnP client to facilitate automatic port forwarding. This can be particularly useful when running the server behind a router or firewall.

### Enabling uPnP

To enable uPnP port forwarding, you can use the `--uPnP` flag when starting the server from the command line:

```sh
cryskura --interface 0.0.0.0 --port 8080 --path /path/to/serve --uPnP
```

### Using uPnP in Python

You can also enable uPnP port forwarding when starting the server using the Python API:

```python
from cryskura import Server

server = Server(interface="0.0.0.0", port=8080, uPnP=True)
server.start()
```

### Custom uPnP Configuration

The built-in uPnP client can be used independently for custom port forwarding needs.

#### Initializing the uPnP Client

```python
from cryskura import uPnP

# Initialize uPnP client for a specific interface
upnp_client = uPnP(interface="0.0.0.0")

if upnp_client.available:
    print("uPnP client initialized successfully.")
else:
    print("uPnP client is not available.")
```

#### Adding a Port Mapping

```python
if upnp_client.available:
    success, mappings = upnp_client.add_port_mapping(
        remote_port=8080,
        local_port=8080,
        protocol="TCP",
        description="CryskuraHTTP Server"
    )
    if success:
        print("Port mapping added successfully.")
        for mapping in mappings:
            print(f"Service is available at {mapping[0]}:{mapping[1]}")
    else:
        print("Failed to add port mapping.")
```

#### Removing All Port Mappings

```python
if upnp_client.available:
    upnp_client.remove_port_mapping()
    print("Port mapping removed.")
```

### Troubleshooting uPnP

If you encounter issues with uPnP, ensure that:

- Your router **supports** uPnP and has it **enabled**.
- The `upnpclient` library is installed. You can install it using:

    ```sh
    pip install upnpclient
    ```

    or install the `cryskura` package with the `upnp` extra:

    ```sh
    pip install cryskura[upnp]
    ```

- The network interface specified is correct and accessible.

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/HofNature/CryskuraHTTP/blob/main/LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Contact

For any questions or suggestions, please open an issue here on [GitHub](https://github.com/HofNature/CryskuraHTTP/issues).

---

Enjoy using CryskuraHTTP!
