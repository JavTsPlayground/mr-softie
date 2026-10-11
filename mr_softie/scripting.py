# SPDX-License-Identifier: GPL-3.0-or-later
"""Script Editor: the command log on top, a script editor underneath, in one window.

Every command you run is logged (as Python) in the top half; copy lines from it
into the editor below and run them with Run Script (or Alt+P).
"""
import bpy

SCRIPT_NAME = "MR.Softie Script"
HEADER = (
    "# MR.Softie Script Editor\n"
    "# The log above shows every command as Python. Copy lines here and press\n"
    "# Run Script (or Alt+P with the mouse over this editor).\n"
    "import bpy\n\n"
)


def _script_text():
    text = bpy.data.texts.get(SCRIPT_NAME)
    if text is None:
        text = bpy.data.texts.new(SCRIPT_NAME)
        text.write(HEADER)
        text.use_fake_user = False
    return text


def _find_window(window_ptr):
    wm = bpy.context.window_manager
    return next((w for w in wm.windows if w.as_pointer() == window_ptr), None)


def _split_into_log(window_ptr):
    """Step 2, a tick after the window opens (a brand-new window has no size before it is drawn)."""
    window = _find_window(window_ptr)
    if window is None or not window.screen.areas:
        return None
    area = window.screen.areas[0]
    if area.width < 50 or area.height < 50:
        return 0.1   # not laid out yet, try again
    try:
        with bpy.context.temp_override(window=window, screen=window.screen, area=area):
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.4)
    except RuntimeError:
        return None
    bpy.app.timers.register(lambda: _assign_editors(window_ptr), first_interval=0.1)
    return None


def _assign_editors(window_ptr):
    """Step 3, once the split is laid out: log on top, script editor underneath."""
    window = _find_window(window_ptr)
    if window is None:
        return None
    areas = list(window.screen.areas)
    if len(areas) < 2:
        return None
    if any(a.height < 20 for a in areas):
        return 0.1
    top = max(areas, key=lambda a: a.y)
    bottom = min(areas, key=lambda a: a.y)
    top.ui_type = 'INFO'
    bottom.ui_type = 'TEXT_EDITOR'
    space = bottom.spaces.active
    space.text = _script_text()
    space.top = 0
    space.show_line_numbers = True
    space.show_syntax_highlight = True
    top.tag_redraw()
    bottom.tag_redraw()
    return None


class MS_OT_open_script_editor(bpy.types.Operator):
    """Script Editor: the command log above a script editor, in its own window"""
    bl_idname = "mr_softie.open_script_editor"
    bl_label = "Script Editor"

    def execute(self, context):
        from .operators import open_floating_window
        window, area = open_floating_window(context, 'TEXT_EDITOR')
        if area is None:
            self.report({'WARNING'}, "Could not open a window")
            return {'CANCELLED'}
        area.spaces.active.text = _script_text()
        ptr = window.as_pointer()
        bpy.app.timers.register(lambda: _split_into_log(ptr), first_interval=0.1)
        return {'FINISHED'}


_last = {"label": "", "count": -1}


def note_command(context, idname):
    """Remember a command run through MR.Softie buttons (nested runs never reach the operator log)."""
    module, name = idname.split(".", 1)
    try:
        label = getattr(getattr(bpy.ops, module), name).get_rna_type().name
    except (AttributeError, KeyError):
        label = name.replace("_", " ").title()
    _last["label"] = label or idname
    _last["count"] = len(context.window_manager.operators)
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'STATUSBAR':
                area.tag_redraw()


def last_command_label(context):
    ops = context.window_manager.operators
    if _last["label"] and len(ops) == _last["count"]:
        return _last["label"]
    if not len(ops):
        return _last["label"]
    op = ops[-1]
    return op.bl_label or op.bl_idname


classes = (MS_OT_open_script_editor,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
