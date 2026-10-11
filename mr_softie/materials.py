# SPDX-License-Identifier: GPL-3.0-or-later
"""Render Tree: material presets, textures, assigning and managing materials.

  Get > Material   presets built on the Principled BSDF (Lambert, Phong, Blinn,
                   Constant, Glass, Chrome, Metal, Plastic, Rubber, Car Paint)
  Get > Texture    Image, Checker, Noise, Gradient, Cell: added to the active
                   material with texture coordinates and a placement node, wired
                   into its color
  Assign Material  put an existing material on the selection
  Material Manager every material in the file, in a floating window
"""
import warnings

import bpy
from bpy.props import EnumProperty, StringProperty

# (key, label, description, Principled settings)
PRESETS = (
    ('LAMBERT', "Lambert", "Matte, no highlight",
     {"Roughness": 1.0, "Specular IOR Level": 0.0}),
    ('PHONG', "Phong", "Classic plastic-like highlight",
     {"Roughness": 0.35, "Specular IOR Level": 0.5}),
    ('BLINN', "Blinn", "Tighter, brighter highlight",
     {"Roughness": 0.2, "Specular IOR Level": 0.7}),
    ('CONSTANT', "Constant", "Flat color, no shading", None),
    ('GLASS', "Glass", "Clear glass",
     {"Roughness": 0.0, "Transmission Weight": 1.0, "IOR": 1.5, "Base Color": (1, 1, 1, 1)}),
    ('CHROME', "Chrome", "Mirror metal",
     {"Metallic": 1.0, "Roughness": 0.05, "Base Color": (0.9, 0.9, 0.9, 1)}),
    ('METAL', "Brushed Metal", "Satin metal with stretched highlights",
     {"Metallic": 1.0, "Roughness": 0.35, "Anisotropic": 0.6, "Base Color": (0.75, 0.75, 0.78, 1)}),
    ('PLASTIC', "Glossy Plastic", "Shiny colored plastic",
     {"Roughness": 0.12, "Specular IOR Level": 0.5, "Base Color": (0.6, 0.05, 0.05, 1)}),
    ('RUBBER', "Rubber", "Dark, soft and rough",
     {"Roughness": 0.85, "Specular IOR Level": 0.2, "Base Color": (0.03, 0.03, 0.03, 1)}),
    ('CARPAINT', "Car Paint", "Colored base under a clear coat",
     {"Roughness": 0.4, "Metallic": 0.6, "Coat Weight": 1.0, "Coat Roughness": 0.03,
      "Base Color": (0.05, 0.12, 0.45, 1)}),
)

TEXTURES = (
    ('IMAGE', "Image", "An image file"),
    ('CHECKER', "Checker", "Two-color checkerboard"),
    ('NOISE', "Noise", "Cloudy fractal noise"),
    ('GRADIENT', "Gradient", "Linear ramp across the object"),
    ('CELL', "Cell", "Cellular (Voronoi) pattern"),
)
TEXTURE_NODES = {'IMAGE': 'ShaderNodeTexImage', 'CHECKER': 'ShaderNodeTexChecker',
                 'NOISE': 'ShaderNodeTexNoise', 'GRADIENT': 'ShaderNodeTexGradient',
                 'CELL': 'ShaderNodeTexVoronoi'}


def _nodes(mat):
    if mat.node_tree is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            mat.use_nodes = True
    return mat.node_tree


def surface_shader(mat):
    """The node plugged into the material output's Surface."""
    tree = _nodes(mat)
    out = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None) or \
        next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None or not out.inputs["Surface"].is_linked:
        return None
    return out.inputs["Surface"].links[0].from_node


def make_material(key):
    """A new material from a preset."""
    _key, label, _desc, settings = next(p for p in PRESETS if p[0] == key)
    mat = bpy.data.materials.new(label)
    tree = _nodes(mat)
    bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    out = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL')
    if settings is None:
        # Constant: an emission shader shows the color exactly, unlit.
        if bsdf is not None:
            tree.nodes.remove(bsdf)
        emit = tree.nodes.new('ShaderNodeEmission')
        emit.location = (out.location.x - 250, out.location.y)
        emit.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)
        tree.links.new(emit.outputs["Emission"], out.inputs["Surface"])
        mat.diffuse_color = (0.8, 0.8, 0.8, 1.0)
    else:
        for name, value in settings.items():
            sock = bsdf.inputs.get(name)
            if sock is not None:
                sock.default_value = value
        if "Base Color" in settings:
            mat.diffuse_color = settings["Base Color"]
        if settings.get("Transmission Weight"):
            for attr in ("use_screen_refraction", "use_raytrace_refraction"):
                if hasattr(mat, attr):
                    setattr(mat, attr, True)
    mat["mr_softie_preset"] = key
    return mat


def assign(objects, mat):
    count = 0
    for obj in objects:
        data = getattr(obj, "data", None)
        if data is None or not hasattr(data, "materials"):
            continue
        if obj.active_material_index < len(obj.material_slots) and obj.material_slots:
            obj.material_slots[obj.active_material_index].material = mat
        else:
            data.materials.append(mat)
        count += 1
    return count


def color_input(node):
    """Where a texture plugs in: Base Color (Principled) or Color (Emission and others)."""
    for name in ("Base Color", "Color"):
        sock = node.inputs.get(name)
        if sock is not None:
            return sock
    return None


def add_texture(mat, key, image=None):
    """Add a texture to `mat`, wired into the surface shader's color. Returns the texture node."""
    tree = _nodes(mat)
    shader = surface_shader(mat)
    target = color_input(shader) if shader is not None else None
    base = shader.location if shader is not None else (0, 0)
    tex = tree.nodes.new(TEXTURE_NODES[key])
    tex.location = (base[0] - 320, base[1])
    mapping = tree.nodes.new('ShaderNodeMapping')
    mapping.location = (base[0] - 520, base[1])
    coords = tree.nodes.new('ShaderNodeTexCoord')
    coords.location = (base[0] - 720, base[1])
    tree.links.new(coords.outputs["UV" if key == 'IMAGE' else "Generated"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    if key == 'IMAGE' and image is not None:
        tex.image = image
    elif key == 'CHECKER':
        tex.inputs["Scale"].default_value = 8.0
    elif key == 'CELL':
        tex.inputs["Scale"].default_value = 6.0
    if target is not None:
        tree.links.new(tex.outputs["Color"], target)
    tree.nodes.active = tex
    return tex


def _target_objects(context):
    return [o for o in context.selected_objects if hasattr(getattr(o, "data", None), "materials")]


class MS_OT_get_material(bpy.types.Operator):
    """Get a new material from a preset and put it on the selected objects"""
    bl_idname = "mr_softie.get_material"
    bl_label = "Get Material"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(items=[(k, label, desc) for k, label, desc, _s in PRESETS])

    def execute(self, context):
        objs = _target_objects(context)
        if not objs:
            self.report({'WARNING'}, "Select an object first")
            return {'CANCELLED'}
        mat = make_material(self.preset)
        assign(objs, mat)
        self.report({'INFO'}, f"{mat.name} on {len(objs)} object(s)")
        return {'FINISHED'}


class MS_OT_get_texture(bpy.types.Operator):
    """Add a texture to the active object's material (making a Phong first if it has none)"""
    bl_idname = "mr_softie.get_texture"
    bl_label = "Get Texture"
    bl_options = {'REGISTER', 'UNDO'}

    texture: EnumProperty(items=TEXTURES)
    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filter_image: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        if self.texture == 'IMAGE' and not self.filepath:
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if obj is None or not hasattr(getattr(obj, "data", None), "materials"):
            self.report({'WARNING'}, "Select an object first")
            return {'CANCELLED'}
        mat = obj.active_material
        if mat is None:
            mat = make_material('PHONG')
            assign([obj], mat)
        image = None
        if self.texture == 'IMAGE' and self.filepath:
            try:
                image = bpy.data.images.load(self.filepath, check_existing=True)
            except RuntimeError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
        add_texture(mat, self.texture, image)
        return {'FINISHED'}


class MS_OT_assign_material(bpy.types.Operator):
    """Put an existing material on the selected objects"""
    bl_idname = "mr_softie.assign_material"
    bl_label = "Assign Material"
    bl_options = {'REGISTER', 'UNDO'}

    material: StringProperty()

    def execute(self, context):
        mat = bpy.data.materials.get(self.material)
        objs = _target_objects(context)
        if mat is None or not objs:
            return {'CANCELLED'}
        assign(objs, mat)
        return {'FINISHED'}


class MS_OT_material_manager(bpy.types.Operator):
    """Material Manager: every material in the file, in a floating window"""
    bl_idname = "mr_softie.material_manager"
    bl_label = "Material Manager"

    def execute(self, context):
        from .operators import open_floating_window
        _window, area = open_floating_window(context, 'OUTLINER')
        if area is None:
            self.report({'WARNING'}, "Could not open a window")
            return {'CANCELLED'}
        space = area.spaces.active
        space.display_mode = 'LIBRARIES'   # shown as "Blender File"
        if hasattr(space, "use_filter_id_type"):
            space.use_filter_id_type = True
            space.filter_id_type = 'MATERIAL'
        return {'FINISHED'}


class MS_MT_get_material(bpy.types.Menu):
    bl_idname = "MS_MT_get_material"
    bl_label = "Material"

    def draw(self, context):
        from .viewport import button
        layout = self.layout
        for key, label, _desc, _s in PRESETS:
            button(layout, label, "mr_softie.get_material", preset=key)
        layout.separator()
        layout.menu("MS_MT_assign_material", text="Assign Existing")
        layout.operator("mr_softie.material_manager", text="Material Manager")


class MS_MT_get_texture(bpy.types.Menu):
    bl_idname = "MS_MT_get_texture"
    bl_label = "Texture"

    def draw(self, context):
        from .viewport import button
        for key, label, _desc in TEXTURES:
            button(self.layout, label, "mr_softie.get_texture", texture=key)


class MS_MT_assign_material(bpy.types.Menu):
    bl_idname = "MS_MT_assign_material"
    bl_label = "Assign Material"

    def draw(self, context):
        layout = self.layout
        if not bpy.data.materials:
            layout.label(text="No materials yet")
        for mat in bpy.data.materials:
            layout.operator("mr_softie.assign_material", text=mat.name).material = mat.name


classes = (MS_OT_get_material, MS_OT_get_texture, MS_OT_assign_material, MS_OT_material_manager,
           MS_MT_get_material, MS_MT_get_texture, MS_MT_assign_material)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
