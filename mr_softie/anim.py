# SPDX-License-Identifier: GPL-3.0-or-later
"""Classic keying and the timeline / playback strip.

  Marked parameters  the SRT set the Key button and K key on (S, R, T or all)
  Save Key (K)       key the marked parameters of the selection at this frame
  Key button         red when the active object has a key here, highlighted
                     when it is animated but not keyed on this frame
  Timeline strip     Start / End, transport, current frame, real-time
                     playback, then the animation controls, in one row
"""
import bpy
from bpy.props import EnumProperty

MARKED = (
    ('SRT', "SRT", "Key scaling, rotation and translation"),
    ('S', "S", "Key scaling only"),
    ('R', "R", "Key rotation only"),
    ('T', "T", "Key translation only"),
)
PATHS = {'S': ("scale",), 'R': ("rotation_euler",), 'T': ("location",),
         'SRT': ("location", "rotation_euler", "scale")}


def marked_paths(context, obj=None):
    paths = PATHS[context.window_manager.mr_softie_marked]
    if obj is not None and obj.rotation_mode == 'QUATERNION':
        paths = tuple("rotation_quaternion" if p == "rotation_euler" else p for p in paths)
    elif obj is not None and obj.rotation_mode == 'AXIS_ANGLE':
        paths = tuple("rotation_axis_angle" if p == "rotation_euler" else p for p in paths)
    return paths


def fcurves(obj):
    """F-curves of the object's assigned action (layered 4.4+/5.x API, legacy fallback)."""
    ad = obj.animation_data if obj else None
    if ad is None or ad.action is None:
        return []
    try:
        from bpy_extras.anim_utils import animdata_get_channelbag_for_assigned_slot
        bag = animdata_get_channelbag_for_assigned_slot(ad)
        return list(bag.fcurves) if bag else []
    except ImportError:
        return list(getattr(ad.action, "fcurves", []))


def key_state(obj, frame, paths=None):
    """'KEY' if keyed on this frame, 'ANIM' if animated, else None."""
    curves = [fc for fc in fcurves(obj) if paths is None or fc.data_path in paths]
    if not curves:
        return None
    for fc in curves:
        for kp in fc.keyframe_points:
            if abs(kp.co[0] - frame) < 0.5:
                return 'KEY'
    return 'ANIM'


class MS_OT_save_key(bpy.types.Operator):
    """Save Key: key the marked parameters of the selection at the current frame"""
    bl_idname = "mr_softie.save_key"
    bl_label = "Save Key"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        frame = context.scene.frame_current
        objs = list(context.selected_objects)
        if not objs and context.active_object is not None:
            objs = [context.active_object]
        for obj in objs:
            for path in marked_paths(context, obj):
                obj.keyframe_insert(path, frame=frame)
        if not objs:
            self.report({'WARNING'}, "Nothing selected")
            return {'CANCELLED'}
        return {'FINISHED'}


class MS_OT_remove_key(bpy.types.Operator):
    """Remove Key: delete the marked parameters' keys on the selection at the current frame"""
    bl_idname = "mr_softie.remove_key"
    bl_label = "Remove Key"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        frame = context.scene.frame_current
        removed = 0
        objs = list(context.selected_objects) or ([context.active_object] if context.active_object else [])
        for obj in objs:
            for path in marked_paths(context, obj):
                try:
                    removed += bool(obj.keyframe_delete(path, frame=frame))
                except RuntimeError:
                    pass
        if not removed:
            self.report({'INFO'}, "No key on this frame")
        return {'FINISHED'}


class MS_OT_key_jump(bpy.types.Operator):
    """Jump to the previous / next key of the selection"""
    bl_idname = "mr_softie.key_jump"
    bl_label = "Jump to Key"
    bl_options = {'INTERNAL'}

    next: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        try:
            bpy.ops.screen.keyframe_jump(next=self.next)
        except RuntimeError:
            return {'CANCELLED'}
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Timeline strip (replaces the timeline header inside the MR.Softie workspace)
# --------------------------------------------------------------------------

def draw_key_button(layout, context):
    obj = context.active_object
    state = key_state(obj, context.scene.frame_current, marked_paths(context, obj)) if obj else None
    row = layout.row(align=True)
    row.scale_x = 1.3
    row.alert = state == 'KEY'
    icon = 'KEYFRAME_HLT' if state == 'KEY' else 'KEYFRAME'
    row.operator("mr_softie.save_key", text="Key", icon=icon, depress=state == 'ANIM')


def draw_softie_timeline(self, context):
    layout = self.layout
    st = context.space_data
    if getattr(st, "mode", None) != 'TIMELINE':
        type(self).draw._mr_softie_original(self, context)
        return
    scene = context.scene
    ts = context.tool_settings
    screen = context.screen
    wm = context.window_manager

    layout.template_header()

    # Range
    row = layout.row(align=True)
    row.scale_x = 0.8
    if scene.use_preview_range:
        row.prop(scene, "frame_preview_start", text="")
        row.prop(scene, "frame_preview_end", text="")
    else:
        row.prop(scene, "frame_start", text="")
        row.prop(scene, "frame_end", text="")
    row.prop(scene, "use_preview_range", text="", icon='PREVIEW_RANGE')

    layout.separator_spacer()

    # Playback
    row = layout.row(align=True)
    row.scale_x = 1.15
    row.operator("screen.frame_jump", text="", icon='REW').end = False
    row.operator("screen.keyframe_jump", text="", icon='PREV_KEYFRAME').next = False
    row.operator("screen.frame_offset", text="", icon='FRAME_PREV').delta = -1
    if screen.is_animation_playing:
        row.operator("screen.animation_cancel", text="", icon='PAUSE').restore_frame = False
    else:
        row.operator("screen.animation_play", text="", icon='PLAY_REVERSE').reverse = True
        row.operator("screen.animation_play", text="", icon='PLAY')
    row.operator("screen.frame_offset", text="", icon='FRAME_NEXT').delta = 1
    row.operator("screen.keyframe_jump", text="", icon='NEXT_KEYFRAME').next = True
    row.operator("screen.frame_jump", text="", icon='FF').end = True

    row = layout.row(align=True)
    row.scale_x = 0.9
    row.prop(scene, "frame_current", text="")
    row = layout.row(align=True)
    row.prop_enum(scene, "sync_mode", 'FRAME_DROP', text="RT")
    sub = row.row(align=True)
    sub.scale_x = 0.7
    sub.prop(scene.render, "fps", text="")

    layout.separator_spacer()

    # Animation
    draw_key_button(layout, context)
    row = layout.row(align=True)
    for ident, label, _desc in MARKED:
        row.prop_enum(wm, "mr_softie_marked", ident, text=label)
    row = layout.row(align=True)
    row.prop(ts, "use_keyframe_insert_auto", text="Auto", toggle=True)
    row.operator("mr_softie.remove_key", text="", icon='KEY_DEHLT')


classes = (MS_OT_save_key, MS_OT_remove_key, MS_OT_key_jump)


def register():
    bpy.types.WindowManager.mr_softie_marked = EnumProperty(
        name="Marked Parameters", items=MARKED, default='SRT',
        description="Which parameters Save Key (K) keys")
    for cls in classes:
        bpy.utils.register_class(cls)
    from . import ui_patch
    ui_patch._wrap(bpy.types.DOPESHEET_HT_header, draw_softie_timeline)


def unregister():
    from . import ui_patch
    ui_patch.unwrap(bpy.types.DOPESHEET_HT_header)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.mr_softie_marked
