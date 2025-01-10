import os
from . import __version__
from urllib.parse import unquote
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler

class HTTPRequestHandler(SimpleHTTPRequestHandler):
    server_version = "CryskuraHTTP/" + __version__
    index_pages=()
    
    def __init__(self, *args, services, errsvc, directory=None, **kwargs):
        self.services = services
        self.errsvc = errsvc
        directory = "/dev/null"
        super().__init__(*args, directory=directory, **kwargs)
    
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
    
    # def do_OPERATION(self,operation:str):
    #     path,args = self.split_Path()
    #     for service in self.services:
    #         for route in service.routes:
    #             if route.match(path,operation):
    #                 try:
    #                     if operation=="GET":
    #                         service.handle_GET(self,path,args)
    #                     elif operation=="POST":
    #                         service.handle_POST(self,path,args)
    #                     elif operation=="HEAD":
    #                         service.handle_HEAD(self,path,args)
    #                     return
    #                 except Exception as e:
    #                     print(f"Error in {service.remote_path} {operation} handler: {e}")
    #                     self.errsvc.handle(self,path,args,operation,HTTPStatus.INTERNAL_SERVER_ERROR)
    #                     return
    #     self.errsvc.handle(self,path,args,operation,HTTPStatus.NOT_FOUND)

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
            path_exists = False
            handled = False
            for service in self.services:
                for route in service.routes:
                    can_handle,path_ok = route.match(path,self.command)
                    if path_ok:
                        path_exists = True
                    if can_handle:
                        try:
                            if not hasattr(service, "handle_"+self.command):
                                raise ValueError(f"{service.remote_path} does not have a {self.command} handler, but a route for it exists.")
                            method = getattr(service, "handle_"+self.command)
                            method(self,path,args)
                            handled = True
                            break
                        except Exception as e:
                            print(f"Error in {service.remote_path} {self.command} handler: {e}")
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

            # mname = 'do_' + self.command
            # if not hasattr(self, mname):
            #     self.send_error(
            #         HTTPStatus.NOT_IMPLEMENTED,
            #         "Unsupported method (%r)" % self.command)
            #     return
            # method = getattr(self, mname)
            # method()

            self.wfile.flush() #actually send the response if not already done.
        except TimeoutError as e:
            #a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return
        
    # def do_GET(self):
    #     self.do_OPERATION("GET")

    # def do_HEAD(self):
    #     self.do_OPERATION("HEAD")

    # def do_POST(self):
    #     self.do_OPERATION("POST")
