# CryskuraHTTP

CryskuraHTTP is a lightweight, customizable HTTP(s) server implemented in Python.  
It supports basic HTTP(s) functionalities, including serving files and handling errors, with optional SSL support.

## Features

CryskuraHTTP is an extension of Python's built-in `http.server`, with minimal dependencies. You can leverage it to implement Python HTTP services without needing to install large software or libraries.

- **Customizable Services**: Easily add custom services by extending the `BaseService` class.
- **Customizable API Calls**: Define custom API calls with the `APIService` class.
- **Error Handling**: Customizable error handling via the `ErrorService` class.
- **File Serving**: Serve files from a specified directory.
- **WebPage Serving**: Serve web pages without allowing directory listing.
- **Customizable Routes**: Define custom routes for your services.
- **Request Handling**: Handle GET, POST, HEAD requests.
- **Resumable Downloads**: Supports resumable downloads for large files when serving files.
- **Redirects**: Supports 301 and 308 redirects.
- **SSL Support**: Optionally enable SSL by providing a certificate file.
- **Threaded Server**: Supports multi-threaded request handling for better performance.
- **Command-Line Interface**: Run the server from the command line with custom settings.

This project is not designed to replace full-scale, production-grade HTTP servers. Instead, it is ideal for small-scale web UI development or for use alongside tools like `pywebview` and `qtwebengine`. So don't expect it to handle thousands of concurrent connections or to have advanced features like load balancing or caching.

## Requirements

- Python 3.x
- `psutil` library

## Installation

1. Download whl file from [GitHub Releases](https://github.com/HofNature/CryskuraHTTP/releases) and install it using pip:

    ```sh
    pip install cryskura-1.0-py3-none-any.wh
    ```

2. You can also clone the repository and install manually:

    ```sh
    git clone https://github.com/HofNature/CryskuraHTTP.git
    cd CryskuraHTTP
    python setup.py install
    ```

## Usage

### Basic Usage

To start the server with default settings:

```python
from cryskura import Server
server = HTTPServer(interface="127.0.0.1", port=8080)
server.start()
```

This will start the server on `localhost` at port `8080` and serve files from the current directory.

Or you can run the server from the command line:

```sh
cryskura --interface 127.0.0.1 --port 8080 --path /path/to/serve
```

This will start the server on `localhost` at port `8080` and serve files from `/path/to/serve`.

### Stopping the Server

When using the Python API, you can stop the server by calling the `stop()` method:

```python
server.stop()
```
> **Note**: Only the threaded server can be stopped using this method. The non-threaded server will block the thread, so it cannot be stopped by calling the `stop()` method. You can stop the non-threaded server by pressing `Ctrl+C` in the terminal.

When using the command line, you can stop the server by pressing `Ctrl+C` in the terminal.

### Command-Line Interface

You can get help on the command-line interface by running:

```sh
cryskura --help
```

This will show the available options:

- `-h, --help`: Show help message and exit.
- `-b, --browser`: Open the browser after starting the server.
- `-w, --webMode`: Enable web mode, which means only files can be accessed, not directories.
- `-f, --forcePort`: Force to use the specified port even if it is already in use.
- `-r, --allowResume`: Allow resume download.

- `-d PATH, --path PATH`: The path to the directory to serve.
- `-n NAME, --name NAME`: The name of the server.
- `-p PORT, --port PORT`: The port to listen on.
- `-c CERTFILE, --certfile CERTFILE`: The path to the certificate file.
- `-i INTERFACE, --interface INTERFACE`: The interface to listen on.

### Custom Configuration

You can customize the server by providing different parameters:

```python
from cryskura import Server
from cryskura.Services import FileService,PageService,RedirectService,APIService

# Create services
fs=FileService(r"/path/to/video","/Videos",allowResume=True)
rs=RedirectService("/Redirect","https://www.google.com")
ps=PageService(r"/path/to/html","/")

# Define API function
def APIFunc(request, path, args, method):
    print(f"API {method} {path} {args}")
    request.send_response(200)
    request.send_header("Content-Type", "text/plain")
    request.end_headers()
    request.wfile.write(b"API Call")

# Create API service
api=APIService("/API",func=APIFunc)

# Start the server
server=Server(services=[fs,rs,api,ps],certfile="/path/to/cert.pem")
server.start()
```

This will start the server with the following services:

- FileService: Serves files from `/path/to/video` at the `/Videos` endpoint with resumable download support.
- RedirectService: Redirects requests from `/Redirect` to `https://www.google.com`.
- PageService: Serves web pages from `/path/to/html` at the root endpoint `/`.
- APIService: Handles API calls at the `/API` endpoint, printing request details and responding with a plain text message.
- SSL Support: Uses the certificate file located at `/path/to/cert.pem` for SSL encryption.

### Route Priority

If multiple services have conflicting routes, the priority is determined by the order in which the services are listed in the `services` parameter. The service listed first will have the highest priority, and so on.

For example:

```python
from cryskura import Server
from cryskura.Services import FileService, PageService

fs = FileService(r"/path/to/files", "/files")
ps = PageService(r"/path/to/pages", "/")

server = Server(services=[fs,ps])
server.start()
```

In this case, `FileService` will have priority over `PageService` for routes that conflict between the two services. So if a request is made to `/files/index.html`, it will be handled by `FileService` and not `PageService`.

## Custom Services

To create a custom service, extend the `BaseService` class and implement the required methods:

```python
from BaseService import BaseService

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

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Contact

For any questions or suggestions, please open an issue here on [GitHub](https://github.com/HofNature/CryskuraHTTP/issues).

---

Enjoy using CryskuraHTTP!
