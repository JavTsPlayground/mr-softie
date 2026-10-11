# SPDX-License-Identifier: GPL-3.0-or-later
"""Skeletons, constraints and envelopes.

  Draw Chain      click joint by joint in any viewport (on the plane through the 3D
                  cursor, facing you); right-click or Enter to finish. You get a
                  chain (a skeleton with connected bones) and an Effector null at the
                  tip that drives it with IK.
  Blend FK / IK   0 = the bones follow their own rotations (FK), 1 = the effector (IK)
  Constraints     Position, Orientation, Direction, Pose, Scaling, Path: select the
                  objects to constrain, then the target last
  Set Envelope    select the mesh(es), then the skeleton last: the mesh follows the
                  bones with automatic weights
"""
import bpy
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

IK_NAME = "Chain IK"


# --------------------------------------------------------------------------
# Building a chain (no UI, tested headless)
# --------------------------------------------------------------------------

def build_chain(context, points, name="Chain"):
    """Make a chain through world-space `points` (2 or more). Returns (armature object, effector)."""
    if len(points) < 2:
        return None, None
    collection = context.collection or context.scene.collection
    arm = bpy.data.armatures.new(name)
    arm.display_type = 'OCTAHEDRAL'
    obj = bpy.data.objects.new(name, arm)
    obj.location = points[0]
    obj.show_in_front = True
    collection.objects.link(obj)

    view_layer = context.view_layer
    for o in view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    previous_mode = context.mode
    if previous_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    root = Vector(points[0])
    parent = None
    names = []
    for i in range(len(points) - 1):
        bone = arm.edit_bones.new(f"Bone{i}")
        bone.head = Vector(points[i]) - root
        bone.tail = Vector(points[i + 1]) - root
        if parent is not None:
            bone.parent = parent
            bone.use_connect = True
        parent = bone
        names.append(bone.name)
    bpy.ops.object.mode_set(mode='OBJECT')

    effector = bpy.data.objects.new(f"{name}_Effector", None)
    effector.empty_display_type = 'SPHERE'
    effector.empty_display_size = max(0.05, (Vector(points[-1]) - Vector(points[-2])).length * 0.15)
    effector.location = points[-1]
    collection.objects.link(effector)

    tip = obj.pose.bones[names[-1]]
    ik = tip.constraints.new('IK')
    ik.name = IK_NAME
    ik.target = effector
    ik.chain_count = len(names)
    ik.use_tail = True
    obj["mr_softie_chain"] = True
    return obj, effector


def chain_ik(obj):
    """The IK constraint driving a chain (None if `obj` isn't one)."""
    if obj is None or obj.type != 'ARMATURE':
        return None
    for pb in obj.pose.bones:
        con = pb.constraints.get(IK_NAME) or next((c for c in pb.constraints if c.type == 'IK'), None)
        if con is not None:
            return con
    return None


# --------------------------------------------------------------------------
# Draw Chain tool
# --------------------------------------------------------------------------

def _view_under_mouse(context, event):
    x, y = event.mouse_x, event.mouse_y
    for area in context.window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for region in area.regions:
            if region.type == 'WINDOW' and region.x <= x < region.x + region.width \
                    and region.y <= y < region.y + region.height:
                return region, area.spaces.active.region_3d, Vector((x - region.x, y - region.y))
    return None, None, None


class MS_OT_draw_chain(bpy.types.Operator):
    """Draw Chain: click joint by joint in a viewport; right-click or Enter to finish"""
    bl_idname = "mr_softie.draw_chain"
    bl_label = "Draw Chain"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.window is not None

    def invoke(self, context, event):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.points = []
        self.region = self.rv3d = None
        self.mouse = None
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.workspace.status_text_set(
            "Draw Chain:  click to place joints  |  Right-click / Enter: finish  |  Esc: cancel")
        context.window.cursor_modal_set('CROSSHAIR')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _draw(self):
        if not self.points or bpy.context.region != self.region:
            return
        pts = [view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, p) for p in self.points]
        pts = [p for p in pts if p is not None]
        if self.mouse is not None:
            pts.append(self.mouse)
        if len(pts) < 2:
            return
        lines = []
        for a, b in zip(pts, pts[1:]):
            lines += [a, b]
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.line_width_set(2.0)
        batch = batch_for_shader(shader, 'LINES', {"pos": lines})
        shader.uniform_float("color", (0.2, 0.75, 1.0, 1.0))
        shader.bind()
        batch.draw(shader)
        gpu.state.line_width_set(1.0)

    def _end(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.workspace.status_text_set(None)
        context.window.cursor_modal_restore()
        for area in context.window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

    def modal(self, context, event):
        region, rv3d, mouse = _view_under_mouse(context, event)
        if event.type == 'ESC' and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        if (event.type == 'RIGHTMOUSE' and event.value == 'PRESS') or \
                (event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS'):
            self._end(context)
            if len(self.points) < 2:
                self.report({'WARNING'}, "A chain needs at least two joints")
                return {'CANCELLED'}
            obj, _eff = build_chain(context, self.points)
            self.report({'INFO'}, f"{obj.name}: {len(self.points) - 1} bone(s)")
            return {'FINISHED'}
        if event.type == 'MOUSEMOVE':
            if region is not None and (self.region is None or region == self.region):
                self.mouse = mouse
                for area in context.window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and region is not None:
            if self.region is None:
                self.region, self.rv3d = region, rv3d
            if region != self.region:
                return {'RUNNING_MODAL'}   # keep a chain in the viewport it was started in
            depth = context.scene.cursor.location if not self.points else self.points[0]
            point = view3d_utils.region_2d_to_location_3d(region, rv3d, mouse, depth)
            self.points.append(point)
            return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


# --------------------------------------------------------------------------
# Constraints, envelopes, poses
# --------------------------------------------------------------------------

CONSTRAINTS = (
    ('POSITION', "Position", "Follow the target's position", 'COPY_LOCATION'),
    ('ORIENTATION', "Orientation", "Follow the target's rotation", 'COPY_ROTATION'),
    ('DIRECTION', "Direction", "Point at the target", 'DAMPED_TRACK'),
    ('POSE', "Pose", "Move as if parented to the target", 'CHILD_OF'),
    ('SCALING', "Scaling", "Follow the target's scale", 'COPY_SCALE'),
    ('PATH', "Path", "Ride along the target curve", 'FOLLOW_PATH'),
)


class MS_OT_constrain(bpy.types.Operator):
    """Constrain the selected objects to the active one (select the target last)"""
    bl_idname = "mr_softie.constrain"
    bl_label = "Constrain"
    bl_options = {'REGISTER', 'UNDO'}

    kind: bpy.props.EnumProperty(items=[(k, label, desc) for k, label, desc, _t in CONSTRAINTS])

    def execute(self, context):
        target = context.active_object
        objs = [o for o in context.selected_objects if o != target]
        if target is None or not objs:
            self.report({'WARNING'}, "Select the objects to constrain, then the target last")
            return {'CANCELLED'}
        if self.kind == 'PATH' and target.type != 'CURVE':
            self.report({'WARNING'}, "The target of a Path constraint must be a curve")
            return {'CANCELLED'}
        ctype = next(t for k, _l, _d, t in CONSTRAINTS if k == self.kind)
        for obj in objs:
            con = obj.constraints.new(ctype)
            con.target = target
            con.name = next(label for k, label, _d, _t in CONSTRAINTS if k == self.kind)
            if ctype == 'CHILD_OF':
                # Keep the object where it is: compensate for the target's current transform.
                con.inverse_matrix = target.matrix_world.inverted()
            elif ctype == 'FOLLOW_PATH':
                con.use_curve_follow = True
                target.data.use_path = True
        self.report({'INFO'}, f"{len(objs)} object(s) constrained to {target.name}")
        return {'FINISHED'}


class MS_OT_set_envelope(bpy.types.Operator):
    """Set Envelope: the selected meshes follow the skeleton (selected last), with automatic weights"""
    bl_idname = "mr_softie.set_envelope"
    bl_label = "Set Envelope"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        skel = context.active_object
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if skel is None or skel.type != 'ARMATURE' or not meshes:
            self.report({'WARNING'}, "Select the mesh(es), then the skeleton last")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex).strip().splitlines()[-1])
            return {'CANCELLED'}
        return {'FINISHED'}


class MS_OT_reset_pose(bpy.types.Operator):
    """Reset Pose: put the selected skeletons back in their rest pose"""
    bl_idname = "mr_softie.reset_pose"
    bl_label = "Reset Pose"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'ARMATURE':
                for pb in obj.pose.bones:
                    pb.location = (0, 0, 0)
                    pb.rotation_quaternion = (1, 0, 0, 0)
                    pb.rotation_euler = (0, 0, 0)
                    pb.scale = (1, 1, 1)
        return {'FINISHED'}


class MS_OT_weight_paint(bpy.types.Operator):
    """Paint envelope weights on the selected mesh (again to stop)"""
    bl_idname = "mr_softie.weight_paint"
    bl_label = "Weight Paint"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'WARNING'}, "Select an enveloped mesh")
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='OBJECT' if context.mode == 'PAINT_WEIGHT' else 'WEIGHT_PAINT')
        return {'FINISHED'}


class MS_MT_constrain(bpy.types.Menu):
    bl_idname = "MS_MT_constrain"
    bl_label = "Constrain"

    def draw(self, context):
        from .viewport import button
        for key, label, _desc, _t in CONSTRAINTS:
            button(self.layout, label, "mr_softie.constrain", kind=key)


def draw_chain_panel(layout, context):
    """FK / IK blend for the active chain (or the chain the selected effector drives)."""
    obj = context.active_object
    if obj is not None and obj.type == 'EMPTY':
        obj = next((o for o in context.scene.objects if o.type == 'ARMATURE'
                    and (chain_ik(o) is not None and chain_ik(o).target == obj)), obj)
    ik = chain_ik(obj)
    if ik is None:
        layout.label(text="Select a chain")
        return
    layout.label(text=obj.name, icon='ARMATURE_DATA')
    row = layout.row(align=True)
    row.label(text="FK")
    row.prop(ik, "influence", text="", slider=True)
    row.label(text="IK")
    layout.prop(ik, "chain_count", text="Bones")


classes = (MS_OT_draw_chain, MS_OT_constrain, MS_OT_set_envelope, MS_OT_reset_pose,
           MS_OT_weight_paint, MS_MT_constrain)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
