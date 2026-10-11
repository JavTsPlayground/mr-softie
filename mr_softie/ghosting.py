# SPDX-License-Identifier: GPL-3.0-or-later
"""Ghosting: see an animated object where it is a few frames before and after now.

Turn Ghost on for an object (Animate > Ghosting, or its property page). In every
viewport it is drawn as faint wireframes at the frames before (red) and after
(green) the current one: how many, and how many frames apart, are scene settings.

Ghosts follow the object's own animation (its keys, layers and clips), relative to
its parent's current position. Constraints and drivers aren't evaluated for ghosts.
"""
import bpy
import gpu
from bpy.props import BoolProperty, IntProperty, PointerProperty
from gpu_extras.batch import batch_for_shader
from mathutils import Euler, Matrix, Quaternion, Vector

_handle = {"draw": None}
_edges = {}   # object name -> (key, local edge coordinates)

BEFORE_COLOR = (0.85, 0.2, 0.2)
AFTER_COLOR = (0.2, 0.75, 0.3)


class MS_GhostSettings(bpy.types.PropertyGroup):
    before: IntProperty(name="Before", default=3, min=0, max=20, description="Ghosts before the current frame")
    after: IntProperty(name="After", default=3, min=0, max=20, description="Ghosts after the current frame")
    step: IntProperty(name="Step", default=2, min=1, max=100, description="Frames between ghosts")
    show: BoolProperty(name="Show Ghosts", default=True, description="Draw ghosts in the viewports")


# --------------------------------------------------------------------------
# Where an object is at another frame (its own animation only)
# --------------------------------------------------------------------------

def _curves(obj):
    from .anim import fcurves
    curves = {}
    for fc in fcurves(obj):
        curves[(fc.data_path, fc.array_index)] = fc
    return curves


def _strip_curves(strip):
    from bpy_extras.anim_utils import action_get_channelbag_for_slot
    slot = getattr(strip, "action_slot", None)
    if slot is None and len(getattr(strip.action, "slots", ())):
        slot = strip.action.slots[0]   # keyed while editing the clip: the slot isn't on the strip yet
    if slot is not None:
        bag = action_get_channelbag_for_slot(strip.action, slot)
        return list(bag.fcurves) if bag else []
    return list(getattr(strip.action, "fcurves", []))


def _blend(value, v, blend_type, weight):
    if blend_type == 'ADD':
        return value + v * weight
    if blend_type == 'SUBTRACT':
        return value - v * weight
    if blend_type == 'MULTIPLY':
        return value * (1 - weight + v * weight)
    return value * (1 - weight) + v * weight


def channel_at(obj, path, index, frame, current):
    """One animated channel at `frame`: Mixer clips / layers bottom-up, then the action on top."""
    ad = obj.animation_data
    if ad is None:
        return current
    value = current
    tweak = ad.use_tweak_mode
    if ad.use_nla and len(ad.nla_tracks):
        for track in ad.nla_tracks:
            if track.mute:
                continue
            for strip in track.strips:
                if strip.mute or strip.action is None:
                    continue
                inside = strip.frame_start <= frame <= strip.frame_end
                if not inside and strip.extrapolation != 'HOLD':
                    continue
                fc = next((f for f in _strip_curves(strip)
                           if f.data_path == path and f.array_index == index), None)
                if fc is None:
                    continue
                clamped = min(max(frame, strip.frame_start), strip.frame_end)
                local = strip.action_frame_start + (clamped - strip.frame_start) / max(strip.scale, 1e-6)
                weight = strip.influence if strip.use_animated_influence else 1.0
                value = _blend(value, fc.evaluate(local), strip.blend_type, weight)
    if ad.action is not None and not tweak:
        fc = next((f for f in _curves(obj).values() if f.data_path == path and f.array_index == index), None)
        if fc is not None:
            blend = getattr(ad, "action_blend_type", 'REPLACE')
            value = _blend(value, fc.evaluate(frame), blend, getattr(ad, "action_influence", 1.0))
    return value


def matrix_at(obj, frame):
    """The object's world matrix at `frame`, from its own animation."""
    def channel(path, index, current):
        return channel_at(obj, path, index, frame, current)

    loc = Vector([channel("location", i, obj.location[i]) for i in range(3)])
    scale = Vector([channel("scale", i, obj.scale[i]) for i in range(3)])
    if obj.rotation_mode == 'QUATERNION':
        rot = Quaternion([channel("rotation_quaternion", i, obj.rotation_quaternion[i]) for i in range(4)])
        rot.normalize()
        rot_m = rot.to_matrix().to_4x4()
    elif obj.rotation_mode == 'AXIS_ANGLE':
        aa = [channel("rotation_axis_angle", i, obj.rotation_axis_angle[i]) for i in range(4)]
        rot_m = Matrix.Rotation(aa[0], 4, Vector(aa[1:]))
    else:
        rot_m = Euler([channel("rotation_euler", i, obj.rotation_euler[i]) for i in range(3)],
                      obj.rotation_mode).to_matrix().to_4x4()
    basis = Matrix.Translation(loc) @ rot_m @ Matrix.Diagonal(scale.to_4d())
    if obj.parent is not None:
        return obj.parent.matrix_world @ obj.matrix_parent_inverse @ basis
    return basis


def ghost_frames(scene, settings):
    now = scene.frame_current
    before = [now - settings.step * k for k in range(settings.before, 0, -1)]
    after = [now + settings.step * k for k in range(1, settings.after + 1)]
    return before, after


def is_animated(obj):
    ad = obj.animation_data
    return ad is not None and (ad.action is not None or len(ad.nla_tracks) > 0)


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------

def _local_edges(obj, depsgraph):
    """Edge endpoints in object space (a small cross for objects without a mesh)."""
    try:
        ev = obj.evaluated_get(depsgraph)
    except (ReferenceError, RuntimeError):
        return []
    if obj.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
        mesh = ev.to_mesh()
        try:
            key = (len(mesh.vertices), len(mesh.edges), round(sum(v.co.length for v in mesh.vertices[:64]), 4))
            cached = _edges.get(obj.name)
            if cached and cached[0] == key:
                return cached[1]
            co = [v.co.copy() for v in mesh.vertices]
            pts = []
            for e in mesh.edges:
                pts += [co[e.vertices[0]], co[e.vertices[1]]]
            _edges[obj.name] = (key, pts)
            return pts
        finally:
            ev.to_mesh_clear()
    s = 0.5
    return [Vector((-s, 0, 0)), Vector((s, 0, 0)), Vector((0, -s, 0)), Vector((0, s, 0)),
            Vector((0, 0, -s)), Vector((0, 0, s))]


def _draw():
    context = bpy.context
    scene = context.scene
    settings = getattr(scene, "mr_softie_ghost", None)
    if settings is None or not settings.show:
        return
    objs = [o for o in context.view_layer.objects
            if getattr(o, "mr_softie_ghost", False) and is_animated(o) and o.visible_get()]
    if not objs:
        return
    depsgraph = context.evaluated_depsgraph_get()
    before, after = ghost_frames(scene, settings)
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('LESS_EQUAL')
    region = context.region
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", 1.2)
    for obj in objs:
        pts = _local_edges(obj, depsgraph)
        if not pts:
            continue
        for frames, color in ((before, BEFORE_COLOR), (after, AFTER_COLOR)):
            n = len(frames)
            for i, frame in enumerate(frames):
                # Nearer ghosts are stronger.
                strength = (i + 1) / n if frames is before else (n - i) / n
                m = matrix_at(obj, frame)
                world = [m @ p for p in pts]
                batch = batch_for_shader(shader, 'LINES', {"pos": world})
                shader.uniform_float("color", (*color, 0.15 + 0.45 * strength))
                batch.draw(shader)
    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('NONE')


@bpy.app.handlers.persistent
def _forget_edges(*_args):
    _edges.clear()


# --------------------------------------------------------------------------
# Operators and UI
# --------------------------------------------------------------------------

class MS_OT_ghost_toggle(bpy.types.Operator):
    """Ghost the selected objects (or stop ghosting them)"""
    bl_idname = "mr_softie.ghost_toggle"
    bl_label = "Ghost"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = list(context.selected_objects)
        if not objs:
            self.report({'WARNING'}, "Select animated objects to ghost")
            return {'CANCELLED'}
        on = not all(o.mr_softie_ghost for o in objs)
        for obj in objs:
            obj.mr_softie_ghost = on
        if on and not any(is_animated(o) for o in objs):
            self.report({'INFO'}, "Ghosts show once the objects are animated")
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


def draw_ghost_panel(layout, context):
    settings = context.scene.mr_softie_ghost
    objs = context.selected_objects
    on = bool(objs) and all(o.mr_softie_ghost for o in objs)
    layout.operator("mr_softie.ghost_toggle", text="Ghost Selected", depress=on)
    col = layout.column(align=True)
    col.prop(settings, "before")
    col.prop(settings, "after")
    col.prop(settings, "step")
    layout.prop(settings, "show", text="Show Ghosts", toggle=True)


classes = (MS_GhostSettings, MS_OT_ghost_toggle)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mr_softie_ghost = PointerProperty(type=MS_GhostSettings)
    bpy.types.Object.mr_softie_ghost = BoolProperty(
        name="Ghost", default=False, description="Show this object's animation as ghosts before and after now")
    if not bpy.app.background:
        _handle["draw"] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_VIEW')
    bpy.app.handlers.load_post.append(_forget_edges)


def unregister():
    if _forget_edges in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_forget_edges)
    if _handle["draw"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle["draw"], 'WINDOW')
        _handle["draw"] = None
    del bpy.types.Object.mr_softie_ghost
    del bpy.types.Scene.mr_softie_ghost
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    _edges.clear()
