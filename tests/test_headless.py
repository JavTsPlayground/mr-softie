"""Headless smoke test. Run with: python tests/test_headless.py (needs `pip install bpy`)."""
import os
import sys

import bpy  # must come first: puts Blender's modules on sys.path
import addon_utils

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "gray_matter")

repo_dir = bpy.utils.user_resource('EXTENSIONS', path="user_default", create=True)
link = os.path.join(repo_dir, "gray_matter")
if not os.path.exists(link):
    os.symlink(SRC, link)

MOD = "bl_ext.user_default.gray_matter"
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
            if kmi.idname.startswith("gray_matter.") or kmi.key_modifier == 'S']
check(f"keymap items registered ({len(gm_items)})", len(gm_items) >= 40)
check("S-modifier nav present", any(k.idname == "view3d.rotate" and k.key_modifier == 'S'
                                    and k.type == 'RIGHTMOUSE' for k in gm_items))

for name in ("srt_tool", "object_select", "component_mode", "open_editor", "quad_view",
             "classic_layout", "freeze", "reset_srt", "apply_theme", "reset_theme", "swallow"):
    check(f"operator gray_matter.{name}", hasattr(bpy.ops.gray_matter, name)
          and bpy.ops.gray_matter.__getattr__(name).idname_py())

for pt in ("GM_PT_mcp_select", "GM_PT_mcp_transform", "GM_PT_mcp_snap",
           "GM_PT_mcp_constrain", "GM_PT_mcp_edit", "GM_PT_mcp_view"):
    check(f"panel {pt}", hasattr(bpy.types, pt))

# Tool keymaps: the tool system creates them when tools register.
from importlib import import_module
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
bpy.ops.gray_matter.reset_srt(kind='T')
check("reset translation", tuple(cube.location) == (0, 0, 0) and cube.scale[0] == 2)
bpy.ops.gray_matter.reset_srt(kind='ALL')
check("reset all", cube.scale[0] == 1)

cube.modifiers.new("bevel", 'BEVEL')
verts_before = len(cube.data.vertices)
bpy.ops.gray_matter.freeze()
check("freeze applies modifiers", len(cube.modifiers) == 0 and len(cube.data.vertices) > verts_before)

bpy.ops.gray_matter.component_mode(component='EDGE')
check("E -> edit mode, edge select",
      bpy.context.mode == 'EDIT_MESH' and tuple(bpy.context.tool_settings.mesh_select_mode) == (False, True, False))
bpy.ops.gray_matter.component_mode(component='FACE')
check("Y -> polygon select", tuple(bpy.context.tool_settings.mesh_select_mode) == (False, False, True))
bpy.ops.gray_matter.object_select()
check("Space -> back to object mode", bpy.context.mode == 'OBJECT')

theme = bpy.context.preferences.themes[0]
before = tuple(theme.view_3d.space.gradients.high_gradient)
bpy.ops.gray_matter.apply_theme()
after = tuple(theme.view_3d.space.gradients.high_gradient)
check("gray theme applied", abs(after[0] - 0.5) < 0.01 and before != after)
check("theme widget text black", tuple(theme.user_interface.wcol_regular.text)[:3] == (0, 0, 0))
bpy.ops.gray_matter.reset_theme()
check("theme reset", tuple(theme.view_3d.space.gradients.high_gradient) != after)

# Preference toggles re-register cleanly
prefs.use_keymap = False
left_over = [kmi for km in kc.keymaps for kmi in km.keymap_items if kmi.idname.startswith("gray_matter.")]
check("keymap off removes items", len(left_over) == 0)
prefs.use_keymap = True
prefs.mouse_axis_mode = 'FREE'
check("tools re-register on mode change", len(tools._registered) == 6)

addon_utils.disable(MOD, default_set=True)
left_over = [kmi for km in kc.keymaps for kmi in km.keymap_items if kmi.idname.startswith("gray_matter.")]
check("disable removes keymap", len(left_over) == 0)
check("disable removes panels", not hasattr(bpy.types, "GM_PT_mcp_select"))
check("disable removes tools", len(tools._registered) == 0)

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
