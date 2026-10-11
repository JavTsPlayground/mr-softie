# SPDX-License-Identifier: GPL-3.0-or-later
"""The Model toolbar's menus, laid out as in the original:

  Get     Primitive, Material, Property
  Create  Curve, Surf. Mesh, Poly. Mesh, Skeleton, Model, Text
  Modify  Curve, Surf. Mesh, Poly. Mesh, Deform, Model
"""
import bpy

from .viewport import button


def poly(label, op, **kwargs):
    """A component command: enters component mode on the polygon mesh first, then runs `op`."""
    return ("run", label, "mr_softie.edit_op", {"op": op, "args": repr(kwargs) if kwargs else ""})


def curve(label, op, **kwargs):
    return ("run", label, "mr_softie.edit_op",
            {"op": op, "args": repr(kwargs) if kwargs else "", "kind": 'CURVE'})


def surface(label, op, **kwargs):
    return ("run", label, "mr_softie.edit_op",
            {"op": op, "args": repr(kwargs) if kwargs else "", "kind": 'SURFACE'})


def tool(label, name):
    return poly(label, "wm.tool_set_by_id", name=name, space_type='VIEW_3D')


# Menu contents: ("run", label, op, kwargs), ("menu", label, idname), ("label", text), ("sep",)
MENUS = {
    "MS_MT_create_surface": ("Surf. Mesh", (
        ("label", "Primitive"),
        ("run", "Grid", "surface.primitive_nurbs_surface_surface_add", {}),
        ("run", "Sphere", "surface.primitive_nurbs_surface_sphere_add", {}),
        ("run", "Cylinder", "surface.primitive_nurbs_surface_cylinder_add", {}),
        ("run", "Torus", "surface.primitive_nurbs_surface_torus_add", {}),
        ("sep",),
        ("label", "From Curves"),
        ("run", "Loft (Curve Bevel)", "mr_softie.loft_curves", {}),
    )),
    "MS_MT_create_polymesh": ("Poly. Mesh", (
        ("run", "From Curve", "object.convert", {"target": 'MESH'}),
        ("run", "Revolution Around Axis", "mr_softie.revolution", {}),
        ("run", "Extrusion Along Curve", "mr_softie.extrude_along_curve", {}),
        ("run", "Filled Curve", "mr_softie.fill_curve", {}),
        ("sep",),
        poly("Hull", "mesh.convex_hull"),
        tool("Add Polygon (Draw)", "builtin.poly_build"),
        ("run", "Subdivision Copy", "mr_softie.subdivision_copy", {}),
    )),
    "MS_MT_create_skeleton": ("Skeleton", (
        ("run", "Draw 2D / 3D Chain", "mr_softie.draw_chain", {}),
        ("run", "Set Envelope", "mr_softie.set_envelope", {}),
        ("run", "Weight Paint", "mr_softie.weight_paint", {}),
        ("run", "Reset Pose", "mr_softie.reset_pose", {}),
        ("sep",),
        ("menu", "Constrain", "MS_MT_constrain"),
    )),
    "MS_MT_create_model": ("Model", (
        ("run", "New Model", "mr_softie.new_model", {}),
        ("run", "Null", "object.empty_add", {"type": 'PLAIN_AXES'}),
        ("run", "Duplicate Model", "object.duplicate_move", {}),
        ("run", "Instance (Linked Copy)", "object.duplicate_move_linked", {}),
    )),
    "MS_MT_modify_curve": ("Curve", (
        curve("Open / Close", "curve.cyclic_toggle"),
        curve("Inverse", "curve.switch_direction"),
        curve("Add Points (Subdivide)", "curve.subdivide"),
        curve("Delete Points", "curve.delete", type='VERT'),
        curve("Smooth", "curve.smooth"),
        ("sep",),
        curve("To Bezier", "curve.spline_type_set", type='BEZIER'),
        curve("To NURBS", "curve.spline_type_set", type='NURBS'),
        curve("To Linear", "curve.spline_type_set", type='POLY'),
    )),
    "MS_MT_modify_surface": ("Surf. Mesh", (
        surface("Open / Close U", "curve.cyclic_toggle", direction='CYCLIC_U'),
        surface("Open / Close V", "curve.cyclic_toggle", direction='CYCLIC_V'),
        surface("Inverse", "curve.switch_direction"),
        surface("Insert Knots (Subdivide)", "curve.subdivide"),
        ("sep",),
        ("run", "Convert to Poly. Mesh", "object.convert", {"target": 'MESH'}),
    )),
    "MS_MT_modify_polymesh": ("Poly. Mesh", (
        ("label", "Tools"),
        tool("Add Edge", "builtin.knife"),
        poly("Split Edge", "mr_softie.split_edge"),
        poly("Weld Points", "mr_softie.weld_points"),
        poly("Weld Edges", "mr_softie.weld_edges"),
        poly("Bridge Polygons", "mr_softie.bridge_polygons"),
        tool("Slice Polygons", "builtin.bisect"),
        tool("Add Polygon", "builtin.poly_build"),
        ("run", "Tweak", "wm.tool_set_by_id", {"name": "builtin.select", "space_type": 'VIEW_3D'}),
        ("sep",),
        ("label", "Polygons"),
        poly("Extrude Along Axis", "mesh.extrude_region_move"),
        poly("Extrude Along Normal", "mesh.extrude_region_shrink_fatten"),
        poly("Bevel", "mesh.bevel"),
        poly("Inset", "mesh.inset"),
        poly("Bridge", "mesh.bridge_edge_loops"),
        poly("Subdivide", "mesh.subdivide"),
        poly("Collapse", "mesh.merge", type='COLLAPSE'),
        poly("Dissolve", "mesh.dissolve_mode"),
        poly("Weld / Merge", "mesh.merge", type='CENTER'),
        poly("Filter Points", "mesh.remove_doubles"),
        poly("Split", "mesh.split"),
        poly("Symmetrize", "mesh.symmetrize"),
        poly("Invert Polygons", "mesh.flip_normals"),
        ("sep",),
        ("run", "Polygon Reduction", "mr_softie.reduce_polygons", {}),
    )),
    "MS_MT_modify_deform": ("Deform", (
        ("run", "Bend", "mr_softie.add_deform", {"method": 'BEND'}),
        ("run", "Twist", "mr_softie.add_deform", {"method": 'TWIST'}),
        ("run", "Taper", "mr_softie.add_deform", {"method": 'TAPER'}),
        ("run", "Push", "object.modifier_add", {"type": 'DISPLACE'}),
        ("run", "Shrinkwrap", "object.modifier_add", {"type": 'SHRINKWRAP'}),
        ("run", "Lattice", "mr_softie.lattice_deform", {}),
        ("sep",),
        ("run", "Smooth (Subdivision)", "object.subdivision_set", {"level": 2, "relative": False}),
        ("run", "Symmetry", "object.modifier_add", {"type": 'MIRROR'}),
    )),
    "MS_MT_modify_model": ("Model", (
        ("run", "Freeze", "mr_softie.freeze", {}),
        ("run", "Freeze Modeling", "mr_softie.freeze_m", {}),
        ("run", "Center to Geometry", "object.origin_set", {"type": 'ORIGIN_GEOMETRY'}),
        ("run", "Freeze Transforms", "object.transform_apply", {"location": True, "rotation": True, "scale": True}),
        ("run", "Reset Transforms", "mr_softie.reset_srt", {"kind": 'ALL'}),
    )),
}


def draw_entries(layout, entries):
    for entry in entries:
        kind = entry[0]
        if kind == "run":
            button(layout, entry[1], entry[2], **entry[3])
        elif kind == "menu":
            layout.menu(entry[2], text=entry[1])
        elif kind == "label":
            layout.label(text=entry[1])
        elif kind == "sep":
            layout.separator()


def _make_menu(idname, label, entries):
    return type(idname, (bpy.types.Menu,), {
        "bl_idname": idname,
        "bl_label": label,
        "draw": lambda self, context: draw_entries(self.layout, entries),
    })


menus = [_make_menu(idname, label, entries) for idname, (label, entries) in MENUS.items()]


# --------------------------------------------------------------------------
# Commands behind the menus
# --------------------------------------------------------------------------

def _curves(context):
    return [o for o in context.selected_objects if o.type == 'CURVE']


class MS_OT_new_model(bpy.types.Operator):
    """New Model: put the selected objects under a new model (a null they're parented to)"""
    bl_idname = "mr_softie.new_model"
    bl_label = "New Model"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.parent is None or not o.parent.select_get()]
        model = bpy.data.objects.new("Model", None)
        model.empty_display_type = 'CUBE'
        model.empty_display_size = 0.25
        context.collection.objects.link(model)
        if objs:
            center = sum((o.matrix_world.translation for o in objs), model.location.copy()) / len(objs)
            model.location = center
            context.view_layer.update()
            for obj in objs:
                world = obj.matrix_world.copy()
                obj.parent = model
                obj.matrix_parent_inverse = model.matrix_world.inverted()
                obj.matrix_world = world
        for o in context.selected_objects:
            o.select_set(False)
        model.select_set(True)
        context.view_layer.objects.active = model
        return {'FINISHED'}


class MS_OT_revolution(bpy.types.Operator):
    """Revolution Around Axis: spin the selected curve into a surface (a live Screw operator)"""
    bl_idname = "mr_softie.revolution"
    bl_label = "Revolution Around Axis"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = _curves(context) + [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "Select a curve")
            return {'CANCELLED'}
        for obj in objs:
            mod = obj.modifiers.new("Revolution", 'SCREW')
            mod.steps = mod.render_steps = 24
            mod.use_merge_vertices = True
            mod.use_normal_calculate = True
        return {'FINISHED'}


class MS_OT_extrude_along_curve(bpy.types.Operator):
    """Extrusion Along Curve: sweep the active curve (the profile) along the other selected curve"""
    bl_idname = "mr_softie.extrude_along_curve"
    bl_label = "Extrusion Along Curve"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        curves = _curves(context)
        profile = context.active_object
        paths = [c for c in curves if c != profile]
        if profile is None or profile.type != 'CURVE' or not paths:
            self.report({'WARNING'}, "Select the path curve, then the profile curve last")
            return {'CANCELLED'}
        for path in paths:
            path.data.bevel_mode = 'OBJECT'
            path.data.bevel_object = profile
            path.data.use_fill_caps = True
        return {'FINISHED'}


class MS_OT_loft_curves(bpy.types.Operator):
    """Loft: give the selected curves a thickness profile so they read as a surface"""
    bl_idname = "mr_softie.loft_curves"
    bl_label = "Loft"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        curves = _curves(context)
        if not curves:
            self.report({'WARNING'}, "Select curves")
            return {'CANCELLED'}
        for c in curves:
            c.data.extrude = max(c.data.extrude, 0.5)
        return {'FINISHED'}


class MS_OT_fill_curve(bpy.types.Operator):
    """Filled Curve: close the selected curves and fill them with polygons"""
    bl_idname = "mr_softie.fill_curve"
    bl_label = "Filled Curve"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        curves = _curves(context)
        if not curves:
            self.report({'WARNING'}, "Select curves")
            return {'CANCELLED'}
        for c in curves:
            c.data.dimensions = '2D'
            c.data.fill_mode = 'BOTH'
            for spline in c.data.splines:
                spline.use_cyclic_u = True
        return {'FINISHED'}


class MS_OT_subdivision_copy(bpy.types.Operator):
    """Subdivision: a new, smoothed polygon mesh from the selected one (the original is kept)"""
    bl_idname = "mr_softie.subdivision_copy"
    bl_label = "Subdivision"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a polygon mesh")
            return {'CANCELLED'}
        depsgraph = context.evaluated_depsgraph_get()
        mod = obj.modifiers.new("Subdivision", 'SUBSURF')
        mod.levels = 1
        depsgraph.update()
        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(context.evaluated_depsgraph_get()))
        obj.modifiers.remove(mod)
        new = bpy.data.objects.new(obj.name + "_subdiv", mesh)
        new.matrix_world = obj.matrix_world
        for coll in obj.users_collection:
            coll.objects.link(new)
        obj.select_set(False)
        new.select_set(True)
        context.view_layer.objects.active = new
        return {'FINISHED'}


class MS_OT_lattice_deform(bpy.types.Operator):
    """Lattice: a lattice around the selected objects that deforms them"""
    bl_idname = "mr_softie.lattice_deform"
    bl_label = "Lattice Deform"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type in {'MESH', 'CURVE', 'SURFACE'}]
        if not objs:
            self.report({'WARNING'}, "Select objects to deform")
            return {'CANCELLED'}
        from mathutils import Vector
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        data = bpy.data.lattices.new("Lattice")
        data.points_u = data.points_v = data.points_w = 3
        lat = bpy.data.objects.new("Lattice", data)
        lat.location = (lo + hi) / 2
        lat.scale = [max(v, 0.01) * 1.05 for v in (hi - lo)]
        context.collection.objects.link(lat)
        for obj in objs:
            mod = obj.modifiers.new("Lattice", 'LATTICE')
            mod.object = lat
        for o in context.selected_objects:
            o.select_set(False)
        lat.select_set(True)
        context.view_layer.objects.active = lat
        return {'FINISHED'}


classes = (MS_OT_new_model, MS_OT_revolution, MS_OT_extrude_along_curve, MS_OT_loft_curves,
           MS_OT_fill_curve, MS_OT_subdivision_copy, MS_OT_lattice_deform, *menus)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
