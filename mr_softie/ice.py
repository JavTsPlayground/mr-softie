# SPDX-License-Identifier: GPL-3.0-or-later
"""ICE-style compounds, built as Geometry Nodes groups.

Each compound is a node group generated on demand (so it is fully editable in
the ICE Tree / Geometry Nodes editor) and applied as a modifier:

  Emit from Surface   scatter copies of another object over a surface
  Simulate Particles  points emitted from a surface, falling under gravity
  Jitter              random offset of every point
  Push                move points along their normals (inflate / deflate)
  Grow Strands        hair-like curves growing out of the surface
  Turbulence          animated noise displacement
  Swarm               wandering points that fly toward a goal object
"""
import bpy
from bpy.props import EnumProperty

COMPOUNDS = (
    ('EMIT', "Emit from Surface", "Scatter copies of another selected object over the surface"),
    ('PARTICLES', "Simulate Particles", "Emit points from the surface and let them fall under gravity"),
    ('JITTER', "Jitter", "Randomly offset every point"),
    ('PUSH', "Push", "Move points along their normals"),
    ('STRANDS', "Grow Strands", "Grow hair-like strands out of the surface"),
    ('TURBULENCE', "Turbulence", "Animated noise displacement of every point"),
    ('SWARM', "Swarm", "Points that wander and fly toward a goal object (copies of another object optional)"),
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


def _collide(tree, gin, geometry, dt, x=0, y=-900):
    """Points that reached or crossed the Collider's surface this step are put back on it
    (Size above it) and bounce off it.

    Needs group inputs "Collider" (object), "Size" and "Bounce"; returns the new geometry socket.
    """
    n, links = tree.nodes, tree.links
    info = n.new('GeometryNodeObjectInfo')
    info.transform_space = 'RELATIVE'
    info.location = (x, y)
    prox = n.new('GeometryNodeProximity')
    prox.target_element = 'FACES'
    prox.location = (x + 180, y)
    normal = n.new('GeometryNodeInputNormal')
    normal.location = (x + 180, y - 220)
    sample = n.new('GeometryNodeSampleNearestSurface')
    sample.data_type = 'FLOAT_VECTOR'
    sample.location = (x + 360, y - 200)
    near = n.new('FunctionNodeCompare')
    near.data_type = 'FLOAT'
    near.operation = 'LESS_THAN'
    near.location = (x + 360, y)
    vel = n.new('GeometryNodeInputNamedAttribute')
    vel.data_type = 'FLOAT_VECTOR'
    vel.inputs["Name"].default_value = "velocity"
    vel.location = (x + 360, y - 400)
    dot = n.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.location = (x + 540, y - 300)
    into = n.new('FunctionNodeCompare')
    into.data_type = 'FLOAT'
    into.operation = 'LESS_THAN'
    into.location = (x + 700, y - 300)
    both = n.new('FunctionNodeBooleanMath')
    both.operation = 'AND'
    both.location = (x + 860, y - 100)
    mark = n.new('GeometryNodeStoreNamedAttribute')
    mark.data_type = 'BOOLEAN'
    mark.inputs["Name"].default_value = "ice_hit"
    mark.location = (x + 1020, y + 200)
    hit = n.new('GeometryNodeInputNamedAttribute')
    hit.data_type = 'BOOLEAN'
    hit.inputs["Name"].default_value = "ice_hit"
    hit.location = (x + 1020, y - 300)
    reflect = n.new('ShaderNodeVectorMath')
    reflect.operation = 'REFLECT'
    reflect.location = (x + 1020, y - 500)
    damp = n.new('ShaderNodeVectorMath')
    damp.operation = 'SCALE'
    damp.location = (x + 1180, y - 500)
    vstore = n.new('GeometryNodeStoreNamedAttribute')
    vstore.data_type = 'FLOAT_VECTOR'
    vstore.inputs["Name"].default_value = "velocity"
    vstore.location = (x + 1340, y + 200)
    out_n = n.new('ShaderNodeVectorMath')
    out_n.operation = 'SCALE'
    out_n.location = (x + 1180, y - 150)
    surface = n.new('ShaderNodeVectorMath')
    surface.operation = 'ADD'
    surface.location = (x + 1340, y - 150)
    push = n.new('GeometryNodeSetPosition')
    push.location = (x + 1500, y + 200)

    links.new(gin.outputs["Collider"], info.inputs["Object"])
    links.new(info.outputs["Geometry"], prox.inputs["Geometry"])
    links.new(info.outputs["Geometry"], sample.inputs["Mesh"])
    links.new(normal.outputs["Normal"], sample.inputs["Value"])
    # Crossed: on the surface's back side (or within Size of it) ...
    pos = n.new('GeometryNodeInputPosition')
    pos.location = (x, y - 600)
    rel = n.new('ShaderNodeVectorMath')
    rel.operation = 'SUBTRACT'
    rel.location = (x + 180, y - 600)
    side = n.new('ShaderNodeVectorMath')
    side.operation = 'DOT_PRODUCT'
    side.location = (x + 360, y - 600)
    behind = n.new('FunctionNodeCompare')
    behind.data_type = 'FLOAT'
    behind.operation = 'LESS_THAN'
    behind.location = (x + 540, y - 600)
    # ... and no farther from it than this step could have carried it.
    speed = n.new('ShaderNodeVectorMath')
    speed.operation = 'LENGTH'
    speed.location = (x + 360, y - 800)
    reach = n.new('ShaderNodeMath')
    reach.operation = 'MULTIPLY_ADD'
    reach.location = (x + 540, y - 800)
    reach2 = n.new('ShaderNodeMath')
    reach2.operation = 'MULTIPLY'
    reach2.inputs[1].default_value = 2.0
    reach2.location = (x + 700, y - 800)
    close = n.new('FunctionNodeBooleanMath')
    close.operation = 'AND'
    close.location = (x + 700, y - 600)
    links.new(pos.outputs["Position"], rel.inputs[0])
    links.new(prox.outputs["Position"], rel.inputs[1])
    links.new(rel.outputs["Vector"], side.inputs[0])
    links.new(sample.outputs["Value"], side.inputs[1])
    links.new(side.outputs["Value"], behind.inputs["A"])
    links.new(gin.outputs["Size"], behind.inputs["B"])
    links.new(vel.outputs["Attribute"], speed.inputs[0])
    links.new(speed.outputs["Value"], reach.inputs[0])
    links.new(dt, reach.inputs[1])
    links.new(gin.outputs["Size"], reach.inputs[2])
    links.new(reach.outputs[0], reach2.inputs[0])
    links.new(prox.outputs["Distance"], near.inputs["A"])
    links.new(reach2.outputs[0], near.inputs["B"])
    links.new(behind.outputs["Result"], close.inputs[0])
    links.new(near.outputs["Result"], close.inputs[1])
    links.new(vel.outputs["Attribute"], dot.inputs[0])
    links.new(sample.outputs["Value"], dot.inputs[1])
    links.new(dot.outputs["Value"], into.inputs["A"])
    links.new(close.outputs[0], both.inputs[0])
    links.new(into.outputs["Result"], both.inputs[1])
    links.new(geometry, mark.inputs["Geometry"])
    links.new(both.outputs[0], mark.inputs["Value"])
    links.new(vel.outputs["Attribute"], reflect.inputs[0])
    links.new(sample.outputs["Value"], reflect.inputs[1])
    links.new(reflect.outputs["Vector"], damp.inputs[0])
    links.new(gin.outputs["Bounce"], damp.inputs["Scale"])
    links.new(mark.outputs["Geometry"], vstore.inputs["Geometry"])
    links.new(hit.outputs["Attribute"], vstore.inputs["Selection"])
    links.new(damp.outputs["Vector"], vstore.inputs["Value"])
    links.new(sample.outputs["Value"], out_n.inputs[0])
    links.new(gin.outputs["Size"], out_n.inputs["Scale"])
    links.new(prox.outputs["Position"], surface.inputs[0])
    links.new(out_n.outputs["Vector"], surface.inputs[1])
    links.new(vstore.outputs["Geometry"], push.inputs["Geometry"])
    links.new(hit.outputs["Attribute"], push.inputs["Selection"])
    links.new(surface.outputs["Vector"], push.inputs["Position"])
    return push.outputs["Geometry"]


def _wind_noise(tree, amount_socket, freq_socket, speed_socket, x=0, y=-400):
    """Animated, centered 4D noise vector scaled by amount; returns the vector socket."""
    n, links = tree.nodes, tree.links
    pos = n.new('GeometryNodeInputPosition')
    pos.location = (x, y)
    time = n.new('GeometryNodeInputSceneTime')
    time.location = (x, y - 150)
    speed = n.new('ShaderNodeMath')
    speed.operation = 'MULTIPLY'
    speed.location = (x + 160, y - 150)
    noise = n.new('ShaderNodeTexNoise')
    noise.noise_dimensions = '4D'
    noise.location = (x + 320, y)
    center = n.new('ShaderNodeVectorMath')
    center.operation = 'SUBTRACT'
    center.inputs[1].default_value = (0.5, 0.5, 0.5)
    center.location = (x + 500, y)
    amp = n.new('ShaderNodeVectorMath')
    amp.operation = 'SCALE'
    amp.location = (x + 660, y)
    links.new(pos.outputs["Position"], noise.inputs["Vector"])
    links.new(time.outputs["Seconds"], speed.inputs[0])
    links.new(speed_socket, speed.inputs[1])
    links.new(speed.outputs[0], noise.inputs["W"])
    if freq_socket is not None:
        links.new(freq_socket, noise.inputs["Scale"])
    links.new(noise.outputs["Color"], center.inputs[0])
    links.new(center.outputs["Vector"], amp.inputs[0])
    links.new(amount_socket, amp.inputs["Scale"])
    return amp.outputs["Vector"]


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
    _socket(tree, "Floor", 'INPUT', 'NodeSocketBool', False)
    _socket(tree, "Floor Height", 'INPUT', 'NodeSocketFloat', 0.0)
    _socket(tree, "Bounce", 'INPUT', 'NodeSocketFloat', 0.5, 0.0, 1.0)
    _socket(tree, "Collider", 'INPUT', 'NodeSocketObject')
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

    # Floor: points that went below it bounce back up (velocity z flipped and damped).
    pos = n.new('GeometryNodeInputPosition')
    pos.location = (780, -350)
    sep = n.new('ShaderNodeSeparateXYZ')
    sep.location = (900, -350)
    below = n.new('FunctionNodeCompare')
    below.data_type = 'FLOAT'
    below.operation = 'LESS_THAN'
    below.location = (1020, -350)
    hit = n.new('FunctionNodeBooleanMath')
    hit.operation = 'AND'
    hit.location = (1140, -350)
    vread = n.new('GeometryNodeInputNamedAttribute')
    vread.data_type = 'FLOAT_VECTOR'
    vread.inputs["Name"].default_value = "velocity"
    vread.location = (900, -550)
    damp = n.new('ShaderNodeCombineXYZ')
    damp.inputs["X"].default_value = 1.0
    damp.inputs["Y"].default_value = 1.0
    nb = n.new('ShaderNodeMath')
    nb.operation = 'MULTIPLY'
    nb.inputs[1].default_value = -1.0
    nb.location = (900, -700)
    damp.location = (1020, -700)
    bounce = n.new('ShaderNodeVectorMath')
    bounce.operation = 'MULTIPLY'
    bounce.location = (1140, -550)
    vstore = n.new('GeometryNodeStoreNamedAttribute')
    vstore.data_type = 'FLOAT_VECTOR'
    vstore.inputs["Name"].default_value = "velocity"
    vstore.location = (1260, 150)
    clamp = n.new('ShaderNodeCombineXYZ')
    clamp.location = (1260, -350)
    clamp_pos = n.new('GeometryNodeSetPosition')
    clamp_pos.location = (1440, 150)
    sim_out.location = (1640, 150)
    radius.location = (1820, 150)
    join.location = (2000, 0)
    gout.location = (2180, 0)

    links.new(pos.outputs["Position"], sep.inputs["Vector"])
    links.new(sep.outputs["Z"], below.inputs["A"])
    links.new(gin.outputs["Floor Height"], below.inputs["B"])
    links.new(below.outputs["Result"], hit.inputs[0])
    links.new(gin.outputs["Floor"], hit.inputs[1])
    links.new(gin.outputs["Bounce"], nb.inputs[0])
    links.new(nb.outputs[0], damp.inputs["Z"])
    links.new(vread.outputs["Attribute"], bounce.inputs[0])
    links.new(damp.outputs[0], bounce.inputs[1])
    links.new(setpos.outputs["Geometry"], vstore.inputs["Geometry"])
    links.new(hit.outputs[0], vstore.inputs["Selection"])
    links.new(bounce.outputs["Vector"], vstore.inputs["Value"])
    links.new(sep.outputs["X"], clamp.inputs["X"])
    links.new(sep.outputs["Y"], clamp.inputs["Y"])
    links.new(gin.outputs["Floor Height"], clamp.inputs["Z"])
    links.new(vstore.outputs["Geometry"], clamp_pos.inputs["Geometry"])
    links.new(hit.outputs[0], clamp_pos.inputs["Selection"])
    links.new(clamp.outputs[0], clamp_pos.inputs["Position"])
    collided = _collide(tree, gin, clamp_pos.outputs["Geometry"], sim_in.outputs["Delta Time"],
                        x=1440, y=-900)
    links.new(collided, sim_out.inputs["Geometry"])

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


def _build_strands(name):
    tree, gin, gout = _new_tree(name)
    _socket(tree, "Density", 'INPUT', 'NodeSocketFloat', 200.0, 0.0)
    _socket(tree, "Length", 'INPUT', 'NodeSocketFloat', 0.3, 0.0)
    _socket(tree, "Length Variation", 'INPUT', 'NodeSocketFloat', 0.5, 0.0, 1.0)
    _socket(tree, "Thickness", 'INPUT', 'NodeSocketFloat', 0.005, 0.0)
    _socket(tree, "Seed", 'INPUT', 'NodeSocketInt', 0)
    _socket(tree, "Wind", 'INPUT', 'NodeSocketFloat', 0.0, 0.0)
    _socket(tree, "Wind Speed", 'INPUT', 'NodeSocketFloat', 1.0)
    n, links = tree.nodes, tree.links
    dist = n.new('GeometryNodeDistributePointsOnFaces')
    dist.location = (-400, 150)
    align = n.new('FunctionNodeAlignRotationToVector')
    align.axis = 'Z'
    align.location = (-150, -100)
    line = n.new('GeometryNodeCurvePrimitiveLine')
    line.inputs["End"].default_value = (0.0, 0.0, 1.0)
    line.location = (-150, -300)
    vmin = n.new('ShaderNodeMath')
    vmin.operation = 'SUBTRACT'
    vmin.inputs[0].default_value = 1.0
    vmin.location = (-400, -450)
    lo = n.new('ShaderNodeMath')
    lo.operation = 'MULTIPLY'
    lo.location = (-250, -450)
    rnd = n.new('FunctionNodeRandomValue')
    rnd.data_type = 'FLOAT'
    rnd.location = (-100, -450)
    inst = n.new('GeometryNodeInstanceOnPoints')
    inst.location = (100, 100)
    real = n.new('GeometryNodeRealizeInstances')
    real.location = (300, 100)
    rad = n.new('GeometryNodeSetCurveRadius')
    rad.location = (480, 100)
    join = n.new('GeometryNodeJoinGeometry')
    join.location = (660, 0)
    gout.location = (840, 0)

    links.new(gin.outputs["Geometry"], dist.inputs["Mesh"])
    links.new(gin.outputs["Density"], dist.inputs["Density"])
    links.new(gin.outputs["Seed"], dist.inputs["Seed"])
    links.new(dist.outputs["Normal"], align.inputs["Vector"])
    links.new(gin.outputs["Length Variation"], vmin.inputs[1])
    links.new(vmin.outputs[0], lo.inputs[0])
    links.new(gin.outputs["Length"], lo.inputs[1])
    links.new(lo.outputs[0], _sock(rnd.inputs, "Min"))
    links.new(gin.outputs["Length"], _sock(rnd.inputs, "Max"))
    links.new(gin.outputs["Seed"], rnd.inputs["Seed"])
    links.new(dist.outputs["Points"], inst.inputs["Points"])
    links.new(line.outputs["Curve"], inst.inputs["Instance"])
    links.new(align.outputs["Rotation"], inst.inputs["Rotation"])
    links.new(_sock(rnd.outputs, "Value"), inst.inputs["Scale"])
    links.new(inst.outputs["Instances"], real.inputs["Geometry"])
    # Wind: animated noise that bends the strands more toward the tip.
    gust = _wind_noise(tree, gin.outputs["Wind"], None, gin.outputs["Wind Speed"], x=300, y=-500)
    tip = n.new('GeometryNodeSplineParameter')
    tip.location = (800, -300)
    bend = n.new('ShaderNodeVectorMath')
    bend.operation = 'SCALE'
    bend.location = (980, -400)
    sway = n.new('GeometryNodeSetPosition')
    sway.location = (480, 300)
    links.new(gust, bend.inputs[0])
    links.new(tip.outputs["Factor"], bend.inputs["Scale"])
    links.new(real.outputs["Geometry"], sway.inputs["Geometry"])
    links.new(bend.outputs["Vector"], sway.inputs["Offset"])
    links.new(sway.outputs["Geometry"], rad.inputs["Curve"])
    links.new(gin.outputs["Thickness"], rad.inputs["Radius"])
    links.new(gin.outputs["Geometry"], join.inputs["Geometry"])
    links.new(rad.outputs["Curve"], join.inputs["Geometry"])
    links.new(join.outputs["Geometry"], gout.inputs["Geometry"])
    return tree


def _build_swarm(name):
    tree, gin, gout = _new_tree(name)
    _socket(tree, "Count Density", 'INPUT', 'NodeSocketFloat', 5.0, 0.0)
    _socket(tree, "Goal", 'INPUT', 'NodeSocketObject')
    _socket(tree, "Attraction", 'INPUT', 'NodeSocketFloat', 1.0)
    _socket(tree, "Wander", 'INPUT', 'NodeSocketFloat', 8.0, 0.0)
    _socket(tree, "Max Speed", 'INPUT', 'NodeSocketFloat', 3.0, 0.0)
    _socket(tree, "Instance", 'INPUT', 'NodeSocketObject')
    _socket(tree, "Size", 'INPUT', 'NodeSocketFloat', 0.05, 0.0)
    _socket(tree, "Seed", 'INPUT', 'NodeSocketInt', 0)
    n, links = tree.nodes, tree.links

    dist = n.new('GeometryNodeDistributePointsOnFaces')
    dist.location = (-500, 200)
    sim_in = n.new('GeometryNodeSimulationInput')
    sim_in.location = (-250, 200)
    sim_out = n.new('GeometryNodeSimulationOutput')
    sim_out.location = (1300, 200)
    sim_in.pair_with_output(sim_out)

    # Steering = wander noise + pull toward the goal (the emitter's origin without one).
    one = n.new('ShaderNodeValue')
    one.outputs[0].default_value = 0.7
    one.location = (-250, -650)
    wander = _wind_noise(tree, gin.outputs["Wander"], one.outputs[0], one.outputs[0], x=-250, y=-300)
    goal = n.new('GeometryNodeObjectInfo')
    goal.transform_space = 'RELATIVE'
    goal.location = (-250, -800)
    pos = n.new('GeometryNodeInputPosition')
    pos.location = (-250, -1000)
    to_goal = n.new('ShaderNodeVectorMath')
    to_goal.operation = 'SUBTRACT'
    to_goal.location = (-50, -850)
    pull = n.new('ShaderNodeVectorMath')
    pull.operation = 'SCALE'
    pull.location = (120, -850)
    steer = n.new('ShaderNodeVectorMath')
    steer.operation = 'ADD'
    steer.location = (520, -500)
    accel = n.new('ShaderNodeVectorMath')
    accel.operation = 'SCALE'
    accel.location = (680, -500)
    vread = n.new('GeometryNodeInputNamedAttribute')
    vread.data_type = 'FLOAT_VECTOR'
    vread.inputs["Name"].default_value = "velocity"
    vread.location = (680, -300)
    newv = n.new('ShaderNodeVectorMath')
    newv.operation = 'ADD'
    newv.location = (840, -400)
    # Speed limit: v * min(|v|, max) / |v|
    length = n.new('ShaderNodeVectorMath')
    length.operation = 'LENGTH'
    length.location = (1000, -550)
    capped = n.new('ShaderNodeMath')
    capped.operation = 'MINIMUM'
    capped.location = (1160, -550)
    unit = n.new('ShaderNodeVectorMath')
    unit.operation = 'NORMALIZE'
    unit.location = (1000, -400)
    limited = n.new('ShaderNodeVectorMath')
    limited.operation = 'SCALE'
    limited.location = (1320, -450)
    store = n.new('GeometryNodeStoreNamedAttribute')
    store.data_type = 'FLOAT_VECTOR'
    store.inputs["Name"].default_value = "velocity"
    store.location = (900, 200)
    step = n.new('ShaderNodeVectorMath')
    step.operation = 'SCALE'
    step.location = (1000, 0)
    vnow = n.new('GeometryNodeInputNamedAttribute')
    vnow.data_type = 'FLOAT_VECTOR'
    vnow.inputs["Name"].default_value = "velocity"
    vnow.location = (840, 0)
    move = n.new('GeometryNodeSetPosition')
    move.location = (1100, 200)

    links.new(gin.outputs["Geometry"], dist.inputs["Mesh"])
    links.new(gin.outputs["Count Density"], dist.inputs["Density"])
    links.new(gin.outputs["Seed"], dist.inputs["Seed"])
    links.new(dist.outputs["Points"], sim_in.inputs["Geometry"])
    links.new(gin.outputs["Goal"], goal.inputs["Object"])
    links.new(goal.outputs["Location"], to_goal.inputs[0])
    links.new(pos.outputs["Position"], to_goal.inputs[1])
    links.new(to_goal.outputs["Vector"], pull.inputs[0])
    links.new(gin.outputs["Attraction"], pull.inputs["Scale"])
    links.new(wander, steer.inputs[0])
    links.new(pull.outputs["Vector"], steer.inputs[1])
    links.new(steer.outputs["Vector"], accel.inputs[0])
    links.new(sim_in.outputs["Delta Time"], accel.inputs["Scale"])
    links.new(vread.outputs["Attribute"], newv.inputs[0])
    links.new(accel.outputs["Vector"], newv.inputs[1])
    links.new(newv.outputs["Vector"], length.inputs[0])
    links.new(newv.outputs["Vector"], unit.inputs[0])
    links.new(length.outputs["Value"], capped.inputs[0])
    links.new(gin.outputs["Max Speed"], capped.inputs[1])
    links.new(unit.outputs["Vector"], limited.inputs[0])
    links.new(capped.outputs[0], limited.inputs["Scale"])
    links.new(sim_in.outputs["Geometry"], store.inputs["Geometry"])
    links.new(limited.outputs["Vector"], store.inputs["Value"])
    links.new(vnow.outputs["Attribute"], step.inputs[0])
    links.new(sim_in.outputs["Delta Time"], step.inputs["Scale"])
    links.new(store.outputs["Geometry"], move.inputs["Geometry"])
    links.new(step.outputs["Vector"], move.inputs["Offset"])
    links.new(move.outputs["Geometry"], sim_out.inputs["Geometry"])

    # Output: points, plus copies of Instance facing the way they fly.
    radius = n.new('GeometryNodeSetPointRadius')
    radius.location = (1500, 300)
    face = n.new('FunctionNodeAlignRotationToVector')
    face.axis = 'Y'
    face.location = (1500, -100)
    fly = n.new('GeometryNodeInputNamedAttribute')
    fly.data_type = 'FLOAT_VECTOR'
    fly.inputs["Name"].default_value = "velocity"
    fly.location = (1340, -150)
    info = n.new('GeometryNodeObjectInfo')
    info.transform_space = 'RELATIVE'
    info.location = (1500, -300)
    inst = n.new('GeometryNodeInstanceOnPoints')
    inst.location = (1700, 0)
    join = n.new('GeometryNodeJoinGeometry')
    join.location = (1900, 100)
    gout.location = (2100, 100)
    links.new(sim_out.outputs["Geometry"], radius.inputs["Points"])
    links.new(gin.outputs["Size"], radius.inputs["Radius"])
    links.new(fly.outputs["Attribute"], face.inputs["Vector"])
    links.new(gin.outputs["Instance"], info.inputs["Object"])
    links.new(sim_out.outputs["Geometry"], inst.inputs["Points"])
    links.new(info.outputs["Geometry"], inst.inputs["Instance"])
    links.new(face.outputs["Rotation"], inst.inputs["Rotation"])
    links.new(gin.outputs["Geometry"], join.inputs["Geometry"])
    links.new(radius.outputs["Points"], join.inputs["Geometry"])
    links.new(inst.outputs["Instances"], join.inputs["Geometry"])
    links.new(join.outputs["Geometry"], gout.inputs["Geometry"])
    return tree


def _build_turbulence(name):
    tree, gin, gout = _new_tree(name)
    _socket(tree, "Amplitude", 'INPUT', 'NodeSocketFloat', 0.2)
    _socket(tree, "Frequency", 'INPUT', 'NodeSocketFloat', 1.5, 0.0)
    _socket(tree, "Speed", 'INPUT', 'NodeSocketFloat', 0.5)
    n, links = tree.nodes, tree.links
    pos = n.new('GeometryNodeInputPosition')
    pos.location = (-500, -150)
    time = n.new('GeometryNodeInputSceneTime')
    time.location = (-500, -300)
    speed = n.new('ShaderNodeMath')
    speed.operation = 'MULTIPLY'
    speed.location = (-320, -300)
    noise = n.new('ShaderNodeTexNoise')
    noise.noise_dimensions = '4D'
    noise.location = (-150, -150)
    center = n.new('ShaderNodeVectorMath')
    center.operation = 'SUBTRACT'
    center.inputs[1].default_value = (0.5, 0.5, 0.5)
    center.location = (50, -150)
    amp = n.new('ShaderNodeVectorMath')
    amp.operation = 'SCALE'
    amp.location = (220, -150)
    setpos = n.new('GeometryNodeSetPosition')
    setpos.location = (400, 0)

    links.new(pos.outputs["Position"], noise.inputs["Vector"])
    links.new(time.outputs["Seconds"], speed.inputs[0])
    links.new(gin.outputs["Speed"], speed.inputs[1])
    links.new(speed.outputs[0], noise.inputs["W"])
    links.new(gin.outputs["Frequency"], noise.inputs["Scale"])
    links.new(noise.outputs["Color"], center.inputs[0])
    links.new(center.outputs["Vector"], amp.inputs[0])
    links.new(gin.outputs["Amplitude"], amp.inputs["Scale"])
    links.new(gin.outputs["Geometry"], setpos.inputs["Geometry"])
    links.new(amp.outputs["Vector"], setpos.inputs["Offset"])
    links.new(setpos.outputs["Geometry"], gout.inputs["Geometry"])
    return tree


BUILDERS = {'EMIT': _build_emit, 'PARTICLES': _build_particles,
            'JITTER': _build_jitter, 'PUSH': _build_push,
            'STRANDS': _build_strands, 'TURBULENCE': _build_turbulence,
            'SWARM': _build_swarm}


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
        others = [o for o in context.selected_objects if o != active]
        if self.compound in {'EMIT', 'SWARM', 'PARTICLES'}:
            # The active object is the emitter; another selected object plays a role:
            # Emit = what gets scattered, Swarm = the goal, Particles = the collider.
            if active is None or active.type != 'MESH':
                self.report({'WARNING'}, "Make the emitting mesh the active object (select it last)")
                return {'CANCELLED'}
            if self.compound == 'EMIT' and not others:
                self.report({'WARNING'}, "Select the object to scatter, then the surface (active) last")
                return {'CANCELLED'}
            mod = apply_compound(active, self.compound)
            if others:
                role = {'EMIT': "Instance", 'SWARM': "Goal", 'PARTICLES': "Collider"}[self.compound]
                set_input(mod, role, others[0])
                if self.compound == 'EMIT':
                    others[0].hide_render = True
            if self.compound in {'PARTICLES', 'SWARM'}:
                context.scene.frame_set(context.scene.frame_start)
            self.report({'INFO'}, f"{GROUP_NAMES[self.compound]} applied to {active.name}")
            return {'FINISHED'}
        targets = [o for o in context.selected_objects if o.type == 'MESH']
        if not targets:
            self.report({'WARNING'}, "Select a polygon mesh")
            return {'CANCELLED'}
        for obj in targets:
            apply_compound(obj, self.compound)
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
