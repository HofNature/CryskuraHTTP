from .. import Handler

class Route:
    def __init__(self, path, methods: list, type: str):
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
        for method in methods:
            if method not in ["GET","POST","HEAD"]:
                raise ValueError(f"Method {method} is not a valid method.")
        self.methods = methods
        if type not in ["prefix","exact"]:
            raise ValueError(f"Type {type} is not a valid type.")
        self.type = type

    def match(self, path:list, method:str):
        if self.type=="exact":
            if path==self.path:
                if method in self.methods:
                    return True
        elif self.type=="prefix":
            if path[:len(self.path)]==self.path:
                if method in self.methods:
                    return True
        return False
        

class BaseService:
    def __init__(self, route:list):
        for r in route:
            if not isinstance(r, Route):
                raise ValueError(f"Route {r} is not a valid route.")
        self.route = route

    def handle_GET(self, request:Handler, path:list,args:dict):
        raise NotImplementedError
    
    def handle_POST(self, request:Handler, path:list,args:dict):
        raise NotImplementedError
    
    def handle_HEAD(self, request:Handler, path:list,args:dict):
        raise NotImplementedError