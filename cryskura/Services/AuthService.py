from __future__ import annotations

import html
import json
import threading
from datetime import datetime
from http import HTTPStatus
from urllib.parse import quote
from uuid import uuid4

from . import BaseService, Route
from .. import Handler
from ..Pages import Login_Page, Cryskura_Icon

class AuthVerify:
    def __init__(self, auth_data:dict[str, str], expire_time:int=7*86400):
        self.auth_data = auth_data
        self.expire_time = expire_time

    def __call__(self, username:str, password:str):
        if username in self.auth_data and self.auth_data[username]==password:
            return True
        return False

class AuthRoute(Route):
    def __init__(self, path, token, key, methods: list, route_type: str, host = None, port = None, token_lock: threading.Lock | None = None):
        self.token = token
        self.key = key
        self.token_lock = token_lock
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
        lock = self.token_lock
        if lock is not None:
            lock.acquire()
        try:
            if user_token in self.token:
                username, expire_time = self.token[user_token]
                if expire_time<datetime.now().timestamp():
                    self.token.pop(user_token)
                    return True, True
                print(f"User {username} passed auth for {request.command} /{'/'.join(path)}")
                return False, False
        finally:
            if lock is not None:
                lock.release()
        return True, True

class AuthService(BaseService):
    def __init__(self, remote_path, verify:AuthVerify, protected_path, methods=None, route_type="prefix", host=None, port=None, title="Cryskura HTTP"):
        if methods is None:
            methods = ["GET", "HEAD", "POST", "OPTIONS"]
        self.token = {}
        self.token_lock = threading.Lock()
        self.key = 'Cryskura_AUTH_' + str(uuid4()).replace("-","").upper()
        login_methods = list(dict.fromkeys(methods + ["OPTIONS"]))
        self.routes = [
            Route(remote_path, login_methods, "exact", host, port),
            AuthRoute(protected_path, self.token, self.key, methods, route_type, host, port, token_lock=self.token_lock),
        ]
        self.login_page = Login_Page.replace("{{TITLE}}", html.escape(title, quote=True)).replace(
            'background: url("Cryskura.png");',
            f'background: url("{Cryskura_Icon}");',
        )
        self.auth_path = '/' + '/'.join(self.routes[0].path)
        self.verify = verify
        for method in login_methods:
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
            body = json.dumps(payload).encode("utf-8")
            request.send_response(status)
            request.send_header("Content-Type", "application/json; charset=utf-8")
            request.send_header("Content-Length", str(len(body)))
            if extra_headers is not None:
                for key, value in extra_headers.items():
                    request.send_header(key, value)
            request.end_headers()
            if method != "HEAD":
                request.wfile.write(body)

        def send_login_page():
            body = self.login_page.encode("utf-8")
            request.send_response(HTTPStatus.OK)
            request.send_header("Content-Type", "text/html; charset=utf-8")
            request.send_header("Content-Length", str(len(body)))
            request.end_headers()
            if method != "HEAD":
                request.wfile.write(body)

        is_auth_page = self.routes[0].match(request, path, request.host, request.port)[0]
        if not is_auth_page:  # 命中受保护路由但未通过认证
            login_url = f"{self.auth_path}?next={quote(request.path, safe='')}"
            if method == "GET":
                request.send_response(HTTPStatus.TEMPORARY_REDIRECT)
                request.send_header("Location", login_url)
                request.end_headers()
            else:
                send_json(HTTPStatus.UNAUTHORIZED, {"message": "Authentication required", "auth_url": login_url})
            return

        if method == "OPTIONS":
            request.send_response(HTTPStatus.NO_CONTENT)
            request.send_header("Content-Length", "0")
            request.end_headers()
            return

        if method == "HEAD":
            send_login_page()
            return

        if method == "GET":
            send_login_page()
            return

        if method == "POST":
            try:
                content_length = int(request.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                send_json(HTTPStatus.BAD_REQUEST, {"message": "Invalid Content-Length"})
                return

            if content_length < 0:
                send_json(HTTPStatus.BAD_REQUEST, {"message": "Invalid Content-Length"})
                return

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
                now = datetime.now().timestamp()
                expire_time = now + self.verify.expire_time
                with self.token_lock:
                    expired = [t for t, (u, exp) in self.token.items() if exp < now]
                    for t in expired:
                        self.token.pop(t)
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
