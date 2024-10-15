from . import BaseService, Route
from .. import Handler
import os
from http import HTTPStatus

class RedirectService(BaseService):
    def __init__(self, remote_path,redirect_path,methods=["GET","HEAD","POST"],remote_type="prefix",redirect_type="prefix",auth_func=None):
        self.routes = [
            Route(remote_path, methods, remote_type),
        ]
        self.redirect_path = redirect_path
        if redirect_type not in ["prefix","exact"]:
            raise ValueError(f"Type {redirect_type} is not a valid type.")
        self.redirect_type = redirect_type
        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path
    
    def calc_path(self,  path:list):
        sub_path = path[len(self.remote_path):]
        if self.redirect_type=="prefix":
            if self.redirect_path[-1]=="/":
                r_path = self.redirect_path + '/'.join(sub_path)
            else:
                r_path = self.redirect_path + '/' + '/'.join(sub_path)
        else:
            r_path = self.redirect_path
        return r_path

    def handle_GET(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "GET"):
            return
        r_path = self.calc_path(path)
        request.send_response(HTTPStatus.MOVED_PERMANENTLY)
        request.send_header("Location", r_path)
        request.end_headers()
    
    def handle_HEAD(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "HEAD"):
            return
        r_path = self.calc_path(path)
        request.send_response(HTTPStatus.MOVED_PERMANENTLY)
        request.send_header("Location", r_path)
        request.end_headers()

    def handle_POST(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "POST"):
            return
        r_path = self.calc_path(path)
        request.send_response(HTTPStatus.PERMANENT_REDIRECT)
        request.send_header("Location", r_path)
        request.end_headers()
