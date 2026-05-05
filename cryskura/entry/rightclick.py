"""右键菜单注册/移除逻辑（仅 Windows）。

Windows right-click context menu registration and removal logic.
"""
from __future__ import annotations

import os
import sys
import ctypes
import locale
import logging
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

resource_path = os.path.dirname(os.path.abspath(__file__))
application_path = os.path.abspath(sys.argv[0])
application_args = sys.argv[1:]


def check_environment() -> Tuple[Any, bool]:
    """检查运行环境是否为 Windows + .exe，并返回 winreg 模块和注册状态。

    Check that the environment is Windows + .exe, then return the winreg
    module and whether the menu entry is already registered.

    Returns:
        tuple: (winreg 模块, 是否已注册) / (winreg module, is_registered).

    Raises:
        OSError: 非 Windows 系统。 / Not running on Windows.
        ValueError: 应用程序不是可执行文件。 / Application is not an .exe.
        PermissionError: 非管理员且无法提权。 / Not admin and cannot elevate.
    """
    if os.name != "nt":
        raise OSError("This function is only available on Windows.")
    if os.path.splitext(application_path)[1] != ".exe":
        raise ValueError("This function is only available for executable files.")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        logger.info("This function requires administrator privileges.")
        # Issue 5: use subprocess.run with list args to prevent shell injection
        import subprocess
        try:
            subprocess.run(["sudo", "-V"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise PermissionError("Please run this script as an administrator.")
        logger.info("Trying to use sudo...")
        subprocess.run(["sudo", application_path] + list(application_args), check=True)
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
    interface: str = "0.0.0.0",
    port: int = 8080,
    certfile: Optional[str] = None,
    forcePort: bool = False,
    name: Optional[str] = None,
    http_to_https: Optional[int] = None,
    allowResume: bool = False,
    browser: bool = False,
    uPnP: bool = False,
    custome_name: bool = False,
    browserAddress: Optional[str] = None,
) -> None:
    """将 CryskuraHTTP 添加到 Windows 右键菜单。

    Add CryskuraHTTP to the Windows Explorer right-click context menu.

    Args:
        interface: 监听地址（默认 "0.0.0.0"）。 / Bind address (default "0.0.0.0").
        port: 监听端口（默认 8080）。 / Listen port (default 8080).
        certfile: PEM 证书路径（启用 HTTPS）。 / PEM cert path (enables HTTPS).
        forcePort: 强制使用端口。 / Force use of the port even if in use.
        name: 服务器显示名称。 / Server display name.
        http_to_https: HTTP 重定向到 HTTPS 的端口。 / Port for HTTP-to-HTTPS redirect.
        allowResume: 是否支持断点续传。 / Enable resume download.
        browser: 是否自动打开浏览器。 / Open browser on start.
        uPnP: 是否启用 UPnP。 / Enable UPnP port forwarding.
        custome_name: 是否使用自定义名称。 / Whether a custom name was provided.
        browserAddress: 浏览器打开地址。 / Address to open in the browser.
    """
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
        winreg.SetValueEx(
            key, "Icon", 0, winreg.REG_SZ,
            os.path.join(icons_path, "cryskura.ico,0"),
        )
        winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, menu_text)
        winreg.SetValueEx(key, "SubCommands", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)

        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, reg + r"\CryskuraHTTP\Shell")

        shell = winreg.CreateKey(key, "Web")
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, web_mode_text)
        winreg.SetValueEx(
            shell, "Icon", 0, winreg.REG_SZ,
            os.path.join(icons_path, "webpage.ico,0"),
        )
        command = winreg.CreateKey(shell, "command")
        winreg.SetValueEx(command, "", 0, winreg.REG_SZ, f'"{application_path}" {args_web} -d "%V"')
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        shell = winreg.CreateKey(key, "File")
        winreg.SetValueEx(
            shell, "Icon", 0, winreg.REG_SZ,
            os.path.join(icons_path, "directory.ico,0"),
        )
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, file_mode_text)
        command = winreg.CreateKey(shell, "command")
        winreg.SetValueEx(command, "", 0, winreg.REG_SZ, f'"{application_path}" {args} -d "%V"')
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        shell = winreg.CreateKey(key, "Upload")
        winreg.SetValueEx(shell, "MUIVerb", 0, winreg.REG_SZ, upload_mode_text)
        winreg.SetValueEx(
            shell, "Icon", 0, winreg.REG_SZ,
            os.path.join(icons_path, "fileupload.ico,0"),
        )
        command = winreg.CreateKey(shell, "command")
        winreg.SetValueEx(
            command, "", 0, winreg.REG_SZ,
            f'"{application_path}" {args_upload} -d "%V"',
        )
        winreg.CloseKey(command)
        winreg.CloseKey(shell)

        winreg.CloseKey(key)

    logger.info("Added to right-click menu.")


def remove_from_right_click_menu() -> None:
    """从 Windows 右键菜单中移除 CryskuraHTTP 条目。

    Remove the CryskuraHTTP entry from the Windows Explorer right-click menu.

    Raises:
        ValueError: 菜单项不存在。 / Menu entry does not exist.
    """
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
