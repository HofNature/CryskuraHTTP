# CryskuraHTTP

CryskuraHTTP is a lightweight, customizable HTTP(s) server implemented in Python.  
It supports basic HTTP(s) functionalities, including serving files and handling errors, with optional SSL support.

README: [English](README.md) | [中文](README_zh.md)

## Features

CryskuraHTTP is an extension of Python's built-in `http.server`, with minimal dependencies. You can leverage it to implement Python HTTP services without needing to install large software or libraries.

- **Customizable Services**: Easily add custom services by extending the `BaseService` class.
- **Customizable API Calls**: Define custom API calls with the `APIService` class.
- **Error Handling**: Customizable error handling via the `ErrorService` class.
- **File Serving**: Serve files from a specified directory.
- **File Uploading**: Handle file uploads via POST requests.
- **WebPage Serving**: Serve web pages without allowing directory listing.
- **Customizable Routes**: Define custom routes for your services.
- **Customizable Authentication**: Implement custom authentication for your services.
- **Auto uPnP Port Forwarding**: Automatically forward ports using uPnP.
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

1. Install the package using pip:

    ```sh
    pip install cryskura
    ```
    
2. You can also download whl file from [GitHub Releases](https://github.com/HofNature/CryskuraHTTP/releases) and install it using pip:

    ```sh
    pip install cryskura-1.0-py3-none-any.wh
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

## Command-Line Interface

You can get help on the command-line interface by running:

```sh
cryskura --help
```

This will show the available options:

- `-h, --help`: Show help message and exit.
- `-u, --uPnP`: Enable uPnP port forwarding.
- `-v, --version`: Show program's version number and exit.
- `-b, --browser`: Open the browser after starting the server.
- `-w, --webMode`: Enable web mode, which means only files can be accessed, not directories.
- `-f, --forcePort`: Force to use the specified port even if it is already in use.
- `-t, --allowUpload`: Allow file upload.
- `-r, --allowResume`: Allow resume download.
- `-d PATH, --path PATH`: The path to the directory to serve.
- `-n NAME, --name NAME`: The name of the server.
- `-p PORT, --port PORT`: The port to listen on.
- `-c CERTFILE, --certfile CERTFILE`: The path to the certificate file.
- `-i INTERFACE, --interface INTERFACE`: The interface to listen on.
- `-j HTTP_TO_HTTPS, --http_to_https HTTP_TO_HTTPS`: Port to redirect HTTP requests to HTTPS.


## Using as a Python Module

### Custom Configuration

You can customize the server by providing different parameters:

```python
from cryskura import Server
from cryskura.Services import FileService,PageService,RedirectService,APIService

# Create services
fs=FileService(r"/path/to/file","/Files",allowResume=True,allowUpload=True)
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
server=Server(services=[fs,rs,api,ps],certfile="/path/to/cert.pem",uPnP=True)
server.start()
```

This will start the server with the following services:

- FileService: Serves files from `/path/to/file` at the `/Files` endpoint, allowing resumable downloads and file uploads.
- RedirectService: Redirects requests from `/Redirect` to `https://www.google.com`.
- PageService: Serves web pages from `/path/to/html` at the root endpoint `/`.
- APIService: Handles API calls at the `/API` endpoint, printing request details and responding with a plain text message.

And with the following settings:

- SSL Support: Uses the certificate file located at `/path/to/cert.pem` for SSL encryption.
- uPnP Port Forwarding: Automatically forwards ports using uPnP.

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

### Authentication

To implement custom authentication, you need to define an authentication function and pass it to the service that requires authentication. The authentication function should accept four parameters: `cookies`, `path`, `args`, and `operation`. It should return `True` if the authentication is successful, and `False` otherwise.

Here is an example of how to implement custom authentication:

```python
from cryskura import Server
from cryskura.Services import FileService

# Define authentication function
def AUTHFunc(cookies, path, args, operation):
    print(f"AUTH {operation} {path} {args}")
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

In this example, the `AUTHFunc` function checks the `passwd` parameter in the request arguments to authenticate GET and POST requests. If the `passwd` parameter is `passwd` for GET requests or `admin` for POST requests, the authentication is successful. Otherwise, the authentication fails.  

You can customize the `AUTHFunc` function to implement your own authentication logic, such as checking cookies, headers, or other request parameters.

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

###  Custom uPnP Configuration

The built-in uPnP client can be used independently for custom port forwarding needs. Here’s how you can use the `uPnPClient` class directly in your Python code:

#### Initializing the uPnP Client

First, you need to initialize the `uPnPClient` with the desired network interface:

```python
from cryskura import uPnP

# Initialize uPnP client for a specific interface
upnp_client = uPnP(interface="0.0.0.0")
# Use 0.0.0.0 for all IPv4 interfaces

if upnp_client.available:
    print("uPnP client initialized successfully.")
else:
    print("uPnP client is not available.")
```

#### Adding a Port Mapping

To add a port mapping, use the `add_port_mapping` method:

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

This will add a port mapping for port `8080` on the remote device to port `8080` on the local device using the TCP protocol. The description is just a label for the mapping, which can be used to identify it later.

#### Removing All Port Mappings

To remove port mappings, use the `remove_port_mapping` method:

```python
if upnp_client.available:
    upnp_client.remove_port_mapping()
    print("Port mapping removed.")
```

This will remove all port mappings that were added by the client. It's a good practice to remove port mappings when they are no longer needed. You can place this code in a cleanup section of your script or in an exception handler to ensure that the mappings are removed even if an error occurs. For example:

```python
try:
    Your code here...
except Exception as exception:
    upnp_client.remove_port_mapping()
    raise exception
```

This will ensure that the port mappings are removed even if an exception occurs during the execution of your code.

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

For more detailed information on the `uPnPClient` class and its methods, refer to the source code in the `uPnP.py` file.

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/HofNature/CryskuraHTTP/blob/main/LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Contact

For any questions or suggestions, please open an issue here on [GitHub](https://github.com/HofNature/CryskuraHTTP/issues).

---

Enjoy using CryskuraHTTP!
