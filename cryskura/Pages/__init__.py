import importlib.resources as res
from cryskura import Pages
import urllib.parse

Directory_Page = res.read_text(Pages, "directory.html", encoding='utf-8', errors='strict')
Error_Page = res.read_text(Pages, "error.html", encoding='utf-8', errors='strict')
Login_Page = res.read_text(Pages, "login.html", encoding='utf-8', errors='strict')
Cryskura_Icon = 'data:image/svg+xml;charset=utf-8,' + urllib.parse.quote(
    ''.join([r.strip() for r in res.read_text(Pages, "Cryskura.svg", encoding='utf-8', errors='strict').splitlines()]
), safe='')