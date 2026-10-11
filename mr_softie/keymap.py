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
    ("  hold instead of tap", "Temporary tool until you let go"),
    ("  in tool: L / M / R drag", "Constrain to X / Y / Z (Shift+L = free)"),
    ("T / E / Y", "Point / Edge / Polygon selection"),
    ("S + Left / Middle / Right", "Pan / Dolly / Orbit"),
    ("F / A", "Frame selection / Frame all"),
    ("Ctrl+A", "Select all"),
    ("Ctrl+D", "Duplicate"),
    ("Ctrl+Y", "Redo"),
    ("K", "Save Key on the marked parameters"),
    ("Alt+4", "Script Editor (command log + editor)"),
    ("Enter", "Property page for the selection (floating)"),
    ("M", "Tweak tool (drag a point, edge, polygon or object to move it)"),
    ("\\", "Add Edge (knife) in component mode"),
    ("Alt + Right click", "Context menu"),
    ("1 / 2 / 3 / 4 / 5", "Toolbar: Model / Animate / Render / Simulate / ICE"),
    ("7 / 8 / 9 / 0", "Render tree / Explorer / Schematic / Animation editor"),
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
    # Tap = switch tool. Hold = temporary tool until the key is released (supra mode).
    yield ("mr_softie.object_select", 'SPACE', 'PRESS', {}, {"supra": True})
    yield ("mr_softie.supra_release", 'SPACE', 'RELEASE', {}, {"key": "select"})
    for key, kind in (('V', 'translate'), ('C', 'rotate'), ('X', 'scale')):
        yield ("mr_softie.srt_tool", key, 'PRESS', {}, {"kind": kind, "supra": True})
        yield ("mr_softie.supra_release", key, 'RELEASE', {}, {"key": kind})
    yield ("mr_softie.component_mode", 'T', 'PRESS', {}, {"component": 'VERT'})
    yield ("mr_softie.component_mode", 'E', 'PRESS', {}, {"component": 'EDGE'})
    yield ("mr_softie.component_mode", 'Y', 'PRESS', {}, {"component": 'FACE'})

    # S held = navigation. The bare press is swallowed so Blender's scale
    # doesn't start.
    yield ("view3d.move", 'LEFTMOUSE', 'PRESS', {"key_modifier": 'S'}, {})
    yield ("view3d.zoom", 'MIDDLEMOUSE', 'PRESS', {"key_modifier": 'S'}, {})
    yield ("view3d.rotate", 'RIGHTMOUSE', 'PRESS', {"key_modifier": 'S'}, {})
    yield ("mr_softie.swallow", 'S', 'PRESS', {}, {})

    yield ("wm.tool_set_by_id", 'M', 'PRESS', {}, {"name": "builtin.select"})
    menu = "VIEW3D_MT_edit_mesh_context_menu" if mode == 'mesh' else "VIEW3D_MT_object_context_menu"
    yield ("wm.call_menu", 'RIGHTMOUSE', 'PRESS', {"alt": True}, {"name": menu})
    yield ("view3d.view_selected", 'F', 'PRESS', {}, {})
    yield ("view3d.view_all", 'A', 'PRESS', {}, {})
    yield ("ed.redo", 'Y', 'PRESS', {"ctrl": True}, {})
    yield ("mr_softie.open_ppg", 'RET', 'PRESS', {}, {})
    yield ("mr_softie.save_key", 'K', 'PRESS', {}, {})
    yield ("mr_softie.open_script_editor", 'FOUR', 'PRESS', {"alt": True}, {})

    if mode in (None, 'object'):
        yield ("object.select_all", 'A', 'PRESS', {"ctrl": True}, {"action": 'SELECT'})
        yield ("object.duplicate_move", 'D', 'PRESS', {"ctrl": True}, {})
    if mode == 'mesh':
        yield ("wm.tool_set_by_id", 'BACK_SLASH', 'PRESS', {}, {"name": "builtin.knife"})
        yield ("mesh.select_all", 'A', 'PRESS', {"ctrl": True}, {"action": 'SELECT'})
        yield ("mesh.duplicate_move", 'D', 'PRESS', {"ctrl": True}, {})

    if number_keys:
        for key, module in (('ONE', 'MODEL'), ('TWO', 'ANIMATE'), ('THREE', 'RENDER'), ('FOUR', 'SIMULATE'),
                            ('FIVE', 'ICE')):
            yield ("wm.context_set_enum", key, 'PRESS', {},
                   {"data_path": "window_manager.mr_softie_module", "value": module})
        yield ("mr_softie.open_editor", 'SEVEN', 'PRESS', {}, {"ui_type": 'ShaderNodeTree'})
        yield ("mr_softie.open_explorer", 'EIGHT', 'PRESS', {}, {})
        yield ("mr_softie.open_schematic", 'NINE', 'PRESS', {}, {})
        yield ("mr_softie.open_editor", 'ZERO', 'PRESS', {}, {"ui_type": 'FCURVES'})


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
            kmi.repeat = False
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
