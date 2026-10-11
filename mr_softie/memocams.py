# SPDX-License-Identifier: GPL-3.0-or-later
"""Memo cams: four saved camera positions per viewport.

  click an empty slot   remember this viewport's view
  click a full slot     go back to it (a short glide)
  the menu next to them Store (replace) or Forget a slot, or forget them all
                        (Ctrl+click / Shift+click on a slot do the same where
                        Blender passes the modifier keys through)

Slots live on the screen (saved in the .blend), one set per viewport.
"""
import bpy
from bpy.props import EnumProperty, IntProperty
from mathutils import Quaternion, Vector

KEY = "mr_softie_memo"
SLOTS = 4
GLIDE_STEPS = 8


def _area_index(screen, area):
    views = [a for a in screen.areas if a.type == 'VIEW_3D']
    return views.index(area) if area in views else -1


def _store(screen):
    data = screen.get(KEY)
    return data.to_dict() if data is not None else {}


def get_slot(screen, area, slot):
    return _store(screen).get(str(_area_index(screen, area)), {}).get(str(slot))


def snapshot(space):
    rv3d = space.region_3d
    return {"location": list(rv3d.view_location), "rotation": list(rv3d.view_rotation),
            "distance": rv3d.view_distance, "perspective": rv3d.view_perspective,
            "lens": space.lens}


def save_slot(screen, area, slot, value):
    data = _store(screen)
    views = data.setdefault(str(_area_index(screen, area)), {})
    if value is None:
        views.pop(str(slot), None)
    else:
        views[str(slot)] = value
    screen[KEY] = data


def apply(space, memo, factor=1.0, start=None):
    """Move the view toward `memo` (factor 1 = all the way) from `start` (a snapshot)."""
    rv3d = space.region_3d
    start = start or snapshot(space)
    if memo["perspective"] == 'CAMERA' or start["perspective"] == 'CAMERA' or factor >= 1.0:
        rv3d.view_perspective = memo["perspective"]
        if memo["perspective"] != 'CAMERA':
            rv3d.view_location = Vector(memo["location"])
            rv3d.view_rotation = Quaternion(memo["rotation"])
            rv3d.view_distance = memo["distance"]
            space.lens = memo["lens"]
        return
    rv3d.view_location = Vector(start["location"]).lerp(Vector(memo["location"]), factor)
    rv3d.view_rotation = Quaternion(start["rotation"]).slerp(Quaternion(memo["rotation"]), factor)
    rv3d.view_distance = start["distance"] + (memo["distance"] - start["distance"]) * factor
    space.lens = start["lens"] + (memo["lens"] - start["lens"]) * factor


def glide(area, memo):
    space = area.spaces.active
    start = snapshot(space)
    if memo["perspective"] != start["perspective"] and 'CAMERA' not in (memo["perspective"], start["perspective"]):
        space.region_3d.view_perspective = memo["perspective"]
        start = snapshot(space)
    step = [0]

    def tick():
        step[0] += 1
        t = step[0] / GLIDE_STEPS
        ease = t * t * (3 - 2 * t)
        try:
            apply(space, memo, 1.0 if step[0] >= GLIDE_STEPS else ease, start)
            area.tag_redraw()
        except ReferenceError:
            return None
        return None if step[0] >= GLIDE_STEPS else 0.016

    if memo["perspective"] == 'CAMERA' or start["perspective"] == 'CAMERA':
        apply(space, memo)
        area.tag_redraw()
    else:
        bpy.app.timers.register(tick, first_interval=0.0)


class MS_OT_memo_cam(bpy.types.Operator):
    """Memo cam: click to remember this view, or go back to it. Ctrl+click: replace. Shift+click: forget"""
    bl_idname = "mr_softie.memo_cam"
    bl_label = "Memo Cam"

    slot: IntProperty(min=0, max=SLOTS, default=1)   # 0 = every slot (Forget only)
    action: EnumProperty(items=(('AUTO', "Auto", "Recall, or store when empty"),
                                ('STORE', "Store", "Remember this view"),
                                ('FORGET', "Forget", "Clear the slot")),
                         default='AUTO', options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        if self.action == 'AUTO':
            self.action = 'FORGET' if event.shift else 'STORE' if event.ctrl else 'AUTO'
        return self.execute(context)

    def execute(self, context):
        mode = self.action
        screen, area = context.screen, context.area
        if mode == 'FORGET' and self.slot == 0:
            for slot in range(1, SLOTS + 1):
                save_slot(screen, area, slot, None)
            area.tag_redraw()
            return {'FINISHED'}
        memo = get_slot(screen, area, self.slot)
        if mode == 'FORGET':
            save_slot(screen, area, self.slot, None)
            self.report({'INFO'}, f"Memo cam {self.slot} cleared")
        elif mode == 'STORE' or memo is None:
            save_slot(screen, area, self.slot, snapshot(area.spaces.active))
            self.report({'INFO'}, f"Memo cam {self.slot} stored")
        else:
            glide(area, memo)
        area.tag_redraw()
        return {'FINISHED'}


def draw_memo_buttons(layout, context):
    screen, area = context.screen, context.area
    row = layout.row(align=True)
    row.scale_x = 0.9
    for slot in range(1, SLOTS + 1):
        full = get_slot(screen, area, slot) is not None
        row.operator("mr_softie.memo_cam", text=str(slot), depress=full).slot = slot
    row.menu("MS_MT_memo_cams", text="", icon='DOWNARROW_HLT')


class MS_MT_memo_cams(bpy.types.Menu):
    bl_idname = "MS_MT_memo_cams"
    bl_label = "Memo Cams"

    def draw(self, context):
        layout = self.layout
        for slot in range(1, SLOTS + 1):
            op = layout.operator("mr_softie.memo_cam", text=f"Store {slot}")
            op.slot, op.action = slot, 'STORE'
        layout.separator()
        for slot in range(1, SLOTS + 1):
            op = layout.operator("mr_softie.memo_cam", text=f"Forget {slot}")
            op.slot, op.action = slot, 'FORGET'
        op = layout.operator("mr_softie.memo_cam", text="Forget All")
        op.slot, op.action = 0, 'FORGET'


classes = (MS_OT_memo_cam, MS_MT_memo_cams)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
