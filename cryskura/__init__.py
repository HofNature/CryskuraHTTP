"""
CryskuraHTTP 主包 | CryskuraHTTP Main Package

一个轻量级、可定制的HTTP(s)服务器实现。
A lightweight, customizable HTTP(s) server implementation.
"""

__version__ = "1.0"
__author__ = "Cryskura"
__license__ = "MIT"

from .Server import HTTPServer as Server
from .Handler import HTTPRequestHandler as Handler
from .uPnP import uPnPClient as uPnP

__all__ = [
    'Server',
    'Handler',
    'uPnP',
    '__version__',
    '__author__',
    '__license__'
]
