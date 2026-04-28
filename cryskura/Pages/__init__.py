import base64
from importlib.resources import files

_pages = files("cryskura.Pages")
Directory_Page = _pages.joinpath("directory.html").read_text(encoding='utf-8')
Error_Page = _pages.joinpath("error.html").read_text(encoding='utf-8')
Cryskura_Icon = "data:image/png;base64," + base64.b64encode(
    _pages.joinpath("Cryskura.png").read_bytes()
).decode('utf-8')
