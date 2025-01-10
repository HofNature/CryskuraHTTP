from . import BaseService, Route
from .. import Handler

class APIService(BaseService):
    def __init__(self, remote_path, func:callable, methods=["GET","HEAD","POST"], type="prefix",auth_func=None,length_limit=1024*1024):
        self.routes = [
            Route(remote_path, methods, type),
        ]
        self.func = func
        self.length_limit = length_limit
        for method in methods:
            setattr(self, f"handle_{method}", lambda request, path, args, method=method: self.handle_API(request, path, args, method))
        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path
    
    def handle_API(self, request:Handler, path:list,args:dict,method:str):
        if not self.auth_verify(request, path, args, method):
            return
        sub_path = path[len(self.remote_path):]
        headers = request.headers
        content= request.rfile.read(min(int(headers.get("Content-Length",0)),self.length_limit))
        code, headers, content = self.func(request, sub_path, args, headers,content, method)
        request.send_response(code)
        for key in headers:
            request.send_header(key, headers[key])
        request.end_headers()
        request.wfile.write(content)

    # def handle_GET(self, request:Handler, path:list,args:dict):
    #     self.handle_API(request, path, args, "GET")
    
    # def handle_HEAD(self, request:Handler, path:list,args:dict):
    #     self.handle_API(request, path, args, "HEAD")

    # def handle_POST(self, request:Handler, path:list,args:dict):
    #     self.handle_API(request, path, args, "POST")