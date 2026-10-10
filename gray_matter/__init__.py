# SPDX-License-Identifier: GPL-3.0-or-later
"""Gray Matter: a classic SI-style workflow layer for Blender.

Not affiliated with or endorsed by Autodesk. All names, icons and artwork
in this project are original.
"""

from . import preferences, operators, tools, mcp_panel, keymap

_modules = (preferences, operators, tools, mcp_panel, keymap)


def register():
    for mod in _modules:
        mod.register()


def unregister():
    for mod in reversed(_modules):
        mod.unregister()
