# SPDX-License-Identifier: GPL-3.0-or-later
"""Render Region (Q): drag a box in any viewport for a live render inside it.

  Q, then drag     draw the region: that viewport renders live inside the box,
                   and draws as before everywhere else
  Q, then click    (no drag) remove the region
  Shift+Q          remove the region in the viewport under the mouse

Outside camera view the region belongs to the viewport only. Looking through the
camera, Blender takes the region from the scene's render region, so it also
limits final renders until you remove it (the region is outlined in the camera
frame, and removing it here clears that too).

The region is drawn as a floating frame: yellow border, blue handles, and a title
bar with a menu (▾) and close (×) button. Drag a handle to resize it, drag the
title bar to move it. Around the region the viewport stays shaded.
"""
import bpy
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

_saved = {}   # area pointer -> shading type before the region, and whether we set the scene border


def area_under_mouse(context, event):
    x, y = event.mouse_x, event.mouse_y
    for area in context.window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for region in area.regions:
            if region.type == 'WINDOW' and region.x <= x < region.x + region.width \
                    and region.y <= y < region.y + region.height:
                return area, region, Vector((x - region.x, y - region.y))
    return None, None, None


def camera_frame_rect(scene, region, rv3d):
    """The camera frame's (xmin, ymin, xmax, ymax) in region pixels, or None."""
    cam = scene.camera
    if cam is None:
        return None
    pts = []
    for co in cam.data.view_frame(scene=scene):
        p = view3d_utils.location_3d_to_region_2d(region, rv3d, cam.matrix_world @ co)
        if p is None:
            return None
        pts.append(p)
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def normalized(rect, frame):
    """`rect` (pixels) as 0..1 fractions of `frame` (pixels), clamped."""
    x0, y0, x1, y1 = rect
    fx0, fy0, fx1, fy1 = frame
    w, h = max(fx1 - fx0, 1e-6), max(fy1 - fy0, 1e-6)

    def clamp(v):
        return min(max(v, 0.0), 1.0)
    return (clamp((x0 - fx0) / w), clamp((y0 - fy0) / h), clamp((x1 - fx0) / w), clamp((y1 - fy0) / h))


def set_region(context, area, region, rect):
    """Turn on a live render region `rect` (pixels in `region`) in `area`."""
    space = area.spaces.active
    rv3d = space.region_3d
    key = area.as_pointer()
    if key not in _saved:
        _saved[key] = {"shading": space.shading.type, "scene_border": False}
    if rv3d.view_perspective == 'CAMERA':
        frame = camera_frame_rect(context.scene, region, rv3d)
        if frame is None:
            return False
        x0, y0, x1, y1 = normalized(rect, frame)
        r = context.scene.render
        r.border_min_x, r.border_min_y, r.border_max_x, r.border_max_y = x0, y0, x1, y1
        r.use_border = True
        _saved[key]["scene_border"] = True
    else:
        x0, y0, x1, y1 = normalized(rect, (0, 0, region.width, region.height))
        space.render_border_min_x, space.render_border_min_y = x0, y0
        space.render_border_max_x, space.render_border_max_y = x1, y1
        space.use_render_border = True
    space.shading.type = 'RENDERED'
    area.tag_redraw()
    return True


def clear_region(context, area):
    space = area.spaces.active
    saved = _saved.pop(area.as_pointer(), None)
    space.use_render_border = False
    if saved is not None:
        if saved["scene_border"]:
            context.scene.render.use_border = False
        space.shading.type = saved["shading"] if saved["shading"] != 'RENDERED' else 'SOLID'
    elif space.shading.type == 'RENDERED':
        space.shading.type = 'SOLID'
    area.tag_redraw()


def has_region(area):
    return area.as_pointer() in _saved


# --------------------------------------------------------------------------
# The region frame: where it is, how it's drawn, and dragging it
# --------------------------------------------------------------------------

FRAME_COLOR = (0.95, 0.85, 0.15, 1.0)
HANDLE_COLOR = (0.25, 0.35, 0.95, 1.0)
BAR_COLOR = (0.72, 0.72, 0.72, 1.0)
BAR_EDGE = (0.45, 0.45, 0.45, 1.0)
GLYPH_COLOR = (0.08, 0.08, 0.08, 1.0)
BAR_H = 16
HANDLE = 6
_frame_handle = {"draw": None, "shade": None}


def region_rect(context, area, region):
    """The live render region of `area` as (x0, y0, x1, y1) region pixels, or None."""
    space = area.spaces.active
    if space.shading.type != 'RENDERED':
        return None
    rv3d = space.region_3d
    if rv3d.view_perspective == 'CAMERA':
        r = context.scene.render
        if not r.use_border:
            return None
        frame = camera_frame_rect(context.scene, region, rv3d)
        if frame is None:
            return None
        fx0, fy0, fx1, fy1 = frame
        w, h = fx1 - fx0, fy1 - fy0
        return (fx0 + r.border_min_x * w, fy0 + r.border_min_y * h,
                fx0 + r.border_max_x * w, fy0 + r.border_max_y * h)
    if not space.use_render_border:
        return None
    return (space.render_border_min_x * region.width, space.render_border_min_y * region.height,
            space.render_border_max_x * region.width, space.render_border_max_y * region.height)


def bar_rect(rect, region):
    """The title bar: above the region, or just inside it when there's no room above."""
    x0, y0, x1, y1 = rect
    if y1 + BAR_H <= region.height - 2:
        return (x0, y1 + 1, x1, y1 + 1 + BAR_H)
    return (x0, y1 - BAR_H, x1, y1)


def hotspots(rect, region):
    """Named hit areas of the frame, in region pixels: (name, (x0, y0, x1, y1))."""
    x0, y0, x1, y1 = rect
    bx0, by0, bx1, by1 = bar_rect(rect, region)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    h = HANDLE + 2
    spots = [
        ("close", (bx1 - BAR_H, by0, bx1, by1)),
        ("menu", (bx0, by0, bx0 + BAR_H, by1)),
    ]
    for name, (px, py) in (("x0y0", (x0, y0)), ("x1y0", (x1, y0)), ("x0y1", (x0, y1)), ("x1y1", (x1, y1)),
                           ("x0", (x0, my)), ("x1", (x1, my)), ("y0", (mx, y0)), ("y1", (mx, y1))):
        spots.append((name, (px - h, py - h, px + h, py + h)))
    spots.append(("move", (bx0, by0, bx1, by1)))
    return spots


def hit(rect, region, point):
    for name, (a, b, c, d) in hotspots(rect, region):
        if a <= point[0] <= c and b <= point[1] <= d:
            return name
    return None


def _quad(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)]


def _outline(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y0), (x1, y1), (x1, y1), (x0, y1), (x0, y1), (x0, y0)]


def _draw_frame():
    context = bpy.context
    area, region = context.area, context.region
    if area is None or region is None or region.type != 'WINDOW':
        return
    rect = region_rect(context, area, region)
    if rect is None:
        return
    x0, y0, x1, y1 = rect
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')

    def fill(verts, color):
        shader.uniform_float("color", color)
        batch_for_shader(shader, 'TRIS', {"pos": verts}).draw(shader)

    def lines(verts, color, width=1.0):
        gpu.state.line_width_set(width)
        shader.uniform_float("color", color)
        batch_for_shader(shader, 'LINES', {"pos": verts}).draw(shader)

    shader.bind()
    # Border (thick enough to cover Blender's dashed region outline).
    lines(_outline(x0, y0, x1, y1), FRAME_COLOR, 2.0)
    # Title bar: ▾ menu on the left, × close on the right.
    bx0, by0, bx1, by1 = bar_rect(rect, region)
    fill(_quad(bx0, by0, bx1, by1), BAR_COLOR)
    lines(_outline(bx0, by0, bx1, by1), BAR_EDGE)
    cx, cy = bx0 + BAR_H / 2, (by0 + by1) / 2
    fill([(cx - 4, cy + 2), (cx + 4, cy + 2), (cx, cy - 3)], GLYPH_COLOR)
    cx = bx1 - BAR_H / 2
    lines([(cx - 3.5, cy - 3.5), (cx + 3.5, cy + 3.5), (cx - 3.5, cy + 3.5), (cx + 3.5, cy - 3.5)], GLYPH_COLOR, 1.5)
    # Handles at the corners and edge midpoints.
    for name, (a, b, c, d) in hotspots(rect, region):
        if name in {"close", "menu", "move"}:
            continue
        px, py = (a + c) / 2, (b + d) / 2
        s = HANDLE / 2
        fill(_quad(px - s, py - s, px + s, py + s), HANDLE_COLOR)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


def _store_rect(context, area, region, rect):
    """Write a region rect (pixels) back to the viewport or the scene."""
    space = area.spaces.active
    rv3d = space.region_3d
    if rv3d.view_perspective == 'CAMERA':
        frame = camera_frame_rect(context.scene, region, rv3d)
        if frame is None:
            return
        r = context.scene.render
        r.border_min_x, r.border_min_y, r.border_max_x, r.border_max_y = normalized(rect, frame)
    else:
        (space.render_border_min_x, space.render_border_min_y,
         space.render_border_max_x, space.render_border_max_y) = normalized(rect, (0, 0, region.width, region.height))
    area.tag_redraw()


class MS_OT_render_region_frame(bpy.types.Operator):
    """Drag the render region's handles to resize it, its title bar to move it; × removes it"""
    bl_idname = "mr_softie.render_region_frame"
    bl_label = "Render Region Frame"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        area, region, mouse = area_under_mouse(context, event)
        if area is None:
            return {'PASS_THROUGH'}
        rect = region_rect(context, area, region)
        if rect is None:
            return {'PASS_THROUGH'}
        spot = hit(rect, region, mouse)
        if spot is None:
            return {'PASS_THROUGH'}
        # Buttons act on release, so the click isn't also seen by the select tool.
        self.area, self.region, self.spot = area, region, spot
        self.start, self.rect = mouse.copy(), rect
        self.released = False
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            _store_rect(context, self.area, self.region, self.rect)
            return {'CANCELLED'}
        if self.released:
            # Blender follows the release with a CLICK: swallow it so the select
            # tool doesn't deselect everything, then act.
            if self.spot == "close":
                clear_region(context, self.area)
            elif self.spot == "menu":
                with context.temp_override(area=self.area, region=self.region):
                    bpy.ops.wm.call_menu(name="MS_MT_render_region")
            if event.type == 'LEFTMOUSE' and event.value in {'CLICK', 'DOUBLE_CLICK'}:
                return {'FINISHED'}
            return {'FINISHED', 'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self.released = True
            return {'RUNNING_MODAL'}
        if self.spot in {"close", "menu"}:
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE':
            mx = event.mouse_x - self.region.x
            my = event.mouse_y - self.region.y
            dx, dy = mx - self.start.x, my - self.start.y
            _store_rect(context, self.area, self.region, moved_rect(self.rect, self.spot, dx, dy))
        return {'RUNNING_MODAL'}


class MS_GT_region_frame(bpy.types.Gizmo):
    """The frame's handles and buttons as a gizmo, so they get the mouse before the active tool."""
    bl_idname = "MS_GT_region_frame"

    def setup(self):
        self.spot = None

    def draw(self, context):
        pass   # drawn by _draw_frame

    def test_select(self, context, location):
        rect = region_rect(context, context.area, context.region)
        if rect is None:
            return -1
        self.spot = hit(rect, context.region, location)
        return 0 if self.spot is not None else -1

    def invoke(self, context, event):
        rect = region_rect(context, context.area, context.region)
        if rect is None or self.spot is None:
            return {'CANCELLED'}
        self.area, self.region = context.area, context.region
        self.start = Vector((event.mouse_region_x, event.mouse_region_y))
        self.rect = rect
        self.moved = False
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        if self.spot in {"close", "menu"}:
            return {'RUNNING_MODAL'}
        dx = event.mouse_region_x - self.start.x
        dy = event.mouse_region_y - self.start.y
        _store_rect(context, self.area, self.region, moved_rect(self.rect, self.spot, dx, dy))
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if cancel:
            if self.spot not in {"close", "menu"}:
                _store_rect(context, self.area, self.region, self.rect)
            return
        if self.spot == "close":
            clear_region(context, self.area)
        elif self.spot == "menu":
            window, area, region = context.window, self.area, self.region
            bpy.app.timers.register(lambda: _open_menu(window, area, region), first_interval=0.01)


def _open_menu(window, area, region):
    try:
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.wm.call_menu(name="MS_MT_render_region")
    except (RuntimeError, ReferenceError, TypeError):
        pass
    return None


def moved_rect(rect, spot, dx, dy):
    x0, y0, x1, y1 = rect
    if spot == "move":
        return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
    if "x0" in spot:
        x0 = min(x0 + dx, x1 - 8)
    if "x1" in spot:
        x1 = max(x1 + dx, x0 + 8)
    if "y0" in spot:
        y0 = min(y0 + dy, y1 - 8)
    if "y1" in spot:
        y1 = max(y1 + dy, y0 + 8)
    return (x0, y0, x1, y1)


class MS_GGT_region_frame(bpy.types.GizmoGroup):
    bl_idname = "MS_GGT_region_frame"
    bl_label = "Render Region Frame"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' \
            and context.area.spaces.active.shading.type == 'RENDERED'

    def setup(self, context):
        self.gizmos.new(MS_GT_region_frame.bl_idname)


class MS_OT_render_region_redraw(bpy.types.Operator):
    """Re-render the region from scratch"""
    bl_idname = "mr_softie.render_region_redraw"
    bl_label = "Refresh Region"

    def execute(self, context):
        for area in context.screen.areas:
            if area.type == 'VIEW_3D' and area.spaces.active.shading.type == 'RENDERED':
                context.view_layer.update()
                area.tag_redraw()
        return {'FINISHED'}


class MS_MT_render_region(bpy.types.Menu):
    bl_idname = "MS_MT_render_region"
    bl_label = "Render Region"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.render, "engine", text="")
        layout.operator("mr_softie.render_region", text="Draw New Region")
        layout.operator("mr_softie.render_region_redraw", text="Refresh")
        layout.operator("mr_softie.open_editor", text="Render Options").ui_type = 'PROPERTIES'
        layout.separator()
        layout.operator("mr_softie.render_region_clear", text="Remove Region")
        layout.operator("mr_softie.render_region_clear", text="Remove All Regions").all_views = True


class MS_OT_render_region(bpy.types.Operator):
    """Render Region: drag a box in a viewport for a live render inside it (click to remove it)"""
    bl_idname = "mr_softie.render_region"
    bl_label = "Render Region"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.window is not None

    def invoke(self, context, event):
        self.start = None
        self.rect = None
        self.area = self.region = None
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.workspace.status_text_set("Render Region:  drag a box  |  click: remove the region  |  Esc: cancel")
        context.window.cursor_modal_set('CROSSHAIR')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _end(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.workspace.status_text_set(None)
        context.window.cursor_modal_restore()
        for area in context.window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

    def _draw(self):
        if self.rect is None or bpy.context.region != self.region:
            return
        x0, y0, x1, y1 = self.rect
        pts = [(x0, y0), (x1, y0), (x1, y0), (x1, y1), (x1, y1), (x0, y1), (x0, y1), (x0, y0)]
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.line_width_set(1.5)
        batch = batch_for_shader(shader, 'LINES', {"pos": pts})
        shader.uniform_float("color", FRAME_COLOR)
        shader.bind()
        batch.draw(shader)
        gpu.state.line_width_set(1.0)

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        area, region, mouse = area_under_mouse(context, event)
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if area is None:
                return {'RUNNING_MODAL'}
            self.area, self.region, self.start = area, region, mouse
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and self.start is not None:
            if region == self.region and mouse is not None:
                self.rect = (min(self.start.x, mouse.x), min(self.start.y, mouse.y),
                             max(self.start.x, mouse.x), max(self.start.y, mouse.y))
                self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.start is not None:
            rect = self.rect
            self._end(context)
            if rect is None or (rect[2] - rect[0]) < 6 or (rect[3] - rect[1]) < 6:
                clear_region(context, self.area)
            else:
                set_region(context, self.area, self.region, rect)
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


class MS_OT_render_region_clear(bpy.types.Operator):
    """Remove the render region in the viewport under the mouse (or all of them)"""
    bl_idname = "mr_softie.render_region_clear"
    bl_label = "Remove Render Region"

    all_views: bpy.props.BoolProperty(name="All Views", default=False, options={'SKIP_SAVE'})

    def invoke(self, context, event):
        if self.all_views:
            return self.execute(context)
        area, _region, _mouse = area_under_mouse(context, event)
        if area is not None:
            clear_region(context, area)
            return {'FINISHED'}
        return self.execute(context)

    def execute(self, context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D' and (has_region(area) or area.spaces.active.use_render_border):
                    clear_region(context, area)
        return {'FINISHED'}


classes = (MS_OT_render_region, MS_OT_render_region_clear, MS_OT_render_region_frame,
           MS_OT_render_region_redraw, MS_MT_render_region, MS_GT_region_frame, MS_GGT_region_frame)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    if not bpy.app.background:
        from . import region_shading
        _frame_handle["draw"] = bpy.types.SpaceView3D.draw_handler_add(_draw_frame, (), 'WINDOW', 'POST_PIXEL')
        _frame_handle["shade"] = bpy.types.SpaceView3D.draw_handler_add(
            region_shading.draw_outside, (), 'WINDOW', 'POST_VIEW')
        bpy.app.handlers.load_post.append(region_shading.forget)


def unregister():
    from . import region_shading
    if region_shading.forget in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(region_shading.forget)
    region_shading._cache.clear()
    region_shading._shader["s"] = None
    for key, where in (("draw", 'WINDOW'), ("shade", 'WINDOW')):
        if _frame_handle[key] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_frame_handle[key], where)
            _frame_handle[key] = None
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    _saved.clear()
