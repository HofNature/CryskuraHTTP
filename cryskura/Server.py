import os
import ssl
import socket
import psutil
import threading
from http.server import ThreadingHTTPServer
from .uPnP import uPnPClient
from .Handler import HTTPRequestHandler as Handler
from .Services import BaseService, FileService, ErrorService

class HTTPServer:
    def __init__(self, interface:str="127.0.0.1", port:int=8080, services=None, error_service=None, server_name:str="CryskuraHTTP/1.0", forcePort:bool=False,certfile=None,uPnP=False):
        # 获取系统所有网卡的IP地址
        addrs = psutil.net_if_addrs()
        available_devices = ["Any Available Interface"]
        available_interfaces = ["0.0.0.0"]
        for device, addrs in addrs.items():
            for addr in addrs:
                if addr.family in [socket.AF_INET,socket.AF_INET6]:
                    available_interfaces.append(addr.address)
                    available_devices.append(device)
        if interface not in available_interfaces:
            raise ValueError(f"Interface {interface} not found. \nAvailable interfaces: \n" + "\n".join([f"{device}: {addr}" for device, addr in zip(available_devices,available_interfaces)]))
        self.interface = interface

        try:
            # 检查端口是否被占用
            used_ports = []
            for conn in psutil.net_connections():
                if conn.laddr.port not in used_ports and conn.laddr.ip == self.interface:
                    used_ports.append(conn.laddr.port)
            if port in used_ports:
                if forcePort:
                    print(f"Port {port} is already in use. Forcing to use port {port}.")
                else:
                    raise ValueError(f"Port {port} is already in use.")
        except Exception as e:
            print(f"Error checking port availability: {e} , skipping check")

        # 检查uPnP是否可用
        if uPnP:
            self.uPnP = uPnPClient(interface)
            if not self.uPnP.available:
                print("Disabling uPnP port forwarding.")
                self.uPnP = None
        else:
            self.uPnP = None
            

        # Linux下端口小于1024需要root权限
        if os.name == "posix" and port < 1024 and os.geteuid() != 0:
            raise PermissionError(f"Port {port} requires root permission.")
        if port < 0 or port > 65535:
            raise ValueError(f"Port {port} is out of range.")
        self.port = port

        # 检查服务是否合法
        if services is None:
            self.services = [FileService(os.fspath(os.getcwd()), "/",server_name=server_name)]
        else:
            self.services = []
            for service in services:
                if isinstance(service, BaseService):
                    self.services.append(service)
                else:
                    raise ValueError(f"Service {service} is not a valid service.")
                
        # 检查错误服务是否合法
        if error_service is None:
            self.error_service = ErrorService(server_name)
        else:
            if isinstance(error_service, BaseService):
                self.error_service = error_service
            else:
                raise ValueError(f"Service {error_service} is not a valid service.") 
            
        # 检查证书是否合法
        if certfile is not None:
            if not os.path.exists(certfile):
                raise ValueError(f"Certfile {certfile} does not exist.")
            self.certfile = certfile
        else:
            self.certfile = None
        
        self.server_name = server_name
        self.server = None
        self.thread = None
        
    def start(self, threaded:bool=True):
        # 启动HTTP服务器
        handler=lambda *args, **kwargs: Handler(*args, services=self.services, errsvc=self.error_service, **kwargs)
        self.server = ThreadingHTTPServer((self.interface, self.port), handler)
        if self.certfile is not None:
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(certfile=self.certfile)
            self.server.socket = ssl_ctx.wrap_socket(self.server.socket, server_side=True)
        print(f"Server started at {self.interface}:{self.port}")
        if self.uPnP is not None:
            res,map=self.uPnP.add_port_mapping(self.port,self.port,"TCP",self.server_name)
            if res:
                for mapping in map:
                    print(f"Service is available at {mapping[0]}:{mapping[1]}")
        if threaded:
            self.thread = threading.Thread(target=self.serve_forever)
            self.thread.setDaemon(True)
            self.thread.start()
        else:
            self.serve_forever()

    def serve_forever(self):
        try:
            self.server.serve_forever()
        except KeyboardInterrupt as e:
            if self.uPnP is not None:
                self.uPnP.remove_port_mapping()
            print(f"Server on port {self.port} stopped.")
            self.stop()
            # os.kill(os.getpid(), 9)
        except Exception as e:
            if self.uPnP is not None:
                self.uPnP.remove_port_mapping()
            raise e
            
    def stop(self):
        # 停止HTTP服务器
        if self.server is not None:
            if self.thread is not None:
                self.server.shutdown()
                self.thread.join()
                self.server.server_close()
                self.server = None
                self.thread = None
            else:
                self.server.shutdown()
                self.server.server_close()
                self.server = None
        else:
            raise ValueError("Server is not running.")
