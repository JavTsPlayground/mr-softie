# SPDX-License-Identifier: GPL-3.0-or-later
"""Animation layers, on the Mixer (NLA).

  Base         the object's existing animation, at the bottom
  New Layer    an additive layer on top: keys you set go into the current layer
               and add to everything below it
  Weight       how much of a layer is applied (0 to 1)
  Mute         switch a layer off
  Current      the layer K / Save Key writes into (the others keep playing)
  Merge        bake everything into one plain animation and remove the layers

Every layer is a Mixer track (named "Layer: ...") holding one clip; the current
layer is the clip being edited in place (NLA tweak mode).
"""
import bpy
from bpy.props import IntProperty

PREFIX = "Layer: "


def _ad(obj):
    return obj.animation_data if obj is not None else None


def layer_tracks(obj):
    ad = _ad(obj)
    if ad is None:
        return []
    return [t for t in ad.nla_tracks if t.name.startswith(PREFIX) and len(t.strips)]


def current_layer(obj):
    ad = _ad(obj)
    if ad is None or not ad.use_tweak_mode:
        return None
    track = ad.nla_tracks.active
    return track if track is not None and track.name.startswith(PREFIX) else None


def weight_key(track):
    """The single keyframe holding a layer's weight (the clip's influence)."""
    strip = track.strips[0]
    if not strip.use_animated_influence:
        strip.use_animated_influence = True
        fc = strip.fcurves.find("influence")
        for kp in fc.keyframe_points:
            kp.co[1] = kp.handle_left[1] = kp.handle_right[1] = 1.0
    fc = strip.fcurves.find("influence")
    return fc.keyframe_points[0] if fc and len(fc.keyframe_points) else None


def set_weight(track, value):
    kp = weight_key(track)
    if kp is not None:
        kp.co[1] = kp.handle_left[1] = kp.handle_right[1] = value
        track.strips[0].fcurves.find("influence").update()


def stop_editing(obj):
    ad = _ad(obj)
    if ad is not None and ad.use_tweak_mode:
        ad.use_tweak_mode = False


def make_current(obj, track):
    """Keys go into `track` from now on; everything else keeps playing."""
    ad = _ad(obj)
    stop_editing(obj)
    for t in ad.nla_tracks:
        t.select = False
        for s in t.strips:
            s.select = False
    track.select = True
    track.strips[0].select = True
    ad.nla_tracks.active = track
    ad.use_tweak_mode = True


def _scene_range(scene):
    return scene.frame_start, scene.frame_end


def ensure_base(obj, scene):
    """Move the object's current animation into the Base layer (once)."""
    ad = obj.animation_data_create()
    stop_editing(obj)
    if any(t.name == PREFIX + "Base" for t in ad.nla_tracks):
        return
    action = ad.action
    if action is None:
        action = bpy.data.actions.new(f"{obj.name} Base")
    if not action.use_frame_range:
        start, end = _scene_range(scene)
        if action.frame_range[1] > action.frame_range[0]:
            start = min(start, int(action.frame_range[0]))
            end = max(end, int(action.frame_range[1]))
        action.use_frame_range = True
        action.frame_start, action.frame_end = start, end
    slot = getattr(ad, "action_slot", None)
    track = ad.nla_tracks.new()
    track.name = PREFIX + "Base"
    strip = track.strips.new("Base", int(action.frame_start), action)
    if slot is not None and hasattr(strip, "action_slot"):
        try:
            strip.action_slot = slot
        except (TypeError, AttributeError, RuntimeError):
            pass
    strip.extrapolation = 'HOLD'
    ad.action = None


def new_layer(obj, scene):
    ensure_base(obj, scene)
    ad = obj.animation_data
    index = len(layer_tracks(obj))
    name = f"Layer {index}"
    action = bpy.data.actions.new(f"{obj.name} {name}")
    start, end = _scene_range(scene)
    action.use_frame_range = True
    action.frame_start, action.frame_end = start, end
    track = ad.nla_tracks.new()
    track.name = PREFIX + name
    strip = track.strips.new(name, start, action)
    strip.blend_type = 'ADD'
    strip.extrapolation = 'HOLD'
    weight_key(track)
    make_current(obj, track)
    return track


def merge_layers(context, obj):
    """Bake every layer into one action and remove the layers."""
    scene = context.scene
    tracks = layer_tracks(obj)
    if not tracks:
        return False
    stop_editing(obj)
    start, end = _scene_range(scene)
    for t in tracks:
        for s in t.strips:
            start, end = min(start, int(s.frame_start)), max(end, int(s.frame_end))
    selected = [o for o in context.view_layer.objects if o.select_get()]
    for o in selected:
        o.select_set(False)
    obj.select_set(True)
    try:
        bpy.ops.nla.bake(frame_start=start, frame_end=end, only_selected=True, visual_keying=True,
                         bake_types={'OBJECT'}, use_current_action=False, clean_curves=True)
    finally:
        for o in selected:
            o.select_set(True)
    ad = obj.animation_data
    for t in list(ad.nla_tracks):
        if t.name.startswith(PREFIX):
            ad.nla_tracks.remove(t)
    if ad.action is not None:
        ad.action.name = f"{obj.name} Merged"
    return True


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------

def _active(context):
    obj = context.active_object
    return obj if obj is not None else None


class MS_OT_layer_new(bpy.types.Operator):
    """New animation layer on top: the keys you set go into it, added to everything below"""
    bl_idname = "mr_softie.layer_new"
    bl_label = "New Animation Layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active(context) is not None

    def execute(self, context):
        track = new_layer(context.active_object, context.scene)
        self.report({'INFO'}, f"{track.name[len(PREFIX):]} is the current layer")
        return {'FINISHED'}


class MS_OT_layer_set(bpy.types.Operator):
    """Make this the current layer: keys go into it"""
    bl_idname = "mr_softie.layer_set"
    bl_label = "Set Current Layer"
    bl_options = {'INTERNAL', 'UNDO'}

    index: IntProperty()

    def execute(self, context):
        obj = context.active_object
        tracks = layer_tracks(obj)
        if not 0 <= self.index < len(tracks):
            return {'CANCELLED'}
        if current_layer(obj) == tracks[self.index]:
            stop_editing(obj)          # click the current one again: stop editing layers
        else:
            make_current(obj, tracks[self.index])
        return {'FINISHED'}


class MS_OT_layer_merge(bpy.types.Operator):
    """Merge all layers into one plain animation"""
    bl_idname = "mr_softie.layer_merge"
    bl_label = "Merge Layers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(layer_tracks(_active(context)))

    def execute(self, context):
        if not merge_layers(context, context.active_object):
            return {'CANCELLED'}
        return {'FINISHED'}


class MS_OT_layer_delete(bpy.types.Operator):
    """Delete this layer (not the Base)"""
    bl_idname = "mr_softie.layer_delete"
    bl_label = "Delete Layer"
    bl_options = {'INTERNAL', 'UNDO'}

    index: IntProperty()

    def execute(self, context):
        obj = context.active_object
        tracks = layer_tracks(obj)
        if not 0 <= self.index < len(tracks) or tracks[self.index].name == PREFIX + "Base":
            return {'CANCELLED'}
        stop_editing(obj)
        obj.animation_data.nla_tracks.remove(tracks[self.index])
        return {'FINISHED'}


def draw_layers(layout, context):
    obj = context.active_object
    if obj is None:
        layout.label(text="Select an object")
        return
    tracks = layer_tracks(obj)
    current = current_layer(obj)
    col = layout.column(align=True)
    for i, track in reversed(list(enumerate(tracks))):
        name = track.name[len(PREFIX):]
        row = col.row(align=True)
        row.operator("mr_softie.layer_set", text=name, depress=track == current).index = i
        row.prop(track, "mute", text="", icon='HIDE_ON' if track.mute else 'HIDE_OFF', emboss=False)
        if name != "Base":
            kp = weight_key(track) if track.strips[0].use_animated_influence else None
            if kp is not None:
                sub = col.row(align=True)
                sub.prop(kp, "co", index=1, text="", slider=True)
    if not tracks:
        col.label(text="No layers yet")
    row = layout.row(align=True)
    row.operator("mr_softie.layer_new", text="New")
    row.operator("mr_softie.layer_merge", text="Merge")
    if current is not None:
        layout.label(text=f"Keying into {current.name[len(PREFIX):]}", icon='KEYFRAME_HLT')


classes = (MS_OT_layer_new, MS_OT_layer_set, MS_OT_layer_merge, MS_OT_layer_delete)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
