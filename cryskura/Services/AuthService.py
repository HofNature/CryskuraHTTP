from uuid import uuid4
from datetime import datetime
from . import BaseService, Route
from .. import Handler
from ..Pages import Login_Page, Cryskura_Icon
from http import HTTPStatus
from urllib.parse import quote
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
    def __init__(self, path, token, key, methods: list, route_type: str, host = None, port = None):
        self.token = token
        self.key = key
        super().__init__(path, methods, route_type, host, port)

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
            if "=" not in item:
                continue
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

class AuthService(BaseService):
    def __init__(self, remote_path, verify:AuthVerify, protected_path, methods=None, route_type="prefix", host=None, port=None, title="Cryskura HTTP"):
        if methods is None:
            methods = ["GET", "HEAD", "POST", "OPTIONS"]
        self.token = {}
        self.key = 'Cryskura_AUTH_' + str(uuid4()).replace("-","").upper()
        self.routes = [
            Route(remote_path, ["HEAD","POST","GET","OPTIONS"], "exact", host, port),
            AuthRoute(protected_path, self.token, self.key, methods, route_type, host, port),
        ]
        self.login_page = Login_Page.replace("{{TITLE}}", title).replace(
            'background: url("Cryskura.png");',
            f'background: url("{Cryskura_Icon}");',
        )
        self.auth_path = '/' + '/'.join(self.routes[0].path)
        self.verify = verify
        for method in methods:
            setattr(self, f"handle_{method}", lambda request, path, args, method=method: self.handle_AUTHV(request, path, args, method))
        super().__init__(self.routes, None)
        self.remote_path = self.routes[0].path

    def handle_GET(self, request:Handler, path:list, args:dict):
        self.handle_AUTHV(request, path, args, "GET")

    def handle_POST(self, request:Handler, path:list, args:dict):
        self.handle_AUTHV(request, path, args, "POST")

    def handle_HEAD(self, request:Handler, path:list, args:dict):
        self.handle_AUTHV(request, path, args, "HEAD")
    
    def handle_AUTHV(self, request:Handler, path:list, _args:dict, method:str):
        def send_json(status: HTTPStatus, payload: dict, extra_headers: dict | None = None):
            request.send_response(status)
            for key, value in ac_headers.items():
                request.send_header(key, value)
            request.send_header("Content-Type", "application/json; charset=utf-8")
            if extra_headers is not None:
                for key, value in extra_headers.items():
                    request.send_header(key, value)
            request.end_headers()
            request.wfile.write(json.dumps(payload).encode("utf-8"))

        def send_login_page():
            request.send_response(HTTPStatus.OK)
            for key, value in ac_headers.items():
                request.send_header(key, value)
            request.send_header("Content-Type", "text/html; charset=utf-8")
            request.end_headers()
            request.wfile.write(self.login_page.encode("utf-8"))

        is_auth_page = self.routes[0].match(request, path, request.host, request.port)[0]
        if not is_auth_page:  # 命中受保护路由但未通过认证
            login_url = f"{self.auth_path}?next={quote(request.path, safe='')}"
            if method == "GET":
                request.send_response(HTTPStatus.TEMPORARY_REDIRECT)
                for key, value in ac_headers.items():
                    request.send_header(key, value)
                request.send_header("Location", login_url)
                request.end_headers()
            else:
                send_json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required", "auth_url": login_url})
            return

        if method == "OPTIONS":
            request.send_response(HTTPStatus.NO_CONTENT)
            for key, value in ac_headers.items():
                request.send_header(key, value)
            request.end_headers()
            return

        if method == "HEAD":
            request.send_response(HTTPStatus.OK)
            for key, value in ac_headers.items():
                request.send_header(key, value)
            request.send_header("Content-Type", "text/html; charset=utf-8")
            request.end_headers()
            return

        if method == "GET":
            send_login_page()
            return

        if method == "POST":
            content_length = int(request.headers.get("Content-Length", 0))
            try:
                content = request.rfile.read(content_length).decode("utf-8")
                data = json.loads(content)
                username = data.get("username", "")
                password = data.get("password", "")
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                print(f"Error parsing auth data: {e}")
                send_json(HTTPStatus.BAD_REQUEST, {"message": "Invalid request payload"})
                return

            if self.verify(username, password):
                token = str(uuid4()).replace("-", "").upper()
                expire_time = datetime.now().timestamp() + self.verify.expire_time
                self.token[token] = (username, expire_time)
                send_json(
                    HTTPStatus.OK,
                    {"message": "Authentication successful"},
                    {
                        "Set-Cookie": (
                            f"{self.key}={token}; Path=/; Max-Age={self.verify.expire_time}; "
                            "HttpOnly; SameSite=Lax"
                        )
                    },
                )
            else:
                send_json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication failed"})
            return

        send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"message": f"Method {method} not allowed"})


# Backward compatibility: older code may still import APIService from this module.
APIService = AuthService
