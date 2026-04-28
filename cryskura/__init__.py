__version__ = "1.0"
__author__ = "Cryskura"
__license__ = "MIT"
__all__ = ["Server", "Handler", "uPnP", "Services", "Compression"]

from .Server import HTTPServer as Server
from .Handler import HTTPRequestHandler as Handler
from .uPnP import uPnPClient as uPnP
from . import Services
from . import Compression
