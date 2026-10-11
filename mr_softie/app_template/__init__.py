# SPDX-License-Identifier: GPL-3.0-or-later
"""MR.Softie application template (installed by the MR.Softie add-on).

Opens Blender straight into the MR.Softie workspace. The template only provides
the startup file; the MR.Softie add-on provides the tools, so it is enabled here
for the session if it is installed but switched off.
"""
import bpy


def register():
    import addon_utils
    for mod in addon_utils.modules(refresh=False):
        name = mod.__name__
        if name == "mr_softie" or name.endswith(".mr_softie"):
            if name not in bpy.context.preferences.addons:
                addon_utils.enable(name, default_set=False)
            break


def unregister():
    pass
