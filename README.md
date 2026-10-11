# MR.Softie

A classic SI-style workflow for Blender. It's for people who learned 3D on the old-school gray DCC and still reach for V, C, X and the spacebar.

MR.Softie is free and open source (GPL-3.0-or-later). It is **not affiliated with or endorsed by Autodesk**. All names, icons and artwork here are original; the project recreates *workflow*, not anyone's software.

![MR.Softie workspace](docs/screenshot.png)

## Features

**The MR.Softie workspace.** Press **N** in any 3D view, open the **MCP** tab and click **Classic Layout**. You get a dedicated **MR.Softie** workspace tab:

- **Module toolbar** on the left: an icon row switches between **Model / Animate / Render / Simulate / ICE**, each with its own collapsible command stacks.
- **Four independent viewports** in the middle, in the classic default arrangement: Top, Camera, Front, Right. Each has its own header with a view menu (Camera, User, Top, Bottom, Front, Back, Right, Left) and a display menu (Wireframe, Shaded, Textured, Material, Rendered), plus maximize / restore.
- **Memo cams**: **1 2 3 4** in every viewport header. Click an empty slot to remember that view, click a full (highlighted) slot to glide back to it. The **▾** next to them stores over a slot or forgets one or all. Saved with the scene.
- **Schematic view** (9, or View > Schematic): the scene graph as color-coded nodes, one per object, with hierarchy links and constraint links. Draw a link from a node's Children output to another node's Parent input to parent it (world position kept); cut the link to unparent. Cycles are refused. Selecting nodes selects objects and the other way round. **Rearrange** lays it out as a tree.
- **Explorer** (8): the scene hierarchy in its own window, with visibility, selectability and render columns.
- **Property pages** (Enter): a floating page for the selected object with Kinematics, Visibility, Display, Geometry/Light/Camera settings, Material and Constraints. Pin one to keep it on a specific object.
- **Classic main menu bar**: File, Edit, Display, View, Render, Window, Help. The View menu opens every editor as a floating window (Explorer, Animation Editor, Mixer, Render Tree, ICE Tree, Script Log...).
- **The MCP** as a full-height column on the right.
- **Timeline** along the bottom, and a **mouse status line** that always shows what Left / Middle / Right do right now.
- **Gray theme**: light-gray UI with black text, flat gray viewports, black wires, white selection. **Reset** restores Blender's theme.
- **Original icon set** for the modules and the most-used MCP buttons (Select, Parent, Cut, Freeze, Reset SRT, Classic Layout, Max / Restore, Explorer, Schematic, Property Page, Script Editor).

**Module toolbar**

| Module | Sections |
|---|---|
| Model | Get (Primitive, Light, Camera, Material presets), Create (Curve, Text, Draw Chain, Lattice), Tools (Add Edge, Split Edge, Weld Points, Weld Edges, Bridge Polygons, Slice Polygons, Add Polygon, Tweak), Poly Mesh (Extrude, Extrude Normal, Bevel, Inset, Bridge, Subdivide, Collapse, Dissolve, Weld / Merge, Filter Points, Split, Symmetrize, Flip Normals, Poly Reduction), Deform (Bend, Twist, Taper, Smooth, Symmetry) |
| Animate | Get, Keys (Save / Remove Key, Remove Anim), Skeleton (Draw Chain, Set Envelope, Weight Paint, Reset Pose, Constrain), Chain (FK / IK blend), Layers, Mixer (Store Clip, Open Mixer), Editors (Anim Editor, Dopesheet) |
| Render | Get (Light, Camera, Material, Texture), Render (Frame, Anim, Region, Preview), Passes, Partitions, Channels, Editors (Render Tree, Material Manager, Texture Editor, Options) |
| Simulate | Create (Rigid / Passive Body, Cloth, Soft Body, Particles, Forces), Simulate (Play, Bake All, Free Bakes) |
| Custom | Your own toolbars (see below) |
| ICE | Create (ICE Tree), Compounds (Emit from Surface, Simulate Particles, Jitter, Push, Grow Strands, Strand Dynamics, Turbulence, Swarm, Trails, Surface Attract), Simulate (Play, Reset, Bake, Free) |

**The MCP**, stacked in the classic order:

| Section | What it does |
|---|---|
| Select | Select tool, Obj / Pnt / Edge / Poly, All / None / Inv, selection filter (All / Geom / Light / Cam / Null / Skel), Explore, Branch, name of selection; Loop / Ring / Grow / Shrink in component mode |
| Transform | S / R / T rows with live x/y/z values (the active tool lights up), Reset S / R / T, Global / Local / View / Par / Ref / Norm, COG, Prop, Sym |
| Snap | Snap on/off, Grid / Increment / Vertex / Edge / Face / Edge Center |
| Constrain | Parent, Cut, add constraint, remove all |
| Edit | Freeze / Freeze M, construction mode, Duplicate, Delete, Hide / Unhide, Center to Geo, Reset SRT |
| Layers | Scene layers: Default plus your own; show / hide, selectable, render, select members, move the selection in, delete |
| View | Classic Layout, Max / Restore, Frame Sel / All, floating Explorer, Schematic, Property Page, Curves and Script Editor, Gray Theme |

The MCP is also available as a sidebar tab in every other workspace.

**SRT tools and manipulator.** Drag *anywhere* in the viewport, or grab the manipulator: arrows for Translate (V), rings for Rotate (C), boxes for Scale (X). Each handle constrains to its axis; the center ring is free. The manipulator can be switched off in preferences.

- Left / Middle / Right drag = X / Y / Z
- Shift + Left drag = free (view plane, view axis, or uniform scale)
- Click = select (Shift adds, Ctrl toggles)

**Selection filters and scene layers.** The MCP's Select section has a **selection filter**: All, Geom, Light, Cam, Null, Skel. With Light on, clicks and boxes only pick lights. It uses each viewport's own per-type selectability, so your objects aren't changed. The MCP's **Layers** section is the Layer Control: every object is in **Default** until you move it, **New Layer from Selection** makes a layer, and each row has show / hide, selectable, render, move-the-selection-here and delete; click the name to select its objects. Layers and render partitions are separate, as before: an object can be in one of each. A layer owns its objects' hidden / unselectable / render flags.

**Construction modes.** Every object's operator stack (Blender modifiers) is grouped into the classic regions, bottom to top: **Modeling**, **Shape Modeling** (shape keys), **Animation** (deformers) and **Secondary Shape** (smoothing, cloth, soft body...). The **construction mode** (MCP > Edit, or the property page) decides where new operators go; **Auto** puts each one where it belongs by type. The stack stays in region order on its own: add a Bend and then a Subdivision, and the Subdivision slides under the Bend. The property page's **Construction** section shows the regions and lets you move an operator to another one. **Freeze M** applies the Modeling region only, so deformers and simulations on top stay live; **Freeze** still bakes everything.

- In Blender shape keys always evaluate before every modifier, so Shape Modeling works, but sits under the Modeling region instead of over it.
- Freeze M can't run on meshes with shape keys or meshes shared between objects (Blender can't apply modifiers there); it tells you which.

**Polygon modeling.** Every Tools and Poly Mesh button drops into component mode by itself, so you can click them straight from object mode.

- **Weld Points**: drag a point onto another one and they merge where the second one was. The tool stays on for the next weld; right-click or Esc to stop. A yellow rubber band shows what you're welding.
- **Split Edge**: click anywhere on an edge to add a point there (the edge under the mouse lights up first). Stays on until right-click or Esc.
- **Weld Edges**: drag an edge onto another; each end merges into the nearer end of the target.
- **Bridge Polygons**: click a polygon, then another with the same number of points: both are replaced by a tube joining them. The polygons under the mouse are outlined as you go.
- **Selection**: in component mode the MCP's Select section has **Loop**, **Ring**, **Grow** and **Shrink**.
- **Polygon Reduction** has its own section on the property page (Enter): **Keep** slider, keep symmetry, and the live polygon count before and after.
- **Slice Polygons**: drag a line to cut through the mesh. **Add Polygon**: build polygons point by point.
- **Collapse**, **Dissolve**, **Filter Points** (merge points closer than a distance), **Symmetrize**, **Extrude Normal** and **Poly Reduction** (a Decimate modifier you can tune) are one click each.
- Weld Points, Weld Edges and Split Edge pick the nearest point or edge on screen, hidden or not: turn on X-ray, or turn the view, if what you want is behind something.

**Component tools.** **Tweak** (M): drag a point, edge, polygon or object to move it directly. **Raycast** (MCP > Select, in component mode): paint over visible components to select them, Shift adds, Ctrl removes. **Add Edge** (`\` or Modify > Add Edge): cut new edges across polygons.

**ICE compounds.** ICE trees are Geometry Nodes trees, so everything stays editable. Each compound is a node group you can open, tweak and reuse:

- **Emit from Surface**: select the object to scatter, then the surface last. Copies land all over the surface with random rotation and scale; the source object is hidden from render.
- **Simulate Particles**: points shoot off the surface along its normals and fall under gravity (a simulation zone). Press Play; Bake to cache.
- Particles can bounce off a floor: turn on **Floor** in the modifier and set **Floor Height** and **Bounce**.
- Particles collide with any mesh: select the collider, then the emitter last, and click **Simulate Particles** (or pick a **Collider** in the modifier). They land on its surface and bounce.
- **Swarm**: a flock. Each member keeps its distance from its nearest neighbor (**Separation**, **Personal Space**), matches its heading (**Alignment**), drifts toward the flock's center (**Cohesion**), wanders, and flies toward a **Goal** object (select the goal, then the emitter last). Without a goal it circles the emitter. Pick an **Instance** object in the modifier and copies fly along, facing the way they move.
- **Grow Strands**: hair-like curves growing out of the surface, with length variation and thickness. Turn up **Wind** and they sway, more at the tips.
- **Strand Dynamics**: makes strands move like hair. They droop under **Gravity**, sway in **Wind**, and lag and overshoot when you animate the object; stiffer at the root, looser at the tip. They keep their length (**Keep Length** sets how hard it tries), and stay outside the body (**Collide With Body**) and an optional **Collider** object. Click it on a mesh without strands and it grows them first.
- **Trails**: motion trails behind the particles or swarm (it adds a Swarm if the object has nothing emitting yet). **Length** sets how many frames they trail, **Thickness** their width; they taper to the tail.
- **Surface Attract**: pulls the particles or swarm onto another object's surface (select the target, then the emitter last). **Strength** from a gentle pull to stuck on.
- **Turbulence**: animated noise that keeps moving the points as the frame changes.
- **Jitter** and **Push**: random offset, and inflate / deflate along normals.

Change Density, Seed, Speed, Gravity and so on in the modifier, or open the tree with **ICE Tree**.

**Render Region (Q).** Press **Q** and drag a box in any viewport: that viewport renders live inside the box while the rest keeps its wireframe or shaded display. **Q** again redraws it; **Q** then a click, or **Shift+Q**, removes it and puts the viewport back. Also on Render > Render Region / Remove Region. Looking through the camera, Blender uses the scene's render region for this, so while a region is up there it also limits F12 renders; removing it clears that.

**Render Tree.** In the Render (or Model) module:

- **Get > Material**: presets on the selection: Lambert, Phong, Blinn, Constant (flat, unlit), Glass, Chrome, Brushed Metal, Glossy Plastic, Rubber, Car Paint. They're ordinary node materials you can open and change in the Render Tree. The same menu has **Assign Existing** and the **Material Manager** (every material in the file, in its own window).
- **Get > Texture**: Image (asks for a file), Checker, Noise, Gradient, Cell. Each goes into the active material with texture coordinates and a placement node, wired into its color; an object with no material gets a Phong first.
- Render Tree, Animation Editor and other node / curve windows now open framed on their contents.

**Render passes and partitions.** In the Render module:

- **Passes** lists every pass (Blender view layer). Click one to make it current, **New** / **Delete**, rename, and **Render** renders only the current one. **Preset** makes a pass with its channels already on: Beauty, Diffuse, Specular, Shadow, Ambient Occlusion, Depth, Normal, Matte. **Region** / **Draw** set a render region, and each pass remembers its own.
- **Partitions** are the scene's top-level collections. **New from Selection** moves the selected objects into a new partition. Each row is per pass: the checkbox shows or hides the partition in this pass, then Matte (holdout) and Indirect (casts shadows and reflections without being seen).
- **Channels**: Depth, Normal, Mist, AO, Diffuse, Emit, Object and Material ID mattes for the current pass.

**Timeline and keying.** The bottom strip in the MR.Softie workspace reads left to right: Start / End, transport (first, previous key, previous frame, play backward, play, next frame, next key, last), current frame, **RT** (real-time playback, drops frames to keep speed) and frame rate, then the animation controls:

- **Key** (or **K**) saves a key on the *marked* parameters of the selection. The button turns red when the active object has a key on this frame, and highlights when it's animated but not keyed here.
- **SRT / S / R / T** chooses which parameters are marked.
- **Auto** is auto-key; the key icon next to it removes the key on this frame.

**Script Editor** (**Alt+4**, View > Script Editor, or MCP > View): one window with the command log on top (every command you run, as Python) and a script editor underneath; copy lines down and press Run Script. The status bar's script line shows the last command; click it to open the Script Editor.

**Rigging** (Animate > Skeleton). **Draw Chain**: click joint by joint in any viewport (on the plane through the 3D cursor, facing you), right-click or Enter to finish. You get a chain of connected bones and an **Effector** null at the tip: move the effector and the chain follows with IK. The **Chain** section has the **FK / IK** blend slider and how many bones the IK drives. **Constrain** has the classic presets: Position, Orientation, Direction, Pose, Scaling, Path (select the objects to constrain, then the target last). **Set Envelope** (select the mesh, then the skeleton last) binds a mesh to a skeleton with automatic weights; **Weight Paint** to touch them up; **Reset Pose** puts skeletons back at rest.

**Animation layers** (Animate > Layers). **New** moves the selected object's animation onto a **Base** layer and adds Layer 1 on top; from then on **K** / Save Key keys into the current layer, added to everything below it, while Base keeps playing. Keys are set so the pose you see is the pose you get. Each layer has a weight slider and an eye to mute it; click a layer to make it current (click it again to stop editing layers). **Merge** bakes all layers into one plain animation and removes them.

**Custom toolbars** (toolbar module 6, Custom). Run any command, then **Add Command**: you get a button that repeats it with the same settings. Write a few lines in the Script Editor (Alt+4), select them (or not, for the whole script), then **Add Script**: a button that runs them. **New Toolbar** makes more toolbars; click a toolbar's name to make it the one new buttons go into. **Edit Buttons** shows rename / move up / move down / delete on every button and toolbar. **Export** / **Import** share them as a .json file (script buttons run Python, so only import files you trust). Toolbars are saved in your user settings, so they're there in every scene.

**Mixer clips.** Animate > Mixer > **Store Clip** moves the selection's animation onto a Mixer (NLA) track as a clip, so you can layer, blend and reuse it.

**Supra modes.** Tap V / C / X / Space to switch tools. **Hold** one instead and it's a temporary tool: let go and you're back to what you had. Object mode and component mode each remember their last tool, so switching back and forth (Space, T / E / Y) puts you back on the tool you were using.

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
| K | Save Key on the marked parameters |
| Alt+4 | Script Editor |
| Q / Shift+Q | Render Region: drag a live render box in any viewport / remove it |
| Enter | Property page for the selection |
| M | Tweak tool |
| \ | Add Edge (component mode) |
| Alt + Right click | Context menu |
| 1 / 2 / 3 / 4 / 5 / 6 | Toolbar module: Model / Animate / Render / Simulate / ICE / Custom |
| 7 / 8 / 9 / 0 | Render tree / Explorer / Schematic / Animation editor |

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

**Or install the zip once by hand:** **[download mr_softie-2.3.0.zip](https://github.com/JavTsPlayground/mr-softie/raw/main/download/mr_softie-2.3.0.zip)** (don't unzip it), then **Get Extensions → ▾ → Install from Disk**. You won't get automatic updates this way.

**Optional: open Blender straight into MR.Softie.** In the add-on's preferences (or **Edit > Install MR.Softie App Template**), click **Install App Template**. MR Softie then shows up in **File > New** and on the splash screen.

A five-page setup and quick-start guide (install, tour, hotkeys, troubleshooting) is in [docs/MR-Softie-Setup-Guide.pdf](docs/MR-Softie-Setup-Guide.pdf).

## Known differences from the original

- These hotkeys replace Blender's own: Space (play), Q (quick favorites), K (keying menu; knife is on `\`), C (circle select), V (rip, in edit mode), X (delete), E (extrude), A (select all), F (fill), T (toolbar), S (scale), and 5/7/8/0 when number keys are enabled. Turn **Classic Hotkeys** off in preferences to get Blender's back.
- ICE is built on Geometry Nodes: compounds are node groups, and the ICE Tree is the Geometry Nodes editor. Node names are Blender's.
- Partitions are collections, so a partition belongs to every pass; what changes per pass is whether it's visible, a matte or indirect.
- The toolbar and MCP columns show a small vertical tab label ("Toolbar", "MCP"); Blender always draws one.
- The classic headers and menu bar only appear in the MR.Softie workspace; every other workspace stays stock Blender.
- The layout's column widths are tuned at 1920x1080. On other screens, click **Classic Layout** again to snap them back.

## Roadmap

- Ghosting (see an animated object on nearby frames)
- Rigging: up-vector (pole) helper for chains, spine and biped guides
- ICE: strand-to-strand collisions (needs a fast "nearest point on another strand" lookup Geometry Nodes doesn't have yet), Flock avoidance of obstacles

## Development

```bash
pip install bpy
python tests/test_headless.py      # must end with "0 failure(s)"
python docs/make_guide.py          # rebuild the setup guide (needs reportlab + pillow)
python docs/make_icons.py          # redraw the icon set into mr_softie/icons (needs pillow)
```

To release a new version: bump `version` in `mr_softie/blender_manifest.toml`, zip `mr_softie/` into `download/mr_softie-<version>.zip`, delete the old zip, then regenerate the index with `blender --command extension server-generate --repo-dir download`.
