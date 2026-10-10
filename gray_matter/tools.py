# SPDX-License-Identifier: GPL-3.0-or-later
"""Classic SRT tools: drag anywhere in the viewport to transform the selection.

Left / middle / right mouse buttons constrain to X / Y / Z, the way the
classic SRT tools worked. Holding S turns the mouse buttons into camera
navigation (pan / dolly / orbit) even while a tool is active.
"""
import bpy
from bpy.types import WorkSpaceTool

from . import preferences

AXES = {
    'X': (True, False, False),
    'Y': (False, True, False),
    'Z': (False, False, True),
}

# Navigation while S is held. Listed first in every tool keymap so it wins.
NAV_ITEMS = (
    ("view3d.move", {"type": 'LEFTMOUSE', "value": 'PRESS', "key_modifier": 'S'}, None),
    ("view3d.zoom", {"type": 'MIDDLEMOUSE', "value": 'PRESS', "key_modifier": 'S'}, None),
    ("view3d.rotate", {"type": 'RIGHTMOUSE', "value": 'PRESS', "key_modifier": 'S'}, None),
)

SELECT_ITEMS = (
    ("view3d.select", {"type": 'LEFTMOUSE', "value": 'CLICK'},
     {"properties": [("deselect_all", True)]}),
    ("view3d.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True},
     {"properties": [("extend", True)]}),
    ("view3d.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "ctrl": True},
     {"properties": [("toggle", True)]}),
)


def _axis_props(op, axis):
    props = [("release_confirm", True)]
    if axis is None:
        return props
    props.append(("constraint_axis", AXES[axis]))
    if op == "transform.rotate":
        props.append(("orient_axis", axis))
    return props


def build_keymap(op, mode='XYZ'):
    """Build the tool keymap tuple for one transform operator."""
    left_axis = 'X' if mode == 'XYZ' else None
    items = list(NAV_ITEMS) + list(SELECT_ITEMS)
    # Shift + left drag is always free (view plane), whatever the mode.
    items.append((op, {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "shift": True},
                  {"properties": _axis_props(op, None)}))
    items.append((op, {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'},
                  {"properties": _axis_props(op, left_axis)}))
    # Middle and right start on press so they beat Blender's view-orbit and
    # context-menu bindings (a drag is never generated once a press is handled).
    items.append((op, {"type": 'MIDDLEMOUSE', "value": 'PRESS'},
                  {"properties": _axis_props(op, 'Y')}))
    items.append((op, {"type": 'RIGHTMOUSE', "value": 'PRESS'},
                  {"properties": _axis_props(op, 'Z')}))
    return tuple(items)


TOOL_DEFS = (
    # (suffix, label, operator, icon, description)
    ("translate", "SRT Translate", "transform.translate", "ops.transform.translate",
     "Drag anywhere to move. Left/Middle/Right = X/Y/Z. Shift+Left = free"),
    ("rotate", "SRT Rotate", "transform.rotate", "ops.transform.rotate",
     "Drag anywhere to rotate. Left/Middle/Right = X/Y/Z. Shift+Left = view axis"),
    ("scale", "SRT Scale", "transform.resize", "ops.transform.resize",
     "Drag anywhere to scale. Left/Middle/Right = X/Y/Z. Shift+Left = uniform"),
)

CONTEXT_MODES = (
    ('OBJECT', "object"),
    ('EDIT_MESH', "mesh"),
)


def tool_id(suffix, mode_key):
    return f"gray_matter.{suffix}_{mode_key}"


def _make_tool_class(suffix, label, op, icon, desc, context_mode, mode_key, axis_mode):
    return type(
        f"GM_TOOL_{suffix}_{mode_key}",
        (WorkSpaceTool,),
        {
            "bl_space_type": 'VIEW_3D',
            "bl_context_mode": context_mode,
            "bl_idname": tool_id(suffix, mode_key),
            "bl_label": label,
            "bl_description": desc,
            "bl_icon": icon,
            "bl_widget": None,
            "bl_keymap": build_keymap(op, axis_mode),
        },
    )


_registered = []


def register():
    axis_mode = preferences.get("mouse_axis_mode", 'XYZ')
    for context_mode, mode_key in CONTEXT_MODES:
        first = True
        for suffix, label, op, icon, desc in TOOL_DEFS:
            cls = _make_tool_class(suffix, label, op, icon, desc, context_mode, mode_key, axis_mode)
            try:
                bpy.utils.register_tool(cls, after={"builtin.transform"},
                                        separator=first, group=False)
            except Exception as ex:  # pragma: no cover - depends on Blender build
                print(f"[Gray Matter] could not register tool {cls.bl_idname}: {ex}")
                continue
            first = False
            _registered.append(cls)


def unregister():
    while _registered:
        cls = _registered.pop()
        try:
            bpy.utils.unregister_tool(cls)
        except Exception as ex:  # pragma: no cover
            print(f"[Gray Matter] could not unregister tool {cls.bl_idname}: {ex}")
