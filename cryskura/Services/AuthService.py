from uuid import uuid4
from datetime import datetime
from . import BaseService, Route
from .. import Handler
from ..Pages import Login_Page
from http import HTTPStatus
import json

ac_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "*",
    "Access-Control-Allow-Headers": "*"
}

class AuthVerify:
    def __init__(self, auth_data:dict[str, str], expire_time:int=7*86400):
        self.auth_data = auth_data
        self.expire_time = expire_time

    def __call__(self, username:str, password:str):
        if username in self.auth_data and self.auth_data[username]==password:
            return True
        return False

class AuthRoute(Route):
    def __init__(self, path, token, key, methods: list, type: str, host = None, port = None):
        self.token = token
        self.key = key
        super().__init__(path, methods, type, host, port)

    def match(self, request:Handler, path:list, host=None, port=None):
        mached, path_exists = super().match(request, path, host, port)
        if not mached:
            return False, path_exists
        headers = request.headers
        cookie = headers.get("Cookie", None)
        if cookie is None:
            return True, True
        user_token = None
        for item in cookie.split(";"):
            item = item.strip()
            ckey, cvalue = item.split("=", 1)
            if ckey==self.key:
                user_token = cvalue
                break
        if user_token is None:
            return True, True
        if user_token in self.token:
            username, expire_time = self.token[user_token]
            if expire_time<datetime.now().timestamp():
                self.token.pop(user_token)
                return True, True
            print(f"User {username} passed auth for {request.command} /{'/'.join(path)}")
            return False, False
        return True, True

class APIService(BaseService):
    def __init__(self, remote_path, verify:AuthVerify, protected_path, methods=["GET","HEAD","POST"], type="prefix", host=None, port=None):
        self.token = {}
        self.key = 'Cryskura_AUTH_' + str(uuid4()).replace("-","").upper()
        self.routes = [
            Route(remote_path, ["HEAD","POST","GET","OPTIONS"], "exact", host, port),
            AuthRoute(protected_path, self.token, self.key, methods, type, host, port),
        ]
        self.auth_path = '/' + '/'.join(self.routes[0].path)
        self.verify = verify
        for method in methods:
            setattr(self, f"handle_{method}", lambda request, path, args, method=method: self.handle_AUTHV(request, path, args, method))
        super().__init__(self.routes, None)
        self.remote_path = self.routes[0].path
    
    def handle_AUTHV(self, request:Handler, path:list, args:dict, method:str):
        for key,value in ac_headers.items():
            request.send_header(key, value)
        if not self.routes[0].match(request, path, request.host, request.port)[0]: # 应当被阻止
            request.send_response(HTTPStatus.UNAUTHORIZED)
            request.end_headers()
            if method=="GET":
                request.send_response(HTTPStatus.OK)
                request.end_headers()
                data = "<html><script>location.href='{}'</script></html>".format(self.auth_path)
                request.wfile.write(data.encode())
            return
        if method=="OPTIONS":
            request.send_response(HTTPStatus.NO_CONTENT)
            request.end_headers()
            return
        if method=="HEAD":
            request.send_response(HTTPStatus.OK)
            request.end_headers()
            return
        if method=="POST":
            content_length = int(request.headers.get("Content-Length", 0))
            try:
                content = request.rfile.read(content_length).decode()
                data = json.loads(content)
                username = data.get("username", "")
                password = data.get("password", "")
            except Exception as e:
                print(f"Error parsing auth data: {e}")
                request.send_response(HTTPStatus.BAD_REQUEST)
                request.end_headers()
                return
            if self.verify(username, password):
                token = str(uuid4()).replace("-","").upper()
                expire_time = datetime.now().timestamp() + self.verify.expire_time
                self.token[token] = (username, expire_time)
                request.send_response(HTTPStatus.OK)
                request.send_header("Set-Cookie", f"{self.key}={token}; Path=/; Max-Age={self.verify.expire_time}")
                request.end_headers()
                data = {"message": "Authentication successful"}
                request.wfile.write(json.dumps(data).encode())
            else:
                request.send_response(HTTPStatus.UNAUTHORIZED)
                request.end_headers()
                data = {"message": "Authentication failed"}
                request.wfile.write(json.dumps(data).encode())
        request.send_response(HTTPStatus.OK)
        request.end_headers()
        request.wfile.write(Login_Page.encode())
