# SPDX-License-Identifier: GPL-3.0-or-later
"""MR.Softie: a classic SI-style workflow layer for Blender.

Not affiliated with or endorsed by Autodesk. All names, icons and artwork
in this project are original.
"""

from . import (icons, preferences, viewport, operators, ui_patch, tools, toolbar, mcp_panel, workspace,
               schematic, ppg, ice, passes, anim, scripting, modeling, materials, layers, keymap)

_modules = (icons, preferences, viewport, operators, ui_patch, tools, toolbar, mcp_panel, workspace,
            schematic, ppg, ice, passes, anim, scripting, modeling, materials, layers, keymap)


def register():
    for mod in _modules:
        mod.register()


def unregister():
    for mod in reversed(_modules):
        mod.unregister()
