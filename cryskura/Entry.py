import os
import webbrowser
from .Server import HTTPServer
from .Services import FileService, PageService

def main():
    import argparse
    parser = argparse.ArgumentParser(description="CryskuraHTTP Server")
    parser.add_argument("-i", "--interface", type=str, default="0.0.0.0", help="The interface to listen on.")
    parser.add_argument("-p", "--port", type=int, default=8080, help="The port to listen on.")
    parser.add_argument("-c", "--certfile", type=str, default=None, help="The path to the certificate file.")
    parser.add_argument("-f", "--forcePort", action="store_true", help="Force to use the specified port even if it is already in use.")
    parser.add_argument("-d", "--path", type=str, default=None, help="The path to the directory to serve.")
    parser.add_argument("-n", "--name", type=str, default="CryskuraHTTP/1.0", help="The name of the server.")
    parser.add_argument("-w", "--webMode", action="store_true", help="Enable web mode. Which means only files can be accessed, not directories.")
    parser.add_argument("-r", "--allowResume", action="store_true", help="Allow resume download.")
    parser.add_argument("-b", "--browser", action="store_true", help="Open the browser after starting the server.")
    parser.add_argument("-u", "--uPnP", action="store_true", help="Enable uPnP port forwarding.")
    args = parser.parse_args()

    if args.path is not None:
        if not os.path.exists(args.path):
            raise ValueError(f"Path {args.path} does not exist.")
        if not os.path.isdir(args.path):
            raise ValueError(f"Path {args.path} is not a directory.")
        if args.webMode:
            if args.allowResume:
                raise ValueError("Web mode does not support resume download.")
            service = PageService(args.path, "/")
        else:
            service = FileService(args.path, "/", server_name=args.name, allowResume=args.allowResume)
        services = [service]
    else:
        services = None
    if args.certfile is not None:
        if not os.path.exists(args.certfile):
            raise ValueError(f"Certfile {args.certfile} does not exist.")
    server = HTTPServer(interface=args.interface, port=args.port, services=services, server_name=args.name, forcePort=args.forcePort, certfile=args.certfile, uPnP=args.uPnP)
    if args.browser:
        webbrowser.open(f"http://{args.interface}:{args.port}")
    server.start(threaded=False)

if __name__ == "__main__":
    main()