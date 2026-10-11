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
    return f"mr_softie.{suffix}_{mode_key}"


def _make_tool_class(suffix, label, op, icon, desc, context_mode, mode_key, axis_mode):
    return type(
        f"MS_TOOL_{suffix}_{mode_key}",
        (WorkSpaceTool,),
        {
            "bl_space_type": 'VIEW_3D',
            "bl_context_mode": context_mode,
            "bl_idname": tool_id(suffix, mode_key),
            "bl_label": label,
            "bl_description": desc,
            "bl_icon": icon,
            # The SRT manipulator is driven by _sync_manipulator() below.
            "bl_widget": None,
            "bl_operator": op,
            "bl_keymap": build_keymap(op, axis_mode),
        },
    )


def raycast_keymap():
    """Paint-select visible components: drag to select, Shift adds, Ctrl removes."""
    items = list(NAV_ITEMS)
    for mods, mode in (({}, 'SET'), ({"shift": True}, 'ADD'), ({"ctrl": True}, 'SUB')):
        items.append(("view3d.select_circle", {"type": 'LEFTMOUSE', "value": 'PRESS', **mods},
                      {"properties": [("wait_for_input", False), ("mode", mode), ("radius", 18)]}))
    return tuple(items)


class MS_TOOL_raycast_mesh(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'
    bl_idname = "mr_softie.raycast_mesh"
    bl_label = "Raycast Select"
    bl_description = "Paint over visible points, edges or polygons to select them. Shift adds, Ctrl removes"
    bl_icon = "ops.generic.select_circle"
    bl_widget = None
    bl_keymap = raycast_keymap()


_registered = []

# --------------------------------------------------------------------------
# SRT manipulator: Blender draws its object transform gizmo for custom tools
# from the viewport's "object gizmo" switches. Keep those switches matched to
# the active SRT tool, and switch them back off when another tool is picked.
# --------------------------------------------------------------------------

_GIZMO_FLAGS = {
    "translate": "show_gizmo_object_translate",
    "rotate": "show_gizmo_object_rotate",
    "scale": "show_gizmo_object_scale",
}
_managed = {}   # space pointer -> kind we turned on


def _active_kind(window):
    try:
        mode = window.view_layer.objects.active.mode if window.view_layer.objects.active else 'OBJECT'
    except AttributeError:
        mode = 'OBJECT'
    context_mode = 'EDIT_MESH' if mode == 'EDIT' else 'OBJECT'
    tool = window.workspace.tools.from_space_view3d_mode(context_mode, create=False)
    if tool is None or not tool.idname.startswith("mr_softie."):
        return None
    kind = tool.idname.split(".", 1)[1].rsplit("_", 1)[0]
    return kind if kind in _GIZMO_FLAGS else None


def _sync_manipulator():
    try:
        enabled = preferences.get("show_manipulator", True)
        for window in bpy.context.window_manager.windows:
            kind = _active_kind(window) if enabled else None
            for area in window.screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                space = area.spaces.active
                key = space.as_pointer()
                if kind is None and key not in _managed:
                    continue          # leave the user's own gizmo settings alone
                if _managed.get(key) == kind:
                    continue
                for k, flag in _GIZMO_FLAGS.items():
                    setattr(space, flag, k == kind)
                if kind is None:
                    _managed.pop(key, None)
                else:
                    _managed[key] = kind
                area.tag_redraw()
    except (ReferenceError, RuntimeError, AttributeError):
        pass
    return 0.2


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
                print(f"[MR.Softie] could not register tool {cls.bl_idname}: {ex}")
                continue
            first = False
            _registered.append(cls)
    if not bpy.app.timers.is_registered(_sync_manipulator):
        bpy.app.timers.register(_sync_manipulator, first_interval=0.5, persistent=True)
    try:
        bpy.utils.register_tool(MS_TOOL_raycast_mesh, after={"builtin.select_circle"}, group=False)
        _registered.append(MS_TOOL_raycast_mesh)
    except Exception as ex:  # pragma: no cover
        print(f"[MR.Softie] could not register raycast tool: {ex}")


def unregister():
    if bpy.app.timers.is_registered(_sync_manipulator):
        bpy.app.timers.unregister(_sync_manipulator)
    # Hand gizmo switches back the way we found them.
    for window in getattr(bpy.context.window_manager, "windows", []):
        for area in window.screen.areas:
            if area.type == 'VIEW_3D' and area.spaces.active.as_pointer() in _managed:
                for flag in _GIZMO_FLAGS.values():
                    setattr(area.spaces.active, flag, False)
    _managed.clear()
    while _registered:
        cls = _registered.pop()
        try:
            bpy.utils.unregister_tool(cls)
        except Exception as ex:  # pragma: no cover
            print(f"[MR.Softie] could not unregister tool {cls.bl_idname}: {ex}")
