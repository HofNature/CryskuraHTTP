from . import BaseService, Route
from .. import Handler
import os
from http import HTTPStatus

class PageService(BaseService):
    def __init__(self, local_path, remote_path,index_pages=("index.html", "index.htm"),auth_func=None):
        self.routes = [
            Route(remote_path, ["GET","HEAD"], "prefix"),
        ]
        self.local_path = os.path.abspath(local_path)
        self.index_pages = index_pages
        super().__init__(self.routes, auth_func)
        self.remote_path = self.routes[0].path
    
    def calc_path(self, path:list):
        sub_path = path[len(self.remote_path):]
        r_directory=os.path.abspath(self.local_path)
        r_path='/'+'/'.join(sub_path)
        real_path = os.path.join(r_directory, '/'.join(sub_path))
        isValid = False
        common_path = os.path.commonpath([real_path, self.local_path])
        if os.path.exists(real_path) and os.path.samefile(common_path, self.local_path):
            if os.path.isfile(real_path):
                isValid = True
            else:
                for file in self.index_pages:
                    if os.path.exists(os.path.join(real_path, file)):
                        isValid = True
                        r_path = os.path.join(r_path, file)
                        break
        return isValid, r_directory, r_path

    def handle_GET(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "GET"):
            return
        isValid, request.directory, request.path = self.calc_path(path)
        if not isValid:
            request.errsvc.handle(request, path, args, "GET",HTTPStatus.NOT_FOUND)
            return
        f = request.send_head()
        if f:
            try:
                request.copyfile(f, request.wfile)
            finally:
                f.close()
    
    def handle_HEAD(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "HEAD"):
            return
        isValid,request.directory, request.path = self.calc_path(path)
        if not isValid:
            request.errsvc.handle(request, path, args, "HEAD",HTTPStatus.NOT_FOUND)
            return
        f = request.send_head()
        if f:
            f.close()