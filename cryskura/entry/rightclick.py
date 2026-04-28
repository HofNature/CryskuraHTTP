"""右键菜单注册/移除逻辑（仅 Windows）。"""
from __future__ import annotations

import os
import sys
import ctypes
import locale
import logging

logger = logging.getLogger(__name__)

resource_path = os.path.dirname(os.path.abspath(__file__))
application_path = os.path.abspath(sys.argv[0])
application_args = sys.argv[1:]


def check_environment():
    """检查是否为 Windows + .exe，返回 (winreg, is_registered)。"""
    if os.name != "nt":
        raise OSError("This function is only available on Windows.")
    if os.path.splitext(application_path)[1] != ".exe":
        raise ValueError("This function is only available for executable files.")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        logger.info("This function requires administrator privileges.")
        if os.system("sudo -V") != 0:
            raise PermissionError("Please run this script as an administrator.")
        logger.info("Trying to use sudo...")
        os.system(f"sudo {application_path} {' '.join(application_args)}")
        sys.exit(0)
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"directory\shell\CryskuraHTTP")
        winreg.CloseKey(key)
        return winreg, True
    except FileNotFoundError:
        pass
    return winreg, False


def add_to_right_click_menu(
    interface: str = "0.0.0.0", port: int = 8080, certfile=None,
    forcePort: bool = False, name=None, http_to_https=None,
    allowResume: bool = False, browser: bool = False, uPnP: bool = False,
    custome_name: bool = False, browserAddress=None,
) -> None:
    winreg, exist = check_environment()
    if exist:
        logger.info("CryskuraHTTP is already in the right-click menu.")
        remove_from_right_click_menu()
    logger.info("Adding to right-click menu...")

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
    if browserAddress is not None:
        args += f' -ba "{browserAddress}"'
    if uPnP:
        args += " -u"
    args_web = args + " -w"
    args_upload = args + " -t"

    try:
        lang = locale.getlocale()[0] or ""
    except Exception:
        lang = ""

    if lang.startswith("zh"):
        if not custome_name or name is None:
            program_name = "水樱"
        else:
            program_name = name
        menu_text = f"使用{program_name}在此启动HTTP服务器"
        file_mode_text = "文件模式(禁用上传)"
        web_mode_text = "网页模式"
        upload_mode_text = "文件模式(启用上传)"
    else:
        if not custome_name or name is None:
            program_name = "Cryskura"
        else:
            program_name = name
        menu_text = f"Start HTTP Server with {program_name} here"
        file_mode_text = "File Mode(Download Only)"
        web_mode_text = "Web Mode"
        upload_mode_text = "File Mode(Allow Upload)"

    icons_path = os.path.join(resource_path, "Icons")
    for reg in [r"directory\shell", r"directory\background\shell"]:
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP")
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, os.path.join(icons_path, "cryskura.ico,0"))
        winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, menu_text)
        winreg.SetValueEx(key, "SubCommands", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)

        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell")

        shell = winreg.CreateKey(key, "Web")
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, web_mode_text)
        winreg.SetValueEx(shell, "Icon", 0, winreg.REG_SZ, os.path.join(icons_path, "webpage.ico,0"))
        command = winreg.CreateKey(shell, "command")
        winreg.SetValueEx(command, "", 0, winreg.REG_SZ, f'"{application_path}" {args_web} -d "%V"')
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        shell = winreg.CreateKey(key, "File")
        winreg.SetValueEx(shell, "Icon", 0, winreg.REG_SZ, os.path.join(icons_path, "directory.ico,0"))
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, file_mode_text)
        command = winreg.CreateKey(shell, "command")
        winreg.SetValueEx(command, "", 0, winreg.REG_SZ, f'"{application_path}" {args} -d "%V"')
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        shell = winreg.CreateKey(key, "Upload")
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, upload_mode_text)
        winreg.SetValueEx(shell, "Icon", 0, winreg.REG_SZ, os.path.join(icons_path, "fileupload.ico,0"))
        command = winreg.CreateKey(shell, "command")
        winreg.SetValueEx(command, "", 0, winreg.REG_SZ, f'"{application_path}" {args_upload} -d "%V"')
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        winreg.CloseKey(key)

    logger.info("Added to right-click menu.")


def remove_from_right_click_menu() -> None:
    winreg, exist = check_environment()
    if not exist:
        raise ValueError("CryskuraHTTP is not in the right-click menu.")
    logger.info("Removing from right-click menu...")
    for reg in [r"directory\shell", r"directory\background\shell"]:
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell\File\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell\File")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell\Web\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell\Web")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell\Upload\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell\Upload")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP")
    logger.info("Removed from right-click menu.")
