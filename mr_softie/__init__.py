# SPDX-License-Identifier: GPL-3.0-or-later
"""MR.Softie: a classic SI-style workflow layer for Blender.

Not affiliated with or endorsed by Autodesk. All names, icons and artwork
in this project are original.
"""

from . import preferences, viewport, operators, tools, toolbar, mcp_panel, workspace, keymap

_modules = (preferences, viewport, operators, tools, toolbar, mcp_panel, workspace, keymap)


def register():
    for mod in _modules:
        mod.register()


def unregister():
    for mod in reversed(_modules):
        mod.unregister()
