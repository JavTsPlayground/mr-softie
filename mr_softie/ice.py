# SPDX-License-Identifier: GPL-3.0-or-later
"""ICE-style compounds, built as Geometry Nodes groups.

Each compound is a node group generated on demand (so it is fully editable in
the ICE Tree / Geometry Nodes editor) and applied as a modifier:

  Emit from Surface   scatter copies of another object over a surface
  Simulate Particles  points emitted from a surface, falling under gravity
  Jitter              random offset of every point
  Push                move points along their normals (inflate / deflate)
"""
import bpy
from bpy.props import EnumProperty

COMPOUNDS = (
    ('EMIT', "Emit from Surface", "Scatter copies of another selected object over the surface"),
    ('PARTICLES', "Simulate Particles", "Emit points from the surface and let them fall under gravity"),
    ('JITTER', "Jitter", "Randomly offset every point"),
    ('PUSH', "Push", "Move points along their normals"),
)
GROUP_NAMES = {key: f"ICE {label}" for key, label, _ in COMPOUNDS}


def _socket(tree, name, in_out, socket_type, default=None, min_value=None, max_value=None):
    sock = tree.interface.new_socket(name, in_out=in_out, socket_type=socket_type)
    if default is not None and hasattr(sock, "default_value"):
        sock.default_value = default
    if min_value is not None and hasattr(sock, "min_value"):
        sock.min_value = min_value
    if max_value is not None and hasattr(sock, "max_value"):
        sock.max_value = max_value
    return sock


def _sock(sockets, name):
    """The enabled socket called `name` (Random Value etc. keep hidden duplicates)."""
    for sock in sockets:
        if sock.name == name and sock.enabled:
            return sock
    return sockets[name]


def _new_tree(name):
    tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    _socket(tree, "Geometry", 'INPUT', 'NodeSocketGeometry')
    _socket(tree, "Geometry", 'OUTPUT', 'NodeSocketGeometry')
    nodes = tree.nodes
    gin = nodes.new('NodeGroupInput')
    gin.location = (-600, 0)
    gout = nodes.new('NodeGroupOutput')
    gout.location = (600, 0)
    return tree, gin, gout


def _build_emit(name):
    tree, gin, gout = _new_tree(name)
    _socket(tree, "Instance", 'INPUT', 'NodeSocketObject')
    _socket(tree, "Density", 'INPUT', 'NodeSocketFloat', 10.0, 0.0)
    _socket(tree, "Seed", 'INPUT', 'NodeSocketInt', 0)
    _socket(tree, "Scale Min", 'INPUT', 'NodeSocketFloat', 0.2, 0.0)
    _socket(tree, "Scale Max", 'INPUT', 'NodeSocketFloat', 0.4, 0.0)
    n, links = tree.nodes, tree.links

    dist = n.new('GeometryNodeDistributePointsOnFaces')
    dist.location = (-350, 100)
    info = n.new('GeometryNodeObjectInfo')
    info.location = (-350, -150)
    info.transform_space = 'RELATIVE'
    rot = n.new('FunctionNodeRandomValue')
    rot.data_type = 'FLOAT_VECTOR'
    rot.location = (-120, -250)
    _sock(rot.inputs, "Max").default_value = (6.2832, 6.2832, 6.2832)
    scale = n.new('FunctionNodeRandomValue')
    scale.data_type = 'FLOAT'
    scale.location = (-120, -450)
    inst = n.new('GeometryNodeInstanceOnPoints')
    inst.location = (120, 50)
    join = n.new('GeometryNodeJoinGeometry')
    join.location = (380, 0)

    links.new(gin.outputs["Geometry"], dist.inputs["Mesh"])
    links.new(gin.outputs["Density"], dist.inputs["Density"])
    links.new(gin.outputs["Seed"], dist.inputs["Seed"])
    links.new(gin.outputs["Instance"], info.inputs["Object"])
    links.new(gin.outputs["Seed"], rot.inputs["Seed"])
    links.new(gin.outputs["Seed"], scale.inputs["Seed"])
    links.new(gin.outputs["Scale Min"], _sock(scale.inputs, "Min"))
    links.new(gin.outputs["Scale Max"], _sock(scale.inputs, "Max"))
    links.new(dist.outputs["Points"], inst.inputs["Points"])
    links.new(info.outputs["Geometry"], inst.inputs["Instance"])
    links.new(_sock(rot.outputs, "Value"), inst.inputs["Rotation"])
    links.new(_sock(scale.outputs, "Value"), inst.inputs["Scale"])
    links.new(gin.outputs["Geometry"], join.inputs["Geometry"])
    links.new(inst.outputs["Instances"], join.inputs["Geometry"])
    links.new(join.outputs["Geometry"], gout.inputs["Geometry"])
    return tree


def _build_particles(name):
    tree, gin, gout = _new_tree(name)
    _socket(tree, "Density", 'INPUT', 'NodeSocketFloat', 20.0, 0.0)
    _socket(tree, "Speed", 'INPUT', 'NodeSocketFloat', 2.0)
    _socket(tree, "Gravity", 'INPUT', 'NodeSocketFloat', 9.8)
    _socket(tree, "Size", 'INPUT', 'NodeSocketFloat', 0.05, 0.0)
    _socket(tree, "Seed", 'INPUT', 'NodeSocketInt', 0)
    n, links = tree.nodes, tree.links

    dist = n.new('GeometryNodeDistributePointsOnFaces')
    dist.location = (-400, 150)
    vel0 = n.new('ShaderNodeVectorMath')
    vel0.operation = 'SCALE'
    vel0.location = (-200, 0)
    store0 = n.new('GeometryNodeStoreNamedAttribute')
    store0.data_type = 'FLOAT_VECTOR'
    store0.inputs["Name"].default_value = "velocity"
    store0.location = (-20, 150)

    sim_in = n.new('GeometryNodeSimulationInput')
    sim_in.location = (180, 150)
    sim_out = n.new('GeometryNodeSimulationOutput')
    sim_out.location = (1000, 150)
    sim_in.pair_with_output(sim_out)

    read = n.new('GeometryNodeInputNamedAttribute')
    read.data_type = 'FLOAT_VECTOR'
    read.inputs["Name"].default_value = "velocity"
    read.location = (180, -150)
    grav = n.new('ShaderNodeCombineXYZ')
    grav.location = (180, -300)
    neg = n.new('ShaderNodeMath')
    neg.operation = 'MULTIPLY'
    neg.inputs[1].default_value = -1.0
    neg.location = (0, -300)
    gdt = n.new('ShaderNodeVectorMath')
    gdt.operation = 'SCALE'
    gdt.location = (380, -300)
    newvel = n.new('ShaderNodeVectorMath')
    newvel.operation = 'ADD'
    newvel.location = (560, -150)
    store = n.new('GeometryNodeStoreNamedAttribute')
    store.data_type = 'FLOAT_VECTOR'
    store.inputs["Name"].default_value = "velocity"
    store.location = (560, 150)
    step = n.new('ShaderNodeVectorMath')
    step.operation = 'SCALE'
    step.location = (740, -150)
    setpos = n.new('GeometryNodeSetPosition')
    setpos.location = (780, 150)

    radius = n.new('GeometryNodeSetPointRadius')
    radius.location = (1180, 150)
    join = n.new('GeometryNodeJoinGeometry')
    join.location = (1380, 0)
    gout.location = (1580, 0)

    # Emit once: points with an initial velocity along the surface normal.
    links.new(gin.outputs["Geometry"], dist.inputs["Mesh"])
    links.new(gin.outputs["Density"], dist.inputs["Density"])
    links.new(gin.outputs["Seed"], dist.inputs["Seed"])
    links.new(dist.outputs["Normal"], vel0.inputs[0])
    links.new(gin.outputs["Speed"], vel0.inputs["Scale"])
    links.new(dist.outputs["Points"], store0.inputs["Geometry"])
    links.new(vel0.outputs["Vector"], store0.inputs["Value"])
    links.new(store0.outputs["Geometry"], sim_in.inputs["Geometry"])

    # Each frame: velocity += gravity * dt, position += velocity * dt.
    links.new(gin.outputs["Gravity"], neg.inputs[0])
    links.new(neg.outputs[0], grav.inputs["Z"])
    links.new(grav.outputs[0], gdt.inputs[0])
    links.new(sim_in.outputs["Delta Time"], gdt.inputs["Scale"])
    links.new(read.outputs["Attribute"], newvel.inputs[0])
    links.new(gdt.outputs["Vector"], newvel.inputs[1])
    links.new(sim_in.outputs["Geometry"], store.inputs["Geometry"])
    links.new(newvel.outputs["Vector"], store.inputs["Value"])
    links.new(newvel.outputs["Vector"], step.inputs[0])
    links.new(sim_in.outputs["Delta Time"], step.inputs["Scale"])
    links.new(store.outputs["Geometry"], setpos.inputs["Geometry"])
    links.new(step.outputs["Vector"], setpos.inputs["Offset"])
    links.new(setpos.outputs["Geometry"], sim_out.inputs["Geometry"])

    links.new(sim_out.outputs["Geometry"], radius.inputs["Points"])
    links.new(gin.outputs["Size"], radius.inputs["Radius"])
    links.new(gin.outputs["Geometry"], join.inputs["Geometry"])
    links.new(radius.outputs["Points"], join.inputs["Geometry"])
    links.new(join.outputs["Geometry"], gout.inputs["Geometry"])
    return tree


def _build_jitter(name):
    tree, gin, gout = _new_tree(name)
    _socket(tree, "Amplitude", 'INPUT', 'NodeSocketFloat', 0.05, 0.0)
    _socket(tree, "Seed", 'INPUT', 'NodeSocketInt', 0)
    n, links = tree.nodes, tree.links
    neg = n.new('ShaderNodeMath')
    neg.operation = 'MULTIPLY'
    neg.inputs[1].default_value = -1.0
    neg.location = (-350, -200)
    lo = n.new('ShaderNodeCombineXYZ')
    lo.location = (-150, -250)
    hi = n.new('ShaderNodeCombineXYZ')
    hi.location = (-150, -100)
    rnd = n.new('FunctionNodeRandomValue')
    rnd.data_type = 'FLOAT_VECTOR'
    rnd.location = (50, -150)
    setpos = n.new('GeometryNodeSetPosition')
    setpos.location = (300, 0)
    links.new(gin.outputs["Amplitude"], neg.inputs[0])
    for axis in "XYZ":
        links.new(neg.outputs[0], lo.inputs[axis])
        links.new(gin.outputs["Amplitude"], hi.inputs[axis])
    links.new(lo.outputs[0], _sock(rnd.inputs, "Min"))
    links.new(hi.outputs[0], _sock(rnd.inputs, "Max"))
    links.new(gin.outputs["Seed"], rnd.inputs["Seed"])
    links.new(gin.outputs["Geometry"], setpos.inputs["Geometry"])
    links.new(_sock(rnd.outputs, "Value"), setpos.inputs["Offset"])
    links.new(setpos.outputs["Geometry"], gout.inputs["Geometry"])
    return tree


def _build_push(name):
    tree, gin, gout = _new_tree(name)
    _socket(tree, "Amount", 'INPUT', 'NodeSocketFloat', 0.1)
    n, links = tree.nodes, tree.links
    normal = n.new('GeometryNodeInputNormal')
    normal.location = (-300, -150)
    scale = n.new('ShaderNodeVectorMath')
    scale.operation = 'SCALE'
    scale.location = (-100, -150)
    setpos = n.new('GeometryNodeSetPosition')
    setpos.location = (200, 0)
    links.new(normal.outputs["Normal"], scale.inputs[0])
    links.new(gin.outputs["Amount"], scale.inputs["Scale"])
    links.new(gin.outputs["Geometry"], setpos.inputs["Geometry"])
    links.new(scale.outputs["Vector"], setpos.inputs["Offset"])
    links.new(setpos.outputs["Geometry"], gout.inputs["Geometry"])
    return tree


BUILDERS = {'EMIT': _build_emit, 'PARTICLES': _build_particles,
            'JITTER': _build_jitter, 'PUSH': _build_push}


def get_compound(key):
    """The node group for a compound, built the first time it is needed."""
    name = GROUP_NAMES[key]
    tree = bpy.data.node_groups.get(name)
    if tree is None or tree.bl_idname != 'GeometryNodeTree':
        tree = BUILDERS[key](name)
    return tree


def _input_id(tree, name):
    for item in tree.interface.items_tree:
        if getattr(item, "in_out", None) == 'INPUT' and item.name == name:
            return item.identifier
    return None


def set_input(mod, name, value):
    """Set a Geometry Nodes modifier input by its interface name (5.x and 4.x APIs)."""
    ident = _input_id(mod.node_group, name)
    if ident is None:
        return False
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        getattr(props.inputs, ident).value = value
    else:
        mod[ident] = value
    return True


def get_input(mod, name):
    ident = _input_id(mod.node_group, name)
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        return getattr(props.inputs, ident).value
    return mod[ident]


def apply_compound(obj, key, instance=None):
    tree = get_compound(key)
    mod = obj.modifiers.new(GROUP_NAMES[key], 'NODES')
    mod.node_group = tree
    if instance is not None:
        set_input(mod, "Instance", instance)
    return mod


class MS_OT_ice_compound(bpy.types.Operator):
    """Apply an ICE compound to the selected objects (editable in the ICE Tree)"""
    bl_idname = "mr_softie.ice_compound"
    bl_label = "ICE Compound"
    bl_options = {'REGISTER', 'UNDO'}

    compound: EnumProperty(items=COMPOUNDS)

    def execute(self, context):
        active = context.active_object
        targets = [o for o in context.selected_objects if o.type == 'MESH']
        instance = None
        if self.compound == 'EMIT':
            # Emitter = active object; the other selected object is what gets scattered.
            others = [o for o in context.selected_objects if o != active]
            if active is None or active.type != 'MESH' or not others:
                self.report({'WARNING'}, "Select the object to scatter, then the surface (active) last")
                return {'CANCELLED'}
            targets, instance = [active], others[0]
            instance.hide_render = True
        if not targets:
            self.report({'WARNING'}, "Select a polygon mesh")
            return {'CANCELLED'}
        for obj in targets:
            apply_compound(obj, self.compound, instance)
        if self.compound == 'PARTICLES':
            context.scene.frame_set(context.scene.frame_start)
        self.report({'INFO'}, f"{GROUP_NAMES[self.compound]} applied to {len(targets)} object(s)")
        return {'FINISHED'}


class MS_OT_ice_tree(bpy.types.Operator):
    """Open the ICE Tree (Geometry Nodes) for the active object in its own window"""
    bl_idname = "mr_softie.ice_tree"
    bl_label = "ICE Tree"

    def execute(self, context):
        obj = context.active_object
        if obj is not None and obj.type == 'MESH' and not any(m.type == 'NODES' for m in obj.modifiers):
            mod = obj.modifiers.new("ICE Tree", 'NODES')
            tree = bpy.data.node_groups.new("ICE Tree", 'GeometryNodeTree')
            _socket(tree, "Geometry", 'INPUT', 'NodeSocketGeometry')
            _socket(tree, "Geometry", 'OUTPUT', 'NodeSocketGeometry')
            gin = tree.nodes.new('NodeGroupInput')
            gin.location = (-300, 0)
            gout = tree.nodes.new('NodeGroupOutput')
            gout.location = (300, 0)
            tree.links.new(gin.outputs[0], gout.inputs[0])
            mod.node_group = tree
        bpy.ops.mr_softie.open_editor(ui_type='GeometryNodeTree')
        return {'FINISHED'}


classes = (MS_OT_ice_compound, MS_OT_ice_tree)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
