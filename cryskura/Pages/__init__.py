"""
页面资源模块 | Page Resources Module

该模块管理静态页面资源和图标。
This module manages static page resources and icons.
"""

import importlib.resources as res
import base64
from cryskura import Pages

# 加载HTML页面模板 | Load HTML page templates
Directory_Page = res.read_text(
    Pages, "directory.html", encoding='utf-8', errors='strict'
)
Error_Page = res.read_text(
    Pages, "error.html", encoding='utf-8', errors='strict'
)

# 将图标转换为base64数据URI | Convert icon to base64 data URI
Cryskura_Icon = (
    "data:image/png;base64,"
    + base64.b64encode(res.read_binary(Pages, "Cryskura.png")).decode('utf-8')
)

__all__ = [
    'Directory_Page',
    'Error_Page',
    'Cryskura_Icon'
]
