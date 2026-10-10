# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.props import BoolProperty, EnumProperty


def _addon_prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def get(name, default=None):
    prefs = _addon_prefs()
    return getattr(prefs, name, default) if prefs else default


def _update_keymap(self, context):
    from . import keymap
    keymap.unregister()
    keymap.register()


def _update_tools(self, context):
    from . import tools
    tools.unregister()
    tools.register()


class MS_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    use_keymap: BoolProperty(
        name="Classic Hotkeys",
        description="Enable the classic SI-style hotkeys (Space, V/C/X, T/E/Y, S-navigation, etc.)",
        default=True,
        update=_update_keymap,
    )
    mouse_axis_mode: EnumProperty(
        name="SRT Mouse Buttons",
        description="How mouse buttons behave with the MR.Softie Translate/Rotate/Scale tools",
        items=(
            ('XYZ', "Left/Middle/Right = X/Y/Z",
             "Each mouse button drags along one axis, classic style"),
            ('FREE', "Left = Free, Middle/Right = Y/Z",
             "Left button drags freely in the view plane"),
        ),
        default='XYZ',
        update=_update_tools,
    )
    override_number_keys: BoolProperty(
        name="Number Keys Open Editors",
        description="7 = Shader Editor, 8 = Outliner (explorer), 0 = Graph Editor, "
                    "each in a floating window. Overrides Blender's collection-visibility keys",
        default=True,
        update=_update_keymap,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_keymap")
        col = layout.column()
        col.active = self.use_keymap
        col.prop(self, "override_number_keys")
        layout.prop(self, "mouse_axis_mode")
        box = layout.box()
        box.label(text="Hotkey cheat sheet", icon='INFO')
        from .keymap import CHEAT_SHEET
        grid = box.grid_flow(columns=2, even_columns=False)
        for key, what in CHEAT_SHEET:
            grid.label(text=key)
            grid.label(text=what)


def register():
    bpy.utils.register_class(MS_AddonPreferences)


def unregister():
    bpy.utils.unregister_class(MS_AddonPreferences)
