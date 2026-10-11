# SPDX-License-Identifier: GPL-3.0-or-later
"""Classic polygon-mesh tools.

  Weld Points   drag a point onto another one: they merge at the target. Stays
                active for the next weld until you right-click or press Esc.
  Split Edge    click on an edge to add a point there. Stays active the same way.
  Weld Edges    drag an edge onto another one: their ends merge.
  Bridge        click two polygons: they're replaced by a tube joining them.

Both switch the mesh into point mode, find points and edges by where they are on
screen (nearest within a few pixels), and draw a rubber band while you drag.
"""
import bmesh
import bpy
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

PICK_RADIUS = 18   # pixels


# --------------------------------------------------------------------------
# Mesh helpers (no UI, tested headless)
# --------------------------------------------------------------------------

def weld(bm, source, target):
    """Merge `source` into `target`; the result sits where `target` was."""
    if source is target:
        return False
    co = target.co.copy()
    bmesh.ops.pointmerge(bm, verts=[source, target], merge_co=co)
    return True


def split_edge(bm, edge, fac):
    """Insert a point on `edge` at `fac` (0 = first vertex, 1 = second). Returns the new vertex."""
    fac = min(max(fac, 0.0), 1.0)
    _new_edge, vert = bmesh.utils.edge_split(edge, edge.verts[0], fac)
    return vert


def weld_edges(bm, source, target):
    """Merge edge `source` onto edge `target`: each end goes to the nearer end of the target."""
    if source is target:
        return False
    a0, a1 = source.verts
    b0, b1 = target.verts
    straight = (a0.co - b0.co).length + (a1.co - b1.co).length
    crossed = (a0.co - b1.co).length + (a1.co - b0.co).length
    pairs = [(a0, b0), (a1, b1)] if straight <= crossed else [(a0, b1), (a1, b0)]
    merged = False
    for src, dst in pairs:
        if src is not dst and src.is_valid and dst.is_valid:
            bmesh.ops.pointmerge(bm, verts=[src, dst], merge_co=dst.co.copy())
            merged = True
    return merged


def bridge_faces(bm, first, second):
    """Remove two polygons and join their borders with a tube. Returns the new faces."""
    if first is second:
        return []
    loops = list(first.edges) + list(second.edges)
    bmesh.ops.delete(bm, geom=[first, second], context='FACES_ONLY')
    result = bmesh.ops.bridge_loops(bm, edges=loops)
    return result.get("faces", [])


def point_in_polygon(p, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > p.y) != (yj > p.y) and p.x < (xj - xi) * (p.y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def closest_on_segment(p, a, b):
    """(factor along a->b, distance) of the 2D point nearest `p`."""
    ab = b - a
    length2 = ab.length_squared
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, (p - a).dot(ab) / length2))
    return t, (a + ab * t - p).length


# --------------------------------------------------------------------------
# Screen-space picking
# --------------------------------------------------------------------------

def _to_screen(region, rv3d, matrix, co):
    return view3d_utils.location_3d_to_region_2d(region, rv3d, matrix @ co)


def view_under_mouse(context, event):
    """(region, region_3d, mouse in region coords) of the 3D view under the mouse, any viewport."""
    x, y = event.mouse_x, event.mouse_y
    for area in context.window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for region in area.regions:
            if region.type == 'WINDOW' and region.x <= x < region.x + region.width \
                    and region.y <= y < region.y + region.height:
                space = area.spaces.active
                rv3d = space.region_3d
                return region, rv3d, Vector((x - region.x, y - region.y))
    return None, None, None


def pick_vertex(view, obj, bm, mouse, exclude=None):
    region, rv3d = view
    matrix = obj.matrix_world
    best, best_d = None, PICK_RADIUS
    for v in bm.verts:
        if v.hide or v is exclude:
            continue
        p = _to_screen(region, rv3d, matrix, v.co)
        if p is None:
            continue
        d = (p - mouse).length
        if d < best_d:
            best, best_d = v, d
    return best


def pick_edge(view, obj, bm, mouse):
    region, rv3d = view
    matrix = obj.matrix_world
    best, best_d, best_t = None, PICK_RADIUS, 0.5
    for e in bm.edges:
        if e.hide:
            continue
        a = _to_screen(region, rv3d, matrix, e.verts[0].co)
        b = _to_screen(region, rv3d, matrix, e.verts[1].co)
        if a is None or b is None:
            continue
        t, d = closest_on_segment(mouse, a, b)
        if d < best_d:
            best, best_d, best_t = e, d, t
    return best, best_t


def _redraw(context):
    for area in context.window.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def pick_face(view, obj, bm, mouse):
    """The polygon under the mouse that is nearest the viewer."""
    region, rv3d = view
    matrix = obj.matrix_world
    eye = rv3d.view_matrix.inverted().translation
    best, best_depth = None, float("inf")
    for f in bm.faces:
        if f.hide:
            continue
        pts = [_to_screen(region, rv3d, matrix, v.co) for v in f.verts]
        if any(q is None for q in pts) or not point_in_polygon(mouse, pts):
            continue
        if rv3d.is_perspective:
            depth = (matrix @ f.calc_center_median() - eye).length
        else:
            depth = -(rv3d.view_rotation.inverted() @ (matrix @ f.calc_center_median())).z
        if depth < best_depth:
            best, best_depth = f, depth
    return best


# --------------------------------------------------------------------------
# Modal tools
# --------------------------------------------------------------------------

class _MeshTool:
    bl_options = {'REGISTER', 'UNDO'}
    hint = ""

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and context.window is not None

    def _start(self, context):
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        context.tool_settings.mesh_select_mode = (True, False, False)
        self.bm = bmesh.from_edit_mesh(context.edit_object.data)
        self.line = None
        self.region = None
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.workspace.status_text_set(self.hint)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.workspace.status_text_set(None)
        _redraw(context)
        return {'FINISHED'}

    def _commit(self, context):
        bmesh.update_edit_mesh(context.edit_object.data)

    def _draw(self):
        if not self.line or bpy.context.region != getattr(self, "region", None):
            return
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.line_width_set(2.0)
        batch = batch_for_shader(shader, 'LINES', {"pos": self.line})
        shader.uniform_float("color", (1.0, 0.85, 0.2, 1.0))
        shader.bind()
        batch.draw(shader)
        gpu.state.line_width_set(1.0)


class MS_OT_weld_points(_MeshTool, bpy.types.Operator):
    """Weld Points: drag a point onto another to merge them. Right-click or Esc to stop"""
    bl_idname = "mr_softie.weld_points"
    bl_label = "Weld Points"
    hint = "Weld Points:  drag a point onto another one  |  Right-click / Esc: done"

    def invoke(self, context, event):
        self.source = None
        return self._start(context)

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._finish(context)
        obj = context.edit_object
        if obj is None:
            return self._finish(context)
        region, rv3d, mouse = view_under_mouse(context, event)
        if region is None:
            return {'PASS_THROUGH'}
        view = (region, rv3d)
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.source = pick_vertex(view, obj, self.bm, mouse)
            self.region = region
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and self.source is not None:
            if region == self.region:
                start = _to_screen(region, rv3d, obj.matrix_world, self.source.co)
                self.line = [start, mouse] if start is not None else None
                _redraw(context)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.source is not None:
            target = pick_vertex(view, obj, self.bm, mouse, exclude=self.source)
            if target is not None and self.source.is_valid:
                weld(self.bm, self.source, target)
                self._commit(context)
            self.source, self.line = None, None
            _redraw(context)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class MS_OT_split_edge(_MeshTool, bpy.types.Operator):
    """Split Edge: click on an edge to add a point there. Right-click or Esc to stop"""
    bl_idname = "mr_softie.split_edge"
    bl_label = "Split Edge"
    hint = "Split Edge:  click on an edge to add a point  |  Right-click / Esc: done"

    def invoke(self, context, event):
        return self._start(context)

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._finish(context)
        obj = context.edit_object
        if obj is None:
            return self._finish(context)
        region, rv3d, mouse = view_under_mouse(context, event)
        if region is None:
            return {'PASS_THROUGH'}
        view = (region, rv3d)
        if event.type == 'MOUSEMOVE':
            # Preview: highlight the edge under the mouse.
            edge, _t = pick_edge(view, obj, self.bm, mouse)
            self.region, self.line = region, None
            if edge is not None:
                a = _to_screen(region, rv3d, obj.matrix_world, edge.verts[0].co)
                b = _to_screen(region, rv3d, obj.matrix_world, edge.verts[1].co)
                if a is not None and b is not None:
                    self.line = [a, b]
            _redraw(context)
            return {'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            edge, t = pick_edge(view, obj, self.bm, mouse)
            if edge is not None:
                vert = split_edge(self.bm, edge, t)
                for v in self.bm.verts:
                    v.select = False
                vert.select = True
                self._commit(context)
                self.line = None
                _redraw(context)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class MS_OT_weld_edges(_MeshTool, bpy.types.Operator):
    """Weld Edges: drag an edge onto another to merge them. Right-click or Esc to stop"""
    bl_idname = "mr_softie.weld_edges"
    bl_label = "Weld Edges"
    hint = "Weld Edges:  drag an edge onto another one  |  Right-click / Esc: done"

    def invoke(self, context, event):
        self.source = None
        result = self._start(context)
        context.tool_settings.mesh_select_mode = (False, True, False)
        return result

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._finish(context)
        obj = context.edit_object
        if obj is None:
            return self._finish(context)
        region, rv3d, mouse = view_under_mouse(context, event)
        if region is None:
            return {'PASS_THROUGH'}
        view = (region, rv3d)
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.source, _t = pick_edge(view, obj, self.bm, mouse)
            self.region = region
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and self.source is not None and self.source.is_valid:
            if region == self.region:
                a = _to_screen(region, rv3d, obj.matrix_world, self.source.verts[0].co)
                b = _to_screen(region, rv3d, obj.matrix_world, self.source.verts[1].co)
                if a is not None and b is not None:
                    mid = (a + b) / 2
                    self.line = [a, b, mid, mouse]
                _redraw(context)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.source is not None:
            target, _t = pick_edge(view, obj, self.bm, mouse)
            if target is not None and target is not self.source and self.source.is_valid:
                weld_edges(self.bm, self.source, target)
                self._commit(context)
            self.source, self.line = None, None
            _redraw(context)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class MS_OT_bridge_polygons(_MeshTool, bpy.types.Operator):
    """Bridge Polygons: click two polygons to join them with a tube. Right-click or Esc to stop"""
    bl_idname = "mr_softie.bridge_polygons"
    bl_label = "Bridge Polygons"
    hint = "Bridge Polygons:  click a polygon, then another one  |  Right-click / Esc: done"

    def invoke(self, context, event):
        self.first = None
        result = self._start(context)
        context.tool_settings.mesh_select_mode = (False, False, True)
        return result

    def _outline(self, view, obj, face):
        region, rv3d = view
        pts = [_to_screen(region, rv3d, obj.matrix_world, v.co) for v in face.verts]
        if any(q is None for q in pts):
            return []
        lines = []
        for i, q in enumerate(pts):
            lines += [q, pts[(i + 1) % len(pts)]]
        return lines

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._finish(context)
        obj = context.edit_object
        if obj is None:
            return self._finish(context)
        region, rv3d, mouse = view_under_mouse(context, event)
        if region is None:
            return {'PASS_THROUGH'}
        view = (region, rv3d)
        if event.type == 'MOUSEMOVE':
            face = pick_face(view, obj, self.bm, mouse)
            self.region = region
            lines = self._outline(view, obj, self.first) if self.first is not None and self.first.is_valid else []
            if face is not None:
                lines += self._outline(view, obj, face)
            self.line = lines or None
            _redraw(context)
            return {'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            face = pick_face(view, obj, self.bm, mouse)
            if face is None:
                return {'RUNNING_MODAL'}
            if self.first is None or not self.first.is_valid:
                self.first = face
                return {'RUNNING_MODAL'}
            if face is not self.first:
                if len(face.verts) != len(self.first.verts):
                    self.report({'WARNING'}, "Bridge needs two polygons with the same number of points")
                else:
                    bridge_faces(self.bm, self.first, face)
                    self._commit(context)
            self.first, self.line = None, None
            _redraw(context)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class MS_OT_reduce_polygons(bpy.types.Operator):
    """Polygon Reduction: add a Decimate modifier to the selected meshes"""
    bl_idname = "mr_softie.reduce_polygons"
    bl_label = "Polygon Reduction"
    bl_options = {'REGISTER', 'UNDO'}

    ratio: bpy.props.FloatProperty(name="Keep", default=0.5, min=0.01, max=1.0, subtype='FACTOR')

    def execute(self, context):
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not meshes:
            self.report({'WARNING'}, "Select a polygon mesh")
            return {'CANCELLED'}
        for obj in meshes:
            mod = next((m for m in obj.modifiers if m.type == 'DECIMATE'), None) or \
                obj.modifiers.new("Polygon Reduction", 'DECIMATE')
            mod.ratio = self.ratio
        return {'FINISHED'}


class MS_OT_edit_op(bpy.types.Operator):
    """Run a polygon-mesh command, entering component mode first if needed"""
    bl_idname = "mr_softie.edit_op"
    bl_label = "Poly Mesh Command"
    bl_options = {'INTERNAL', 'UNDO'}

    op: bpy.props.StringProperty()
    args: bpy.props.StringProperty()
    invoke_op: bpy.props.BoolProperty(default=True)

    @classmethod
    def description(cls, context, props):
        if not props or not props.op:
            return cls.__doc__
        return props.op.split(".", 1)[-1].replace("_", " ").title()

    def execute(self, context):
        from .viewport import parse_args
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a polygon mesh")
            return {'CANCELLED'}
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        module, name = self.op.split(".", 1)
        op = getattr(getattr(bpy.ops, module), name)
        try:
            op('INVOKE_DEFAULT' if self.invoke_op else 'EXEC_DEFAULT', **parse_args(self.args))
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex).strip().splitlines()[-1])
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (MS_OT_weld_points, MS_OT_split_edge, MS_OT_weld_edges, MS_OT_bridge_polygons,
           MS_OT_reduce_polygons, MS_OT_edit_op)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
