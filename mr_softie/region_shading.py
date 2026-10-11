# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep the viewport shaded around a render region.

Blender only draws the scene inside a viewport's render region; outside it you'd
see an empty background. Here the visible meshes are drawn with simple shading in
the strips around the region, so the region floats over a shaded scene.
"""
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

_shader = {"s": None}
_cache = {}   # object name -> (key, batch)

VERT = """
void main()
{
    vec4 world = model * vec4(pos, 1.0);
    wnor = normalize(mat3(model) * nor);
    gl_Position = viewProj * world;
}
"""

FRAG = """
void main()
{
    vec3 n = normalize(wnor);
    if (!gl_FrontFacing) {
        n = -n;
    }
    float key = max(dot(n, normalize(lightDir)), 0.0);
    float fill = 0.5 + 0.5 * n.z;
    vec3 c = baseColor.rgb * (0.12 + 0.75 * key + 0.10 * fill);
    fragColor = vec4(c, 1.0);
}
"""


def shader():
    if _shader["s"] is None:
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant('MAT4', "viewProj")
        info.push_constant('MAT4', "model")
        info.push_constant('VEC4', "baseColor")
        info.push_constant('VEC3', "lightDir")
        info.vertex_in(0, 'VEC3', "pos")
        info.vertex_in(1, 'VEC3', "nor")
        iface = gpu.types.GPUStageInterfaceInfo("ms_region_shade")
        iface.smooth('VEC3', "wnor")
        info.vertex_out(iface)
        info.fragment_out(0, 'VEC4', "fragColor")
        info.vertex_source(VERT)
        info.fragment_source(FRAG)
        _shader["s"] = gpu.shader.create_from_info(info)
    return _shader["s"]


def object_color(obj):
    """A color for shading: the material's base color (or viewport color), else the object color."""
    mat = obj.active_material
    if mat is not None:
        if mat.use_nodes and mat.node_tree is not None:
            for node in mat.node_tree.nodes:
                sock = node.inputs.get("Base Color") if node.type == 'BSDF_PRINCIPLED' else None
                if sock is not None and not sock.is_linked:
                    return tuple(sock.default_value)
                if sock is not None:
                    return tuple(mat.diffuse_color)
        return tuple(mat.diffuse_color)
    c = obj.color
    if tuple(c[:3]) == (1.0, 1.0, 1.0):
        return (0.6, 0.6, 0.6, 1.0)
    return tuple(c)


def _batch(obj, depsgraph):
    ev = obj.evaluated_get(depsgraph)
    try:
        mesh = ev.to_mesh()
    except RuntimeError:
        return None
    try:
        key = (len(mesh.vertices), len(mesh.polygons),
               round(sum(v.co.x + 2 * v.co.y + 3 * v.co.z for v in mesh.vertices[:256]), 5))
        cached = _cache.get(obj.name)
        if cached and cached[0] == key:
            return cached[1]
        mesh.calc_loop_triangles()
        co = [v.co for v in mesh.vertices]
        pos, nor = [], []
        for tri in mesh.loop_triangles:
            normals = None
            try:
                normals = tri.split_normals
            except AttributeError:
                pass
            for k, vi in enumerate(tri.vertices):
                pos.append(co[vi][:])
                nor.append(normals[k][:] if normals else tri.normal[:])
        if not pos:
            return None
        batch = batch_for_shader(shader(), 'TRIS', {"pos": pos, "nor": nor})
        _cache[obj.name] = (key, batch)
        return batch
    finally:
        ev.to_mesh_clear()


def strips(rect, width, height):
    """The parts of the viewport outside `rect`, as scissor boxes (x, y, w, h)."""
    x0, y0, x1, y1 = (int(round(v)) for v in rect)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, width), min(y1, height)
    boxes = [(0, 0, width, y0), (0, y1, width, height - y1), (0, y0, x0, y1 - y0), (x1, y0, width - x1, y1 - y0)]
    return [b for b in boxes if b[2] > 0 and b[3] > 0]


def draw_outside():
    from .regions import region_rect
    context = bpy.context
    area, region = context.area, context.region
    if area is None or region is None or region.type != 'WINDOW':
        return
    rect = region_rect(context, area, region)
    if rect is None:
        return
    rv3d = context.region_data
    space = area.spaces.active
    depsgraph = context.evaluated_depsgraph_get()
    objs = [o for o in context.view_layer.objects
            if o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'} and o.visible_get(viewport=space)]
    if not objs:
        return
    sh = shader()
    view = rv3d.view_matrix
    light = (view.inverted().to_3x3() @ Vector((-0.45, 0.55, 0.7))).normalized()
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.depth_mask_set(True)
    gpu.state.face_culling_set('NONE')
    sh.bind()
    sh.uniform_float("viewProj", rv3d.perspective_matrix)
    sh.uniform_float("lightDir", light)
    batches = [(o, _batch(o, depsgraph)) for o in objs]
    gpu.state.scissor_test_set(True)
    for x, y, w, h in strips(rect, region.width, region.height):
        gpu.state.scissor_set(x, y, w, h)
        for obj, batch in batches:
            if batch is None:
                continue
            sh.uniform_float("model", obj.matrix_world)
            sh.uniform_float("baseColor", object_color(obj))
            batch.draw(sh)
    gpu.state.scissor_test_set(False)
    gpu.state.depth_mask_set(False)
    gpu.state.depth_test_set('NONE')


@bpy.app.handlers.persistent
def forget(*_args):
    _cache.clear()
