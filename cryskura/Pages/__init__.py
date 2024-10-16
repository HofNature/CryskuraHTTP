import importlib.resources as res
from cryskura import Pages
import base64

Directory_Page = res.read_text(Pages, "directory.html", encoding='utf-8', errors='strict')
Error_Page = res.read_text(Pages, "error.html", encoding='utf-8', errors='strict')
Cryskura_Icon = "data:image/png;base64,"+base64.b64encode(res.read_binary(Pages, "Cryskura.png")).decode('utf-8')