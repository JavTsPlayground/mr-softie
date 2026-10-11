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
from .viewport import button, column_kind, tag_columns


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

    # The big select button, with Group / Center beside it.
    row = layout.row()
    split = row.split(factor=0.42)
    big = split.column()
    big.scale_y = 2.3
    big.operator("mr_softie.object_select", text="", icon_value=icon("select"),
                 depress=_active_tool_id(context).startswith("builtin.select"))
    side = split.column(align=True)
    side.scale_y = 1.15
    if in_edit:
        side.operator("mesh.select_linked", text="Island")
    else:
        op = side.operator("object.select_grouped", text="Group")
        op.type = 'COLLECTION'
        op.extend = True
    side.prop(ts, "use_transform_data_origin", text="Center", toggle=True)

    grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
    grid.operator("mr_softie.object_select", text="Object", depress=context.mode == 'OBJECT')
    for i, (comp, label) in enumerate((('VERT', "Point"), ('EDGE', "Edge"), ('FACE', "Polygon"))):
        on = in_edit and ts.mesh_select_mode[i]
        grid.operator("mr_softie.component_mode", text=label, depress=on).component = comp

    if in_edit:
        row = layout.row(align=True)
        row.operator("mesh.select_edge_loop_multi", text="Loop")
        row.operator("mesh.select_edge_ring_multi", text="Ring")
        row.operator("mesh.select_more", text="Grow")
        row.operator("mesh.select_less", text="Shrink")
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
    if not in_edit:
        from .scenelayers import draw_selection_filter
        draw_selection_filter(layout, context)
    if obj is not None:
        layout.prop(obj, "name", text="")
    grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
    if in_edit:
        grid.operator("mr_softie.open_explorer", text="Explore")
    else:
        op = grid.operator("object.select_grouped", text="Branch")
        op.type = 'CHILDREN_RECURSIVE'
        op.extend = True
    grid.operator("mr_softie.open_explorer", text="Scene").scope = 'SCENE'
    grid.operator("mr_softie.open_explorer", text="Selection").scope = 'SELECTION'
    grid.operator("mr_softie.open_clusters", text="Clusters")


def _srt_block(layout, context, kind, letter, obj, attr):
    """One transform block as in the original: three stacked x / y / z boxes and the tool letter."""
    active = _active_tool_id(context) == tool_id(kind, _mode_key(context))
    row = layout.row(align=True)
    split = row.split(factor=0.8, align=True)
    fields = split.column(align=True)
    if obj is None:
        fields.label(text="drag in view")
    elif attr == "rotation_euler" and obj.rotation_mode in {'QUATERNION', 'AXIS_ANGLE'}:
        fields.prop(obj, "rotation_mode", text="")
    else:
        for i, axis in enumerate("xyz"):
            r = fields.split(factor=0.8, align=True)
            r.prop(obj, attr, index=i, text="")
            r.label(text=axis)
    btn = split.column(align=True)
    btn.scale_y = 3.0 if obj is not None else 1.0
    btn.operator("mr_softie.srt_tool", text=letter, depress=active).kind = kind


def draw_transform(layout, context):
    obj = context.active_object
    ts = context.tool_settings

    col = layout.column()
    _srt_block(col, context, 'scale', "s", obj, "scale")
    _srt_block(col, context, 'rotate', "r", obj, "rotation_euler")
    _srt_block(col, context, 'translate', "t", obj, "location")
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
    row = col.row(align=True)
    row.operator("mr_softie.freeze", text="Freeze", icon_value=icon("freeze"))
    row.operator("mr_softie.freeze_m", text="Freeze M")
    col.prop(context.window_manager, "mr_softie_cons_mode", text="")
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


def draw_layers(layout, context):
    from .scenelayers import draw_scene_layers
    draw_scene_layers(layout, context)


def draw_keying(layout, context):
    """KP/L: keying for the marked parameters."""
    scene = context.scene
    obj = context.active_object
    col = layout.column(align=True)
    col.scale_y = 1.2
    col.operator("mr_softie.save_key", text="Key Marked Parameters")
    row = col.row(align=True)
    row.operator("mr_softie.remove_key", text="Remove Key")
    row.operator("anim.keyframe_clear_v3d", text="Remove Anim")
    row = layout.row(align=True)
    row.prop(scene.tool_settings, "use_keyframe_insert_auto", text="Auto Key", toggle=True)
    row.operator("screen.keyframe_jump", text="", icon='PREV_KEYFRAME').next = False
    row.operator("screen.keyframe_jump", text="", icon='NEXT_KEYFRAME').next = True
    layout.label(text="Marked Parameters")
    layout.row(align=True).prop(context.window_manager, "mr_softie_marked", expand=True)
    if obj is None:
        layout.label(text="Nothing selected")


def draw_anim_layers(layout, context):
    from .layers import draw_layers as draw
    draw(layout, context)


def draw_material(layout, context):
    """MAT: the active object's materials and the main surface settings."""
    obj = context.active_object
    if obj is None or not hasattr(getattr(obj, "data", None), "materials"):
        layout.label(text="Select an object")
        return
    row = layout.row()
    row.template_list("MATERIAL_UL_matslots", "", obj, "material_slots", obj, "active_material_index", rows=3)
    row = layout.row(align=True)
    row.menu("MS_MT_get_material", text="Get")
    row.menu("MS_MT_get_shader", text="Shader")
    row.menu("MS_MT_get_texture", text="Texture")
    mat = obj.active_material
    if mat is None:
        return
    layout.prop(mat, "name", text="")
    tree = mat.node_tree
    bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if tree else None
    col = layout.column(align=True)
    if bsdf is not None:
        for name in ("Base Color", "Metallic", "Roughness", "IOR", "Alpha"):
            sock = bsdf.inputs.get(name)
            if sock is not None and not sock.is_linked:
                col.prop(sock, "default_value", text=name)
        for name, label in (("Transmission Weight", "Transmission"), ("Emission Strength", "Emission")):
            sock = bsdf.inputs.get(name)
            if sock is not None and not sock.is_linked:
                col.prop(sock, "default_value", text=label)
    else:
        col.prop(mat, "diffuse_color", text="Color")
    row = layout.row(align=True)
    row.operator("mr_softie.open_editor", text="Render Tree").ui_type = 'ShaderNodeTree'
    row.operator("mr_softie.material_manager", text="Manager")


SECTIONS = (
    ("select", "Select", draw_select),
    ("transform", "Transform", draw_transform),
    ("snap", "Snap", draw_snap),
    ("constrain", "Constrain", draw_constrain),
    ("edit", "Edit", draw_edit),
    ("view", "View", draw_view),
    ("layers", "Layers", draw_layers),
)

# The other two tabs of the MCP column: KP/L (keying and layers) and MAT (materials).
TAB_SECTIONS = (
    ("KPL", "kp_keying", "Keying", draw_keying),
    ("KPL", "kp_layers", "Scene Layers", draw_layers),
    ("KPL", "kp_animlayers", "Animation Layers", draw_anim_layers),
    ("MAT", "mat_material", "Material", draw_material),
)

TABS = (('MCP', "MCP", "Main command panel"),
        ('KPL', "KP/L", "Keying panel and layers"),
        ('MAT', "MAT", "Materials"))


def _tab(context):
    return getattr(context.window_manager, "mr_softie_mcp_tab", 'MCP')


class MS_PT_mcp_tabs(bpy.types.Panel):
    """MCP | KP/L | MAT, at the bottom of the MCP column."""
    bl_idname = "MS_PT_mcp_tabs"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "MCP"
    bl_label = "Tabs"
    bl_options = {'HIDE_HEADER'}
    bl_order = 200

    @classmethod
    def poll(cls, context):
        return column_kind(context) == "mcp"

    def draw(self, context):
        row = self.layout.row(align=True)
        row.scale_y = 1.3
        row.prop(context.window_manager, "mr_softie_mcp_tab", expand=True)


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
            "poll": classmethod(lambda cls, context: column_kind(context) == "mcp" and _tab(context) == 'MCP'),
            "draw": (lambda fn: lambda self, context: fn(self.layout, context))(fn),
        }))
    for order, (tab, key, label, fn) in enumerate(TAB_SECTIONS):
        classes.append(type(f"MS_PT_mcpcol_{key}", (bpy.types.Panel,), {
            "bl_idname": f"MS_PT_mcpcol_{key}",
            "bl_space_type": 'TEXT_EDITOR',
            "bl_region_type": 'UI',
            "bl_category": "MCP",
            "bl_label": label,
            "bl_order": order + 50,
            "poll": (lambda tab: classmethod(
                lambda cls, context: column_kind(context) == "mcp" and _tab(context) == tab))(tab),
            "draw": (lambda fn: lambda self, context: fn(self.layout, context))(fn),
        }))
    classes.append(MS_PT_mcp_tabs)
    return classes


classes = _make_panels()


def register():
    bpy.types.WindowManager.mr_softie_mcp_tab = bpy.props.EnumProperty(
        name="MCP Tab", items=TABS, default='MCP', update=lambda self, context: tag_columns())
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.mr_softie_mcp_tab
