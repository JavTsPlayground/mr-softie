# SPDX-License-Identifier: GPL-3.0-or-later
"""Classic SI-style hotkeys, added on top of the user's keymap.

Everything lives in Blender's add-on keyconfig, so disabling the add-on (or
the "Classic Hotkeys" preference) restores Blender's own bindings untouched.
"""
import bpy

from . import preferences

CHEAT_SHEET = (
    ("Space", "Object selection (leaves component mode)"),
    ("V / C / X", "SRT Translate / Rotate / Scale tool"),
    ("  in tool: L / M / R drag", "Constrain to X / Y / Z (Shift+L = free)"),
    ("T / E / Y", "Point / Edge / Polygon selection"),
    ("S + Left / Middle / Right", "Pan / Dolly / Orbit"),
    ("F / A", "Frame selection / Frame all"),
    ("Ctrl+A", "Select all"),
    ("Ctrl+D", "Duplicate"),
    ("Ctrl+Y", "Redo"),
    ("Enter", "Property editor for selection (floating)"),
    ("7 / 8 / 0", "Shader editor / Outliner (explorer) / Graph editor"),
)

# keymap name -> (space_type, mode)  mode is 'object', 'mesh' or None (both)
KEYMAPS = (
    ("Object Mode", 'EMPTY', 'object'),
    ("Mesh", 'EMPTY', 'mesh'),
    ("3D View", 'VIEW_3D', None),
)

_addon_keymaps = []


def _items(mode, number_keys):
    """Yield (idname, type, value, modifiers, properties) for one keymap."""
    yield ("gray_matter.object_select", 'SPACE', 'PRESS', {}, {})
    yield ("gray_matter.srt_tool", 'V', 'PRESS', {}, {"kind": 'translate'})
    yield ("gray_matter.srt_tool", 'C', 'PRESS', {}, {"kind": 'rotate'})
    yield ("gray_matter.srt_tool", 'X', 'PRESS', {}, {"kind": 'scale'})
    yield ("gray_matter.component_mode", 'T', 'PRESS', {}, {"component": 'VERT'})
    yield ("gray_matter.component_mode", 'E', 'PRESS', {}, {"component": 'EDGE'})
    yield ("gray_matter.component_mode", 'Y', 'PRESS', {}, {"component": 'FACE'})

    # S held = navigation. The bare press is swallowed so Blender's scale
    # doesn't start.
    yield ("view3d.move", 'LEFTMOUSE', 'PRESS', {"key_modifier": 'S'}, {})
    yield ("view3d.zoom", 'MIDDLEMOUSE', 'PRESS', {"key_modifier": 'S'}, {})
    yield ("view3d.rotate", 'RIGHTMOUSE', 'PRESS', {"key_modifier": 'S'}, {})
    yield ("gray_matter.swallow", 'S', 'PRESS', {}, {})

    yield ("view3d.view_selected", 'F', 'PRESS', {}, {})
    yield ("view3d.view_all", 'A', 'PRESS', {}, {})
    yield ("ed.redo", 'Y', 'PRESS', {"ctrl": True}, {})
    yield ("gray_matter.open_editor", 'RET', 'PRESS', {}, {"ui_type": 'PROPERTIES'})

    if mode in (None, 'object'):
        yield ("object.select_all", 'A', 'PRESS', {"ctrl": True}, {"action": 'SELECT'})
        yield ("object.duplicate_move", 'D', 'PRESS', {"ctrl": True}, {})
    if mode == 'mesh':
        yield ("mesh.select_all", 'A', 'PRESS', {"ctrl": True}, {"action": 'SELECT'})
        yield ("mesh.duplicate_move", 'D', 'PRESS', {"ctrl": True}, {})

    if number_keys:
        yield ("gray_matter.open_editor", 'SEVEN', 'PRESS', {}, {"ui_type": 'ShaderNodeTree'})
        yield ("gray_matter.open_editor", 'EIGHT', 'PRESS', {}, {"ui_type": 'OUTLINER'})
        yield ("gray_matter.open_editor", 'ZERO', 'PRESS', {}, {"ui_type": 'FCURVES'})


def register():
    if not preferences.get("use_keymap", True):
        return
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is None:
        return
    number_keys = preferences.get("override_number_keys", True)
    for name, space_type, mode in KEYMAPS:
        km = kc.keymaps.new(name=name, space_type=space_type)
        for idname, key, value, mods, props in _items(mode, number_keys):
            kmi = km.keymap_items.new(idname, key, value, **mods)
            for prop, val in props.items():
                setattr(kmi.properties, prop, val)
            _addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in _addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _addon_keymaps.clear()
