"""Headless smoke test. Run with: python tests/test_headless.py (needs `pip install bpy`)."""
import os
import sys
from contextlib import nullcontext

import bpy  # must come first: puts Blender's modules on sys.path
import addon_utils

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "mr_softie")

repo_dir = bpy.utils.user_resource('EXTENSIONS', path="user_default", create=True)
link = os.path.join(repo_dir, "mr_softie")
if not os.path.exists(link):
    os.symlink(SRC, link)

MOD = "bl_ext.user_default.mr_softie"
failures = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        failures.append(name)


addon_utils.extensions_refresh(ensure_wheels=False) if hasattr(addon_utils, "extensions_refresh") else None
mod = addon_utils.enable(MOD, default_set=True, handle_error=lambda ex: print("ENABLE ERROR", ex))
check("add-on enables", mod is not None)

prefs = bpy.context.preferences.addons[MOD].preferences
check("preferences registered", prefs.use_keymap is True)

kc = bpy.context.window_manager.keyconfigs.addon
gm_items = [kmi for km in kc.keymaps for kmi in km.keymap_items
            if kmi.idname.startswith("mr_softie.") or kmi.key_modifier == 'S']
check(f"keymap items registered ({len(gm_items)})", len(gm_items) >= 40)
check("S-modifier nav present", any(k.idname == "view3d.rotate" and k.key_modifier == 'S'
                                    and k.type == 'RIGHTMOUSE' for k in gm_items))

# Operators must be real registered classes (bpy.ops lookups are lazy, so check bpy.types).
for name in ("SRT_TOOL", "SUPRA_RELEASE", "OBJECT_SELECT", "COMPONENT_MODE", "OPEN_EDITOR",
             "QUAD_VIEW", "TOGGLE_COG", "FREEZE", "RESET_SRT", "ADD_MATERIAL", "ADD_DEFORM",
             "TOGGLE_RENDER_PREVIEW", "APPLY_THEME", "RESET_THEME", "SWALLOW", "RUN",
             "BUILD_WORKSPACE", "FIT_COLUMNS", "SET_VIEW", "SET_DISPLAY", "TOGGLE_ALL", "MAXIMIZE",
             "INSTALL_APP_TEMPLATE", "OPEN_EXPLORER", "OPEN_SCHEMATIC", "SCHEMATIC_RELAYOUT",
             "OPEN_PPG", "PPG_PIN"):
    check(f"operator MR_SOFTIE_OT_{name.lower()}", hasattr(bpy.types, f"MR_SOFTIE_OT_{name.lower()}"))

for key in ("select", "transform", "snap", "constrain", "edit", "view"):
    check(f"sidebar panel {key}", hasattr(bpy.types, f"MS_PT_mcp_{key}"))
    check(f"MCP column panel {key}", hasattr(bpy.types, f"MS_PT_mcpcol_{key}"))
for menu in ("MS_MT_view_camera", "MS_MT_view_display", "MS_MT_main_edit",
             "MS_MT_main_display", "MS_MT_main_view"):
    check(f"menu {menu}", hasattr(bpy.types, menu))
check("viewport header wrapped", hasattr(bpy.types.VIEW3D_HT_header.draw, "_mr_softie_original"))
check("menu bar wrapped", hasattr(bpy.types.TOPBAR_MT_editor_menus.draw, "_mr_softie_original"))
check("toolbar module panel", hasattr(bpy.types, "MS_PT_tb_module"))
check("toolbar section panels", all(hasattr(bpy.types, f"MS_PT_tb_section{i}") for i in range(4)))
check("Get > Primitive menu", hasattr(bpy.types, "MS_MT_get_primitive"))
check("module property", bpy.context.window_manager.mr_softie_module == 'MODEL')
check("builtin text panels hidden in columns", "poll" in bpy.types.TEXT_PT_find.__dict__)

from importlib import import_module
toolbar = import_module(MOD + ".toolbar")
missing_ops = []
for module, sections in toolbar.SECTIONS.items():
    for _title, entries in sections:
        for entry in entries:
            if entry[0] == "run":
                a, b = entry[2].split(".")
                try:
                    getattr(getattr(bpy.ops, a), b).get_rna_type()
                except (KeyError, AttributeError):
                    missing_ops.append(entry[2])
            elif entry[0] == "menu":
                if not hasattr(bpy.types, entry[2]):
                    missing_ops.append(entry[2])
check(f"every toolbar command exists (missing: {missing_ops})", not missing_ops)

# The bundled layout template holds the MR.Softie workspace with sized columns.
template = os.path.join(SRC, "layout.blend")
check("layout template bundled", os.path.exists(template))
with bpy.data.libraries.load(template) as (data_from, _data_to):
    check("template has MR.Softie workspace", "MR.Softie" in list(data_from.workspaces))

# App template installs into the user's app-template folder.
bpy.ops.mr_softie.install_app_template()
tdir = bpy.utils.user_resource('SCRIPTS', path="startup/bl_app_templates_user/MR_Softie")
check("app template installed", os.path.exists(os.path.join(tdir, "startup.blend"))
      and os.path.exists(os.path.join(tdir, "__init__.py")))
check("app template listed", "MR_Softie" in [os.path.basename(p) for d in bpy.utils.app_template_paths()
                                             for p in [os.path.join(d, n) for n in os.listdir(d)]])
with bpy.data.libraries.load(os.path.join(tdir, "startup.blend")) as (data_from, _):
    check("app template opens MR.Softie", "MR.Softie" in list(data_from.workspaces))

# mr_softie.run executes commands (no window in background: runs directly).
before = len(bpy.data.objects)
bpy.ops.mr_softie.run(op="object.empty_add", args="{'type': 'PLAIN_AXES'}", invoke=False)
check("run executes a viewport command", len(bpy.data.objects) == before + 1)
bpy.ops.object.delete()

# Every operator name referenced anywhere in the source must exist in Blender.
import re
src = ""
for fn in os.listdir(SRC):
    if fn.endswith(".py"):
        src += open(os.path.join(SRC, fn), encoding="utf-8").read()
refs = set(re.findall(r"bpy\.ops\.([a-z_]+)\.([a-z_]+)\(", src))
refs |= {tuple(m.split(".")) for m in re.findall(r"[\"']([a-z_]+\.[a-z_]+)[\"']", src)
         if m.split(".")[0] in {"object", "mesh", "view3d", "screen", "transform", "ed", "wm",
                                "preferences", "mr_softie"}}
def _op_exists(a, b):
    try:
        return bool(getattr(getattr(bpy.ops, a), b).get_rna_type())
    except (KeyError, AttributeError):
        return False


tool_ids = {"raycast_mesh"}  # workspace tool ids, not operators
missing = [f"{a}.{b}" for a, b in sorted(refs) if b not in tool_ids and not _op_exists(a, b)]
check(f"all {len(refs)} referenced operators exist (missing: {missing})", not missing)

# Tool keymaps: the tool system creates them when tools register.

tools = import_module(MOD + ".tools")
check("SRT + raycast tools registered", len(tools._registered) == 7)
srt = [c for c in tools._registered if c.bl_idname.startswith("mr_softie.translate")]
check("manipulator sync running", bpy.app.timers.is_registered(tools._sync_manipulator))
check("SRT tools tied to their transform", all(c.bl_operator == "transform.translate" for c in srt))
kc_items = [kmi for km in bpy.context.window_manager.keyconfigs.addon.keymaps for kmi in km.keymap_items]
check("backslash = Add Edge", any(k.type == 'BACK_SLASH' and k.properties.name == "builtin.knife" for k in kc_items
                                 if k.idname == "wm.tool_set_by_id"))
km = tools.build_keymap("transform.rotate", 'XYZ')
check("tool keymap: S-nav listed first", km[0][1].get("key_modifier") == 'S')
right = [i for i in km if i[1]["type"] == 'RIGHTMOUSE' and not i[1].get("key_modifier")][0]
check("rotate RMB constrains Z", ("orient_axis", 'Z') in right[2]["properties"])
free = tools.build_keymap("transform.translate", 'FREE')
left = [i for i in free if i[1]["type"] == 'LEFTMOUSE' and i[1]["value"] == 'CLICK_DRAG'
        and not i[1].get("shift")][0]
check("FREE mode: left drag unconstrained",
      not any(p[0] == "constraint_axis" for p in left[2]["properties"]))

# Schematic: scene graph sync and two-way parenting
schematic = import_module(MOD + ".schematic")
bpy.ops.wm.read_homefile(use_empty=True)
for name in ("A", "B", "C"):
    bpy.ops.object.empty_add()
    bpy.context.active_object.name = name
A, B, C = (bpy.data.objects[n] for n in "ABC")
B.parent = A
C.constraints.new('TRACK_TO').target = A
tree = schematic.get_tree(create=True)
schematic.sync(tree, bpy.context.scene, relayout=True)
nodes = {n.obj.name: n for n in tree.nodes}
check("schematic: one node per object", set(nodes) == {"A", "B", "C"})
hier = [(l.from_node.obj.name, l.to_node.obj.name) for l in tree.links if l.to_socket.name == "Parent"]
cns = [(l.from_node.obj.name, l.to_node.obj.name) for l in tree.links if l.to_socket.name == "Cns"]
check("schematic: parent link A->B", hier == [("A", "B")])
check("schematic: constraint link A->C", cns == [("A", "C")])
check("schematic: child laid out below parent", nodes["B"].location.y < nodes["A"].location.y)
# user links C under B -> C is parented, world transform kept
C.location = (3, 0, 0)
bpy.context.view_layer.update()
tree.links.new(nodes["B"].outputs["Children"], nodes["C"].inputs["Parent"])
schematic._apply_user_links(tree)
bpy.context.view_layer.update()
check("schematic: linking re-parents", C.parent == B)
check("schematic: re-parent keeps world position", abs(C.matrix_world.translation.x - 3) < 1e-4)
# user cuts the link -> unparented
for link in list(tree.links):
    if link.to_node.obj == C and link.to_socket.name == "Parent":
        tree.links.remove(link)
schematic._apply_user_links(tree)
check("schematic: cutting the link un-parents", C.parent is None)
# cycle is refused
tree.links.new(nodes["B"].outputs["Children"], nodes["A"].inputs["Parent"])
schematic._apply_user_links(tree)
check("schematic: cycles refused", A.parent is None)
# delete an object -> node removed
bpy.data.objects.remove(C)
schematic.sync(tree, bpy.context.scene)
check("schematic: deleted object's node removed", len(tree.nodes) == 2)
# Re-enabling the add-on with a schematic in the file must not touch half-registered nodes.
addon_utils.disable(MOD, default_set=True)
addon_utils.enable(MOD, default_set=True)
schematic = import_module(MOD + ".schematic")
tree = schematic.get_tree()
check("schematic survives add-on reload", tree is not None and len(tree.nodes) == 2)
for pt in ("header", "kinematics", "visibility", "data", "material", "constraints"):
    check(f"property page panel {pt}", hasattr(bpy.types, f"MS_PT_ppg_{pt}"))

# Scene operations
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.active_object
cube.location = (1, 2, 3)
cube.scale = (2, 2, 2)
bpy.ops.mr_softie.reset_srt(kind='T')
check("reset translation", tuple(cube.location) == (0, 0, 0) and cube.scale[0] == 2)
bpy.ops.mr_softie.reset_srt(kind='ALL')
check("reset all", cube.scale[0] == 1)

cube.modifiers.new("bevel", 'BEVEL')
verts_before = len(cube.data.vertices)
bpy.ops.mr_softie.freeze()
check("freeze applies modifiers", len(cube.modifiers) == 0 and len(cube.data.vertices) > verts_before)

bpy.ops.mr_softie.component_mode(component='EDGE')
check("E -> edit mode, edge select",
      bpy.context.mode == 'EDIT_MESH' and tuple(bpy.context.tool_settings.mesh_select_mode) == (False, True, False))
bpy.ops.mr_softie.component_mode(component='FACE')
check("Y -> polygon select", tuple(bpy.context.tool_settings.mesh_select_mode) == (False, False, True))
bpy.ops.mr_softie.object_select()
check("Space -> back to object mode", bpy.context.mode == 'OBJECT')

theme = bpy.context.preferences.themes[0]
before = tuple(theme.view_3d.space.gradients.high_gradient)
bpy.ops.mr_softie.apply_theme()
after = tuple(theme.view_3d.space.gradients.high_gradient)
check("gray theme applied", abs(after[0] - 0.5) < 0.01 and before != after)
check("theme widget text black", tuple(theme.user_interface.wcol_regular.text)[:3] == (0, 0, 0))
bpy.ops.mr_softie.reset_theme()
check("theme reset", tuple(theme.view_3d.space.gradients.high_gradient) != after)

# ICE compounds (Geometry Nodes)
ice = import_module(MOD + ".ice")
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add()
ice_cube = bpy.context.active_object
bpy.ops.mesh.primitive_ico_sphere_add(radius=0.1, location=(5, 0, 0))
ice_inst = bpy.context.active_object
for key in ice.BUILDERS:
    for m in list(ice_cube.modifiers):
        ice_cube.modifiers.remove(m)
    if key == 'EMIT':
        ice_inst.select_set(True)
        ice_cube.select_set(True)
        bpy.context.view_layer.objects.active = ice_cube
        res = bpy.ops.mr_softie.ice_compound(compound='EMIT')
        mod = ice_cube.modifiers[-1]
    else:
        mod = ice.apply_compound(ice_cube, key)
        res = {'FINISHED'}
    check(f"ice {key} links valid", res == {'FINISHED'} and all(l.is_valid for l in mod.node_group.links))
    for f in range(1, 11):   # simulations only advance frame by frame
        bpy.context.scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ice_cube.evaluated_get(dg)
    me = ev.to_mesh()
    z0 = me.vertices[0].co.z
    ev.to_mesh_clear()
    if key == 'EMIT':
        n = sum(1 for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == ice_cube)
        check("ice emit scatters instances", n > 10 and ice.get_input(mod, "Instance") == ice_inst)
        check("ice emit hides source from render", ice_inst.hide_render)
    elif key == 'PARTICLES':
        g = ev.evaluated_geometry()
        zs = [p.vector.z for p in g.pointcloud.attributes["position"].data] if g.pointcloud else []
        check("ice particles fall", zs and min(zs) < -1.5)
    elif key not in {'STRANDS', 'SWARM', 'STRAND_DYNAMICS'}:
        check(f"ice {key} moves points", abs(z0 + 1.0) > 0.01)
bpy.context.scene.frame_set(1)
check("ice compound groups reused", len([g for g in bpy.data.node_groups if g.name.startswith("ICE Push")]) == 1)

# More ICE: strands, turbulence, particle floor
for m in list(ice_cube.modifiers):
    ice_cube.modifiers.remove(m)
mod = ice.apply_compound(ice_cube, 'STRANDS')
bpy.context.scene.frame_set(1)
g = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
check("ice strands grow curves", g.curves is not None and len(g.curves.curves) > 50)
ice_cube.modifiers.remove(mod)
mod = ice.apply_compound(ice_cube, 'TURBULENCE')
zs = []
for f in (1, 30):
    bpy.context.scene.frame_set(f)
    me = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    zs.append(tuple(me.vertices[0].co))
    ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
check("ice turbulence animates", zs[0] != zs[1] and abs(zs[0][2] + 1) > 1e-4)
ice_cube.modifiers.remove(mod)
mod = ice.apply_compound(ice_cube, 'PARTICLES')
ice.set_input(mod, "Floor", True)
ice.set_input(mod, "Floor Height", -1.5)
for f in range(1, 41):
    bpy.context.scene.frame_set(f)
g = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
zs = [p.vector.z for p in g.pointcloud.attributes["position"].data]
check("ice particles stop at the floor", zs and min(zs) >= -1.5 - 1e-4)
ice_cube.modifiers.remove(mod)
bpy.context.scene.frame_set(1)

# Phase 6 ICE: collider, swarm, strand wind
bpy.ops.mesh.primitive_plane_add(size=50, location=(0, 0, -3))
floor_obj = bpy.context.active_object
bpy.ops.object.select_all(action='DESELECT')
floor_obj.select_set(True)
ice_cube.select_set(True)
bpy.context.view_layer.objects.active = ice_cube
check("particles take selected collider", bpy.ops.mr_softie.ice_compound(compound='PARTICLES') == {'FINISHED'})
mod = ice_cube.modifiers[-1]
check("collider input set", ice.get_input(mod, "Collider") == floor_obj)
for f in range(1, 80):
    bpy.context.scene.frame_set(f)
g = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
zs = [p.vector.z for p in g.pointcloud.attributes["position"].data]
check("particles collide with the collider", zs and min(zs) > -3.01)
ice_cube.modifiers.remove(mod)
bpy.ops.object.empty_add(location=(10, 0, 0))
goal_obj = bpy.context.active_object
goal_obj.select_set(True)
ice_cube.select_set(True)
bpy.context.view_layer.objects.active = ice_cube
bpy.ops.mr_softie.ice_compound(compound='SWARM')
mod = ice_cube.modifiers[-1]
check("swarm goal set", ice.get_input(mod, "Goal") == goal_obj)
for f in range(1, 60):
    bpy.context.scene.frame_set(f)
g = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
xs = [p.vector.x for p in g.pointcloud.attributes["position"].data]
check("swarm flies toward goal", xs and sum(xs) / len(xs) > 3)
ice_cube.modifiers.remove(mod)
mod = ice.apply_compound(ice_cube, 'STRANDS')
ice.set_input(mod, "Wind", 0.5)
def _tips():
    g = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
    return [tuple(p.vector) for p in g.curves.attributes["position"].data][:4]
bpy.context.scene.frame_set(1)
a = _tips()
bpy.context.scene.frame_set(30)
b = _tips()
check("strand wind sways tips, roots stay", a[0] == b[0] and a[1] != b[1])
ice_cube.modifiers.remove(mod)
for o in (floor_obj, goal_obj):
    bpy.data.objects.remove(o)
bpy.context.scene.frame_set(1)

# Script editor
scripting = import_module(MOD + ".scripting")
check("script editor operator", hasattr(bpy.ops.mr_softie, "open_script_editor"))
check("last command label", isinstance(scripting.last_command_label(bpy.context), str))
scripting.note_command(bpy.context, "mr_softie.save_key")
check("button commands show on the script line", scripting.last_command_label(bpy.context) == "Save Key")
km_items = [kmi for km in kc.keymaps for kmi in km.keymap_items if kmi.idname == "mr_softie.open_script_editor"]
check("Alt+4 opens script editor", any(k.type == 'FOUR' and k.alt for k in km_items))

# Phase 7: strand dynamics, flock spacing
mod1 = ice.apply_compound(ice_cube, 'STRANDS')
mod2 = ice.apply_compound(ice_cube, 'STRAND_DYNAMICS')
check("strand dynamics links valid", all(l.is_valid for l in mod2.node_group.links))
bpy.context.scene.frame_set(1)
g = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
a = [tuple(p.vector) for p in g.curves.attributes["position"].data][:3]
check("strands have 8 points each", len(g.curves.attributes["position"].data) == 8 * len(g.curves.curves))
for f in range(2, 25):
    bpy.context.scene.frame_set(f)
g = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
b = [tuple(p.vector) for p in g.curves.attributes["position"].data][:3]
check("strand dynamics: root pinned, tip droops", a[0] == b[0] and b[2][2] < a[2][2])
check("strand dynamics keeps the mesh", g.mesh is not None and len(g.mesh.vertices) == 8)
for m in (mod2, mod1):
    ice_cube.modifiers.remove(m)
mod = ice.apply_compound(ice_cube, 'SWARM')
for f in range(1, 60):
    bpy.context.scene.frame_set(f)
g = ice_cube.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
ps = [p.vector.copy() for p in g.pointcloud.attributes["position"].data]
nn = min(min((p - q).length for j, q in enumerate(ps) if j != i) for i, p in enumerate(ps[:40]))
check("flock keeps members apart", nn > 0.05)
ice_cube.modifiers.remove(mod)
bpy.ops.object.select_all(action='DESELECT')
ice_cube.select_set(True)
bpy.context.view_layer.objects.active = ice_cube
bpy.ops.mr_softie.ice_compound(compound='STRAND_DYNAMICS')
check("strand dynamics grows strands first", [m.name for m in ice_cube.modifiers][-2:] == ["ICE Grow Strands", "ICE Strand Dynamics"])
ice_cube.modifiers.clear()
bpy.context.scene.frame_set(1)

# Passes, partitions, channels
scene = bpy.context.scene
win = bpy.context.window_manager.windows[0] if bpy.context.window_manager.windows else None
n_layers = len(scene.view_layers)
bpy.context.view_layer.objects.active = ice_cube
with bpy.context.temp_override(window=win) if win else nullcontext():
    bpy.ops.mr_softie.pass_new()
check("pass new adds view layer", len(scene.view_layers) == n_layers + 1)
check("pass new keeps active object", bpy.context.view_layer.objects.active is not None)
ice_cube.select_set(True)
bpy.context.view_layer.objects.active = ice_cube
bpy.ops.mr_softie.partition_new()
part = scene.collection.children[-1]
check("partition holds selection", ice_cube.name in part.objects and part.get("mr_softie_partition"))
passes = import_module(MOD + ".passes")
lc = passes._find_layer_collection(bpy.context.view_layer.layer_collection, part)
check("partition layer collection found", lc is not None)
check("channels exist", sum(hasattr(bpy.context.view_layer, a) for a, _ in passes.CHANNELS) >= 6)
for fn in (passes.draw_passes, passes.draw_partitions, passes.draw_channels):
    check(f"{fn.__name__} callable", callable(fn))

# Render region per pass
r = scene.render
first = passes.current_pass(bpy.context)
r.use_border, r.border_min_x = True, 0.25
with bpy.context.temp_override(window=win) if win else nullcontext():
    bpy.ops.mr_softie.pass_new()
second = passes.current_pass(bpy.context)
if win is None:
    # Headless: no window to hold the current pass; exercise the helpers directly.
    passes.save_region(scene, first)
    r.use_border, r.border_min_x = False, 0.0
    passes.save_region(scene, second)
    passes.load_region(scene, first)
    check("render region restored per pass", r.use_border and abs(r.border_min_x - 0.25) < 1e-6)
    passes.load_region(scene, second)
    check("other pass keeps its own region", not r.use_border)
else:
    r.use_border = False
    passes.switch_pass(bpy.context, first)
    check("render region restored per pass", r.use_border and abs(r.border_min_x - 0.25) < 1e-6)

# Mixer clip
bpy.ops.object.select_all(action='DESELECT')
ice_cube.select_set(True)
ice_cube.keyframe_insert("location", frame=1)
ice_cube.location.x = 3
ice_cube.keyframe_insert("location", frame=20)
res = bpy.ops.mr_softie.store_clip()
ad = ice_cube.animation_data
check("store clip moves action to mixer", res == {'FINISHED'} and ad.action is None
      and len(ad.nla_tracks) == 1 and len(ad.nla_tracks[0].strips) == 1)
bpy.context.scene.frame_set(20)
check("clip still animates", abs(ice_cube.matrix_world.translation.x - 3) < 1e-3)
check("ICE module in toolbar", 'ICE' in toolbar.SECTIONS)

# Classic keying and timeline strip
anim = import_module(MOD + ".anim")
bpy.ops.object.select_all(action='DESELECT')
ice_cube.select_set(True)
bpy.context.view_layer.objects.active = ice_cube
bpy.context.window_manager.mr_softie_marked = 'T'
bpy.context.scene.frame_set(5)
check("save key runs", bpy.ops.mr_softie.save_key() == {'FINISHED'})
paths = {fc.data_path for fc in anim.fcurves(ice_cube)}
check("save key keys only marked params", "location" in paths and "scale" not in paths)
check("key state on key", anim.key_state(ice_cube, 5, ("location",)) == 'KEY')
check("key state animated", anim.key_state(ice_cube, 6, ("location",)) == 'ANIM')
bpy.ops.mr_softie.remove_key()
check("remove key", anim.key_state(ice_cube, 5, ("location",)) != 'KEY')
bpy.context.window_manager.mr_softie_marked = 'SRT'
check("timeline header wrapped", hasattr(bpy.types.DOPESHEET_HT_header.draw, "_mr_softie_original"))
km_items = [kmi for km in kc.keymaps for kmi in km.keymap_items if kmi.idname == "mr_softie.save_key"]
check("K saves key", any(k.type == 'K' for k in km_items))
ice_cube.animation_data_clear()
bpy.context.scene.frame_set(1)

# Pass presets
n_layers = len(scene.view_layers)
with bpy.context.temp_override(window=win) if win else nullcontext():
    bpy.ops.mr_softie.pass_preset(preset='DEPTH')
depth = scene.view_layers[-1]
check("pass preset adds pass with channels", len(scene.view_layers) == n_layers + 1
      and depth.name.startswith("Depth") and depth.use_pass_z and depth.use_pass_mist)
check("pass preset menu", hasattr(bpy.types, "MS_MT_pass_presets"))

# Preference toggles re-register cleanly
prefs = bpy.context.preferences.addons[MOD].preferences
tools = import_module(MOD + ".tools")
prefs.use_keymap = False
left_over = [kmi for km in kc.keymaps for kmi in km.keymap_items if kmi.idname.startswith("mr_softie.")]
check("keymap off removes items", len(left_over) == 0)
prefs.use_keymap = True
prefs.mouse_axis_mode = 'FREE'
check("tools re-register on mode change", len(tools._registered) == 7)

addon_utils.disable(MOD, default_set=True)
left_over = [kmi for km in kc.keymaps for kmi in km.keymap_items if kmi.idname.startswith("mr_softie.")]
check("disable removes keymap", len(left_over) == 0)
check("disable removes panels", not hasattr(bpy.types, "MS_PT_mcp_select")
      and not hasattr(bpy.types, "MS_PT_mcpcol_select") and not hasattr(bpy.types, "MS_PT_tb_module"))
check("disable restores viewport header",
      not hasattr(bpy.types.VIEW3D_HT_header.draw, "_mr_softie_original"))
check("disable restores timeline header",
      not hasattr(bpy.types.DOPESHEET_HT_header.draw, "_mr_softie_original"))
check("disable restores menu bar",
      not hasattr(bpy.types.TOPBAR_MT_editor_menus.draw, "_mr_softie_original"))
check("disable restores builtin text panels", "poll" not in bpy.types.TEXT_PT_find.__dict__)
check("disable removes redraw handler",
      not any(h.__name__ == "_on_depsgraph_update" for h in bpy.app.handlers.depsgraph_update_post))
check("disable removes tools", len(tools._registered) == 0)
check("disable stops manipulator sync", not bpy.app.timers.is_registered(tools._sync_manipulator))

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
