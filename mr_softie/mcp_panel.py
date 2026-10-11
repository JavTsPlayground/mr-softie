# SPDX-License-Identifier: GPL-3.0-or-later
"""The MCP: main command panel.

Drawn in two places:
  * the full-height MCP column of the MR.Softie workspace (a Text Editor area
    whose sidebar fills the area), and
  * the "MCP" tab of any 3D viewport sidebar, for use in other workspaces.

Sections in the classic order: Select, Transform, Snap, Constrain, Edit, View.
"""
import bpy

from .icons import icon
from .tools import tool_id
from .viewport import button, column_kind


def _active_tool_id(context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    except (AttributeError, TypeError):
        return ""
    return tool.idname if tool else ""


def _mode_key(context):
    return "mesh" if context.mode == 'EDIT_MESH' else "object"


# --------------------------------------------------------------------------
# Section drawing (shared)
# --------------------------------------------------------------------------

def draw_select(layout, context):
    ts = context.tool_settings
    obj = context.active_object
    in_edit = context.mode == 'EDIT_MESH'

    col = layout.column(align=True)
    col.scale_y = 1.25
    col.operator("mr_softie.object_select", text="Select", icon_value=icon("select"),
                 depress=_active_tool_id(context).startswith("builtin.select"))

    row = layout.row(align=True)
    row.operator("mr_softie.object_select", text="Obj", depress=context.mode == 'OBJECT')
    for i, (comp, label) in enumerate((('VERT', "Pnt"), ('EDGE', "Edge"), ('FACE', "Poly"))):
        on = in_edit and ts.mesh_select_mode[i]
        row.operator("mr_softie.component_mode", text=label, depress=on).component = comp

    if in_edit:
        row = layout.row(align=True)
        for label, name in (("Raycast", "mr_softie.raycast_mesh"), ("Tweak", "builtin.select")):
            op = row.operator("wm.tool_set_by_id", text=label)
            op.name = name
            op.space_type = 'VIEW_3D'   # the MCP may live in a non-3D area
    row = layout.row(align=True)
    ns = "mesh" if in_edit else "object"
    row.operator(f"{ns}.select_all", text="All").action = 'SELECT'
    row.operator(f"{ns}.select_all", text="None").action = 'DESELECT'
    row.operator(f"{ns}.select_all", text="Inv").action = 'INVERT'
    row = layout.row(align=True)
    row.operator("mr_softie.open_explorer", text="Explore")
    if not in_edit:
        op = row.operator("object.select_grouped", text="Branch")
        op.type = 'CHILDREN_RECURSIVE'
        op.extend = True
    if obj is not None:
        layout.prop(obj, "name", text="")


def _srt_row(layout, context, kind, letter, obj, attr):
    active = _active_tool_id(context) == tool_id(kind, _mode_key(context))
    row = layout.row(align=True)
    split = row.split(factor=0.16, align=True)
    split.operator("mr_softie.srt_tool", text=letter, depress=active).kind = kind
    fields = split.row(align=True)
    if obj is not None and context.mode == 'OBJECT':
        if attr == "rotation_euler" and obj.rotation_mode in {'QUATERNION', 'AXIS_ANGLE'}:
            fields.prop(obj, "rotation_mode", text="")
        else:
            for i in range(3):
                fields.prop(obj, attr, index=i, text="")
    else:
        fields.label(text="drag in view")


def draw_transform(layout, context):
    obj = context.active_object
    ts = context.tool_settings

    col = layout.column(align=True)
    _srt_row(col, context, 'scale', "S", obj, "scale")
    _srt_row(col, context, 'rotate', "R", obj, "rotation_euler")
    _srt_row(col, context, 'translate', "T", obj, "location")
    if obj is not None and context.mode == 'OBJECT':
        row = col.row(align=True)
        row.operator("mr_softie.reset_srt", text="Reset S").kind = 'S'
        row.operator("mr_softie.reset_srt", text="R").kind = 'R'
        row.operator("mr_softie.reset_srt", text="T").kind = 'T'

    # Reference frame: Global / Local / View / Par / Ref
    slot = context.scene.transform_orientation_slots[0]
    grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    grid.prop_enum(slot, "type", 'GLOBAL', text="Global")
    grid.prop_enum(slot, "type", 'LOCAL', text="Local")
    grid.prop_enum(slot, "type", 'VIEW', text="View")
    grid.prop_enum(slot, "type", 'PARENT', text="Par")
    grid.prop_enum(slot, "type", 'CURSOR', text="Ref")
    grid.prop_enum(slot, "type", 'NORMAL', text="Norm")

    # COG / Prop / Sym
    row = layout.row(align=True)
    cog = ts.transform_pivot_point == 'MEDIAN_POINT'
    row.operator("mr_softie.toggle_cog", text="COG", depress=cog)
    prop_attr = "use_proportional_edit" if context.mode == 'EDIT_MESH' else "use_proportional_edit_objects"
    row.prop(ts, prop_attr, text="Prop", toggle=True)
    mesh = obj.data if (obj is not None and obj.type == 'MESH') else None
    if mesh is not None:
        row.prop(mesh, "use_mirror_x", text="Sym", toggle=True)
    else:
        sub = row.row(align=True)
        sub.enabled = False
        sub.label(text="Sym")


def draw_snap(layout, context):
    ts = context.tool_settings
    layout.prop(ts, "use_snap", text="Snap", toggle=True)
    col = layout.column(align=True)
    col.active = ts.use_snap
    grid = col.grid_flow(columns=2, even_columns=True, align=True)
    for item in ('GRID', 'INCREMENT', 'VERTEX', 'EDGE', 'FACE', 'EDGE_MIDPOINT'):
        grid.prop_enum(ts, "snap_elements", item)


def draw_constrain(layout, context):
    if context.mode != 'OBJECT':
        layout.label(text="Object mode only")
        return
    row = layout.row(align=True)
    button(row, "Parent", "object.parent_set", icon_value=icon("parent"), type='OBJECT')
    button(row, "Cut", "object.parent_clear", icon_value=icon("cut"), type='CLEAR_KEEP_TRANSFORM')
    layout.operator_menu_enum("object.constraint_add", "type", text="Constraint")
    layout.operator("object.constraints_clear", text="Remove Cns")


def draw_edit(layout, context):
    col = layout.column(align=True)
    if context.mode == 'EDIT_MESH':
        button(col, "Duplicate", "mesh.duplicate_move")
        button(col, "Delete", "mesh.delete", type='VERT')
        button(col, "Merge", "mesh.merge", type='CENTER')
        row = col.row(align=True)
        button(row, "Weld Pts", "mr_softie.weld_points")
        button(row, "Split Edge", "mr_softie.split_edge")
        return
    col.scale_y = 1.1
    col.operator("mr_softie.freeze", text="Freeze", icon_value=icon("freeze"))
    row = col.row(align=True)
    button(row, "Duplicate", "object.duplicate_move")
    row.operator("object.delete", text="Delete")
    row = col.row(align=True)
    row.operator("object.hide_view_set", text="Hide")
    row.operator("object.hide_view_clear", text="Unhide")
    col.operator("object.origin_set", text="Center to Geo").type = 'ORIGIN_GEOMETRY'
    col.operator("mr_softie.reset_srt", text="Reset SRT", icon_value=icon("reset")).kind = 'ALL'


def draw_view(layout, context):
    col = layout.column(align=True)
    col.operator("mr_softie.build_workspace", text="Classic Layout", icon_value=icon("layout"))
    col.operator("mr_softie.maximize", text="Max / Restore View", icon_value=icon("maximize"))
    row = col.row(align=True)
    button(row, "Frame Sel", "view3d.view_selected")
    button(row, "Frame All", "view3d.view_all")
    row = layout.row(align=True)
    row.operator("mr_softie.open_explorer", text="Explorer", icon_value=icon("explorer"))
    row.operator("mr_softie.open_schematic", text="Schematic", icon_value=icon("schematic"))
    col = layout.column(align=True)
    col.operator("mr_softie.open_ppg", text="Property Page", icon_value=icon("ppg"))
    col.operator("mr_softie.open_script_editor", text="Script Editor", icon_value=icon("script"))
    col.operator("mr_softie.open_editor", text="Animation Curves").ui_type = 'FCURVES'
    row = layout.row(align=True)
    row.operator("mr_softie.apply_theme", text="Gray Theme")
    row.operator("mr_softie.reset_theme", text="Reset")


SECTIONS = (
    ("select", "Select", draw_select),
    ("transform", "Transform", draw_transform),
    ("snap", "Snap", draw_snap),
    ("constrain", "Constrain", draw_constrain),
    ("edit", "Edit", draw_edit),
    ("view", "View", draw_view),
)


# --------------------------------------------------------------------------
# Panel classes, generated for both hosts
# --------------------------------------------------------------------------

def _make_panels():
    classes = []
    for order, (key, label, fn) in enumerate(SECTIONS):
        # Sidebar tab in any 3D viewport
        classes.append(type(f"MS_PT_mcp_{key}", (bpy.types.Panel,), {
            "bl_idname": f"MS_PT_mcp_{key}",
            "bl_space_type": 'VIEW_3D',
            "bl_region_type": 'UI',
            "bl_category": "MCP",
            "bl_label": label,
            "bl_order": order,
            "draw": (lambda fn: lambda self, context: fn(self.layout, context))(fn),
        }))
        # Full-height MCP column
        classes.append(type(f"MS_PT_mcpcol_{key}", (bpy.types.Panel,), {
            "bl_idname": f"MS_PT_mcpcol_{key}",
            "bl_space_type": 'TEXT_EDITOR',
            "bl_region_type": 'UI',
            "bl_category": "MCP",
            "bl_label": label,
            "bl_order": order,
            "poll": classmethod(lambda cls, context: column_kind(context) == "mcp"),
            "draw": (lambda fn: lambda self, context: fn(self.layout, context))(fn),
        }))
    return classes


classes = _make_panels()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
