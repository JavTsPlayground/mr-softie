# SPDX-License-Identifier: GPL-3.0-or-later
"""The MCP: main command panel docked on the right of the 3D view.

Five stacked sections in the classic order: Select, Transform, Snap,
Constrain, Edit, followed by a View section for layout and theme.
"""
import bpy

from .tools import tool_id

CATEGORY = "MCP"


def _active_tool_id(context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    except (AttributeError, TypeError):
        return ""
    return tool.idname if tool else ""


def _mode_key(context):
    return "mesh" if context.mode == 'EDIT_MESH' else "object"


class _MCPPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY


class MS_PT_mcp_select(_MCPPanel, bpy.types.Panel):
    bl_idname = "MS_PT_mcp_select"
    bl_label = "Select"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        ts = context.tool_settings
        obj = context.active_object
        in_edit = context.mode == 'EDIT_MESH'

        col = layout.column(align=True)
        col.scale_y = 1.3
        col.operator("mr_softie.object_select", text="Select", icon='RESTRICT_SELECT_OFF',
                     depress=_active_tool_id(context).startswith("builtin.select"))

        row = layout.row(align=True)
        row.operator("mr_softie.object_select", text="Obj", depress=context.mode == 'OBJECT')
        for i, (comp, label) in enumerate((('VERT', "Pnt"), ('EDGE', "Edge"), ('FACE', "Poly"))):
            on = in_edit and ts.mesh_select_mode[i]
            op = row.operator("mr_softie.component_mode", text=label, depress=on)
            op.component = comp

        row = layout.row(align=True)
        ns = "mesh" if in_edit else "object"
        row.operator(f"{ns}.select_all", text="All").action = 'SELECT'
        row.operator(f"{ns}.select_all", text="None").action = 'DESELECT'
        row.operator(f"{ns}.select_all", text="Invert").action = 'INVERT'
        if not in_edit:
            op = layout.operator("object.select_grouped", text="Select Branch")
            op.type = 'CHILDREN_RECURSIVE'
            op.extend = True

        if obj is not None:
            layout.prop(obj, "name", text="", icon='OBJECT_DATA')


class MS_PT_mcp_transform(_MCPPanel, bpy.types.Panel):
    bl_idname = "MS_PT_mcp_transform"
    bl_label = "Transform"
    bl_order = 1

    def _srt_block(self, layout, context, kind, letter, obj, attr):
        active = _active_tool_id(context) == tool_id(kind, _mode_key(context))
        row = layout.row(align=True)
        split = row.split(factor=0.18, align=True)
        btn = split.operator("mr_softie.srt_tool", text=letter, depress=active)
        btn.kind = kind
        fields = split.row(align=True)
        if obj is not None and context.mode == 'OBJECT' and attr:
            if attr == "rotation_euler" and obj.rotation_mode not in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'}:
                fields.prop(obj, "rotation_mode", text="")
            else:
                for i, axis in enumerate("xyz"):
                    fields.prop(obj, attr, index=i, text=axis)
            reset = fields.operator("mr_softie.reset_srt", text="", icon='LOOP_BACK')
            reset.kind = letter
        else:
            fields.label(text="drag in viewport")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        ts = context.tool_settings

        col = layout.column(align=True)
        self._srt_block(col, context, 'scale', "S", obj, "scale")
        self._srt_block(col, context, 'rotate', "R", obj, "rotation_euler")
        self._srt_block(col, context, 'translate', "T", obj, "location")

        slot = context.scene.transform_orientation_slots[0]
        row = layout.row(align=True)
        row.prop_enum(slot, "type", 'GLOBAL', text="Global")
        row.prop_enum(slot, "type", 'LOCAL', text="Local")
        row.prop_enum(slot, "type", 'VIEW', text="View")

        row = layout.row(align=True)
        row.prop(ts, "transform_pivot_point", text="")
        prop_attr = "use_proportional_edit" if context.mode == 'EDIT_MESH' else "use_proportional_edit_objects"
        row.prop(ts, prop_attr, text="Prop", toggle=True)


class MS_PT_mcp_snap(_MCPPanel, bpy.types.Panel):
    bl_idname = "MS_PT_mcp_snap"
    bl_label = "Snap"
    bl_order = 2

    def draw_header(self, context):
        self.layout.prop(context.tool_settings, "use_snap", text="")

    def draw(self, context):
        layout = self.layout
        ts = context.tool_settings
        layout.active = ts.use_snap
        grid = layout.grid_flow(columns=2, align=True)
        grid.prop(ts, "snap_elements", expand=True)
        layout.prop(ts, "snap_target", text="Target")


class MS_PT_mcp_constrain(_MCPPanel, bpy.types.Panel):
    bl_idname = "MS_PT_mcp_constrain"
    bl_label = "Constrain"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("object.parent_set", text="Parent").type = 'OBJECT'
        row.operator("object.parent_clear", text="Cut").type = 'CLEAR_KEEP_TRANSFORM'
        layout.operator_menu_enum("object.constraint_add", "type", text="Constraint", icon='CONSTRAINT')
        layout.operator("object.constraints_clear", text="Remove All Constraints")


class MS_PT_mcp_edit(_MCPPanel, bpy.types.Panel):
    bl_idname = "MS_PT_mcp_edit"
    bl_label = "Edit"
    bl_order = 4

    def draw(self, context):
        layout = self.layout
        if context.mode == 'EDIT_MESH':
            row = layout.row(align=True)
            row.operator("mesh.duplicate_move", text="Duplicate")
            row.operator("mesh.delete", text="Delete").type = 'VERT'
            return
        col = layout.column(align=True)
        col.scale_y = 1.2
        col.operator("mr_softie.freeze", text="Freeze")
        row = col.row(align=True)
        row.operator("object.duplicate_move", text="Duplicate")
        row.operator("object.delete", text="Delete")
        row = col.row(align=True)
        row.operator("object.hide_view_set", text="Hide")
        row.operator("object.hide_view_clear", text="Unhide")
        col.operator("object.origin_set", text="Center to Geometry").type = 'ORIGIN_GEOMETRY'
        col.operator("mr_softie.reset_srt", text="Reset SRT").kind = 'ALL'


class MS_PT_mcp_view(_MCPPanel, bpy.types.Panel):
    bl_idname = "MS_PT_mcp_view"
    bl_label = "View"
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        space = context.space_data
        quad = bool(space and getattr(space, "region_quadviews", None))
        col = layout.column(align=True)
        col.operator("mr_softie.classic_layout", icon='VIEW3D')
        col.operator("mr_softie.quad_view", text="Four Views", depress=quad)
        row = col.row(align=True)
        row.operator("view3d.view_selected", text="Frame Sel")
        row.operator("view3d.view_all", text="Frame All")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("mr_softie.open_editor", text="Explorer").ui_type = 'OUTLINER'
        row.operator("mr_softie.open_editor", text="Shaders").ui_type = 'ShaderNodeTree'
        row.operator("mr_softie.open_editor", text="Curves").ui_type = 'FCURVES'

        row = layout.row(align=True)
        row.operator("mr_softie.apply_theme", text="Gray Theme", icon='COLOR')
        row.operator("mr_softie.reset_theme", text="Reset", icon='LOOP_BACK')


classes = (
    MS_PT_mcp_select,
    MS_PT_mcp_transform,
    MS_PT_mcp_snap,
    MS_PT_mcp_constrain,
    MS_PT_mcp_edit,
    MS_PT_mcp_view,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
