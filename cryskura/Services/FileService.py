from . import BaseService, Route
from .. import Handler
import os
import json
from http import HTTPStatus
from ..Pages import Directory_Page

class FileService(BaseService):
    def __init__(self, local_path, remote_path, isFolder=True,allowResume=False,server_name="CryskuraHTTP"):
        self.routes = [
            Route(remote_path, ["GET","HEAD"], "prefix" if isFolder else "exact"),
        ]
        self.isFolder = isFolder
        self.allowResume = allowResume
        self.local_path = os.path.abspath(local_path)
        if not os.path.exists(local_path):
            raise ValueError(f"Path {local_path} does not exist.")
        if isFolder and not os.path.isdir(local_path):
            raise ValueError(f"Path {local_path} is not a folder.")
        if not isFolder and not os.path.isfile(local_path):
            raise ValueError(f"Path {local_path} is not a file.")
        self.server_name = server_name
        super().__init__(self.routes)
        self.remote_path = self.routes[0].path
    
    def calc_path(self, path:list):
        if self.isFolder:
            sub_path = path[len(self.remote_path):]
            r_directory=os.path.abspath(self.local_path)
            r_path='/'+'/'.join(sub_path)
            real_path = os.path.join(r_directory, '/'.join(sub_path))
        else:
            r_directory=os.path.dirname(self.local_path)
            r_path=os.path.basename(self.local_path)
            real_path = self.local_path
        common_path = os.path.commonpath([real_path, self.local_path])
        isValid = os.path.exists(real_path) and os.path.samefile(common_path, self.local_path)
        return isValid,r_directory, r_path, real_path

    def handle_GET(self, request:Handler, path:list,args:dict):
        isValid,request.directory, request.path,real_path = self.calc_path(path)
        if not isValid:
            request.errsvc.handle(request, path, args, "GET",HTTPStatus.NOT_FOUND)
            return
        if self.allowResume and 'Range' in request.headers and os.path.isfile(real_path):
            range_header = request.headers["Range"]
            range_h=range_header.strip("bytes=").split("-")
            start=int(range_h[0])
            file_size = os.path.getsize(real_path)
            if range_h[1]!="":
                end = min(int(range_h[1]), file_size - 1)
            else:
                end = file_size - 1
            length = end - start + 1
            request.send_response(HTTPStatus.PARTIAL_CONTENT)
            request.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            request.send_header("Content-Length", length)
            request.send_header("Accept-Ranges", "bytes")
            request.send_header("Content-Type", request.guess_type(request.path))
            request.end_headers()
            with open(real_path, 'rb') as f:
                f.seek(start)
                chunk_size = 8192
                while length > 0:
                    chunk = f.read(min(chunk_size, length))
                    request.wfile.write(chunk)
                    length -= len(chunk)
        elif os.path.isdir(real_path):
            request.send_response(HTTPStatus.OK)
            request.send_header("Content-Type", "text/html")
            request.end_headers()
            Page=Directory_Page.replace("CryskuraHTTP", self.server_name)
            # 列出目录下的文件和文件夹
            dirs, files = [], []
            for file in os.listdir(real_path):
                if os.path.isdir(os.path.join(real_path, file)):
                    dirs.append(file)
                else:
                    files.append(file)
            dirs.sort()
            files.sort()
            Page=Page.replace("<script>", f"<script>let subfolders='{json.dumps(dirs,ensure_ascii=True)}';let files='{json.dumps(files,ensure_ascii=True)}';")
            request.wfile.write(Page.encode())
        else:
            f = request.send_head()
            if f:
                try:
                    request.copyfile(f, request.wfile)
                finally:
                    f.close()
    
    def handle_HEAD(self, request:Handler, path:list,args:dict):
        isValid,request.directory, request.path,real_path = self.calc_path(path)
        if not isValid:
            request.errsvc.handle(request, path, args, "HEAD",HTTPStatus.NOT_FOUND)
            return
        if os.path.isdir(real_path):
            request.send_response(HTTPStatus.OK)
            request.send_header("Content-Type", "text/html")
            request.end_headers()
        else:
            f = request.send_head()
            if f:
                f.close()