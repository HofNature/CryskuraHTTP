try:
    import ssl
except ImportError:
    ssl = None
import sys
from . import __version__
from urllib.parse import unquote
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler

class HTTPRequestHandler(SimpleHTTPRequestHandler):
    server_version = "CryskuraHTTP/" + __version__
    index_pages=()
    
    def __init__(self, *args, services, errsvc, directory=None,
                 proxy=None, cors_manager=None, log_manager=None, **kwargs):
        self.services = services
        self.errsvc = errsvc
        self.proxy = proxy
        self.cors_manager = cors_manager
        self.log_manager = log_manager
        directory = "/dev/null"
        super().__init__(*args, directory=directory, **kwargs)

    def finish(self):
        if not self.wfile.closed:
            try:
                self.wfile.flush()
            except (OSError, ValueError):
                pass
        if ssl and isinstance(self.connection, ssl.SSLSocket):
            try:
                self.connection.unwrap()
            except Exception:
                pass
        self.wfile.close()
        self.rfile.close()

    def address_string(self):
        if hasattr(self, 'proxy') and self.proxy is not None:
            return self.proxy.get_client_ip(self)
        addr = self.client_address[0]
        if addr.startswith('::ffff:'):
            return addr[7:]
        return addr

    def send_response(self, code, message=None):
        self._response_status = code
        self._response_length = 0
        self._cors_manual = False
        super().send_response(code, message)

    def send_header(self, keyword, value):
        if keyword == "Content-Length":
            try:
                self._response_length = int(value)
            except (ValueError, TypeError):
                pass
        if keyword.startswith("Access-Control-"):
            self._cors_manual = True
        super().send_header(keyword, value)

    def end_headers(self):
        if (hasattr(self, 'cors_manager') and self.cors_manager is not None
                and not getattr(self, '_cors_manual', False)):
            service = getattr(self, '_current_service', None)
            self.cors_manager.add_cors_headers(self, self.command, service)
        super().end_headers()

    def split_Path(self):
        # 将路径分割为路径和参数
        path=unquote(self.path).split("?",1)
        if len(path)==1:
            path, args = path[0], ""
        else:
            path, args = path
        path= path.replace("\\","/").split("/")
        if path[0]=="":
            path.pop(0)
        if path[-1]=="":
            path.pop(-1)
        args = args.split("&")
        processed_args = {}
        for arg in args:
            if "=" not in arg:
                if arg!="":
                    processed_args[arg] = ""
            else:
                arg = arg.split("=",1)
                processed_args[arg[0]] = arg[1]
        return path,processed_args
    
    def handle_one_request(self):
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                # An error code has been sent, just exit
                return

            path,args = self.split_Path()

            host = None
            port = None

            if hasattr(self, 'proxy') and self.proxy is not None:
                host, port = self.proxy.get_host_port(self)

            if host is None and port is None:
                host = self.headers.get('Host', None)
                if host is None:
                    port = None
                else:
                    try:
                        if host.startswith('['):  # IPv6 address
                            if ']' in host:
                                host, _, port = host[1:].partition(']')
                                if port.startswith(':'):
                                    port = port[1:]
                                else:
                                    port = None
                            else:
                                host = None
                                port = None
                        else:  # IPv4 or hostname
                            host, _, port = host.partition(':')
                        if port:
                            try:
                                port = int(port)
                            except ValueError:
                                if hasattr(self, 'log_manager') and self.log_manager is not None:
                                    self.log_manager.error(f"Invalid port number {port!r}")
                                else:
                                    print(f"Invalid port number {port!r}", file=sys.stderr)
                                port = None
                                return
                    except Exception:
                        if hasattr(self, 'log_manager') and self.log_manager is not None:
                            self.log_manager.error(f"Invalid host {host!r}")
                        else:
                            print(f"Invalid host {host!r}", file=sys.stderr)
                        host = None
                        port = None

            self.host = host
            self.port = port

            path_exists = False
            handled = False
            for service in self.services:
                for route in service.routes:
                    can_handle,path_ok = route.match(self,path,host,port)
                    if path_ok:
                        path_exists = True
                    if can_handle:
                        try:
                            if not hasattr(service, "handle_"+self.command):
                                raise ValueError(f"Service to handle {path} does not have a {self.command} handler, but a route for it exists.")
                            method = getattr(service, "handle_"+self.command)
                            self._current_service = service
                            method(self,path,args)
                            handled = True
                            break
                        except Exception as e:
                            if isinstance(e, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)) or (ssl and isinstance(e, ssl.SSLEOFError)):
                                msg = f"Client disconnected while handling {self.command} request for /{'/'.join(path)}: {e}"
                                if hasattr(self, 'log_manager') and self.log_manager is not None:
                                    self.log_manager.error(msg)
                                else:
                                    print(msg, file=sys.stderr)
                                return
                            msg = f"Error while handling {self.command} request for /{'/'.join(path)}: {e}"
                            if hasattr(self, 'log_manager') and self.log_manager is not None:
                                self.log_manager.error(msg)
                            else:
                                print(msg, file=sys.stderr)
                            self.errsvc.handle(self,path,args,self.command,HTTPStatus.INTERNAL_SERVER_ERROR)
                            handled = True
                            break
                if handled:
                    break
            if not handled:
                if path_exists:
                    self.errsvc.handle(self,path,args,self.command,HTTPStatus.METHOD_NOT_ALLOWED)
                else:
                    self.errsvc.handle(self,path,args,self.command,HTTPStatus.NOT_FOUND)

            self.wfile.flush()

            if hasattr(self, 'log_manager') and self.log_manager is not None:
                status = getattr(self, '_response_status', 0)
                length = getattr(self, '_response_length', 0)
                client_ip = self.address_string()
                self.log_manager.access(self.requestline, status, client_ip, length)

        except TimeoutError as e:
            #a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return
        except Exception as e:
            if isinstance(e, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)) or \
               (ssl and isinstance(e, (ssl.SSLEOFError, ssl.SSLError))):
                self.log_error("Client disconnected: %r", e)
                self.close_connection = True
                return
            raise
