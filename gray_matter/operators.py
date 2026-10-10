# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.props import EnumProperty, StringProperty

from . import theme as gm_theme
from .tools import tool_id


def _mode_key(context):
    if context.mode == 'EDIT_MESH':
        return "mesh"
    if context.mode == 'OBJECT':
        return "object"
    return None


def _view3d_area(context):
    if context.area and context.area.type == 'VIEW_3D':
        return context.area
    screen = context.screen
    if screen:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                return area
    return None


class GM_OT_swallow(bpy.types.Operator):
    """Consume a key press so Blender's default binding doesn't fire"""
    bl_idname = "gray_matter.swallow"
    bl_label = "Hold for Navigation"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}


class GM_OT_srt_tool(bpy.types.Operator):
    """Activate a classic SRT tool (drag anywhere to transform)"""
    bl_idname = "gray_matter.srt_tool"
    bl_label = "SRT Tool"

    kind: EnumProperty(items=(
        ('translate', "Translate", ""),
        ('rotate', "Rotate", ""),
        ('scale', "Scale", ""),
    ))

    def execute(self, context):
        key = _mode_key(context)
        if key is None:
            fallback = {'translate': "builtin.move", 'rotate': "builtin.rotate",
                        'scale': "builtin.scale"}[self.kind]
            try:
                bpy.ops.wm.tool_set_by_id(name=fallback)
            except RuntimeError:
                return {'CANCELLED'}
            return {'FINISHED'}
        bpy.ops.wm.tool_set_by_id(name=tool_id(self.kind, key))
        return {'FINISHED'}


class GM_OT_object_select(bpy.types.Operator):
    """Object selection: leave component editing and switch to the select tool"""
    bl_idname = "gray_matter.object_select"
    bl_label = "Object Selection"
    bl_options = {'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT' and context.active_object is not None:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
        except RuntimeError:
            pass
        return {'FINISHED'}


class GM_OT_component_mode(bpy.types.Operator):
    """Select points, edges or polygons on the active mesh"""
    bl_idname = "gray_matter.component_mode"
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
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
        except RuntimeError:
            pass
        return {'FINISHED'}


class GM_OT_open_editor(bpy.types.Operator):
    """Open an editor in its own floating window"""
    bl_idname = "gray_matter.open_editor"
    bl_label = "Open Editor Window"

    ui_type: StringProperty(default='OUTLINER')

    def execute(self, context):
        wm = context.window_manager
        before = {w.as_pointer() for w in wm.windows}
        area = context.area
        if area is None:
            self.report({'WARNING'}, "No area to open from")
            return {'CANCELLED'}
        try:
            with context.temp_override(area=area):
                bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        except RuntimeError as ex:
            self.report({'WARNING'}, f"Could not open window: {ex}")
            return {'CANCELLED'}
        new = [w for w in wm.windows if w.as_pointer() not in before]
        if not new:
            return {'CANCELLED'}
        target = new[-1].screen.areas[0]
        try:
            target.ui_type = self.ui_type
        except TypeError:
            self.report({'WARNING'}, f"Editor type {self.ui_type} not available")
        return {'FINISHED'}


class GM_OT_quad_view(bpy.types.Operator):
    """Toggle the four-viewport layout (Top, Front, Right, Perspective)"""
    bl_idname = "gray_matter.quad_view"
    bl_label = "Four Views"

    def execute(self, context):
        area = _view3d_area(context)
        if area is None:
            return {'CANCELLED'}
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        with context.temp_override(area=area, region=region):
            bpy.ops.screen.region_quadviews()
        return {'FINISHED'}


class GM_OT_classic_layout(bpy.types.Operator):
    """Set up the 3D view the classic way: four views and the MCP docked on the right"""
    bl_idname = "gray_matter.classic_layout"
    bl_label = "Classic Layout"

    def execute(self, context):
        area = _view3d_area(context)
        if area is None:
            self.report({'WARNING'}, "No 3D viewport found")
            return {'CANCELLED'}
        space = area.spaces.active
        space.show_region_ui = True
        space.show_region_toolbar = False
        if len(space.region_quadviews) == 0:
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            with context.temp_override(area=area, region=region):
                bpy.ops.screen.region_quadviews()
        context.scene.transform_orientation_slots[0].type = 'GLOBAL'
        return {'FINISHED'}


class GM_OT_freeze(bpy.types.Operator):
    """Freeze: bake the modifier stack into the mesh"""
    bl_idname = "gray_matter.freeze"
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


class GM_OT_reset_srt(bpy.types.Operator):
    """Reset scale, rotation or translation of the selection"""
    bl_idname = "gray_matter.reset_srt"
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


class GM_OT_apply_theme(bpy.types.Operator):
    """Apply the light-gray classic theme (undo with Reset Theme)"""
    bl_idname = "gray_matter.apply_theme"
    bl_label = "Apply Gray Theme"

    def execute(self, context):
        n = gm_theme.apply()
        self.report({'INFO'}, f"Gray theme applied ({n} colors)")
        return {'FINISHED'}


class GM_OT_reset_theme(bpy.types.Operator):
    """Restore Blender's default theme"""
    bl_idname = "gray_matter.reset_theme"
    bl_label = "Reset Theme"

    def execute(self, context):
        bpy.ops.preferences.reset_default_theme()
        return {'FINISHED'}


classes = (
    GM_OT_swallow,
    GM_OT_srt_tool,
    GM_OT_object_select,
    GM_OT_component_mode,
    GM_OT_open_editor,
    GM_OT_quad_view,
    GM_OT_classic_layout,
    GM_OT_freeze,
    GM_OT_reset_srt,
    GM_OT_apply_theme,
    GM_OT_reset_theme,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
