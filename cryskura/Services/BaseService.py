from .. import Handler
from http import HTTPStatus

class Route:
    def __init__(self, path, methods: list, type: str, host = None, port = None):
        if host is not None:
            if isinstance(host, str):
                host = [host]
            for h in host:
                if h is not None and not isinstance(h, str):
                    raise ValueError(f"Host {h} is not a valid host.")
        self.host = host
        if port is not None:
            if isinstance(port, int):
                port = [port]
            for p in port:
                if p is not None and not isinstance(p, int):
                    raise ValueError(f"Port {p} is not a valid port.")
        self.port = port

        if not isinstance(path, list):
            if isinstance(path, str):
                path=path.split("/")
                if path[0]=='':
                    path.pop(0)
                if path[-1]=='':
                    path.pop(-1)
            else:
                raise ValueError(f"Path {path} is not a valid path.")
        self.path = path    
        # for method in methods:
        #     if method not in ["GET","POST","HEAD"]:
        #         raise ValueError(f"Method {method} is not a valid method.")
        self.methods = methods
        if type not in ["prefix","exact"]:
            raise ValueError(f"Type {type} is not a valid type.")
        self.type = type

    def match(self, path:list, method:str, host=None, port=None):
        path_exists = False
        if self.host is None:
            host_match = True
        else:
            host_match =  host in self.host
        if self.port is None:
            port_match = True
        else:
            port_match = port in self.port
        if not host_match or not port_match:
            return False,False

        if self.type=="exact":
            if path==self.path:
                path_exists = True
                if method in self.methods:
                    return True,True
        elif self.type=="prefix":
            if path[:len(self.path)]==self.path:
                path_exists = True
                if method in self.methods:
                    return True,True
        return False,path_exists
        

class BaseService:
    def __init__(self, routes:list, auth_func=None):
        for r in routes:
            if not isinstance(r, Route):
                raise ValueError(f"Route {r} is not a valid route.")
        self.auth_func = auth_func
        self.routes = routes

    def auth_verify(self, request:Handler, path:list,args:dict,operation:str):
        if self.auth_func is not None:
            origin_cookie = request.headers.get("Cookie")
            cookies = {}
            if origin_cookie is not None:
                for cookie in origin_cookie.split(";"):
                    cookie = cookie.split("=")
                    cookies[cookie[0].strip()] = cookie[1].strip()
            if not self.auth_func(cookies,path,args,operation):
                request.errsvc.handle(request,path,args,operation,HTTPStatus.UNAUTHORIZED)
                return False
        return True

    def handle_GET(self, request:Handler, path:list,args:dict):
        raise NotImplementedError
    
    def handle_POST(self, request:Handler, path:list,args:dict):
        raise NotImplementedError
    
    def handle_HEAD(self, request:Handler, path:list,args:dict):
        raise NotImplementedError