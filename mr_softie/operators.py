# SPDX-License-Identifier: GPL-3.0-or-later
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import theme as gm_theme
from .tools import tool_id
from .viewport import find_view3d, parse_args, run_in_view3d, tag_columns

# Supra mode: remember the tool that was active before a hotkey switched tools,
# so releasing a held key can go back to it.
SUPRA_HOLD_SECONDS = 0.3
_supra = {"key": None, "time": 0.0, "previous": None}


def _mode_key(context):
    if context.mode == 'EDIT_MESH':
        return "mesh"
    if context.mode == 'OBJECT':
        return "object"
    return None


def _current_tool(context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    except (AttributeError, TypeError):
        return None
    return tool.idname if tool else None


def _set_tool(name):
    try:
        bpy.ops.wm.tool_set_by_id(name=name, space_type='VIEW_3D')
    except (RuntimeError, TypeError):
        return False
    tag_columns()
    return True


def _supra_press(context, key):
    """Called on hotkey press: remember the previous tool unless the key is auto-repeating."""
    if _supra["key"] == key:
        return
    _supra.update(key=key, time=time.monotonic(), previous=_current_tool(context))


class MS_OT_swallow(bpy.types.Operator):
    """Consume a key press so Blender's default binding doesn't fire"""
    bl_idname = "mr_softie.swallow"
    bl_label = "Hold for Navigation"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}


class MS_OT_run(bpy.types.Operator):
    """Run a command in the main 3D viewport"""
    bl_idname = "mr_softie.run"
    bl_label = "Run in Viewport"
    bl_options = {'INTERNAL'}

    op: StringProperty()
    args: StringProperty()
    invoke: BoolProperty(default=True)

    @classmethod
    def description(cls, context, props):
        if not props or not props.op:
            return cls.__doc__
        name = props.op.split(".", 1)[-1].replace("_", " ").title()
        return f"{name} (runs in the main viewport)"

    def execute(self, context):
        try:
            kwargs = parse_args(self.args)
            run_in_view3d(context, self.op, kwargs, self.invoke)
            from .scripting import note_command
            note_command(context, self.op)
        except (RuntimeError, AttributeError, ValueError, TypeError) as ex:
            msg = str(ex).strip().splitlines()[-1] if str(ex).strip() else type(ex).__name__
            self.report({'WARNING'}, f"{self.op}: {msg}")
            return {'CANCELLED'}
        return {'FINISHED'}


class MS_OT_srt_tool(bpy.types.Operator):
    """Activate a classic SRT tool (drag anywhere to transform). Hold the key for a temporary tool"""
    bl_idname = "mr_softie.srt_tool"
    bl_label = "SRT Tool"

    kind: EnumProperty(items=(
        ('translate', "Translate", ""),
        ('rotate', "Rotate", ""),
        ('scale', "Scale", ""),
    ))
    supra: BoolProperty(default=False, options={'SKIP_SAVE'})

    def execute(self, context):
        if self.supra:
            _supra_press(context, self.kind)
        key = _mode_key(context)
        if key is None:
            fallback = {'translate': "builtin.move", 'rotate': "builtin.rotate",
                        'scale': "builtin.scale"}[self.kind]
            return {'FINISHED'} if _set_tool(fallback) else {'CANCELLED'}
        _set_tool(tool_id(self.kind, key))
        return {'FINISHED'}


class MS_OT_supra_release(bpy.types.Operator):
    """Key released: if it was held, return to the previous tool"""
    bl_idname = "mr_softie.supra_release"
    bl_label = "Supra Mode Release"
    bl_options = {'INTERNAL'}

    key: StringProperty()

    def execute(self, context):
        if _supra["key"] != self.key:
            return {'CANCELLED'}
        held = time.monotonic() - _supra["time"]
        previous = _supra["previous"]
        _supra.update(key=None, previous=None)
        if held >= SUPRA_HOLD_SECONDS and previous:
            _set_tool(previous)
        return {'FINISHED'}


class MS_OT_object_select(bpy.types.Operator):
    """Object selection: leave component editing and switch to the select tool"""
    bl_idname = "mr_softie.object_select"
    bl_label = "Object Selection"
    bl_options = {'UNDO'}

    supra: BoolProperty(default=False, options={'SKIP_SAVE'})

    def execute(self, context):
        if self.supra:
            _supra_press(context, "select")
        if context.mode != 'OBJECT' and context.active_object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')
        _set_tool("builtin.select_box")
        return {'FINISHED'}


class MS_OT_component_mode(bpy.types.Operator):
    """Select points, edges or polygons on the active mesh"""
    bl_idname = "mr_softie.component_mode"
    bl_label = "Component Selection"
    bl_options = {'UNDO'}

    component: EnumProperty(items=(
        ('VERT', "Point", "Point selection"),
        ('EDGE', "Edge", "Edge selection"),
        ('FACE', "Polygon", "Polygon selection"),
    ))

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type=self.component)
        _set_tool("builtin.select_box")
        return {'FINISHED'}


def open_floating_window(context, ui_type=None, source=None):
    """Open a new window by duplicating `source` (default: the main 3D view).

    Returns (window, area) of the new window, or (None, None).
    """
    wm = context.window_manager
    before = {w.as_pointer() for w in wm.windows}
    window, area, _region = find_view3d(context)
    if source is not None:
        area = source
        window = next((w for w in wm.windows if any(a == source for a in w.screen.areas)), window)
    area = area or context.area
    window = window or context.window
    if area is None or window is None:
        return None, None
    try:
        with context.temp_override(window=window, screen=window.screen, area=area):
            bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
    except RuntimeError:
        return None, None
    new = [w for w in wm.windows if w.as_pointer() not in before]
    if not new:
        return None, None
    target = new[-1].screen.areas[0]
    if ui_type:
        try:
            target.ui_type = ui_type
        except TypeError:
            pass
    return new[-1], target


class MS_OT_open_editor(bpy.types.Operator):
    """Open an editor in its own floating window"""
    bl_idname = "mr_softie.open_editor"
    bl_label = "Open Editor Window"

    ui_type: StringProperty(default='OUTLINER')

    def execute(self, context):
        window, area = open_floating_window(context, self.ui_type)
        if area is None:
            self.report({'WARNING'}, "Could not open a window")
            return {'CANCELLED'}
        if area.ui_type != self.ui_type:
            self.report({'WARNING'}, f"Editor type {self.ui_type} not available")
        return {'FINISHED'}


class MS_OT_open_explorer(bpy.types.Operator):
    """Explorer: the scene hierarchy in a floating window"""
    bl_idname = "mr_softie.open_explorer"
    bl_label = "Explorer"

    def execute(self, context):
        window, area = open_floating_window(context, 'OUTLINER')
        if area is None:
            self.report({'WARNING'}, "Could not open a window")
            return {'CANCELLED'}
        space = area.spaces.active
        space.display_mode = 'VIEW_LAYER'
        space.use_filter_children = True
        space.use_sort_alpha = True
        space.show_restrict_column_select = True
        space.show_restrict_column_render = True
        space.use_filter_object_content = True
        return {'FINISHED'}


class MS_OT_quad_view(bpy.types.Operator):
    """Toggle the four-viewport layout (Top, Front, Right, Perspective)"""
    bl_idname = "mr_softie.quad_view"
    bl_label = "Four Views"

    def execute(self, context):
        window, area, _region = find_view3d(context)
        if area is None:
            return {'CANCELLED'}
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        with context.temp_override(window=window, area=area, region=region):
            bpy.ops.screen.region_quadview()
        return {'FINISHED'}


class MS_OT_toggle_cog(bpy.types.Operator):
    """COG: transform around the center of the whole selection instead of each object's own center"""
    bl_idname = "mr_softie.toggle_cog"
    bl_label = "COG"
    bl_options = {'UNDO'}

    def execute(self, context):
        ts = context.tool_settings
        ts.transform_pivot_point = ('INDIVIDUAL_ORIGINS' if ts.transform_pivot_point == 'MEDIAN_POINT'
                                    else 'MEDIAN_POINT')
        tag_columns()
        return {'FINISHED'}


class MS_OT_freeze(bpy.types.Operator):
    """Freeze: bake the modifier stack into the mesh"""
    bl_idname = "mr_softie.freeze"
    bl_label = "Freeze"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        frozen = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            with context.temp_override(object=obj, active_object=obj):
                for mod in list(obj.modifiers):
                    try:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                        frozen += 1
                    except RuntimeError as ex:
                        self.report({'WARNING'}, f"{obj.name}: {mod.name} skipped ({ex})")
        self.report({'INFO'}, f"Froze {frozen} modifier(s)")
        return {'FINISHED'}


class MS_OT_reset_srt(bpy.types.Operator):
    """Reset scale, rotation or translation of the selection"""
    bl_idname = "mr_softie.reset_srt"
    bl_label = "Reset"
    bl_options = {'REGISTER', 'UNDO'}

    kind: EnumProperty(items=(
        ('ALL', "All", ""),
        ('S', "Scale", ""),
        ('R', "Rotation", ""),
        ('T', "Translation", ""),
    ))

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        if self.kind in {'ALL', 'S'}:
            bpy.ops.object.scale_clear()
        if self.kind in {'ALL', 'R'}:
            bpy.ops.object.rotation_clear()
        if self.kind in {'ALL', 'T'}:
            bpy.ops.object.location_clear()
        return {'FINISHED'}


class MS_OT_add_material(bpy.types.Operator):
    """Give the selected objects a new material"""
    bl_idname = "mr_softie.add_material"
    bl_label = "Add Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = [o for o in context.selected_objects if hasattr(o.data, "materials")]
        if not objs:
            self.report({'WARNING'}, "Select an object first")
            return {'CANCELLED'}
        mat = bpy.data.materials.new("Material")
        mat.use_nodes = True
        for obj in objs:
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
        return {'FINISHED'}


class MS_OT_add_deform(bpy.types.Operator):
    """Add a Bend, Twist or Taper deformer to the selected objects"""
    bl_idname = "mr_softie.add_deform"
    bl_label = "Add Deform"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(items=(('BEND', "Bend", ""), ('TWIST', "Twist", ""),
                                ('TAPER', "Taper", ""), ('STRETCH', "Stretch", "")))

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type in {'MESH', 'CURVE', 'LATTICE'}]
        if not objs:
            self.report({'WARNING'}, "Select a mesh first")
            return {'CANCELLED'}
        for obj in objs:
            mod = obj.modifiers.new(self.method.title(), 'SIMPLE_DEFORM')
            mod.deform_method = self.method
        return {'FINISHED'}


class MS_OT_toggle_render_preview(bpy.types.Operator):
    """Toggle a live render preview in the perspective view"""
    bl_idname = "mr_softie.toggle_render_preview"
    bl_label = "Render Preview"

    def execute(self, context):
        _window, area, _region = find_view3d(context)
        if area is None:
            return {'CANCELLED'}
        shading = area.spaces.active.shading
        shading.type = 'SOLID' if shading.type == 'RENDERED' else 'RENDERED'
        return {'FINISHED'}


class MS_OT_apply_theme(bpy.types.Operator):
    """Apply the light-gray classic theme (undo with Reset Theme)"""
    bl_idname = "mr_softie.apply_theme"
    bl_label = "Apply Gray Theme"

    def execute(self, context):
        n = gm_theme.apply()
        self.report({'INFO'}, f"Gray theme applied ({n} colors)")
        return {'FINISHED'}


class MS_OT_reset_theme(bpy.types.Operator):
    """Restore Blender's default theme"""
    bl_idname = "mr_softie.reset_theme"
    bl_label = "Reset Theme"

    def execute(self, context):
        bpy.ops.preferences.reset_default_theme()
        return {'FINISHED'}


class MS_OT_install_app_template(bpy.types.Operator):
    """Install MR.Softie as an application template: it then appears in File > New and on the splash screen"""
    bl_idname = "mr_softie.install_app_template"
    bl_label = "Install App Template"

    def execute(self, context):
        import os
        import shutil
        source = os.path.join(os.path.dirname(__file__), "app_template")
        target = bpy.utils.user_resource('SCRIPTS', path=os.path.join(
            "startup", "bl_app_templates_user", "MR_Softie"), create=True)
        for name in ("__init__.py", "startup.blend"):
            shutil.copyfile(os.path.join(source, name), os.path.join(target, name))
        self.report({'INFO'}, "Installed: File > New > MR Softie")
        return {'FINISHED'}


classes = (
    MS_OT_swallow,
    MS_OT_run,
    MS_OT_srt_tool,
    MS_OT_supra_release,
    MS_OT_object_select,
    MS_OT_component_mode,
    MS_OT_open_editor,
    MS_OT_open_explorer,
    MS_OT_quad_view,
    MS_OT_toggle_cog,
    MS_OT_freeze,
    MS_OT_reset_srt,
    MS_OT_add_material,
    MS_OT_add_deform,
    MS_OT_toggle_render_preview,
    MS_OT_apply_theme,
    MS_OT_reset_theme,
    MS_OT_install_app_template,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
