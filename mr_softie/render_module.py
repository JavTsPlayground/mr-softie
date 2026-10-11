# SPDX-License-Identifier: GPL-3.0-or-later
"""Commands behind the Render toolbar, laid out as in the original:

  Get     Primitive, Material, Property, Shader, Texture, Clip
  Modify  Materials, Shader, Texture, Projection, Ambience
  Render  Regions, Render, Export, Preview
"""
import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty

from .materials import _nodes, make_material, assign
from .viewport import button

SHADERS = (
    ('ShaderNodeBsdfPrincipled', "Principled", "All-round surface (the default)"),
    ('ShaderNodeBsdfDiffuse', "Lambert", "Matte diffuse"),
    ('ShaderNodeEmission', "Constant", "Flat color that ignores lights"),
    ('ShaderNodeBsdfGlass', "Glass", "Refractive glass"),
    ('ShaderNodeBsdfMetallic', "Metal", "Metallic surface"),
    ('ShaderNodeBsdfToon', "Toon", "Cartoon shading"),
    ('ShaderNodeSubsurfaceScattering', "Skin (SSS)", "Subsurface scattering"),
    ('ShaderNodeBsdfTransparent', "Transparent", "See-through"),
    ('ShaderNodeHoldout', "Matte", "Holdout: cuts a hole in the render"),
)

PROJECTIONS = (
    ('SMART', "Unique UVs", "Unwrap into islands automatically"),
    ('CUBIC', "Cubic", "Project from six sides"),
    ('CYLINDRICAL', "Cylindrical", "Wrap around the object's Z axis"),
    ('SPHERICAL', "Spherical", "Wrap around a sphere"),
    ('PLANAR', "Planar (View)", "Project from the current view"),
    ('UNWRAP', "Unfold (Seams)", "Unwrap along marked seams"),
)

EXPORTERS = (
    ("FBX", "export_scene.fbx"),
    ("OBJ", "wm.obj_export"),
    ("glTF", "export_scene.gltf"),
    ("Alembic", "wm.alembic_export"),
    ("USD", "wm.usd_export"),
)


def _available(idname):
    mod, name = idname.split(".", 1)
    try:
        getattr(getattr(bpy.ops, mod), name).get_rna_type()
        return True
    except (AttributeError, KeyError):
        return False


def surface_output(tree):
    out = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    if out is None:
        out = tree.nodes.new('ShaderNodeOutputMaterial')
    return out


def set_shader(mat, node_type):
    """Put a new shader of `node_type` on the material's surface, keeping its color."""
    tree = _nodes(mat)
    out = surface_output(tree)
    old = out.inputs["Surface"].links[0].from_node if out.inputs["Surface"].is_linked else None
    node = tree.nodes.new(node_type)
    node.location = (out.location.x - 300, out.location.y)
    if old is not None:
        old.location.x -= 300
        color_in = node.inputs.get("Color") or node.inputs.get("Base Color")
        old_color = old.inputs.get("Base Color") or old.inputs.get("Color")
        if color_in is not None and old_color is not None:
            if old_color.is_linked:
                tree.links.new(old_color.links[0].from_socket, color_in)
            elif hasattr(color_in, "default_value") and len(color_in.default_value) == len(old_color.default_value):
                color_in.default_value = old_color.default_value
    tree.links.new(node.outputs[0], out.inputs["Surface"])
    return node


class MS_OT_get_shader(bpy.types.Operator):
    """Put a new shader on the active object's material (making one if it has none)"""
    bl_idname = "mr_softie.get_shader"
    bl_label = "Get Shader"
    bl_options = {'REGISTER', 'UNDO'}

    shader: EnumProperty(items=SHADERS)

    def execute(self, context):
        obj = context.active_object
        if obj is None or not hasattr(getattr(obj, "data", None), "materials"):
            self.report({'WARNING'}, "Select an object first")
            return {'CANCELLED'}
        mat = obj.active_material
        if mat is None:
            mat = make_material('PHONG')
            assign([obj], mat)
        set_shader(mat, self.shader)
        return {'FINISHED'}


def _view3d(context):
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            return area, region
    return None, None


class MS_OT_projection(bpy.types.Operator):
    """Texture projection: lay out UVs on the selected meshes"""
    bl_idname = "mr_softie.projection"
    bl_label = "Texture Projection"
    bl_options = {'REGISTER', 'UNDO'}

    kind: EnumProperty(items=PROJECTIONS)

    def execute(self, context):
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if context.active_object is not None and context.active_object.type == 'MESH' \
                and context.active_object not in meshes:
            meshes.append(context.active_object)
        if not meshes:
            self.report({'WARNING'}, "Select a polygon mesh")
            return {'CANCELLED'}
        area, region = _view3d(context)
        was_edit = context.mode == 'EDIT_MESH'
        override = {"area": area, "region": region} if area is not None else {}
        with context.temp_override(**override):
            if not was_edit:
                if context.view_layer.objects.active not in meshes:
                    context.view_layer.objects.active = meshes[0]
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
            for obj in meshes:
                if not obj.data.uv_layers:
                    obj.data.uv_layers.new(name="Texture_Projection")
            kind = self.kind
            if kind == 'SMART':
                bpy.ops.uv.smart_project()
            elif kind == 'CUBIC':
                bpy.ops.uv.cube_project()
            elif kind == 'CYLINDRICAL':
                bpy.ops.uv.cylinder_project(direction='ALIGN_TO_OBJECT', align='POLAR_ZX')
            elif kind == 'SPHERICAL':
                bpy.ops.uv.sphere_project(direction='ALIGN_TO_OBJECT', align='POLAR_ZX')
            elif kind == 'PLANAR':
                bpy.ops.uv.project_from_view(scale_to_bounds=True)
            else:
                bpy.ops.uv.unwrap()
            if not was_edit:
                bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


def _world(context):
    scene = context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    world = scene.world
    tree = _nodes(world)
    bg = next((n for n in tree.nodes if n.type == 'BACKGROUND'), None)
    if bg is None:
        bg = tree.nodes.new('ShaderNodeBackground')
        out = next((n for n in tree.nodes if n.type == 'OUTPUT_WORLD'), None) \
            or tree.nodes.new('ShaderNodeOutputWorld')
        tree.links.new(bg.outputs[0], out.inputs["Surface"])
    return world, bg


class MS_OT_ambience(bpy.types.Operator):
    """Ambience: the scene's background / ambient light color and strength"""
    bl_idname = "mr_softie.ambience"
    bl_label = "Ambience"
    bl_options = {'REGISTER', 'UNDO'}

    color: FloatVectorProperty(name="Color", subtype='COLOR', size=3, min=0.0, max=1.0,
                               default=(0.05, 0.05, 0.05))
    strength: FloatProperty(name="Strength", min=0.0, soft_max=10.0, default=1.0)

    def invoke(self, context, event):
        _world_, bg = _world(context)
        self.color = bg.inputs["Color"].default_value[:3]
        self.strength = bg.inputs["Strength"].default_value
        return context.window_manager.invoke_props_dialog(self, width=260)

    def execute(self, context):
        world, bg = _world(context)
        bg.inputs["Color"].default_value = (*self.color, 1.0)
        bg.inputs["Strength"].default_value = self.strength
        world.color = self.color
        return {'FINISHED'}


class MS_OT_add_parameter(bpy.types.Operator):
    """Add a custom parameter to the active object (shown in its property page)"""
    bl_idname = "mr_softie.add_parameter"
    bl_label = "Custom Parameter"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({'WARNING'}, "Select an object first")
            return {'CANCELLED'}
        name, i = "Param", 1
        while name in obj.keys():
            i += 1
            name = f"Param{i}"
        obj[name] = 1.0
        ui = obj.id_properties_ui(name)
        ui.update(min=-1000.0, max=1000.0, soft_min=0.0, soft_max=1.0)
        self.report({'INFO'}, f"Added {name} to {obj.name}")
        return {'FINISHED'}


class MS_OT_save_render(bpy.types.Operator):
    """Save the last render to an image file"""
    bl_idname = "mr_softie.save_render"
    bl_label = "Save Rendered Image"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filter_image: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        if bpy.data.images.get("Render Result") is None:
            self.report({'WARNING'}, "Nothing rendered yet: Render > Current Frame first")
            return {'CANCELLED'}
        ext = context.scene.render.file_extension
        self.filepath = bpy.path.ensure_ext(bpy.path.abspath("//render"), ext)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        image = bpy.data.images.get("Render Result")
        if image is None or not self.filepath:
            return {'CANCELLED'}
        path = bpy.path.ensure_ext(self.filepath, context.scene.render.file_extension)
        image.save_render(path, scene=context.scene)
        self.report({'INFO'}, f"Saved {path}")
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Menus
# --------------------------------------------------------------------------

class MS_MT_get_property(bpy.types.Menu):
    bl_idname = "MS_MT_get_property"
    bl_label = "Property"

    def draw(self, context):
        layout = self.layout
        button(layout, "Geometry Approximation", "object.subdivision_set", level=2, relative=False)
        button(layout, "Custom Parameter", "mr_softie.add_parameter")
        layout.separator()
        layout.operator("mr_softie.open_ppg", text="Display / Visibility")


class MS_MT_get_shader(bpy.types.Menu):
    bl_idname = "MS_MT_get_shader"
    bl_label = "Shader"

    def draw(self, context):
        for key, label, _desc in SHADERS:
            button(self.layout, label, "mr_softie.get_shader", shader=key)


class MS_MT_projection(bpy.types.Menu):
    bl_idname = "MS_MT_projection"
    bl_label = "Projection"

    def draw(self, context):
        for key, label, _desc in PROJECTIONS:
            button(self.layout, label, "mr_softie.projection", kind=key)
        self.layout.separator()
        self.layout.operator("mr_softie.open_editor", text="Texture Editor").ui_type = 'UV'


class MS_MT_render_render(bpy.types.Menu):
    bl_idname = "MS_MT_render_render"
    bl_label = "Render"

    def draw(self, context):
        layout = self.layout
        button(layout, "Current Frame", "render.render", use_viewport=True)
        button(layout, "Sequence", "render.render", animation=True, use_viewport=True)
        layout.operator("mr_softie.pass_render", text="Current Pass")
        layout.separator()
        layout.operator("mr_softie.open_editor", text="Render Options").ui_type = 'PROPERTIES'
        button(layout, "Show Last Render", "render.view_show")


class MS_MT_render_regions(bpy.types.Menu):
    bl_idname = "MS_MT_render_regions"
    bl_label = "Regions"

    def draw(self, context):
        layout = self.layout
        button(layout, "Draw Region (Q)", "mr_softie.render_region")
        layout.operator("mr_softie.render_region_clear", text="Remove All Regions").all_views = True
        layout.operator("mr_softie.render_region_redraw", text="Refresh")


class MS_MT_render_export(bpy.types.Menu):
    bl_idname = "MS_MT_render_export"
    bl_label = "Export"

    def draw(self, context):
        layout = self.layout
        layout.operator("mr_softie.save_render", text="Rendered Image...")
        layout.separator()
        for label, idname in EXPORTERS:
            if _available(idname):
                button(layout, label + "...", idname)


classes = (MS_OT_get_shader, MS_OT_projection, MS_OT_ambience, MS_OT_add_parameter, MS_OT_save_render,
           MS_MT_get_property, MS_MT_get_shader, MS_MT_projection, MS_MT_render_render,
           MS_MT_render_regions, MS_MT_render_export)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
