# SPDX-License-Identifier: GPL-3.0-or-later
"""The MR.Softie workspace: toolbar column | four viewports | MCP column,
with the timeline along the bottom.

The two columns are Text Editor areas showing only their sidebar. Blender
lets code size areas (not sidebars), and a sidebar clamps to its area, so a
narrow Text Editor area becomes a clean full-height column of panels.
"""
import os

import bpy
from bpy.props import BoolProperty

from . import theme as gm_theme
from .viewport import COLUMN_KEY, column_kind, column_text

WORKSPACE_NAME = "MR.Softie"
COLUMN_WIDTH = 160      # matches the Text Editor sidebar's default width (at UI scale 1)
TOOLBAR_FRACTION = 0.10


# --------------------------------------------------------------------------
# Hide Blender's own Text Editor sidebar panels inside our columns
# --------------------------------------------------------------------------

_patched = []


def _not_in_column(cls, context):
    return column_kind(context) is None


def _patch_builtin_text_panels():
    for name in ("TEXT_PT_find", "TEXT_PT_properties"):
        cls = getattr(bpy.types, name, None)
        if cls is None or "poll" in cls.__dict__:
            continue
        bpy.utils.unregister_class(cls)
        cls.poll = classmethod(_not_in_column)
        bpy.utils.register_class(cls)
        _patched.append(cls)


def _unpatch_builtin_text_panels():
    while _patched:
        cls = _patched.pop()
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
        if "poll" in cls.__dict__:
            del cls.poll
        bpy.utils.register_class(cls)


# --------------------------------------------------------------------------
# Building the workspace
# --------------------------------------------------------------------------

def _ui_scale():
    return bpy.context.preferences.system.ui_scale


def _setup_column(area, kind):
    area.type = 'TEXT_EDITOR'
    space = area.spaces.active
    space.text = column_text(kind)
    space.show_region_ui = True
    space.show_region_header = False
    if hasattr(space, "show_region_footer"):
        space.show_region_footer = False
    space.show_line_numbers = False
    space.show_syntax_highlight = False


def _move_edge(window, area, x, delta):
    if delta == 0:
        return
    y = area.y + area.height // 2
    with bpy.context.temp_override(window=window, screen=window.screen, area=area):
        bpy.ops.screen.area_move(x=x, y=y, delta=int(delta))


def _fit_columns(window):
    """Size each column area to exactly its sidebar width."""
    for area in list(window.screen.areas):
        if area.type != 'TEXT_EDITOR':
            continue
        text = area.spaces.active.text
        kind = text.get(COLUMN_KEY) if text else None
        if kind is None:
            continue
        ui = next((r for r in area.regions if r.type == 'UI'), None)
        target = ui.width if (ui and ui.width > 20) else int(COLUMN_WIDTH * _ui_scale())
        if kind == "toolbar":
            _move_edge(window, area, area.x + area.width, target - area.width)
        else:
            # The shared edge sits just left of the area's first pixel.
            _move_edge(window, area, area.x - 1, area.width - target)


def _area_key(area):
    return area.as_pointer()


def _reshape(window, apply_theme):
    screen = window.screen
    views = [a for a in screen.areas if a.type == 'VIEW_3D']
    if not views:
        return
    main = max(views, key=lambda a: a.width * a.height)
    bottom = [a for a in screen.areas if a.type in {'DOPESHEET_EDITOR', 'TIMELINE'}
              and a.y < main.y]

    # Everything else becomes (or joins) the MCP column on the right.
    others = [a for a in screen.areas if a != main and a not in bottom]
    right = [a for a in others if a.x >= main.x + main.width - 2]
    mcp = max(right or others, key=lambda a: a.height) if (right or others) else None
    if mcp is not None:
        for other in [a for a in right if a != mcp]:
            src = (mcp.x + mcp.width // 2, mcp.y + mcp.height // 2)
            dst = (other.x + other.width // 2, other.y + other.height // 2)
            try:
                with bpy.context.temp_override(window=window, screen=screen, area=mcp):
                    bpy.ops.screen.area_join(source_xy=src, target_xy=dst)
            except RuntimeError:
                pass
        _setup_column(mcp, "mcp")
    else:
        before = {_area_key(a) for a in screen.areas}
        with bpy.context.temp_override(window=window, screen=screen, area=main):
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.88)
        new = [a for a in screen.areas if _area_key(a) not in before]
        pair = [main] + new
        mcp = max(pair, key=lambda a: a.x)
        main = min(pair, key=lambda a: a.x)
        _setup_column(mcp, "mcp")

    # Toolbar column on the left of the viewports.
    before = {_area_key(a) for a in screen.areas}
    with bpy.context.temp_override(window=window, screen=screen, area=main):
        bpy.ops.screen.area_split(direction='VERTICAL', factor=TOOLBAR_FRACTION)
    pair = [main] + [a for a in screen.areas if _area_key(a) not in before]
    toolbar = min(pair, key=lambda a: a.x)
    main = max(pair, key=lambda a: a.x)
    _setup_column(toolbar, "toolbar")

    # Viewports: four views, no sidebar or toolbar (the columns replace them).
    space = main.spaces.active
    space.show_region_ui = False
    space.show_region_toolbar = False
    space.show_gizmo_navigate = False
    if len(space.region_quadviews) == 0:
        region = next((r for r in main.regions if r.type == 'WINDOW'), None)
        with bpy.context.temp_override(window=window, screen=screen, area=main, region=region):
            bpy.ops.screen.region_quadview()

    bpy.context.scene.transform_orientation_slots[0].type = 'GLOBAL'
    if apply_theme:
        gm_theme.apply()

    # Sidebar widths are only known after a redraw: size the columns then.
    def _later():
        try:
            _fit_columns(window)
        except (RuntimeError, ReferenceError):
            pass
        return None
    bpy.app.timers.register(_later, first_interval=0.3)


TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "layout.blend")


def _finish_template(window, apply_theme):
    """After appending the template: hook up the columns and the viewports."""
    screen = window.screen
    columns = sorted((a for a in screen.areas if a.type == 'TEXT_EDITOR'), key=lambda a: a.x)
    if len(columns) >= 2:
        _setup_column(columns[0], "toolbar")
        _setup_column(columns[-1], "mcp")
    views = [a for a in screen.areas if a.type == 'VIEW_3D']
    if views:
        main = max(views, key=lambda a: a.width * a.height)
        space = main.spaces.active
        space.show_region_ui = False
        space.show_region_toolbar = False
        if len(space.region_quadviews) == 0:
            region = next((r for r in main.regions if r.type == 'WINDOW'), None)
            with bpy.context.temp_override(window=window, screen=screen, area=main, region=region):
                bpy.ops.screen.region_quadview()
    if apply_theme:
        gm_theme.apply()

    def _later():
        try:
            _fit_columns(window)
        except (RuntimeError, ReferenceError):
            pass
        return None
    bpy.app.timers.register(_later, first_interval=0.3)


def _when_active(window, workspace, callback):
    """Run callback once `workspace` is the window's active workspace."""
    attempts = [0]

    def _poll():
        try:
            if window.workspace != workspace:
                attempts[0] += 1
                return 0.1 if attempts[0] < 30 else None
            callback()
        except (RuntimeError, ReferenceError) as ex:
            print(f"[MR.Softie] workspace build failed: {ex}")
        return None
    bpy.app.timers.register(_poll, first_interval=0.2)


class MS_OT_build_workspace(bpy.types.Operator):
    """Open the MR.Softie workspace: module toolbar, four views, full-height MCP. Creates it the first time"""
    bl_idname = "mr_softie.build_workspace"
    bl_label = "Classic Layout"

    apply_theme: BoolProperty(name="Gray Theme", default=True,
                              description="Also apply the light-gray classic theme")

    def execute(self, context):
        window = context.window
        existing = bpy.data.workspaces.get(WORKSPACE_NAME)
        if existing is not None:
            if window.workspace != existing:
                window.workspace = existing
            bpy.app.timers.register(lambda: (_fit_columns(window), None)[1], first_interval=0.3)
            return {'FINISHED'}

        # Duplicate the current workspace. Blender activates the copy itself on
        # the next event-loop pass, so never assign window.workspace here: two
        # workspace switches queued in one pass crash Blender 5.2.
        if context.area is None:
            # Switching workspaces outside a real window context (e.g. from a
            # script timer) crashes Blender 5.2, so refuse instead.
            self.report({'ERROR'}, "Run Classic Layout from a button or menu")
            return {'CANCELLED'}
        before = {w.name for w in bpy.data.workspaces}
        apply_theme = self.apply_theme

        # Preferred: append the bundled, pre-sized layout.
        if os.path.exists(TEMPLATE_PATH):
            try:
                bpy.ops.workspace.append_activate(idname=WORKSPACE_NAME, filepath=TEMPLATE_PATH)
            except RuntimeError as ex:
                print(f"[MR.Softie] template append failed, building instead: {ex}")
            else:
                created = [w for w in bpy.data.workspaces if w.name not in before]
                if created:
                    workspace = created[0]
                    workspace.name = WORKSPACE_NAME
                    _when_active(window, workspace, lambda: _finish_template(window, apply_theme))
                    return {'FINISHED'}

        # Fallback: build the layout from the current workspace.
        bpy.ops.workspace.duplicate()
        created = [w for w in bpy.data.workspaces if w.name not in before]
        if not created:
            self.report({'ERROR'}, "Could not create the workspace")
            return {'CANCELLED'}
        workspace = created[0]
        workspace.name = WORKSPACE_NAME
        _when_active(window, workspace, lambda: _reshape(window, apply_theme))
        return {'FINISHED'}


class MS_OT_fit_columns(bpy.types.Operator):
    """Snap the toolbar and MCP columns back to their sidebar width"""
    bl_idname = "mr_softie.fit_columns"
    bl_label = "Fit Columns"

    def execute(self, context):
        _fit_columns(context.window)
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Mouse status line (bottom bar): what L / M / R do right now
# --------------------------------------------------------------------------

_MOUSE_HINTS = {
    "translate": ("X", "Y", "Z"),
    "rotate": ("X", "Y", "Z"),
    "scale": ("X", "Y", "Z"),
}


def draw_mouse_line(self, context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    except (AttributeError, TypeError):
        return
    idname = tool.idname if tool else ""
    layout = self.layout
    row = layout.row(align=True)
    if idname.startswith("mr_softie."):
        kind = idname.split(".", 1)[1].rsplit("_", 1)[0]
        verb = {"translate": "Translate", "rotate": "Rotate", "scale": "Scale"}.get(kind, kind)
        x, y, z = _MOUSE_HINTS.get(kind, ("X", "Y", "Z"))
        row.label(text=f"{verb}:", icon='NONE')
        row.label(text=x, icon='MOUSE_LMB')
        row.label(text=y, icon='MOUSE_MMB')
        row.label(text=z, icon='MOUSE_RMB')
        row.label(text="Free", icon='EVENT_SHIFT')
    elif idname.startswith("builtin.select"):
        row.label(text="Select:")
        row.label(text="Pick / Box", icon='MOUSE_LMB')
        row.label(text="Add", icon='EVENT_SHIFT')
        row.label(text="Toggle", icon='EVENT_CTRL')
    else:
        return
    row.separator(factor=2.0)
    row.label(text="Navigate", icon='EVENT_S')


classes = (MS_OT_build_workspace, MS_OT_fit_columns)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    _patch_builtin_text_panels()
    bpy.types.STATUSBAR_HT_header.prepend(draw_mouse_line)


def unregister():
    bpy.types.STATUSBAR_HT_header.remove(draw_mouse_line)
    _unpatch_builtin_text_panels()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
