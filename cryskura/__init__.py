"""CryskuraHTTP — 轻量级 Python HTTP(S) 服务器库。

CryskuraHTTP — A lightweight Python HTTP(S) server library.
"""

__version__ = "1.0"
__author__ = "Cryskura"
__license__ = "MIT"
__all__ = ["Server", "Handler", "uPnP", "Services", "Compression"]

from .server import HTTPServer as Server
from .handler import HTTPRequestHandler as Handler
from .upnp import UPnPClient as uPnP
from . import Services
from . import compression as Compression
