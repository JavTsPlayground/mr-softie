# SPDX-License-Identifier: GPL-3.0-or-later
"""Selection filters and scene layers.

Selection filter (MCP > Select): which kinds of object a click or box can pick:
All, Geometry, Lights, Cameras, Nulls, Skeletons. It uses each viewport's own
per-type selectability, so nothing about the objects themselves changes.

Scene layers (MCP > Layers): every object is in one layer (Default unless you
move it). A layer can be shown / hidden, made unselectable, and left out of
renders, for all its objects at once. Layers are independent of render
partitions: an object can be in one layer and one partition.
"""
import bpy
from bpy.props import EnumProperty, StringProperty

# --------------------------------------------------------------------------
# Selection filter
# --------------------------------------------------------------------------

TYPE_FLAGS = {
    'GEOMETRY': ("mesh", "curve", "surf", "meta", "font", "curves", "pointcloud", "volume",
                 "lattice", "grease_pencil"),
    'LIGHT': ("light", "light_probe"),
    'CAMERA': ("camera",),
    'NULL': ("empty",),
    'SKELETON': ("armature",),
}
ALL_FLAGS = sorted({f for flags in TYPE_FLAGS.values() for f in flags} | {"speaker"})
FILTERS = (
    ('ALL', "All", "Every kind of object can be selected"),
    ('GEOMETRY', "Geom", "Only geometry: meshes, curves, surfaces, text, hair..."),
    ('LIGHT', "Light", "Only lights"),
    ('CAMERA', "Cam", "Only cameras"),
    ('NULL', "Null", "Only nulls (empties)"),
    ('SKELETON', "Skel", "Only skeletons (armatures)"),
)


def _view_spaces():
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                yield area.spaces.active


def apply_filter(kind):
    allowed = set(ALL_FLAGS) if kind == 'ALL' else set(TYPE_FLAGS[kind])
    for space in _view_spaces():
        for flag in ALL_FLAGS:
            attr = f"show_object_select_{flag}"
            if hasattr(space, attr):
                setattr(space, attr, flag in allowed)


def _filter_update(self, context):
    apply_filter(self.mr_softie_select_filter)


# --------------------------------------------------------------------------
# Scene layers
# --------------------------------------------------------------------------

LAYERS_KEY = "mr_softie_layers"
MEMBER_KEY = "mr_softie_layer"
DEFAULT = "Default"


def layers(scene):
    data = scene.get(LAYERS_KEY)
    table = data.to_dict() if data is not None else {}
    table.setdefault(DEFAULT, {"view": 1, "select": 1, "render": 1})
    return table


def _save(scene, table):
    scene[LAYERS_KEY] = table


def layer_of(obj):
    return obj.get(MEMBER_KEY) or DEFAULT


def members(scene, name):
    return [o for o in scene.objects if layer_of(o) == name]


def apply_layer(scene, name):
    """Push a layer's flags onto its objects."""
    flags = layers(scene).get(name)
    if flags is None:
        return
    for obj in members(scene, name):
        obj.hide_viewport = not flags["view"]
        obj.hide_select = not flags["select"]
        obj.hide_render = not flags["render"]


def new_layer(scene, objects):
    table = layers(scene)
    index = 1
    while f"Layer {index}" in table:
        index += 1
    name = f"Layer {index}"
    table[name] = {"view": 1, "select": 1, "render": 1}
    _save(scene, table)
    move_to_layer(scene, objects, name)
    return name


def move_to_layer(scene, objects, name):
    for obj in objects:
        if name == DEFAULT:
            if MEMBER_KEY in obj:
                del obj[MEMBER_KEY]
        else:
            obj[MEMBER_KEY] = name
    flags = layers(scene)[name]
    for obj in objects:
        obj.hide_viewport = not flags["view"]
        obj.hide_select = not flags["select"]
        obj.hide_render = not flags["render"]


def toggle(scene, name, flag):
    table = layers(scene)
    table[name][flag] = 0 if table[name][flag] else 1
    _save(scene, table)
    apply_layer(scene, name)


def delete_layer(scene, name):
    if name == DEFAULT:
        return
    objs = members(scene, name)
    table = layers(scene)
    table.pop(name, None)
    _save(scene, table)
    move_to_layer(scene, objs, DEFAULT)


class MS_OT_layer_ctl(bpy.types.Operator):
    """Scene layers: toggle, select, move the selection into a layer, new, delete"""
    bl_idname = "mr_softie.scene_layer"
    bl_label = "Scene Layer"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(items=(
        ('NEW', "New Layer", "New layer holding the selected objects"),
        ('MOVE', "Move Here", "Move the selected objects into this layer"),
        ('SELECT', "Select", "Select the objects in this layer"),
        ('VIEW', "View", "Show / hide this layer"),
        ('SELECTABLE', "Selectable", "Make this layer selectable or not"),
        ('RENDER', "Render", "Include this layer in renders or not"),
        ('DELETE', "Delete", "Delete this layer (its objects go back to Default)"),
    ))
    layer: StringProperty(default=DEFAULT)

    TIPS = {'NEW': "New layer holding the selected objects",
            'MOVE': "Move the selected objects into this layer",
            'SELECT': "Select the objects in this layer",
            'VIEW': "Show / hide this layer",
            'SELECTABLE': "Make this layer selectable or not",
            'RENDER': "Include this layer in renders or not",
            'DELETE': "Delete this layer (its objects go back to Default)"}

    @classmethod
    def description(cls, context, props):
        return cls.TIPS.get(props.action, cls.__doc__) if props else cls.__doc__

    def execute(self, context):
        scene = context.scene
        selected = list(context.selected_objects)
        if self.action == 'NEW':
            if not selected:
                self.report({'WARNING'}, "Select the objects for the new layer")
                return {'CANCELLED'}
            name = new_layer(scene, selected)
            self.report({'INFO'}, f"{name}: {len(selected)} object(s)")
        elif self.action == 'MOVE':
            move_to_layer(scene, selected, self.layer)
        elif self.action == 'SELECT':
            for obj in context.view_layer.objects:
                obj.select_set(False)
            objs = [o for o in members(scene, self.layer) if o.name in context.view_layer.objects
                    and not o.hide_select and o.visible_get()]
            for obj in objs:
                obj.select_set(True)
            if objs:
                context.view_layer.objects.active = objs[0]
        elif self.action in {'VIEW', 'SELECTABLE', 'RENDER'}:
            toggle(scene, self.layer, {'VIEW': "view", 'SELECTABLE': "select", 'RENDER': "render"}[self.action])
        elif self.action == 'DELETE':
            delete_layer(scene, self.layer)
        return {'FINISHED'}


def draw_selection_filter(layout, context):
    grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for key, label, _d in FILTERS:
        grid.prop_enum(context.window_manager, "mr_softie_select_filter", key, text=label)


def draw_scene_layers(layout, context):
    scene = context.scene
    table = layers(scene)
    names = [DEFAULT] + sorted(n for n in table if n != DEFAULT)
    col = layout.column(align=True)
    for name in names:
        flags = table[name]
        row = col.row(align=True)
        op = row.operator("mr_softie.scene_layer", text=name)
        op.action, op.layer = 'SELECT', name
        for action, flag, on, off in (('VIEW', "view", 'HIDE_OFF', 'HIDE_ON'),
                                      ('SELECTABLE', "select", 'RESTRICT_SELECT_OFF', 'RESTRICT_SELECT_ON'),
                                      ('RENDER', "render", 'RESTRICT_RENDER_OFF', 'RESTRICT_RENDER_ON')):
            op = row.operator("mr_softie.scene_layer", text="", icon=on if flags[flag] else off)
            op.action, op.layer = action, name
        op = row.operator("mr_softie.scene_layer", text="", icon='IMPORT')
        op.action, op.layer = 'MOVE', name
        if name != DEFAULT:
            op = row.operator("mr_softie.scene_layer", text="", icon='X')
            op.action, op.layer = 'DELETE', name
    row = layout.row(align=True)
    op = row.operator("mr_softie.scene_layer", text="New Layer from Selection")
    op.action = 'NEW'


classes = (MS_OT_layer_ctl,)


def register():
    bpy.types.WindowManager.mr_softie_select_filter = EnumProperty(
        name="Selection Filter", items=FILTERS, default='ALL', update=_filter_update,
        description="Which kinds of object can be selected")
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    try:
        apply_filter('ALL')
    except (AttributeError, RuntimeError):
        pass
    del bpy.types.WindowManager.mr_softie_select_filter
