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
from .ui_patch import WORKSPACE_FLAG
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


VIEW_LAYOUT = (("TL", 'TOP'), ("TR", 'CAMERA'), ("BL", 'FRONT'), ("BR", 'RIGHT'))


def _configure_view(window, area, view):
    space = area.spaces.active
    space.show_region_ui = False
    space.show_region_toolbar = False
    space.show_region_tool_header = False
    space.show_gizmo_navigate = False
    space.overlay.show_text = False
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    r3d = space.region_3d
    if view not in {'CAMERA', 'USER'}:
        space.shading.type = 'WIREFRAME'
    if view == 'CAMERA':
        if bpy.context.scene.camera is not None:
            r3d.view_perspective = 'CAMERA'
        else:
            r3d.view_perspective = 'PERSP'
        return
    with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=region):
        bpy.ops.view3d.view_axis(type=view)
    r3d.view_perspective = 'ORTHO'


def _view_areas(screen):
    return [a for a in screen.areas if a.type == 'VIEW_3D' and a.width > 1 and a.height > 1]


def _split_steps(window, main):
    """Generator: split one 3D area into four viewports, one split per redraw.

    A freshly split area has no size until the screen redraws, so each split
    waits for the next timer tick before looking at area positions.
    """
    screen = window.screen
    space = main.spaces.active
    if len(space.region_quadviews):
        region = next((r for r in main.regions if r.type == 'WINDOW'), None)
        with bpy.context.temp_override(window=window, screen=screen, area=main, region=region):
            bpy.ops.screen.region_quadview()
        yield

    with bpy.context.temp_override(window=window, screen=screen, area=main):
        bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
    yield

    for side in ("left", "right"):
        views = _view_areas(screen)
        mid = sum(a.x + a.width / 2 for a in views) / len(views)
        candidates = [a for a in views if (a.x + a.width / 2 < mid) == (side == "left")]
        target = max(candidates, key=lambda a: a.height)
        with bpy.context.temp_override(window=window, screen=screen, area=target):
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.5)
        yield

    views = _view_areas(screen)
    cx = sum(a.x + a.width / 2 for a in views) / len(views)
    cy = sum(a.y + a.height / 2 for a in views) / len(views)
    for area in views:
        right = area.x + area.width / 2 > cx
        top = area.y + area.height / 2 > cy
        place = ("T" if top else "B") + ("R" if right else "L")
        _configure_view(window, area, dict(VIEW_LAYOUT).get(place, 'TOP'))
    yield


def _run_steps(steps, then=None):
    """Drive a generator from a timer, one step per tick, then call `then`."""
    def _tick():
        try:
            next(steps)
            return 0.05
        except StopIteration:
            if then is not None:
                try:
                    then()
                except (RuntimeError, ReferenceError) as ex:
                    print(f"[MR.Softie] layout finish failed: {ex}")
        except (RuntimeError, ReferenceError, ValueError) as ex:
            print(f"[MR.Softie] layout step failed: {ex}")
        return None
    bpy.app.timers.register(_tick, first_interval=0.05)


def _area_key(area):
    return area.as_pointer()


def _reshape_steps(window, apply_theme):
    """Generator: turn a duplicated workspace into the MR.Softie layout (fallback path)."""
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
    if right:
        mcp = max(right, key=lambda a: a.height)
        for other in [a for a in right if a != mcp]:
            src = (mcp.x + mcp.width // 2, mcp.y + mcp.height // 2)
            dst = (other.x + other.width // 2, other.y + other.height // 2)
            try:
                with bpy.context.temp_override(window=window, screen=screen, area=mcp):
                    bpy.ops.screen.area_join(source_xy=src, target_xy=dst)
            except RuntimeError:
                pass
            yield
        _setup_column(mcp, "mcp")
    else:
        with bpy.context.temp_override(window=window, screen=screen, area=main):
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.88)
        yield
        views = _view_areas(screen)
        _setup_column(max(views, key=lambda a: a.x), "mcp")
    yield

    # Toolbar column on the left of the viewports.
    main = max(_view_areas(screen), key=lambda a: a.width * a.height)
    with bpy.context.temp_override(window=window, screen=screen, area=main):
        bpy.ops.screen.area_split(direction='VERTICAL', factor=TOOLBAR_FRACTION)
    yield
    views = _view_areas(screen)
    _setup_column(min(views, key=lambda a: a.x), "toolbar")
    yield

    main = max(_view_areas(screen), key=lambda a: a.width * a.height)
    yield from _split_steps(window, main)

    window.workspace[WORKSPACE_FLAG] = True
    bpy.context.scene.transform_orientation_slots[0].type = 'GLOBAL'
    if apply_theme:
        gm_theme.apply()


TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "layout.blend")


def _finish_template(window, apply_theme):
    """After appending the template: hook up the columns and the viewports."""
    screen = window.screen
    columns = sorted((a for a in screen.areas if a.type == 'TEXT_EDITOR'), key=lambda a: a.x)
    if len(columns) >= 2:
        _setup_column(columns[0], "toolbar")
        _setup_column(columns[-1], "mcp")
    views = [a for a in screen.areas if a.type == 'VIEW_3D']
    if len(views) == 1:
        _run_steps(_split_steps(window, views[0]), then=lambda: _fit_columns(window))
        window.workspace[WORKSPACE_FLAG] = True
        if apply_theme:
            gm_theme.apply()
        return
    else:
        for area in views:
            space = area.spaces.active
            space.show_region_ui = False
            space.show_region_toolbar = False
            space.show_region_tool_header = False
    window.workspace[WORKSPACE_FLAG] = True
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
        _when_active(window, workspace, lambda: _run_steps(
            _reshape_steps(window, apply_theme), then=lambda: _fit_columns(window)))
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
    elif idname.startswith("builtin.select") and context.mode == 'OBJECT':
        row.label(text="Select NODE", icon='MOUSE_LMB')
        row.separator(factor=1.5)
        row.label(text="Select BRANCH", icon='MOUSE_MMB')
        row.separator(factor=1.5)
        row.label(text="Select TREE", icon='MOUSE_RMB')
        row.separator(factor=1.5)
        row.label(text="Add", icon='EVENT_SHIFT')
        row.label(text="Toggle", icon='EVENT_CTRL')
    elif idname.startswith("builtin.select"):
        row.label(text="Select:")
        row.label(text="Pick / Box", icon='MOUSE_LMB')
        row.label(text="Add", icon='EVENT_SHIFT')
        row.label(text="Toggle", icon='EVENT_CTRL')
    else:
        row = None
    if row is not None:
        row.separator(factor=2.0)
        row.label(text="Navigate", icon='EVENT_S')
        row.label(text="", icon='EVENT_ALT')
    # The script line: the last command, click to open the Script Editor.
    from .scripting import last_command_label
    last = last_command_label(context)
    if last:
        sub = layout.row(align=True)
        sub.separator(factor=2.0)
        sub.operator("mr_softie.open_script_editor", text=last, icon='CONSOLE', emboss=False)


def _modal_running(context):
    window = context.window
    return bool(window is not None and len(getattr(window, "modal_operators", ())))


def draw_status(self, context, original):
    """The status bar: our mouse line, then Blender's own hints only while a command is running
    (so the select tool reads "Select NODE / BRANCH / TREE" alone, as in the original)."""
    layout = self.layout
    draw_mouse_line(self, context)
    try:
        tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    except (AttributeError, TypeError):
        tool = None
    ours = tool is not None and (tool.idname.startswith("mr_softie.") or tool.idname.startswith("builtin.select"))
    if not ours or _modal_running(context):
        layout.template_input_status()
    layout.separator_spacer()
    layout.template_reports_banner()
    layout.template_running_jobs()
    layout.separator_spacer()
    layout.template_status_info()
    # Anything other add-ons added to the status bar.
    for func in getattr(original, "_draw_funcs", ()):
        if getattr(func, "__module__", "") != "bl_ui.space_statusbar":
            func(self, context)


_status = {"original": None}


def _status_draw(self, context):
    draw_status(self, context, _status["original"])


classes = (MS_OT_build_workspace, MS_OT_fit_columns)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    _patch_builtin_text_panels()
    _status["original"] = bpy.types.STATUSBAR_HT_header.draw
    bpy.types.STATUSBAR_HT_header.draw = _status_draw


def unregister():
    if bpy.types.STATUSBAR_HT_header.draw is _status_draw and _status["original"] is not None:
        bpy.types.STATUSBAR_HT_header.draw = _status["original"]
    _status["original"] = None
    _unpatch_builtin_text_panels()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
