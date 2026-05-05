"""CLI 入口：参数解析、服务启动、Windows 右键菜单。

CLI entry point: argument parsing, server startup, Windows right-click menu.
"""
from __future__ import annotations

import argparse
import os
import sys
import logging
from cryskura import __version__
from .server import HTTPServer
from .Services.file_service import FileService
from .Services.page_service import PageService
from .Services.redirect_service import RedirectService

logger = logging.getLogger(__name__)

resource_path = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    """CLI 主入口：解析命令行参数并启动服务器或管理右键菜单。

    CLI main entry point: parse command-line arguments and start the server
    or manage the Windows right-click menu.
    """
    parser = argparse.ArgumentParser(description="CryskuraHTTP Server")
    parser.add_argument(
        "-i", "--interface", type=str, default="0.0.0.0",
        help="The interface to listen on.",
    )
    parser.add_argument("-p", "--port", type=int, default=8080, help="The port to listen on.")
    parser.add_argument(
        "-c", "--certfile", type=str, default=None,
        help="The path to the certificate file.",
    )
    parser.add_argument("-f", "--forcePort", action="store_true",
                        help="Force to use the specified port even if it is already in use.")
    parser.add_argument(
        "-d", "--path", type=str, default=None,
        help="The path to the directory to serve.",
    )
    parser.add_argument("-n", "--name", type=str, default=None, help="The name of the server.")
    parser.add_argument("-j", "--http_to_https", type=int, default=None,
                        help="Port to redirect HTTP requests to HTTPS.")
    parser.add_argument(
        "-w", "--webMode", action="store_true",
        help="Enable web mode. Which means only files can be accessed, not directories.",
    )
    parser.add_argument("-r", "--allowResume", action="store_true", help="Allow resume download.")
    parser.add_argument(
        "-b", "--browser", action="store_true",
        help="Open the browser after starting the server.",
    )
    parser.add_argument(
        "-ba", "--browserAddress", type=str, default=None,
        help="The address to open in the browser.",
    )
    parser.add_argument("-t", "--allowUpload", action="store_true", help="Allow file upload.")
    parser.add_argument("-u", "--uPnP", action="store_true", help="Enable uPnP port forwarding.")
    parser.add_argument("-al", "--accessLog", action="store_true", help="Enable access logging.")
    parser.add_argument("-6", "--ipv6Only", action="store_true",
                        help="Disable IPv6 dual-stack (set IPV6_V6ONLY=1). "
                             "By default, IPv6 sockets accept IPv4 connections.")
    parser.add_argument("-pf", "--pidFile", type=str, default=None, help="Path to PID file.")
    parser.add_argument(
        "-ar", "--addRightClick", action="store_true",
        help="Add to right-click menu.",
    )
    parser.add_argument(
        "-rr", "--removeRightClick", action="store_true",
        help="Remove from right-click menu.",
    )
    parser.add_argument("-v", "--version", action="version", version=f"CryskuraHTTP/{__version__}")
    args = parser.parse_args()

    custom_name = args.name is not None
    if args.name is None:
        args.name = f"CryskuraHTTP/{__version__}"

    launching = not args.addRightClick and not args.removeRightClick

    # ── 右键菜单操作 / Right-click menu operations ──────────────
    if not launching:
        _handle_right_click(args, custom_name)
        return

    # ── 路径校验 / Path validation ───────────────────────────────
    if args.path is not None:
        if not os.path.exists(args.path):
            raise ValueError(f"Path {args.path} does not exist.")
        if not os.path.isdir(args.path):
            raise ValueError(f"Path {args.path} is not a directory.")
    else:
        args.path = os.getcwd()

    # ── 服务创建 / Service creation ──────────────────────────────
    services = _build_services(args)

    # ── HTTP→HTTPS 重定向 / HTTP-to-HTTPS redirect ───────────────
    if args.certfile is not None:
        if not os.path.exists(args.certfile) or not os.path.isfile(args.certfile):
            raise ValueError(f"Certfile {args.certfile} does not exist.")
        if args.http_to_https is not None:
            rs = RedirectService("/", "/", default_protocol="https")
            redirect_server = HTTPServer(
                interface=args.interface, port=args.http_to_https,
                services=[rs], server_name=args.name,
                forcePort=args.forcePort, uPnP=args.uPnP,
                ipv6_v6only=True if args.ipv6Only else None,
            )
            redirect_server.start()
    elif args.http_to_https is not None:
        raise ValueError("HTTP to HTTPS redirection requires a certificate file.")

    # ── 启动服务器 / Launch server ───────────────────────────────
    _launch_server(args, services)


def _build_services(args: argparse.Namespace) -> list:
    """根据命令行参数创建服务列表。

    Build the list of services from parsed command-line arguments.

    Args:
        args: 已解析的命令行参数。 / Parsed command-line arguments.

    Returns:
        list: 服务实例列表。 / List of service instances.
    """
    if args.webMode:
        if args.allowResume:
            logger.warning(
                "Web mode does not support resume download, "
                "resume download is disabled.")
        if args.allowUpload:
            raise ValueError("Web mode does not support file upload.")
        return [PageService(args.path, "/")]
    return [FileService(
        args.path, "/", server_name=args.name,
        allowResume=args.allowResume, allowUpload=args.allowUpload,
    )]


def _launch_server(args: argparse.Namespace, services: list) -> None:
    """启动服务器主循环，处理 PID 文件写入与清理。

    Start the server main loop, handling PID file creation and cleanup.

    Args:
        args: 已解析的命令行参数。 / Parsed command-line arguments.
        services: 服务实例列表。 / List of service instances.
    """
    # PID 文件写入 / Write PID file if requested.
    if args.pidFile is not None:
        try:
            with open(args.pidFile, "w", encoding="utf-8") as pf:
                pf.write(str(os.getpid()))
            logger.info("PID file written to %s", args.pidFile)
        except OSError as e:
            logger.warning("Failed to write PID file %s: %s", args.pidFile, e)

    server = HTTPServer(
        interface=args.interface, port=args.port,
        services=services, server_name=args.name,
        forcePort=args.forcePort, certfile=args.certfile,
        uPnP=args.uPnP, access_log=args.accessLog,
        ipv6_v6only=True if args.ipv6Only else None,
    )
    try:
        _maybe_open_browser(args)
        server.start(threaded=False)
    finally:
        if args.pidFile is not None:
            try:
                os.remove(args.pidFile)
                logger.info("PID file %s removed.", args.pidFile)
            except OSError:
                pass


def _maybe_open_browser(args: argparse.Namespace) -> None:
    """根据参数决定是否打开浏览器。

    Open the default web browser if the --browser flag was set.

    Args:
        args: 已解析的命令行参数。 / Parsed command-line arguments.
    """
    if not args.browser:
        return
    try:
        import webbrowser
    except ImportError as exc:
        raise ImportError("The webbrowser module is not available.") from exc

    protocol = "https" if args.certfile is not None else "http"
    if args.browserAddress is not None:
        if (
            args.browserAddress.startswith("http://")
            or args.browserAddress.startswith("https://")
        ):
            url = args.browserAddress
        else:
            url = f"{protocol}://{args.browserAddress}"
    elif args.interface in ("0.0.0.0", "::1"):
        url = f"{protocol}://localhost:{args.port}"
    else:
        url = f"{protocol}://{args.interface}:{args.port}"
    webbrowser.open(url)


def _handle_right_click(args: argparse.Namespace, custom_name: bool) -> None:
    """处理右键菜单添加/移除操作（仅 Windows）。

    Handle right-click menu add/remove operations (Windows only).

    Args:
        args: 已解析的命令行参数。 / Parsed command-line arguments.
        custom_name: 是否使用自定义服务器名称。
                     Whether a custom server name was provided.
    """
    from .entry.rightclick import add_to_right_click_menu, remove_from_right_click_menu
    try:
        if args.addRightClick:
            add_to_right_click_menu(
                args.interface, args.port, args.certfile, args.forcePort,
                args.name, args.http_to_https, args.allowResume,
                args.browser, args.uPnP, custom_name, args.browserAddress,
            )
        elif args.removeRightClick:
            remove_from_right_click_menu()
    except OSError as e:
        logger.error("Right-click menu operation failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
