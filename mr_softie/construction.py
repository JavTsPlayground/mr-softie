# SPDX-License-Identifier: GPL-3.0-or-later
"""Construction modes: the classic Modeling / Shape / Animation / Secondary Shape stack.

An object's modifiers are grouped into regions, bottom to top:

  Modeling           building the shape: subdivision, bevel, mirror, ICE trees...
  Shape Modeling     shape keys (Blender always evaluates these first, under everything)
  Animation          deformers: skeleton, lattice, bend / twist / taper, hooks, cages...
  Secondary Shape    on top of the animation: smoothing, cloth, soft body...

The current construction mode decides where new modifiers go (Auto puts each one
where it belongs by type). The stack is kept in region order, and Freeze M applies
the Modeling region only, so deformers and simulations on top stay live.

Regions are remembered per modifier (by its persistent id) on the object.
"""
import bpy
from bpy.props import EnumProperty

KEY = "mr_softie_regions"
REGIONS = (
    ('MODELING', "Modeling", "Building the shape"),
    ('SHAPE', "Shape Modeling", "Shape keys"),
    ('ANIMATION', "Animation", "Deformers"),
    ('SECONDARY', "Secondary Shape", "On top of the animation"),
)
ORDER = {key: i for i, (key, _l, _d) in enumerate(REGIONS)}
LABELS = {key: label for key, label, _d in REGIONS}

ANIMATION_TYPES = {
    'ARMATURE', 'LATTICE', 'CURVE', 'HOOK', 'MESH_DEFORM', 'SIMPLE_DEFORM', 'CAST', 'WARP', 'WAVE',
    'DISPLACE', 'SHRINKWRAP', 'LAPLACIANDEFORM', 'SURFACE_DEFORM', 'MESH_CACHE', 'MESH_SEQUENCE_CACHE',
}
SECONDARY_TYPES = {
    'CORRECTIVE_SMOOTH', 'SMOOTH', 'LAPLACIANSMOOTH', 'CLOTH', 'SOFT_BODY', 'COLLISION',
    'DYNAMIC_PAINT', 'OCEAN', 'EXPLODE',
}


def default_region(mod):
    if mod.type in ANIMATION_TYPES:
        return 'ANIMATION'
    if mod.type in SECONDARY_TYPES:
        return 'SECONDARY'
    return 'MODELING'


def _uid(mod):
    return str(getattr(mod, "persistent_uid", mod.name))


def _table(obj):
    data = obj.get(KEY)
    return data.to_dict() if data is not None else {}


def region_of(obj, mod):
    return _table(obj).get(_uid(mod)) or default_region(mod)


def set_region(obj, mod, region):
    table = _table(obj)
    table[_uid(mod)] = region
    obj[KEY] = table
    sort_stack(obj)


def adopt_new(obj, mode):
    """Give modifiers we haven't seen a region (from `mode`, or by type for Auto). Returns True if any."""
    table = _table(obj)
    changed = False
    live = set()
    for mod in obj.modifiers:
        uid = _uid(mod)
        live.add(uid)
        if uid not in table:
            region = default_region(mod) if mode == 'AUTO' or mode == 'SHAPE' else mode
            table[uid] = region
            changed = True
    for uid in [u for u in table if u not in live]:   # forget removed modifiers
        del table[uid]
        changed = True
    if changed:
        obj[KEY] = table
    return changed


def sort_stack(obj):
    """Reorder the modifiers by region (stable inside a region). Returns True if anything moved."""
    mods = list(obj.modifiers)
    wanted = sorted(range(len(mods)), key=lambda i: (ORDER[region_of(obj, mods[i])], i))
    if wanted == list(range(len(mods))):
        return False
    names = [mods[i].name for i in wanted]
    for target, name in enumerate(names):
        current = next(i for i, m in enumerate(obj.modifiers) if m.name == name)
        if current != target:
            obj.modifiers.move(current, target)
    return True


def modifiers_in(obj, region):
    return [m for m in obj.modifiers if region_of(obj, m) == region]


def freeze_modeling(context, obj):
    """Apply the Modeling region. Returns (applied, error message or None)."""
    mods = modifiers_in(obj, 'MODELING')
    if not mods:
        return 0, None
    if obj.data.users > 1:
        return 0, "The mesh is shared with other objects (make it single-user first)"
    if getattr(obj.data, "shape_keys", None) is not None:
        return 0, "Blender can't apply modifiers to a mesh with shape keys"
    mode = context.mode
    if mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    applied = 0
    for mod in mods:
        with context.temp_override(object=obj, active_object=obj):
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
                applied += 1
            except RuntimeError as ex:
                return applied, str(ex).strip().splitlines()[-1]
    adopt_new(obj, 'AUTO')
    return applied, None


# --------------------------------------------------------------------------
# Keeping new modifiers in their region
# --------------------------------------------------------------------------

_pending = set()


def _process():
    wm = bpy.context.window_manager
    mode = wm.mr_softie_cons_mode if wm else 'AUTO'
    for name in list(_pending):
        obj = bpy.data.objects.get(name)
        if obj is None or not hasattr(obj, "modifiers"):
            continue
        try:
            adopt_new(obj, mode)
            sort_stack(obj)
        except (ReferenceError, RuntimeError, AttributeError):
            pass
    _pending.clear()
    return None


@bpy.app.handlers.persistent
def _on_update(scene, depsgraph):
    for update in depsgraph.updates:
        ob = update.id.original if hasattr(update.id, "original") else update.id
        if isinstance(ob, bpy.types.Object) and len(getattr(ob, "modifiers", ())) \
                and len(ob.modifiers) != len(_table(ob)):
            _pending.add(ob.name)
    if _pending and not bpy.app.timers.is_registered(_process):
        bpy.app.timers.register(_process, first_interval=0.05)


# --------------------------------------------------------------------------
# Operators and UI
# --------------------------------------------------------------------------

class MS_OT_freeze_m(bpy.types.Operator):
    """Freeze M: apply the Modeling region of the stack; deformers and simulations on top stay live"""
    bl_idname = "mr_softie.freeze_m"
    bl_label = "Freeze M"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == 'MESH'] or \
            ([context.active_object] if context.active_object and context.active_object.type == 'MESH' else [])
        if not objs:
            self.report({'WARNING'}, "Select a polygon mesh")
            return {'CANCELLED'}
        total = 0
        for obj in objs:
            adopt_new(obj, 'AUTO')
            applied, error = freeze_modeling(context, obj)
            total += applied
            if error:
                self.report({'WARNING'}, f"{obj.name}: {error}")
        self.report({'INFO'}, f"Froze {total} modeling operator(s)")
        return {'FINISHED'}


class MS_OT_cons_move(bpy.types.Operator):
    """Move this operator to another region of the construction stack"""
    bl_idname = "mr_softie.cons_move"
    bl_label = "Move to Region"
    bl_options = {'INTERNAL', 'UNDO'}

    modifier: bpy.props.StringProperty()
    region: EnumProperty(items=[r for r in REGIONS if r[0] != 'SHAPE'])

    def execute(self, context):
        from .ppg import ppg_object
        obj = ppg_object(context) or context.active_object
        mod = obj.modifiers.get(self.modifier) if obj else None
        if mod is None:
            return {'CANCELLED'}
        set_region(obj, mod, self.region)
        return {'FINISHED'}


def draw_construction(layout, context, obj):
    wm = context.window_manager
    row = layout.row(align=True)
    row.label(text="Mode")
    row.prop(wm, "mr_softie_cons_mode", text="")
    adopt_ok = len(obj.modifiers) == len(_table(obj))
    for key, label, _desc in reversed(REGIONS):
        box = layout.box()
        head = box.row()
        current = wm.mr_softie_cons_mode == key
        head.label(text=label, icon='RADIOBUT_ON' if current else 'RADIOBUT_OFF')
        if key == 'SHAPE':
            keys = obj.data.shape_keys.key_blocks if getattr(obj.data, "shape_keys", None) else []
            for kb in list(keys)[1:]:
                r = box.row(align=True)
                r.prop(kb, "value", text=kb.name, slider=True)
                r.prop(kb, "mute", text="", emboss=False)
            if len(keys) < 2:
                box.label(text="No shape keys")
            continue
        mods = [m for m in obj.modifiers if region_of(obj, m) == key] if adopt_ok else \
            [m for m in obj.modifiers if default_region(m) == key]
        for mod in reversed(mods):
            r = box.row(align=True)
            r.prop(mod, "show_viewport", text="", emboss=False)
            r.label(text=mod.name)
            for target, tlabel, _d in REGIONS:
                if target in (key, 'SHAPE'):
                    continue
                op = r.operator("mr_softie.cons_move", text="", icon={
                    'MODELING': 'TRIA_DOWN_BAR', 'ANIMATION': 'TRIA_RIGHT', 'SECONDARY': 'TRIA_UP_BAR'}[target])
                op.modifier, op.region = mod.name, target
        if not mods:
            box.label(text="Empty")
    layout.label(text="Polygon Mesh  (base geometry)", icon='MESH_DATA')
    row = layout.row(align=True)
    row.operator("mr_softie.freeze_m", text="Freeze M")
    row.operator("mr_softie.freeze", text="Freeze All")


classes = (MS_OT_freeze_m, MS_OT_cons_move)


def register():
    bpy.types.WindowManager.mr_softie_cons_mode = EnumProperty(
        name="Construction Mode",
        items=(('AUTO', "Auto", "Each new operator goes where it belongs by type"),) + REGIONS,
        default='AUTO',
        description="Where new operators (modifiers) go in the construction stack")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.depsgraph_update_post.append(_on_update)


def unregister():
    if _on_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_update)
    if bpy.app.timers.is_registered(_process):
        bpy.app.timers.unregister(_process)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.WindowManager.mr_softie_cons_mode
