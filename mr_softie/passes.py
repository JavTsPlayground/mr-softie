# SPDX-License-Identifier: GPL-3.0-or-later
"""Render passes, partitions, render channels and mixer clips.

  Pass       = a Blender view layer. The current pass is the window's view layer.
  Partition  = a top-level collection. Each pass decides per partition whether
               it is visible, a holdout (matte) or indirect only (shadows and
               reflections without being seen), like partition overrides.
  Channel    = an extra render pass (depth, normal, mist, AO, mattes).
  Clip       = an action stored on a mixer (NLA) track.
"""
import bpy
from bpy.props import EnumProperty, StringProperty

from .viewport import button

PARTITION_KEY = "mr_softie_partition"

CHANNELS = (
    ("use_pass_z", "Depth"),
    ("use_pass_normal", "Normal"),
    ("use_pass_mist", "Mist"),
    ("use_pass_ambient_occlusion", "AO"),
    ("use_pass_diffuse_color", "Diffuse"),
    ("use_pass_emit", "Emit"),
    ("use_pass_cryptomatte_object", "Obj ID"),
    ("use_pass_cryptomatte_material", "Mat ID"),
)


PRESETS = (
    ('BEAUTY', "Beauty", "The full image", ()),
    ('DIFFUSE', "Diffuse", "Diffuse lighting and color",
     ("use_pass_diffuse_direct", "use_pass_diffuse_indirect", "use_pass_diffuse_color")),
    ('SPECULAR', "Specular", "Reflections",
     ("use_pass_glossy_direct", "use_pass_glossy_indirect", "use_pass_glossy_color")),
    ('SHADOW', "Shadow", "Shadows", ("use_pass_shadow",)),
    ('AO', "Ambient Occlusion", "Contact shadowing", ("use_pass_ambient_occlusion",)),
    ('DEPTH', "Depth", "Z depth and mist", ("use_pass_z", "use_pass_mist")),
    ('NORMAL', "Normal", "Surface normals and position", ("use_pass_normal", "use_pass_position")),
    ('MATTE', "Matte", "Object and material ID mattes",
     ("use_pass_cryptomatte_object", "use_pass_cryptomatte_material")),
)


def new_pass(context, name):
    """New view layer named after `name` (numbered if taken), selection carried over, made current."""
    scene = context.scene
    unique, index = name, 1
    while unique in scene.view_layers:
        index += 1
        unique = f"{name} {index}"
    previous = current_pass(context)
    layer = scene.view_layers.new(unique)
    # Carry the selection over so the MCP and tools keep working on it.
    for obj in previous.objects:
        if obj.select_get(view_layer=previous) and obj.name in layer.objects:
            obj.select_set(True, view_layer=layer)
    if previous.objects.active and previous.objects.active.name in layer.objects:
        layer.objects.active = previous.objects.active
    switch_pass(context, layer)
    return layer


REGION_KEY = "mr_softie_region"


def save_region(scene, layer):
    r = scene.render
    layer[REGION_KEY] = [float(r.use_border), r.border_min_x, r.border_max_x, r.border_min_y, r.border_max_y]


def load_region(scene, layer):
    saved = layer.get(REGION_KEY)
    if saved is None:
        return False
    r = scene.render
    use, r.border_min_x, r.border_max_x, r.border_min_y, r.border_max_y = saved
    r.use_border = bool(use)
    return True


def switch_pass(context, layer):
    """Make `layer` the current pass; each pass keeps its own render region."""
    scene = context.scene
    save_region(scene, current_pass(context))
    if context.window:
        context.window.view_layer = layer
    load_region(scene, layer)


def current_pass(context):
    return context.window.view_layer if context.window else context.view_layer


def _find_layer_collection(layer_collection, collection):
    if layer_collection.collection == collection:
        return layer_collection
    for child in layer_collection.children:
        found = _find_layer_collection(child, collection)
        if found is not None:
            return found
    return None


def partitions(scene):
    return list(scene.collection.children)


# --------------------------------------------------------------------------
# Passes
# --------------------------------------------------------------------------

class MS_OT_pass_new(bpy.types.Operator):
    """New render pass (a view layer) that becomes the current pass"""
    bl_idname = "mr_softie.pass_new"
    bl_label = "New Pass"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        new_pass(context, "Pass")
        return {'FINISHED'}


class MS_OT_pass_preset(bpy.types.Operator):
    """New pass from a preset: the pass with its render channels already on"""
    bl_idname = "mr_softie.pass_preset"
    bl_label = "New Pass from Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(items=[(k, label, desc) for k, label, desc, _ in PRESETS])

    def execute(self, context):
        key, label, _desc, attrs = next(p for p in PRESETS if p[0] == self.preset)
        layer = new_pass(context, label)
        for attr in attrs:
            if hasattr(layer, attr):
                setattr(layer, attr, True)
        return {'FINISHED'}


class MS_MT_pass_presets(bpy.types.Menu):
    bl_idname = "MS_MT_pass_presets"
    bl_label = "Pass Preset"

    def draw(self, context):
        for key, label, _desc, _attrs in PRESETS:
            self.layout.operator("mr_softie.pass_preset", text=label).preset = key


class MS_OT_pass_set(bpy.types.Operator):
    """Make this the current pass"""
    bl_idname = "mr_softie.pass_set"
    bl_label = "Set Current Pass"
    bl_options = {'INTERNAL', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        layer = context.scene.view_layers.get(self.name)
        if layer is None or context.window is None:
            return {'CANCELLED'}
        switch_pass(context, layer)
        return {'FINISHED'}


class MS_OT_pass_delete(bpy.types.Operator):
    """Delete the current pass"""
    bl_idname = "mr_softie.pass_delete"
    bl_label = "Delete Pass"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and len(context.scene.view_layers) > 1

    def execute(self, context):
        scene = context.scene
        layer = current_pass(context)
        other = next(vl for vl in scene.view_layers if vl != layer)
        switch_pass(context, other)
        scene.view_layers.remove(layer)
        return {'FINISHED'}


class MS_OT_pass_render(bpy.types.Operator):
    """Render the current pass only"""
    bl_idname = "mr_softie.pass_render"
    bl_label = "Render Current Pass"

    def execute(self, context):
        layer = current_pass(context)
        bpy.ops.render.render('INVOKE_DEFAULT', layer=layer.name)
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Partitions
# --------------------------------------------------------------------------

class MS_OT_partition_new(bpy.types.Operator):
    """New partition holding the selected objects (they leave their other partitions)"""
    bl_idname = "mr_softie.partition_new"
    bl_label = "New Partition"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        objects = list(context.selected_objects)
        index = 1
        while f"Partition {index}" in bpy.data.collections:
            index += 1
        coll = bpy.data.collections.new(f"Partition {index}")
        coll[PARTITION_KEY] = True
        scene.collection.children.link(coll)
        for obj in objects:
            for old in list(obj.users_collection):
                old.objects.unlink(obj)
            coll.objects.link(obj)
        self.report({'INFO'}, f"{coll.name}: {len(objects)} object(s)")
        return {'FINISHED'}


class MS_OT_partition_select(bpy.types.Operator):
    """Select the objects of this partition"""
    bl_idname = "mr_softie.partition_select"
    bl_label = "Select Partition"
    bl_options = {'INTERNAL', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        coll = bpy.data.collections.get(self.name)
        if coll is None:
            return {'CANCELLED'}
        layer = current_pass(context)
        for obj in layer.objects:
            obj.select_set(False)
        selectable = [o for o in coll.all_objects if o.name in layer.objects and o.visible_get(view_layer=layer)]
        for obj in selectable:
            obj.select_set(True, view_layer=layer)
        if selectable:
            layer.objects.active = selectable[0]
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Mixer clips
# --------------------------------------------------------------------------

def store_clip(obj):
    """Move the object's action onto a new mixer track. Returns the strip or None."""
    ad = obj.animation_data
    if ad is None or ad.action is None:
        return None
    action = ad.action
    slot = getattr(ad, "action_slot", None)
    start = int(action.frame_range[0])
    track = ad.nla_tracks.new()
    track.name = action.name
    strip = track.strips.new(action.name, start, action)
    if slot is not None and hasattr(strip, "action_slot"):
        try:
            strip.action_slot = slot
        except (TypeError, AttributeError, RuntimeError):
            pass
    ad.action = None
    return strip


class MS_OT_store_clip(bpy.types.Operator):
    """Store the selected objects' animation as clips on the Mixer"""
    bl_idname = "mr_softie.store_clip"
    bl_label = "Store Action as Clip"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        stored = [obj for obj in context.selected_objects if store_clip(obj) is not None]
        if not stored:
            self.report({'WARNING'}, "Nothing selected has animation to store")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Stored {len(stored)} clip(s) on the Mixer")
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Toolbar section drawing
# --------------------------------------------------------------------------

def draw_passes(layout, context):
    scene = context.scene
    current = current_pass(context)
    col = layout.column(align=True)
    for layer in scene.view_layers:
        col.operator("mr_softie.pass_set", text=layer.name,
                     depress=layer == current).name = layer.name
    row = layout.row(align=True)
    row.operator("mr_softie.pass_new", text="New")
    row.menu("MS_MT_pass_presets", text="Preset")
    layout.prop(current, "name", text="")
    row = layout.row(align=True)
    row.operator("mr_softie.pass_render", text="Render")
    row.operator("mr_softie.pass_delete", text="Delete")
    row = layout.row(align=True)
    row.prop(scene.render, "use_border", text="Region", toggle=True)
    button(row, "Draw", "view3d.render_border")


def draw_partitions(layout, context):
    scene = context.scene
    layer = current_pass(context)
    layout.operator("mr_softie.partition_new", text="New from Selection")
    colls = partitions(scene)
    if not colls:
        layout.label(text="No partitions")
        return
    for coll in colls:
        lc = _find_layer_collection(layer.layer_collection, coll)
        if lc is None:
            continue
        row = layout.row(align=True)
        row.prop(lc, "exclude", text="", invert_checkbox=True)
        sub = row.row(align=True)
        sub.active = not lc.exclude
        sub.operator("mr_softie.partition_select", text=coll.name).name = coll.name
        sub.prop(lc, "holdout", text="")
        sub.prop(lc, "indirect_only", text="")
    layout.label(text="Visible · Matte · Indirect")


def draw_channels(layout, context):
    layer = current_pass(context)
    grid = layout.grid_flow(columns=2, even_columns=True, align=True)
    for attr, label in CHANNELS:
        if hasattr(layer, attr):
            grid.prop(layer, attr, text=label, toggle=True)
    eevee = getattr(layer, "eevee", None)
    if eevee is not None and hasattr(eevee, "use_pass_volume_direct"):
        grid.prop(eevee, "use_pass_volume_direct", text="Volume", toggle=True)


classes = (MS_OT_pass_new, MS_OT_pass_preset, MS_MT_pass_presets, MS_OT_pass_set, MS_OT_pass_delete, MS_OT_pass_render,
           MS_OT_partition_new, MS_OT_partition_select, MS_OT_store_clip)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
