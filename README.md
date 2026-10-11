# MR.Softie

A classic SI-style workflow for Blender. It's for people who learned 3D on the old-school gray DCC and still reach for V, C, X and the spacebar.

MR.Softie is free and open source (GPL-3.0-or-later). It is **not affiliated with or endorsed by Autodesk**. All names, icons and artwork here are original; the project recreates *workflow*, not anyone's software.

![MR.Softie workspace](docs/screenshot.png)

## What's in 0.2

**The MR.Softie workspace.** Press **N** in any 3D view, open the **MCP** tab and click **Classic Layout**. You get a dedicated **MR.Softie** workspace tab:

- **Module toolbar** on the left: switch between **Model / Animate / Render / Simulate**, each with its own collapsible command stacks.
- **Four views** in the middle: Top, Front, Right and Perspective.
- **The MCP** as a full-height column on the right.
- **Timeline** along the bottom, and a **mouse status line** that always shows what Left / Middle / Right do right now.
- **Gray theme**: light-gray UI with black text, flat gray viewports, black wires, white selection. **Reset** restores Blender's theme.

**Module toolbar**

| Module | Sections |
|---|---|
| Model | Get (Primitive, Light, Camera, Material), Create (Curve, Text, Skeleton, Lattice), Modify (Extrude, Bevel, Subdivide, Inset, Bridge, Weld, Split, Flip Normals), Deform (Bend, Twist, Taper, Smooth, Symmetry) |
| Animate | Get, Keys (Save / Remove Key, Remove Anim), Create (Path and Track constraints, Skeleton), Editors (Anim Editor, Dopesheet, Mixer) |
| Render | Get (Light, Camera, Material), Render (Frame, Anim, Region, Preview), Editors (Render Tree, Texture Editor, Options) |
| Simulate | Create (Rigid / Passive Body, Cloth, Soft Body, Particles, Forces), Simulate (Play, Bake All, Free Bakes) |

**The MCP**, stacked in the classic order:

| Section | What it does |
|---|---|
| Select | Select tool, Obj / Pnt / Edge / Poly, All / None / Inv, Explore, Branch, name of selection |
| Transform | S / R / T rows with live x/y/z values (the active tool lights up), Reset S / R / T, Global / Local / View / Par / Ref / Norm, COG, Prop, Sym |
| Snap | Snap on/off, Grid / Increment / Vertex / Edge / Face / Edge Center |
| Constrain | Parent, Cut, add constraint, remove all |
| Edit | Freeze (bake modifier stack), Duplicate, Delete, Hide / Unhide, Center to Geo, Reset SRT |
| View | Classic Layout, Four Views, Frame Sel / All, floating Explorer and Curves, Gray Theme |

The MCP is also available as a sidebar tab in every other workspace.

**SRT tools.** Drag *anywhere* in the viewport; no gizmo to grab.

- Left / Middle / Right drag = X / Y / Z
- Shift + Left drag = free (view plane, view axis, or uniform scale)
- Click = select (Shift adds, Ctrl toggles)

**Supra modes.** Tap V / C / X / Space to switch tools. **Hold** one instead and it's a temporary tool: let go and you're back to what you had.

**Classic hotkeys** (can be switched off in preferences):

| Key | Action |
|---|---|
| Space | Object selection (also leaves component mode) |
| V / C / X | Translate / Rotate / Scale (tap to switch, hold for temporary) |
| T / E / Y | Point / Edge / Polygon selection |
| S + Left / Middle / Right | Pan / Dolly / Orbit |
| F / A | Frame selection / Frame all |
| Ctrl+A | Select all |
| Ctrl+D | Duplicate |
| Ctrl+Y | Redo |
| Enter | Floating property editor |
| 7 / 8 / 0 | Shader editor / Outliner (explorer) / Graph editor |

## Install

Requires Blender 4.2 or newer (tested on 5.2).

**Recommended: add MR.Softie as a repository (you get updates automatically)**

1. In Blender, go to **Edit → Preferences → Get Extensions**. If it asks, click **Allow Online Access** (or turn it on under **System → Network**).
2. Open the **Repositories** dropdown (top right) and click **+ → Add Remote Repository**.
3. Paste this URL and turn on **Check for Updates on Startup**:
   ```
   https://raw.githubusercontent.com/JavTsPlayground/mr-softie/main/download/index.json
   ```
4. Search **MR.Softie** in Get Extensions and click **Install**. (If you installed it from a zip before, uninstall that copy first.)
5. In the 3D view, press **N**, open the **MCP** tab, and click **Classic Layout**. From then on, just click the **MR.Softie** workspace tab.

**Or install the zip once by hand:** **[download mr_softie-0.2.0.zip](https://github.com/JavTsPlayground/mr-softie/raw/main/download/mr_softie-0.2.0.zip)** (don't unzip it), then **Get Extensions → ▾ → Install from Disk**. You won't get automatic updates this way.

A step-by-step setup guide with troubleshooting is in [docs/MR-Softie-Setup-Guide.pdf](docs/MR-Softie-Setup-Guide.pdf).

## Known differences from the original

- These hotkeys replace Blender's own: Space (play), C (circle select), V (rip, in edit mode), X (delete), E (extrude), A (select all), F (fill), T (toolbar), S (scale), and 7/8/0 when number keys are enabled. Turn **Classic Hotkeys** off in preferences to get Blender's back.
- Blender has no direct equivalents for the schematic view or ICE. These are on the roadmap.
- The toolbar and MCP columns show a small vertical tab label ("Toolbar", "MCP"); Blender always draws one.
- The layout's column widths are tuned at 1920x1080. On other screens, click **Classic Layout** again to snap them back.

## Roadmap

- Schematic view (hierarchy graph)
- Explorer with classic filters
- Tag-style raycast component selection
- Transform setup: "remember last tool" per selection
- Timeline / playback strip in the classic style
- Original icon set

## Development

```bash
pip install bpy
python tests/test_headless.py
```

To release a new version: bump `version` in `mr_softie/blender_manifest.toml`, zip `mr_softie/` into `download/mr_softie-<version>.zip`, delete the old zip, then regenerate the index with `blender --command extension server-generate --repo-dir download`.
