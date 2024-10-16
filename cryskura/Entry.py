import os
import sys
import ctypes
import locale
import webbrowser
from cryskura import __version__
from .Server import HTTPServer
from .Services import FileService, PageService,RedirectService

current_pid = os.getpid()
resource_path = os.path.dirname(os.path.abspath(__file__))
application_path = os.path.abspath(sys.argv[0])
python_path = os.path.abspath(sys.executable)
application_args = sys.argv[1:]

def right_click_menu_check():
    # 检查是否是Windows系统
    if os.name != "nt":
        raise OSError("This function is only available on Windows.")
    application_extension = os.path.splitext(application_path)[1]
    if application_extension != ".exe":
        raise ValueError("This function is only available for executable files.")
    # 检查是否有管理员权限
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # 检查sudo是否可用
        print("This function requires administrator privileges.")
        if os.system("sudo -V") != 0:
            raise PermissionError("Please run this script as an administrator.")
        else:
            print("Trying to use sudo...")
            os.system(f"sudo {application_path} {' '.join(application_args)}")
            sys.exit(0)
        # raise PermissionError("This function requires administrator privileges.")
    import winreg
    # 检查是否已经添加到右键菜单
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"directory\shell\CryskuraHTTP")
        winreg.CloseKey(key)
        return winreg,True
    except FileNotFoundError:
        pass
    return winreg,False

def add_to_right_click_menu(interface:str="0.0.0.0", port:int=8080, certfile=None, forcePort:bool=False, name=None, http_to_https=None, allowResume=False, browser=False, uPnP=False,custome_name=False):
    winreg,exist = right_click_menu_check()
    if exist:
        print("CryskuraHTTP is already in the right-click menu.")
        remove_from_right_click_menu()
    print("Adding to right-click menu...")
    args = f'-i {interface} -p {port} -n "{name}"'
    if certfile is not None:
        args += f' -c "{certfile}"'
    if forcePort:
        args += " -f"
    if http_to_https is not None:
        args += f' -j {http_to_https}'
    if allowResume:
        args += " -r"
    if browser:
        args += " -b"
    if uPnP:
        args += " -u"
    args_web = args + " -w"
    args_upload = args + " -t"
    # 针对文件夹，及文件夹内部的空白处，创建右键菜单项，支持多语言
    # 菜单项下包括三个子项，分别为以文件模式、网页模式、上传模式启动服务器
    lang, _ = locale.getdefaultlocale()
    
    if lang.startswith("zh"):
        if not custome_name or name is None:
            program_name="水樱"
        else:
            program_name=name
        menu_text = f"使用{program_name}在此启动HTTP服务器"
        file_mode_text = "文件模式(禁用上传)"
        web_mode_text = "网页模式"
        upload_mode_text = "文件模式(启用上传)"
    else:
        if not custome_name or name is None:
            program_name="Cryskura"
        else:
            program_name=name
        menu_text = f"Start HTTP Server with {program_name} here"
        file_mode_text = "File Mode(Download Only)"
        web_mode_text = "Web Mode"
        upload_mode_text = "File Mode(Allow Upload)"

    for reg in [r"directory\shell", r"directory\background\shell"]:
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP")
        winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, menu_text)
        winreg.SetValueEx(key, "SubCommands", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)
        
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP\Shell")

        shell=winreg.CreateKey(key, "Web")
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, web_mode_text)
        command=winreg.CreateKey(shell, "command")
        winreg.SetValueEx(command, "", 0, winreg.REG_SZ, f'"{application_path}" {args_web} -d "%V"')
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        shell=winreg.CreateKey(key, "File")
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, file_mode_text)
        command=winreg.CreateKey(shell, "command")
        winreg.SetValueEx(command, "", 0, winreg.REG_SZ, f'"{application_path}" {args} -d "%V"')
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        shell=winreg.CreateKey(key, "Upload")
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, upload_mode_text)
        command=winreg.CreateKey(shell, "command")
        winreg.SetValueEx(command, "", 0, winreg.REG_SZ, f'"{application_path}" {args_upload} -d "%V"')
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        winreg.CloseKey(key)

    print("Added to right-click menu.")


def remove_from_right_click_menu():
    winreg,exist = right_click_menu_check()
    if not exist:
        raise ValueError("CryskuraHTTP is not in the right-click menu.")
    print("Removing from right-click menu...")
    for reg in [r"directory\shell", r"directory\background\shell"]:
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP\Shell\File\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP\Shell\File")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP\Shell\Web\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP\Shell\Web")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP\Shell\Upload\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP\Shell\Upload")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP\Shell")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg+r"\CryskuraHTTP")
    print("Removed from right-click menu.")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="CryskuraHTTP Server")
    parser.add_argument("-i", "--interface", type=str, default="0.0.0.0", help="The interface to listen on.")
    parser.add_argument("-p", "--port", type=int, default=8080, help="The port to listen on.")
    parser.add_argument("-c", "--certfile", type=str, default=None, help="The path to the certificate file.")
    parser.add_argument("-f", "--forcePort", action="store_true", help="Force to use the specified port even if it is already in use.")
    parser.add_argument("-d", "--path", type=str, default=None, help="The path to the directory to serve.")
    parser.add_argument("-n", "--name", type=str, default=None, help="The name of the server.")
    parser.add_argument("-j", "--http_to_https", type=int, default=None, help="Port to redirect HTTP requests to HTTPS.")
    parser.add_argument("-w", "--webMode", action="store_true", help="Enable web mode. Which means only files can be accessed, not directories.")
    parser.add_argument("-r", "--allowResume", action="store_true", help="Allow resume download.")
    parser.add_argument("-b", "--browser", action="store_true", help="Open the browser after starting the server.")
    parser.add_argument("-t", "--allowUpload", action="store_true", help="Allow file upload.")
    parser.add_argument("-u", "--uPnP", action="store_true", help="Enable uPnP port forwarding.")
    parser.add_argument("-ar", "--addRightClick", action="store_true", help="Add to right-click menu.")
    parser.add_argument("-rr", "--removeRightClick", action="store_true", help="Remove from right-click menu.")
    parser.add_argument("-v", "--version", action="version", version=f"CryskuraHTTP/{__version__}")
    args = parser.parse_args()

    if args.name is None:
        args.name = f"CryskuraHTTP/{__version__}"
        custome_name=False
    else:
        custome_name=True

    lanuch = not args.addRightClick and not args.removeRightClick

    if args.path is not None:
        if not os.path.exists(args.path):
            raise ValueError(f"Path {args.path} does not exist.")
        if not os.path.isdir(args.path):
            raise ValueError(f"Path {args.path} is not a directory.")
    else:
        args.path = os.getcwd()
    if args.webMode:
        if args.allowResume:
            raise ValueError("Web mode does not support resume download.")
        if args.allowUpload:
            raise ValueError("Web mode does not support file upload.")
        if lanuch:
            service = PageService(args.path, "/")
    else:
        if lanuch:
            service = FileService(args.path, "/", server_name=args.name, allowResume=args.allowResume, allowUpload=args.allowUpload)
    if lanuch:
        services = [service]
    # else:
    #     services = None
    if args.certfile is not None:
        if not os.path.exists(args.certfile) or not os.path.isfile(args.certfile):
            raise ValueError(f"Certfile {args.certfile} does not exist.")
        if args.http_to_https is not None and lanuch:
            rs=RedirectService("/","/",default_protocol="https")#f"https://{args.interface}:{args.port}")
            redirect_server = HTTPServer(interface=args.interface, port=args.http_to_https, services=[rs], server_name=args.name, forcePort=args.forcePort, uPnP=args.uPnP)
            redirect_server.start()
    elif args.http_to_https is not None:
        raise ValueError("HTTP to HTTPS redirection requires a certificate file.")
    
    if lanuch:
        server = HTTPServer(interface=args.interface, port=args.port, services=services, server_name=args.name, forcePort=args.forcePort, certfile=args.certfile, uPnP=args.uPnP)
        if args.browser:
            if args.interface == "0.0.0.0" or args.interface == "::1":
                webbrowser.open(f"http://localhost:{args.port}")
            else:
                webbrowser.open(f"http://{args.interface}:{args.port}")
        server.start(threaded=False)
    elif args.addRightClick:
        add_to_right_click_menu(args.interface, args.port, args.certfile, args.forcePort, args.name, args.http_to_https, args.allowResume, args.browser, args.uPnP,custome_name)
    elif args.removeRightClick:
        remove_from_right_click_menu()

if __name__ == "__main__":
    main()