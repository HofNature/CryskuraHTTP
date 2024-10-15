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
    
    def do_OPERATION(self,operation:str):
        path,args = self.split_Path()
        for service in self.services:
            for route in service.routes:
                if route.match(path,operation):
                    if operation=="GET":
                        service.handle_GET(self,path,args)
                    elif operation=="POST":
                        service.handle_POST(self,path,args)
                    elif operation=="HEAD":
                        service.handle_HEAD(self,path,args)
                    return
        self.errsvc.handle(self,path,args,operation,HTTPStatus.NOT_FOUND)

    def do_GET(self):
        self.do_OPERATION("GET")

    def do_HEAD(self):
        self.do_OPERATION("HEAD")

    def do_POST(self):
        self.do_OPERATION("POST")
