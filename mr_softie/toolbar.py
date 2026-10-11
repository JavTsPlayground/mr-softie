# SPDX-License-Identifier: GPL-3.0-or-later
"""The module toolbar: the left column of the MR.Softie workspace.

A module switcher (Model / Animate / Render / Simulate) on top, then stacked,
collapsible sections of commands for the current module.
"""
import bpy
from bpy.props import EnumProperty

from .custom_toolbars import draw_custom, draw_custom_tools
from .layers import draw_layers
from .ghosting import draw_ghost_panel
from .rigging import draw_chain_panel
from .passes import draw_channels, draw_partitions, draw_passes
from .viewport import button, column_kind, tag_columns

MODULES = (
    ('MODEL', "Model", "Modeling commands"),
    ('ANIMATE', "Animate", "Animation commands"),
    ('RENDER', "Render", "Rendering commands"),
    ('SIMULATE', "Simulate", "Simulation commands"),
    ('ICE', "ICE", "ICE trees and compounds (Geometry Nodes)"),
    ('CUSTOM', "Custom", "Your own toolbars"),
)

def poly(label, op, **kwargs):
    """A polygon-mesh command: enters component mode first if needed, then runs `op`."""
    return ("run", label, "mr_softie.edit_op", {"op": op, "args": repr(kwargs) if kwargs else ""})


# Button entries:
#   ("run", label, operator, {kwargs})  -> runs in the main viewport
#   ("menu", label, MenuClass.bl_idname)
#   ("editor", label, ui_type)          -> floating editor window
#   ("draw", function)                  -> function(layout, context) draws the section
#   ("sep",)
SECTIONS = {
    'MODEL': (
        ("Get", (
            ("menu", "Primitive", "MS_MT_get_primitive"),
            ("menu", "Material", "MS_MT_get_material"),
            ("menu", "Property", "MS_MT_get_property"),
        )),
        ("Create", (
            ("menu", "Curve", "MS_MT_create_curve"),
            ("menu", "Surf. Mesh", "MS_MT_create_surface"),
            ("menu", "Poly. Mesh", "MS_MT_create_polymesh"),
            ("menu", "Skeleton", "MS_MT_create_skeleton"),
            ("menu", "Model", "MS_MT_create_model"),
            ("run", "Text", "object.text_add", {}),
        )),
        ("Modify", (
            ("menu", "Curve", "MS_MT_modify_curve"),
            ("menu", "Surf. Mesh", "MS_MT_modify_surface"),
            ("menu", "Poly. Mesh", "MS_MT_modify_polymesh"),
            ("menu", "Deform", "MS_MT_modify_deform"),
            ("menu", "Model", "MS_MT_modify_model"),
        )),
    ),
    'ANIMATE': (
        ("Get", (
            ("menu", "Primitive", "MS_MT_get_primitive"),
            ("run", "Camera", "object.camera_add", {}),
        )),
        ("Keys", (
            ("run", "Save Key", "mr_softie.save_key", {}),
            ("run", "Remove Key", "mr_softie.remove_key", {}),
            ("run", "Remove Anim", "anim.keyframe_clear_v3d", {}),
        )),
        ("Skeleton", (
            ("run", "Draw Chain", "mr_softie.draw_chain", {}),
            ("run", "Set Envelope", "mr_softie.set_envelope", {}),
            ("run", "Weight Paint", "mr_softie.weight_paint", {}),
            ("run", "Reset Pose", "mr_softie.reset_pose", {}),
            ("menu", "Constrain", "MS_MT_constrain"),
        )),
        ("Chain", (("draw", draw_chain_panel),)),
        ("Ghosting", (("draw", draw_ghost_panel),)),
        ("Layers", (("draw", draw_layers),)),
        ("Mixer", (
            ("run", "Store Clip", "mr_softie.store_clip", {}),
            ("editor", "Open Mixer", 'NLA_EDITOR'),
        )),
        ("Editors", (
            ("editor", "Anim Editor", 'FCURVES'),
            ("editor", "Dopesheet", 'DOPESHEET'),
        )),
    ),
    'RENDER': (
        ("Get", (
            ("menu", "Primitive", "MS_MT_get_primitive"),
            ("menu", "Material", "MS_MT_get_material"),
            ("menu", "Property", "MS_MT_get_property"),
            ("menu", "Shader", "MS_MT_get_shader"),
            ("menu", "Texture", "MS_MT_get_texture"),
            ("run", "Clip", "mr_softie.get_texture", {"texture": 'IMAGE'}),
            ("menu", "Light", "MS_MT_get_light"),
        )),
        ("Modify", (
            ("run", "Materials", "mr_softie.material_manager", {}),
            ("editor", "Shader", 'ShaderNodeTree'),
            ("editor", "Texture", 'UV'),
            ("menu", "Projection", "MS_MT_projection"),
            ("run", "Ambience", "mr_softie.ambience", {}),
        )),
        ("Render", (
            ("menu", "Regions", "MS_MT_render_regions"),
            ("menu", "Render", "MS_MT_render_render"),
            ("menu", "Export", "MS_MT_render_export"),
            ("run", "Preview", "mr_softie.toggle_render_preview", {}),
        )),
        ("Pass", (("draw", draw_passes),)),
        ("Partitions", (("draw", draw_partitions),)),
        ("Channels", (("draw", draw_channels),)),
    ),
    'SIMULATE': (
        ("Create", (
            ("run", "Rigid Body", "rigidbody.object_add", {"type": 'ACTIVE'}),
            ("run", "Passive Body", "rigidbody.object_add", {"type": 'PASSIVE'}),
            ("run", "Cloth", "object.modifier_add", {"type": 'CLOTH'}),
            ("run", "Soft Body", "object.modifier_add", {"type": 'SOFT_BODY'}),
            ("run", "Particles", "object.particle_system_add", {}),
            ("menu", "Force", "MS_MT_create_force"),
        )),
        ("Simulate", (
            ("run", "Play", "screen.animation_play", {}),
            ("run", "Bake All", "ptcache.bake_all", {"bake": True}),
            ("run", "Free Bakes", "ptcache.free_bake_all", {}),
        )),
    ),
    'CUSTOM': (
        ("Toolbars", (("draw", draw_custom),)),
        ("Make Buttons", (("draw", draw_custom_tools),)),
    ),
    'ICE': (
        ("Create", (
            ("run", "ICE Tree", "mr_softie.ice_tree", {}),
            ("editor", "Open ICE Tree", 'GeometryNodeTree'),
        )),
        ("Compounds", (
            ("run", "Emit from Surface", "mr_softie.ice_compound", {"compound": 'EMIT'}),
            ("run", "Simulate Particles", "mr_softie.ice_compound", {"compound": 'PARTICLES'}),
            ("run", "Jitter", "mr_softie.ice_compound", {"compound": 'JITTER'}),
            ("run", "Push", "mr_softie.ice_compound", {"compound": 'PUSH'}),
            ("run", "Grow Strands", "mr_softie.ice_compound", {"compound": 'STRANDS'}),
            ("run", "Strand Dynamics", "mr_softie.ice_compound", {"compound": 'STRAND_DYNAMICS'}),
            ("run", "Turbulence", "mr_softie.ice_compound", {"compound": 'TURBULENCE'}),
            ("run", "Swarm", "mr_softie.ice_compound", {"compound": 'SWARM'}),
            ("run", "Trails", "mr_softie.ice_compound", {"compound": 'TRAILS'}),
            ("run", "Surface Attract", "mr_softie.ice_compound", {"compound": 'SURFACE_ATTRACT'}),
        )),
        ("Simulate", (
            ("run", "Play", "screen.animation_play", {}),
            ("run", "Reset", "screen.frame_jump", {"end": False}),
            ("run", "Bake Selected", "object.simulation_nodes_cache_bake", {"selected": True}),
            ("run", "Free Bake", "object.simulation_nodes_cache_delete", {"selected": True}),
        )),
    ),
}

MAX_SECTIONS = max(len(v) for v in SECTIONS.values())


def current_module(context):
    return context.window_manager.mr_softie_module


def _draw_entries(layout, entries, context=None):
    if entries and entries[0][0] == "draw":
        entries[0][1](layout, context or bpy.context)
        return
    col = layout.column(align=True)
    for entry in entries:
        kind = entry[0]
        if kind == "run":
            _, label, idname, kwargs = entry
            button(col, label, idname, **kwargs)
        elif kind == "menu":
            col.menu(entry[2], text=entry[1])
        elif kind == "editor":
            col.operator("mr_softie.open_editor", text=entry[1]).ui_type = entry[2]


# --------------------------------------------------------------------------
# Menus
# --------------------------------------------------------------------------

class MS_MT_get_primitive(bpy.types.Menu):
    bl_idname = "MS_MT_get_primitive"
    bl_label = "Primitive"

    def draw(self, context):
        layout = self.layout
        button(layout, "Null", "object.empty_add", type='PLAIN_AXES')
        layout.separator()
        layout.label(text="Polygon Mesh")
        for label, op in (("Cube", "mesh.primitive_cube_add"),
                          ("Sphere", "mesh.primitive_uv_sphere_add"),
                          ("Geosphere", "mesh.primitive_ico_sphere_add"),
                          ("Cylinder", "mesh.primitive_cylinder_add"),
                          ("Cone", "mesh.primitive_cone_add"),
                          ("Torus", "mesh.primitive_torus_add"),
                          ("Grid", "mesh.primitive_grid_add"),
                          ("Disc", "mesh.primitive_circle_add")):
            button(layout, label, op)
        layout.separator()
        layout.label(text="Curve")
        button(layout, "Circle", "curve.primitive_bezier_circle_add")
        button(layout, "Line", "curve.primitive_bezier_curve_add")
        layout.separator()
        layout.menu("MS_MT_create_surface", text="Surface")
        layout.menu("MS_MT_get_light", text="Light")
        button(layout, "Camera", "object.camera_add")
        button(layout, "Lattice", "object.add", type='LATTICE')


class MS_MT_get_light(bpy.types.Menu):
    bl_idname = "MS_MT_get_light"
    bl_label = "Light"

    def draw(self, context):
        for label, kind in (("Point", 'POINT'), ("Spot", 'SPOT'),
                            ("Infinite", 'SUN'), ("Area", 'AREA')):
            button(self.layout, label, "object.light_add", type=kind)


class MS_MT_create_curve(bpy.types.Menu):
    bl_idname = "MS_MT_create_curve"
    bl_label = "Curve"

    def draw(self, context):
        button(self.layout, "Bezier", "curve.primitive_bezier_curve_add")
        button(self.layout, "NURBS", "curve.primitive_nurbs_curve_add")
        button(self.layout, "Path", "curve.primitive_nurbs_path_add")


class MS_MT_create_force(bpy.types.Menu):
    bl_idname = "MS_MT_create_force"
    bl_label = "Force"

    def draw(self, context):
        for label, kind in (("Gravity / Force", 'FORCE'), ("Wind", 'WIND'),
                            ("Vortex", 'VORTEX'), ("Turbulence", 'TURBULENCE'),
                            ("Drag", 'DRAG')):
            button(self.layout, label, "object.effector_add", type=kind)


# --------------------------------------------------------------------------
# Panels in the toolbar column
# --------------------------------------------------------------------------

def _is_toolbar(context):
    return column_kind(context) == "toolbar"


class MS_PT_tb_module(bpy.types.Panel):
    bl_idname = "MS_PT_tb_module"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Toolbar"
    bl_label = "Module"
    bl_options = {'HIDE_HEADER'}
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return _is_toolbar(context)

    def draw(self, context):
        # The module menu at the top of the toolbar, as in the original ("Render ▾").
        layout = self.layout
        row = layout.row()
        row.scale_y = 1.3
        row.prop(context.window_manager, "mr_softie_module", text="")


class MS_PT_tb_switch(bpy.types.Panel):
    """Module icons at the bottom of the toolbar: one click per module."""
    bl_idname = "MS_PT_tb_switch"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Toolbar"
    bl_label = "Modules"
    bl_options = {'HIDE_HEADER'}
    bl_order = 100

    @classmethod
    def poll(cls, context):
        return _is_toolbar(context)

    def draw(self, context):
        wm = context.window_manager
        row = self.layout.row(align=True)
        row.scale_y = 1.2
        for ident, _label, _desc in MODULES:
            row.prop_enum(wm, "mr_softie_module", ident, text="")


def _make_section_panel(index):
    def poll(cls, context):
        return _is_toolbar(context) and index < len(SECTIONS[current_module(context)])

    def draw_header(self, context):
        self.layout.label(text=SECTIONS[current_module(context)][index][0])

    def draw(self, context):
        _draw_entries(self.layout, SECTIONS[current_module(context)][index][1], context)

    return type(f"MS_PT_tb_section{index}", (bpy.types.Panel,), {
        "bl_idname": f"MS_PT_tb_section{index}",
        "bl_space_type": 'TEXT_EDITOR',
        "bl_region_type": 'UI',
        "bl_category": "Toolbar",
        "bl_label": "",
        "bl_order": index + 1,
        "poll": classmethod(poll),
        "draw_header": draw_header,
        "draw": draw,
    })


section_panels = [_make_section_panel(i) for i in range(MAX_SECTIONS)]

classes = (MS_MT_get_primitive, MS_MT_get_light, MS_MT_create_curve, MS_MT_create_force,
           MS_PT_tb_module, *section_panels, MS_PT_tb_switch)


def _module_items():
    from .icons import icon
    return [(ident, label, desc, icon(ident.lower()), i) for i, (ident, label, desc) in enumerate(MODULES)]


def register():
    bpy.types.WindowManager.mr_softie_module = EnumProperty(
        name="Module", items=_module_items(), default='MODEL',
        description="Toolbar module",
        update=lambda self, context: tag_columns())
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.mr_softie_module
