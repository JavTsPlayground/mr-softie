"""Build docs/MR-Softie-Setup-Guide.pdf.

Dev-only: needs `pip install reportlab pillow`. Run from the repo root:
    python docs/make_guide.py
"""
import os
import re

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "MR-Softie-Setup-Guide.pdf")
SHOT = os.path.join(HERE, "screenshot.png")
REPO_URL = "https://raw.githubusercontent.com/JavTsPlayground/mr-softie/main/download/index.json"

with open(os.path.join(ROOT, "mr_softie", "blender_manifest.toml")) as f:
    VERSION = re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1)

INK = colors.HexColor("#1a1a1a")
GRAY = colors.HexColor("#6b6b6b")
PANEL = colors.HexColor("#d9d9d9")
LIGHT = colors.HexColor("#efefef")
ACCENT = colors.HexColor("#4d6b9e")

title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=28, leading=32, textColor=INK)
sub = ParagraphStyle("s", fontName="Helvetica", fontSize=12, leading=16, textColor=GRAY)
h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK,
                   spaceBefore=14, spaceAfter=6, keepWithNext=1)
body = ParagraphStyle("b", fontName="Helvetica", fontSize=10.5, leading=15, textColor=INK)
small = ParagraphStyle("sm", parent=body, fontSize=9.5, leading=13, textColor=GRAY)
mono = ParagraphStyle("m", parent=body, fontName="Courier", fontSize=8.6, leading=12)
num = ParagraphStyle("n", fontName="Helvetica-Bold", fontSize=16, leading=18, textColor=colors.white,
                     alignment=1)
cell = ParagraphStyle("c", parent=body, fontSize=10, leading=13)
cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")


def step(n, heading, lines):
    content = [Paragraph(f"<b>{heading}</b>", ParagraphStyle("sh", parent=body, fontSize=12, leading=16))]
    for ln in lines:
        content.append(Spacer(1, 3))
        content.append(ln if not isinstance(ln, str) else Paragraph(ln, body))
    t = Table([[Paragraph(str(n), num), content]], colWidths=[0.45 * inch, 6.05 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), ACCENT),
        ("BACKGROUND", (1, 0), (1, 0), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (1, 0), (1, 0), 10),
    ]))
    return KeepTogether([t, Spacer(1, 8)])


def table(rows, widths, pad=5):
    data = [[Paragraph(a, cellb), Paragraph(b, cell)] for a, b in rows]
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT, colors.white]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, PANEL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
    ]))
    return t


# Numbered callouts on the screenshot (pixel positions in the 1920x1057 capture).
CALLOUTS = [
    (1, (345, 14), "Menu bar"),
    (2, (118, 80), "Module toolbar"),
    (3, (540, 360), "Four viewports"),
    (4, (1880, 600), "MCP"),
    (5, (1160, 975), "Timeline strip"),
    (6, (560, 1040), "Mouse / script line"),
]


def annotated_screenshot():
    img = Image.open(SHOT).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    r = 24
    for n, (x, y), _label in CALLOUTS:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(77, 107, 158), outline=(255, 255, 255), width=4)
        draw.text((x, y), str(n), fill=(255, 255, 255), font=font, anchor="mm")
    path = os.path.join(HERE, "_guide_shot.png")
    img.save(path)
    return path


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(inch, 0.55 * inch, f"MR.Softie {VERSION}  |  Setup and quick-start guide")
    canvas.drawRightString(7.5 * inch, 0.55 * inch, f"Page {doc.page}")
    canvas.restoreState()


s = []
s += [Paragraph("MR.Softie", title), Spacer(1, 4),
      Paragraph(f"Setup and quick-start guide, version {VERSION}: the classic SI-style workflow, "
                "built on Blender", sub), Spacer(1, 14)]
shot = annotated_screenshot()
w = 6.5 * inch
s.append(RLImage(shot, width=w, height=w * 1057 / 1920))
s.append(Spacer(1, 6))
s.append(Table([[Paragraph(f"<b>{n}</b>  {label}", cell) for n, _p, label in CALLOUTS[:3]],
                [Paragraph(f"<b>{n}</b>  {label}", cell) for n, _p, label in CALLOUTS[3:]]],
               colWidths=[2.17 * inch] * 3))
s.append(Spacer(1, 10))
s.append(Paragraph(
    "You need <b>Blender 4.2 or newer</b> (tested on 5.2) and an internet connection for the "
    "install. It takes about five minutes, and after that updates arrive on their own.", body))
s.append(PageBreak())
s.append(Paragraph("What you get", h))
s.append(table([
    ("Layout", "Module toolbar, four independent viewports, the MCP, a classic menu bar, timeline "
               "strip and gray theme, in their own MR.Softie workspace tab."),
    ("Workflow", "Supra-mode V / C / X / Space tools, Left / Middle / Right = X / Y / Z, S to "
                 "navigate, Tweak, Raycast, property pages, Explorer and Schematic."),
    ("Construction", "Modeling / Shape / Animation / Secondary Shape regions in every object's stack, "
                     "a construction mode for new operators, and Freeze M."),
    ("Modeling", "Add Edge, Split Edge, Weld Points / Edges, Bridge, Slice, Add Polygon, Loop / Ring, Collapse, Dissolve, Filter "
                 "Points, Symmetrize, Poly Reduction and the usual extrude / bevel / bridge."),
    ("Animation", "Save Key on marked parameters (K), auto-key, animation layers with weights, Mixer clips, Animation Editor."),
    ("Rigging", "Draw Chain with an IK effector, FK / IK blend, constraint presets (Position, Orientation, "
                "Direction, Pose, Scaling, Path), Set Envelope, Weight Paint."),
    ("ICE", "Compounds built as editable Geometry Nodes: Emit, Particles (floor and collision), "
            "Swarm, Strands, Strand Dynamics (length-keeping, collides with the body), Turbulence, Jitter, Push."),
    ("Rendering", "Material presets (Phong, Glass, Chrome, Car Paint...), textures, Material Manager, passes with presets, partitions with matte / indirect overrides, render channels, "
                  "a render region per pass."),
], [1.3 * inch, 5.2 * inch], pad=4))

# ---------------------------------------------------------------------------
s.append(Paragraph("Install", h))
s.append(step(1, "Let Blender go online", [
    "Open Blender and go to <b>Edit &gt; Preferences &gt; Get Extensions</b>. If it shows "
    "<b>Allow Online Access</b>, click it. (It's also under <b>System &gt; Network</b>.)"]))
s.append(step(2, "Add the MR.Softie repository", [
    "On the Get Extensions page, open the <b>Repositories</b> dropdown in the top-right corner "
    "and click <b>+ &gt; Add Remote Repository</b>.",
    "Paste this URL and turn on <b>Check for Updates on Startup</b>:",
    Paragraph(REPO_URL, mono)]))
s.append(step(3, "Install it", [
    "Search for <b>MR.Softie</b> on the Get Extensions page and click <b>Install</b>.",
    "<b>Installed it from a zip before?</b> Uninstall that copy first (Preferences &gt; Add-ons, "
    "arrow next to MR.Softie, Uninstall), so the two don't clash."]))
s.append(step(4, "Build the workspace", [
    "Close Preferences. With the mouse over the 3D viewport press <b>N</b>, click the <b>MCP</b> tab "
    "on the right edge of the sidebar, and click <b>Classic Layout</b> in its View section.",
    "You now have a <b>MR.Softie</b> workspace tab at the top. From then on, just click that tab.",
    "Want it to look like the picture? Click <b>Gray Theme</b> in the same section "
    "(<b>Reset</b> goes back to Blender's theme)."]))
s.append(step(5, "Optional: start Blender straight into MR.Softie", [
    "In the add-on's preferences (Preferences &gt; Add-ons &gt; MR.Softie) click "
    "<b>Install App Template</b>, or use <b>Edit &gt; Install MR.Softie App Template</b>.",
    "<b>MR Softie</b> then appears under <b>File &gt; New</b> and on the splash screen."]))
s.append(step(6, "Optional: pick your options", [
    "In the add-on's preferences: <b>Classic Hotkeys</b> (off gives you Blender's keys back), "
    "<b>SRT Mouse Buttons</b> (Left / Middle / Right = X / Y / Z by default), "
    "<b>SRT Manipulator</b> and <b>Number Keys Open Editors</b>."]))

# ---------------------------------------------------------------------------
s.append(Paragraph("Find your way around", h))
s.append(table([
    ("1  Menu bar", "File, Edit, Display, View, Render, Window, Help. <b>View</b> opens every editor "
                    "in its own floating window: Explorer, Schematic, Property Page, Script Editor, "
                    "Animation Editor, Mixer, Render Tree, ICE Tree and more."),
    ("2  Module toolbar", "The five icons at the top switch module: Model, Animate, Render, Simulate "
                          "ICE and Custom (keys 1 to 6); the current one is named underneath. Custom holds your own "
                          "toolbars: Add Command makes a button from the last command, Add Script from the "
                          "Script Editor. Each has its "
                          "own stack of commands. Get &gt; Primitive is where new objects come from."),
    ("3  Four viewports", "Top, Camera, Front and Right, each with its own view and display menus, "
                          "a maximize button and memo cams <b>1 2 3 4</b>: click an empty one to "
                          "remember the view, a lit one to go back to it (the arrow next to them "
                          "stores over or forgets)."),
    ("4  MCP", "Select (with a selection filter: All, Geom, Light, Cam, Null, Skel), Transform, Snap, "
               "Constrain, Edit, View and Layers (scene layers: show, select, render per layer)."),
    ("5  Timeline strip", "Start / End, playback, current frame, RT (real-time playback), then "
                          "<b>Key</b> (red when keyed on this frame), the marked parameters "
                          "(SRT / S / R / T) and Auto-key."),
    ("6  Status line", "What the mouse buttons do right now, and the last command you ran "
                       "(click it to open the Script Editor)."),
], [1.6 * inch, 4.9 * inch]))

# ---------------------------------------------------------------------------
s.append(PageBreak())
s.append(Paragraph("Hotkeys", h))
s.append(Paragraph("They work while the mouse is over a 3D viewport.", small))
s.append(Spacer(1, 4))
s.append(table([
    ("Space", "Object selection (also leaves point / edge / polygon mode)."),
    ("V / C / X", "Translate / Rotate / Scale. Tap to switch tools; hold for a temporary tool."),
    ("  in V / C / X", "Left / Middle / Right drag = X / Y / Z. Shift + Left drag = free."),
    ("T / E / Y", "Point / Edge / Polygon selection."),
    ("S + Left / Middle / Right", "Pan / Dolly / Orbit."),
    ("F / A", "Frame selection / Frame all."),
    ("Ctrl+A / Ctrl+D / Ctrl+Y", "Select all / Duplicate / Redo."),
    ("Enter", "Property page for the selection."),
    ("M", "Tweak: drag a point, edge, polygon or object to move it."),
    ("\\", "Add Edge (cut new edges) in component mode."),
    ("K", "Save Key on the marked parameters."),
    ("Alt+4", "Script Editor: command log above a script editor."),
    ("Q / Shift+Q", "Render Region: drag a live render box in a viewport / remove it."),
    ("Alt + Right click", "Context menu."),
    ("1 / 2 / 3 / 4 / 5 / 6", "Toolbar module: Model / Animate / Render / Simulate / ICE / Custom."),
    ("7 / 8 / 9 / 0", "Render Tree / Explorer / Schematic / Animation Editor."),
], [1.9 * inch, 4.6 * inch], pad=3))

# ---------------------------------------------------------------------------
s.append(PageBreak())
s.append(Paragraph("Ten-minute tour", h))
s.append(step(1, "Model", [
    "Model &gt; Get &gt; Primitive &gt; Cube. Press <b>V</b> and drag with the left, middle and right "
    "buttons to move it along X, Y and Z. Press <b>Y</b> for polygons, select one, then "
    "Poly Mesh &gt; Extrude. Tools &gt; <b>Weld Points</b>: drag one corner onto another; "
    "<b>Split Edge</b>: click an edge to add a point. <b>Space</b> takes you back to objects."]))
s.append(step(2, "Animate", [
    "Go to frame 1 and press <b>K</b>. Go to frame 24, move the cube, press <b>K</b> again, and "
    "press Play on the timeline strip. Animate &gt; Layers &gt; <b>New</b> adds a layer: move "
    "the cube up at frame 12 and press K, and the bounce rides on top of the slide. "
    "Mixer &gt; <b>Store Clip</b> turns animation into a clip on the Mixer."]))
s.append(step(3, "ICE", [
    "Press <b>5</b> for the ICE module, select the cube and click <b>Grow Strands</b>, then "
    "<b>Strand Dynamics</b>, and press Play: springy hair. Or click <b>Swarm</b> for a flock, "
    "<b>Simulate Particles</b> for falling points. Settings are in the modifier "
    "(Property Editor &gt; wrench tab); <b>ICE Tree</b> opens the node tree."]))
s.append(step(4, "Render", [
    "Press <b>3</b>. Get &gt; Material &gt; <b>Chrome</b>, then Get &gt; Texture &gt; <b>Checker</b>, and "
    "open the Render Tree to see what it built. Press <b>Q</b> over the Camera view and drag a box "
    "around the cube for a live render of just that part (Shift+Q removes it). Passes &gt; <b>Preset</b> &gt; Depth makes a depth pass. Partitions &gt; "
    "<b>New from Selection</b> puts the cube in its own partition; its toggles show or hide it, "
    "make it a matte or indirect-only, in the current pass. <b>Render</b> renders just that pass."]))

# ---------------------------------------------------------------------------
s.append(Paragraph("Updating and sharing", h))
s.append(Paragraph(
    "With the repository added, Blender checks for a new version every time it starts; install "
    "updates from Preferences &gt; Get Extensions. To share MR.Softie, send people the repository "
    "URL above, or the project page: <b>github.com/JavTsPlayground/mr-softie</b>.", body))

s.append(PageBreak())
s.append(Paragraph("If something doesn't work", h))
s.append(table([
    ("MR.Softie isn't in Get Extensions", "Check that online access is allowed and the repository "
                                          "URL is exactly the one above, then choose "
                                          "<b>Check for Updates</b> from the small down-arrow menu "
                                          "at the top right of Get Extensions."),
    ("No MCP tab", "Check the add-on is ticked in Preferences &gt; Add-ons, then press N with the "
                   "mouse over the 3D viewport."),
    ("Columns look the wrong width", "The layout is tuned at 1920 x 1080. Click <b>Classic Layout</b> "
                                     "again to snap the columns back."),
    ("Hotkeys do nothing", "Turn on <b>Classic Hotkeys</b> in the add-on's preferences, and keep the "
                           "mouse over a 3D viewport."),
    ("A Blender key I need is gone", "MR.Softie takes over Space, S, C, V, X, E, A, F, T, Y, K, M, "
                                     "Enter, Q and the number keys in the 3D view. Turn Classic Hotkeys "
                                     "(or Number Keys Open Editors) off to get Blender's back."),
    ("Middle drag doesn't work", "Use a three-button mouse; Blender's 3-button emulation conflicts "
                                 "with the classic keys."),
    ("A simulation doesn't move", "Simulations advance frame by frame: press Play, or Bake. "
                                  "Jumping around the timeline doesn't simulate."),
    ("Uninstall", "Click <b>Reset</b> in the MCP's View section if you applied the theme, then "
                  "Preferences &gt; Add-ons &gt; arrow next to MR.Softie &gt; Uninstall."),
], [2.0 * inch, 4.5 * inch]))

s.append(Spacer(1, 14))
s.append(Paragraph(
    "MR.Softie is free and open source (GPL-3.0-or-later). It isn't affiliated with or endorsed by "
    "Autodesk, and all names, icons and artwork in it are original.", small))

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=inch, rightMargin=inch,
                        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
                        title="MR.Softie Setup Guide", author="Jason Toledo")
doc.build(s, onFirstPage=footer, onLaterPages=footer)
os.remove(shot)
print("wrote", OUT)
