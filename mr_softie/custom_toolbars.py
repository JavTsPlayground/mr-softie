# SPDX-License-Identifier: GPL-3.0-or-later
"""Custom toolbars: your own buttons, in the Custom module of the toolbar.

  New Toolbar          an empty toolbar
  Add Last Command     a button that repeats the last command you ran, with its settings
  Add Script           a button that runs the Script Editor's selected lines (or all of it)
  Edit                 rename, move up / down, delete buttons and toolbars
  Export / Import      share toolbars as a .json file

Toolbars are saved in your user settings (not in the scene), so they're there in
every file.
"""
import ast
import json
import os

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty

_cache = {"data": None}
_path_override = {"path": None}   # tests point this elsewhere


def store_path():
    if _path_override["path"]:
        return _path_override["path"]
    try:
        folder = bpy.utils.extension_path_user(__package__, create=True)
    except (ValueError, AttributeError, TypeError):
        folder = bpy.utils.user_resource('CONFIG', path="mr_softie", create=True)
    return os.path.join(folder, "toolbars.json")


def data():
    if _cache["data"] is None:
        try:
            with open(store_path(), encoding="utf-8") as f:
                _cache["data"] = json.load(f)
        except (OSError, ValueError):
            _cache["data"] = {"toolbars": []}
        _cache["data"].setdefault("toolbars", [])
    return _cache["data"]


def save():
    path = store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data(), f, indent=2)
    try:
        from .viewport import tag_columns
        tag_columns()
    except (AttributeError, RuntimeError):
        pass


def toolbars():
    return data()["toolbars"]


def new_toolbar(name=None):
    bars = toolbars()
    name = name or f"Toolbar {len(bars) + 1}"
    bars.append({"name": name, "buttons": []})
    save()
    return len(bars) - 1


def add_button(index, button):
    bars = toolbars()
    if not bars:
        index = new_toolbar("My Tools")
    index = min(max(index, 0), len(bars) - 1)
    bars[index]["buttons"].append(button)
    save()


def run_button(context, button):
    """Run one custom button. Returns an error message or None."""
    if button.get("kind") == "script":
        try:
            exec(compile(button.get("code", ""), f"<{button.get('label', 'script')}>", "exec"),
                 {"bpy": bpy, "C": context, "D": bpy.data, "__name__": "__main__"})
        except Exception as ex:   # the user's own script: report whatever went wrong
            return f"{type(ex).__name__}: {ex}"
        return None
    from .viewport import run_in_view3d
    try:
        kwargs = ast.literal_eval(button.get("args") or "{}")
        run_in_view3d(context, button["op"], kwargs, True)
    except (RuntimeError, AttributeError, ValueError, TypeError, SyntaxError) as ex:
        msg = str(ex).strip().splitlines()[-1] if str(ex).strip() else type(ex).__name__
        return f"{button.get('op')}: {msg}"
    return None


def selected_script(text):
    """The selected lines of a Text (or all of it when nothing is selected)."""
    lines = text.as_string().split("\n")
    a, b = text.current_line_index, text.select_end_line_index
    if a == b and text.current_character == text.select_end_character:
        return text.as_string()
    a, b = sorted((a, b))
    return "\n".join(lines[a:b + 1])


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------

def _current_bar(context):
    return context.window_manager.mr_softie_custom_bar


class MS_OT_custom_run(bpy.types.Operator):
    """Run this custom button"""
    bl_idname = "mr_softie.custom_run"
    bl_label = "Custom Button"
    bl_options = {'REGISTER', 'UNDO'}

    bar: IntProperty()
    button: IntProperty()

    @classmethod
    def description(cls, context, props):
        try:
            b = toolbars()[props.bar]["buttons"][props.button]
        except (IndexError, KeyError, AttributeError):
            return cls.__doc__
        if b.get("kind") == "script":
            first = next((ln for ln in b.get("code", "").splitlines() if ln.strip() and not ln.startswith("#")), "")
            return f"Script: {first[:80]}"
        return f"{b.get('op')}  {b.get('args') or ''}".strip()

    def execute(self, context):
        try:
            button = toolbars()[self.bar]["buttons"][self.button]
        except (IndexError, KeyError):
            return {'CANCELLED'}
        error = run_button(context, button)
        if error:
            self.report({'WARNING'}, error)
            return {'CANCELLED'}
        from .scripting import note_command
        if button.get("kind") != "script":
            note_command(context, button["op"], button.get("args", ""))
        return {'FINISHED'}


class MS_OT_custom_new(bpy.types.Operator):
    """New custom toolbar"""
    bl_idname = "mr_softie.custom_new"
    bl_label = "New Toolbar"

    name: StringProperty(name="Name", default="My Tools")

    def invoke(self, context, event):
        self.name = f"Toolbar {len(toolbars()) + 1}"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        context.window_manager.mr_softie_custom_bar = new_toolbar(self.name)
        return {'FINISHED'}


class MS_OT_custom_add_last(bpy.types.Operator):
    """Add a button that repeats the last command you ran, with its settings"""
    bl_idname = "mr_softie.custom_add_last"
    bl_label = "Add Last Command"

    label: StringProperty(name="Label")

    def invoke(self, context, event):
        from .scripting import last_command
        last = last_command(context)
        if last is None or not last[1] or last[1].partition(".")[2].startswith("custom_"):
            self.report({'WARNING'}, "Run a command first, then add it")
            return {'CANCELLED'}
        self._last = last
        self.label = last[0]
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .scripting import last_command
        last = getattr(self, "_last", None) or last_command(context)
        if last is None:
            return {'CANCELLED'}
        add_button(_current_bar(context), {"label": self.label or last[0], "kind": "op",
                                           "op": last[1], "args": last[2]})
        return {'FINISHED'}


class MS_OT_custom_add_script(bpy.types.Operator):
    """Add a button that runs the Script Editor's selected lines (or the whole script)"""
    bl_idname = "mr_softie.custom_add_script"
    bl_label = "Add Script"

    label: StringProperty(name="Label", default="Script")

    def invoke(self, context, event):
        from .scripting import SCRIPT_NAME
        text = bpy.data.texts.get(SCRIPT_NAME)
        if text is None or not text.as_string().strip():
            self.report({'WARNING'}, "Write the script in the Script Editor (Alt+4) first")
            return {'CANCELLED'}
        self._code = selected_script(text)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        code = getattr(self, "_code", None)
        if code is None:
            from .scripting import SCRIPT_NAME
            text = bpy.data.texts.get(SCRIPT_NAME)
            if text is None:
                return {'CANCELLED'}
            code = selected_script(text)
        add_button(_current_bar(context), {"label": self.label, "kind": "script", "code": code})
        return {'FINISHED'}


class MS_OT_custom_edit(bpy.types.Operator):
    """Edit custom toolbars: rename, move, delete"""
    bl_idname = "mr_softie.custom_edit"
    bl_label = "Edit Custom Toolbar"
    bl_options = {'INTERNAL'}

    bar: IntProperty()
    button: IntProperty(default=-1)        # -1 = the toolbar itself
    action: StringProperty()                # RENAME, UP, DOWN, DELETE
    name: StringProperty(name="Name")

    def invoke(self, context, event):
        if self.action == 'RENAME':
            item = self._item()
            if item is None:
                return {'CANCELLED'}
            self.name = item.get("label") or item.get("name", "")
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def _item(self):
        try:
            bar = toolbars()[self.bar]
            return bar if self.button < 0 else bar["buttons"][self.button]
        except IndexError:
            return None

    def execute(self, context):
        bars = toolbars()
        if not 0 <= self.bar < len(bars):
            return {'CANCELLED'}
        items = bars if self.button < 0 else bars[self.bar]["buttons"]
        i = self.bar if self.button < 0 else self.button
        if not 0 <= i < len(items):
            return {'CANCELLED'}
        if self.action == 'RENAME':
            items[i]["name" if self.button < 0 else "label"] = self.name
        elif self.action == 'UP' and i > 0:
            items[i - 1], items[i] = items[i], items[i - 1]
        elif self.action == 'DOWN' and i < len(items) - 1:
            items[i + 1], items[i] = items[i], items[i + 1]
        elif self.action == 'DELETE':
            items.pop(i)
            wm = context.window_manager
            if self.button < 0 and wm.mr_softie_custom_bar >= len(bars):
                wm.mr_softie_custom_bar = max(0, len(bars) - 1)
        save()
        return {'FINISHED'}


class MS_OT_custom_export(bpy.types.Operator):
    """Save your custom toolbars to a .json file to share"""
    bl_idname = "mr_softie.custom_export"
    bl_label = "Export Toolbars"

    filepath: StringProperty(subtype='FILE_PATH', default="mr_softie_toolbars.json")
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        with open(bpy.path.abspath(self.filepath), "w", encoding="utf-8") as f:
            json.dump(data(), f, indent=2)
        self.report({'INFO'}, f"Saved {len(toolbars())} toolbar(s)")
        return {'FINISHED'}


class MS_OT_custom_import(bpy.types.Operator):
    """Add toolbars from a .json file (they're added next to yours)"""
    bl_idname = "mr_softie.custom_import"
    bl_label = "Import Toolbars"

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            with open(bpy.path.abspath(self.filepath), encoding="utf-8") as f:
                incoming = json.load(f).get("toolbars", [])
        except (OSError, ValueError, AttributeError) as ex:
            self.report({'WARNING'}, f"Couldn't read toolbars: {ex}")
            return {'CANCELLED'}
        bars = [b for b in incoming if isinstance(b, dict) and isinstance(b.get("buttons"), list)]
        toolbars().extend(bars)
        save()
        scripts = sum(1 for b in bars for x in b["buttons"] if x.get("kind") == "script")
        msg = f"Added {len(bars)} toolbar(s)"
        if scripts:
            msg += f" ({scripts} script button(s): they run Python, only use files you trust)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Drawing (Custom module of the toolbar)
# --------------------------------------------------------------------------

def draw_custom(layout, context):
    wm = context.window_manager
    bars = toolbars()
    editing = wm.mr_softie_custom_edit
    if not bars:
        layout.label(text="No custom toolbars yet")
        layout.operator("mr_softie.custom_new", text="New Toolbar")
        return
    for bi, bar in enumerate(bars):
        box = layout.box()
        head = box.row(align=True)
        head.operator("mr_softie.custom_select_bar", text=bar.get("name", "Toolbar"),
                      depress=wm.mr_softie_custom_bar == bi).bar = bi
        if editing:
            for action, icon in (('RENAME', 'GREASEPENCIL'), ('UP', 'TRIA_UP'), ('DOWN', 'TRIA_DOWN'),
                                 ('DELETE', 'X')):
                op = head.operator("mr_softie.custom_edit", text="", icon=icon)
                op.bar, op.button, op.action = bi, -1, action
        col = box.column(align=True)
        for i, button in enumerate(bar.get("buttons", [])):
            row = col.row(align=True)
            op = row.operator("mr_softie.custom_run", text=button.get("label", "?"),
                              icon='SCRIPT' if button.get("kind") == "script" else 'NONE')
            op.bar, op.button = bi, i
            if editing:
                for action, icon in (('RENAME', 'GREASEPENCIL'), ('UP', 'TRIA_UP'), ('DOWN', 'TRIA_DOWN'),
                                     ('DELETE', 'X')):
                    e = row.operator("mr_softie.custom_edit", text="", icon=icon)
                    e.bar, e.button, e.action = bi, i, action
        if not bar.get("buttons"):
            col.label(text="Empty")


def draw_custom_tools(layout, context):
    wm = context.window_manager
    col = layout.column(align=True)
    col.operator("mr_softie.custom_add_last", text="Add Command")
    col.operator("mr_softie.custom_add_script", text="Add Script")
    col.operator("mr_softie.custom_new", text="New Toolbar")
    layout.prop(wm, "mr_softie_custom_edit", text="Edit Buttons", toggle=True)
    row = layout.row(align=True)
    row.operator("mr_softie.custom_export", text="Export")
    row.operator("mr_softie.custom_import", text="Import")


class MS_OT_custom_select_bar(bpy.types.Operator):
    """Make this the toolbar new buttons go into"""
    bl_idname = "mr_softie.custom_select_bar"
    bl_label = "Current Toolbar"
    bl_options = {'INTERNAL'}

    bar: IntProperty()

    def execute(self, context):
        context.window_manager.mr_softie_custom_bar = self.bar
        return {'FINISHED'}


classes = (MS_OT_custom_run, MS_OT_custom_new, MS_OT_custom_add_last, MS_OT_custom_add_script,
           MS_OT_custom_edit, MS_OT_custom_export, MS_OT_custom_import, MS_OT_custom_select_bar)


def register():
    bpy.types.WindowManager.mr_softie_custom_bar = IntProperty(min=0, default=0)
    bpy.types.WindowManager.mr_softie_custom_edit = BoolProperty(
        name="Edit Buttons", description="Rename, reorder and delete custom buttons and toolbars")
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.mr_softie_custom_edit
    del bpy.types.WindowManager.mr_softie_custom_bar
    _cache["data"] = None
