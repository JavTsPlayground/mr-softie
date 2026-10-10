# MR.Softie

A classic SI-style workflow for Blender. It's for people who learned 3D on the old-school gray DCC and still reach for V, C, X and the spacebar.

MR.Softie is free and open source (GPL-3.0-or-later). It is **not affiliated with or endorsed by Autodesk**. All names, icons and artwork here are original; the project recreates *workflow*, not anyone's software.

## What's in 0.1

**The MCP.** A main command panel docked on the right of the 3D view (sidebar tab "MCP"), stacked in the classic order:

| Section | What it does |
|---|---|
| Select | Select tool, Obj / Pnt / Edge / Poly modes, All / None / Invert, Select Branch, name of selection |
| Transform | S / R / T rows with live x/y/z fields and per-row reset; Global / Local / View; pivot; Prop (proportional) |
| Snap | Snap on/off, snap targets |
| Constrain | Parent, Cut, add constraint, remove all |
| Edit | Freeze (bake modifier stack), Duplicate, Delete, Hide/Unhide, Center to Geometry, Reset SRT |
| View | Classic Layout, Four Views, Frame, floating Explorer / Shaders / Curves, Gray Theme |

**SRT tools.** Three tools on the toolbar: SRT Translate, SRT Rotate and SRT Scale. Drag *anywhere* in the viewport. You don't have to grab a gizmo.

- Left / Middle / Right drag = X / Y / Z
- Shift + Left drag = free (view plane, view axis, or uniform scale)
- Click = select (Shift adds, Ctrl toggles)

**Classic hotkeys** (can be switched off in preferences):

| Key | Action |
|---|---|
| Space | Object selection (also leaves component mode) |
| V / C / X | Translate / Rotate / Scale tool |
| T / E / Y | Point / Edge / Polygon selection |
| S + Left / Middle / Right | Pan / Dolly / Orbit |
| F / A | Frame selection / Frame all |
| Ctrl+A | Select all |
| Ctrl+D | Duplicate |
| Ctrl+Y | Redo |
| Enter | Floating property editor |
| 7 / 8 / 0 | Shader editor / Outliner (explorer) / Graph editor |

**Classic Layout** switches to four views (Top, Front, Right, Perspective) with the MCP docked on the right. **Gray Theme** is opt-in. It gives you a light-gray UI with black text, a flat gray viewport, black wires and white selection, and **Reset** restores Blender's theme.

## Install

Requires Blender 4.2 or newer (tested on 5.2).

1. Download `mr_softie-0.1.0.zip` from Releases.
2. In Blender, go to **Edit → Preferences → Get Extensions → ▾ → Install from Disk** and pick the zip.
3. In the 3D view, press **N**, open the **MCP** tab, and click **Classic Layout**.

## Known differences from the original

- These hotkeys replace Blender's own: Space (play), C (circle select), V (rip, in edit mode), X (delete), E (extrude), A (select all), F (fill), T (toolbar), S (scale), and 7/8/0 when number keys are enabled. Turn **Classic Hotkeys** off in preferences to get Blender's back.
- Blender has no direct equivalents for the schematic view, ICE, or the animation mixer. These are on the roadmap.

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

To rebuild the extension zip: `blender --command extension build --source-dir mr_softie`.
