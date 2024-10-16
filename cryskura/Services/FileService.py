from . import BaseService, Route
from .. import Handler
import os
import json
from http import HTTPStatus
from ..Pages import Directory_Page
from urllib.parse import quote

class FileService(BaseService):
    def __init__(self, local_path, remote_path, isFolder=True,allowResume=False,server_name="CryskuraHTTP",auth_func=None,allowUpload=False):
        methods = ["GET","HEAD"]
        if allowUpload:
            methods.append("POST")
        self.routes = [
            Route(remote_path, methods, "prefix" if isFolder else "exact"),
        ]
        self.allowUpload = allowUpload
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
        super().__init__(self.routes, auth_func)
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
        if not self.auth_verify(request, path, args, "GET"):
            return
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
            Page=Page.replace("<script>", f"<script>let subfolders='{json.dumps(dirs,ensure_ascii=True)}';let files='{json.dumps(files,ensure_ascii=True)}';let allowUpload={self.allowUpload*1};")
            request.wfile.write(Page.encode())
        else:
            f = request.send_head()
            if f:
                try:
                    request.copyfile(f, request.wfile)
                finally:
                    f.close()
    
    def handle_HEAD(self, request:Handler, path:list,args:dict):
        if not self.auth_verify(request, path, args, "HEAD"):
            return
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
        
    def handle_POST(self, request: Handler, path: list, args: dict):
        if not self.auth_verify(request, path, args, "POST"):
            return
        if not self.allowUpload:
            request.errsvc.handle(request, path, args, "POST", HTTPStatus.METHOD_NOT_ALLOWED)
            return
        isValid, request.directory, request.path, real_path = self.calc_path(path)
        if not isValid or not os.path.isdir(real_path):
            request.errsvc.handle(request, path, args, "POST", HTTPStatus.NOT_FOUND)
            return
        if 'Content-Length' in request.headers:
            length = int(request.headers['Content-Length'])
        else:
            length = 0
        if length>0:
            split_length = 1024*1024 # 1MB
            first_part = request.rfile.read(min(length, split_length))
            boundary = first_part.split(b'\r\n')[0]+b'\r\n'
            head_part = first_part.split(boundary)
            file_start = head_part[1].find(b'\r\n\r\n')+4
            fileinfo = head_part[1][:file_start].decode('utf-8')
            filename = fileinfo.split("filename=")[1].split('"')[1]
            if filename == "":
                request.errsvc.handle(request, path, args, "POST", HTTPStatus.BAD_REQUEST)
                return
            local_filepaths = os.path.join(real_path, filename)
            if os.path.exists(local_filepaths):
                request.errsvc.handle(request, path, args, "POST", HTTPStatus.CONFLICT)
                return
            
            # if length <= split_length:
            #     file = head_part[1][file_start:-len(boundary)-2]
            #     with open(local_filepaths, 'wb') as f:
            #         f.write(file)
            # else:
            #     length -= split_length
                # this_part = head_part[1][file_start:]
                # if len(head_part)>2:
                #     for part in head_part[2:]:
                #         this_part += part
                # finished=False
                # with open(local_filepaths, 'wb') as f:
                #     while length > 0:
                #         next_part = request.rfile.read(min(length, split_length))
                #         length -= min(length, split_length)
                #         if next_part == b'':
                #             request.errsvc.handle(request, path, args, "POST", HTTPStatus.BAD_REQUEST)
                #             return
                #         file_end=(this_part+next_part).rfind(boundary)-len(boundary)-2
                #         if file_end>0:
                #             f.write((this_part+next_part)[:file_end])
                #             finished=True
                #             break
                #         f.write(this_part)
                #         this_part = next_part     
            this_part = head_part[1][file_start:]
            length -= len(boundary)+4
            if length <= split_length:
                with open(local_filepaths, 'wb') as f:
                    f.write(head_part[1][file_start:-len(boundary)-4])
            else:
                length -= split_length
                with open(local_filepaths, 'wb') as f:
                    f.write(this_part)
                    while length > 0:
                        this_part = request.rfile.read(min(length, split_length))
                        length -= min(length, split_length)
                        if this_part == b'':
                            request.errsvc.handle(request, path, args, "POST", HTTPStatus.BAD_REQUEST)
                            return
                        f.write(this_part)
            request.send_response(HTTPStatus.CREATED)
            if request.path[-1]!="/":
                request.send_header("Location", request.path+"/"+quote(filename))
            else:
                request.send_header("Location", request.path+quote(filename))
            request.end_headers()
        else:
            request.errsvc.handle(request, path, args, "POST", HTTPStatus.LENGTH_REQUIRED)
            return