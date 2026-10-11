# SPDX-License-Identifier: GPL-3.0-or-later
"""MR.Softie's own icon set (drawn by docs/make_icons.py), loaded as Blender previews."""
import os

import bpy.utils.previews

_DIR = os.path.join(os.path.dirname(__file__), "icons")
_previews = None


def icon(name):
    """icon_value for one of our icons, or 0 (no icon) if it isn't available."""
    if _previews is None:
        return 0
    item = _previews.get(name)
    return item.icon_id if item else 0


def register():
    global _previews
    _previews = bpy.utils.previews.new()
    if os.path.isdir(_DIR):
        for file in sorted(os.listdir(_DIR)):
            if file.endswith(".png"):
                _previews.load(file[:-4], os.path.join(_DIR, file), 'IMAGE')


def unregister():
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
