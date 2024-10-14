import importlib.resources as res
from cryskura import Pages

Directory_Page = res.read_text(Pages, "directory.html", encoding='utf-8', errors='strict')
Error_Page = res.read_text(Pages, "error.html", encoding='utf-8', errors='strict')