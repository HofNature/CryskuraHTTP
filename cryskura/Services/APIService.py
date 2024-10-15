from . import BaseService, Route
from .. import Handler

class APIService(BaseService):
    def __init__(self, remote_path, func:callable, methods=["GET","HEAD","POST"], type="prefix",auth_func=None):
        self.routes = [
            Route(remote_path, methods, type),
        ]
        self.func = func
        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path

    def handle_GET(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "GET"):
            return
        sub_path = path[len(self.remote_path):]
        self.func(request, sub_path, args, "GET")
    
    def handle_HEAD(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "HEAD"):
            return
        sub_path = path[len(self.remote_path):]
        self.func(request, sub_path, args, "HEAD")

    def handle_POST(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "POST"):
            return
        sub_path = path[len(self.remote_path):]
        self.func(request, sub_path, args, "POST")