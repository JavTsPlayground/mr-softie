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
        shader.uniform_float("color", (1.0, 0.25, 0.25, 1.0))
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

    def invoke(self, context, event):
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


classes = (MS_OT_render_region, MS_OT_render_region_clear)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    _saved.clear()
