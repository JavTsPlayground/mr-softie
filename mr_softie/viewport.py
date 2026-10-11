# SPDX-License-Identifier: GPL-3.0-or-later
"""Helpers for running viewport operators from the side columns.

The toolbar and MCP columns live in their own screen areas, so buttons there
have no 3D viewport in their context. These helpers find the main viewport
and run operators inside it.
"""
import ast

import bpy

COLUMN_KEY = "mr_softie_column"   # id-property on the Text datablock of a column
COLUMN_TEXT_NAMES = {"toolbar": "MR.Softie Toolbar", "mcp": "MR.Softie MCP"}


def column_kind(context):
    """Return 'toolbar' / 'mcp' when drawing inside a MR.Softie column, else None."""
    space = getattr(context, "space_data", None)
    if space is None or space.type != 'TEXT_EDITOR':
        return None
    text = space.text
    if text is None:
        return None
    return text.get(COLUMN_KEY)


def column_text(kind):
    """Get or create the (empty) Text datablock that marks a column."""
    for text in bpy.data.texts:
        if text.get(COLUMN_KEY) == kind:
            return text
    text = bpy.data.texts.new(COLUMN_TEXT_NAMES[kind])
    text[COLUMN_KEY] = kind
    text.use_fake_user = False
    return text


def find_view3d(context):
    """Return (window, area, region) for the main 3D viewport, or (None, None, None)."""
    windows = [context.window] if context.window else []
    windows += [w for w in context.window_manager.windows if w != context.window]
    for window in windows:
        areas = [a for a in window.screen.areas if a.type == 'VIEW_3D']
        if not areas:
            continue
        area = max(areas, key=lambda a: a.width * a.height)
        space = area.spaces.active
        regions = [r for r in area.regions if r.type == 'WINDOW']
        # In quad view, prefer the perspective quadrant (the space's own region_3d).
        region = next((r for r in regions if r.data == space.region_3d), None)
        region = region or (regions[-1] if regions else None)
        return window, area, region
    return None, None, None


def run_in_view3d(context, idname, kwargs=None, invoke=True):
    """Run operator `idname` ('module.name') inside the main 3D viewport."""
    kwargs = kwargs or {}
    module, name = idname.split(".", 1)
    op = getattr(getattr(bpy.ops, module), name)
    window, area, region = find_view3d(context)
    mode = 'INVOKE_DEFAULT' if invoke else 'EXEC_DEFAULT'
    if area is None:
        return op(mode, **kwargs)
    with context.temp_override(window=window, screen=window.screen, area=area,
                               region=region, space_data=area.spaces.active):
        return op(mode, **kwargs)


def parse_args(text):
    if not text:
        return {}
    value = ast.literal_eval(text)
    if not isinstance(value, dict):
        raise ValueError("args must be a dict literal")
    return value


def button(layout, text, idname, icon='NONE', invoke=True, icon_value=0, **kwargs):
    """Draw a button that runs `idname` in the main viewport."""
    if icon_value:
        props = layout.operator("mr_softie.run", text=text, icon_value=icon_value)
    else:
        props = layout.operator("mr_softie.run", text=text, icon=icon)
    props.op = idname
    props.args = repr(kwargs) if kwargs else ""
    props.invoke = invoke
    return props


def tag_columns(*_args):
    """Redraw the toolbar/MCP columns (Text Editor areas don't listen to scene changes)."""
    wm = bpy.context.window_manager
    if wm is None:
        return
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type != 'TEXT_EDITOR':
                continue
            text = area.spaces.active.text
            if text is not None and text.get(COLUMN_KEY):
                area.tag_redraw()


@bpy.app.handlers.persistent
def _on_depsgraph_update(_scene, _depsgraph):
    tag_columns()


def register():
    if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)


def unregister():
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
