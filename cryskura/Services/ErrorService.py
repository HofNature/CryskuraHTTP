from ..Pages import Error_Page

from . import BaseService
from .. import Handler

from http import HTTPStatus

class ErrorService(BaseService):
    def __init__(self, server_name):
        self.server_name = server_name

    def handle(self, request:Handler, path:list,args:dict, method:str, status:int):
        if method=="HEAD":
            request.send_response(status)
            request.end_headers()
            return
        request.send_response(status)
        request.send_header("Content-Type", "text/html")
        request.end_headers()
        statusStr=HTTPStatus(status).phrase
        Page=Error_Page.replace("CryskuraHTTP", self.server_name)
        Page=Page.replace("<script>", f"<script>let error='{str(status)+' '+statusStr}';")
        request.wfile.write(Page.encode())
