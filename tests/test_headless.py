"""Headless smoke test. Run with: python tests/test_headless.py (needs `pip install bpy`)."""
import os
import sys

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
             "INSTALL_APP_TEMPLATE"):
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


missing = [f"{a}.{b}" for a, b in sorted(refs) if not _op_exists(a, b)]
check(f"all {len(refs)} referenced operators exist (missing: {missing})", not missing)

# Tool keymaps: the tool system creates them when tools register.
tools = import_module(MOD + ".tools")
check("6 SRT tools registered", len(tools._registered) == 6)
km = tools.build_keymap("transform.rotate", 'XYZ')
check("tool keymap: S-nav listed first", km[0][1].get("key_modifier") == 'S')
right = [i for i in km if i[1]["type"] == 'RIGHTMOUSE' and not i[1].get("key_modifier")][0]
check("rotate RMB constrains Z", ("orient_axis", 'Z') in right[2]["properties"])
free = tools.build_keymap("transform.translate", 'FREE')
left = [i for i in free if i[1]["type"] == 'LEFTMOUSE' and i[1]["value"] == 'CLICK_DRAG'
        and not i[1].get("shift")][0]
check("FREE mode: left drag unconstrained",
      not any(p[0] == "constraint_axis" for p in left[2]["properties"]))

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

# Preference toggles re-register cleanly
prefs.use_keymap = False
left_over = [kmi for km in kc.keymaps for kmi in km.keymap_items if kmi.idname.startswith("mr_softie.")]
check("keymap off removes items", len(left_over) == 0)
prefs.use_keymap = True
prefs.mouse_axis_mode = 'FREE'
check("tools re-register on mode change", len(tools._registered) == 6)

addon_utils.disable(MOD, default_set=True)
left_over = [kmi for km in kc.keymaps for kmi in km.keymap_items if kmi.idname.startswith("mr_softie.")]
check("disable removes keymap", len(left_over) == 0)
check("disable removes panels", not hasattr(bpy.types, "MS_PT_mcp_select")
      and not hasattr(bpy.types, "MS_PT_mcpcol_select") and not hasattr(bpy.types, "MS_PT_tb_module"))
check("disable restores viewport header",
      not hasattr(bpy.types.VIEW3D_HT_header.draw, "_mr_softie_original"))
check("disable restores menu bar",
      not hasattr(bpy.types.TOPBAR_MT_editor_menus.draw, "_mr_softie_original"))
check("disable restores builtin text panels", "poll" not in bpy.types.TEXT_PT_find.__dict__)
check("disable removes redraw handler",
      not any(h.__name__ == "_on_depsgraph_update" for h in bpy.app.handlers.depsgraph_update_post))
check("disable removes tools", len(tools._registered) == 0)

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
