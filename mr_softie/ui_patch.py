# SPDX-License-Identifier: GPL-3.0-or-later
"""Classic-style viewport headers and main menu bar, inside the MR.Softie workspace only.

Blender's own header/menu draw functions are wrapped, not removed: outside the
MR.Softie workspace (or with the add-on disabled) Blender draws exactly as before.
"""
import bpy
from bpy.props import BoolProperty, EnumProperty
from mathutils import Vector

from .viewport import button

WORKSPACE_FLAG = "mr_softie"


def in_softie(context):
    ws = getattr(context, "workspace", None)
    return ws is not None and (ws.get(WORKSPACE_FLAG) or ws.name.startswith("MR.Softie"))


# --------------------------------------------------------------------------
# Viewport naming
# --------------------------------------------------------------------------

_AXES = (
    ("Top", Vector((0, 0, -1))), ("Bottom", Vector((0, 0, 1))),
    ("Front", Vector((0, 1, 0))), ("Back", Vector((0, -1, 0))),
    ("Right", Vector((-1, 0, 0))), ("Left", Vector((1, 0, 0))),
)


def view_name(space):
    r3d = space.region_3d
    if r3d is None:
        return "View"
    if r3d.view_perspective == 'CAMERA':
        cam = space.camera or bpy.context.scene.camera
        return cam.name if cam else "Camera"
    if r3d.view_perspective == 'ORTHO':
        direction = r3d.view_rotation @ Vector((0, 0, -1))
        for name, axis in _AXES:
            if direction.dot(axis) > 0.999:
                return name
    return "User"


_DISPLAY = (
    ('WIREFRAME', "Wireframe"),
    ('SHADED', "Shaded"),
    ('TEXTURED', "Textured"),
    ('MATERIAL', "Material"),
    ('RENDERED', "Rendered"),
)


def display_name(space):
    s = space.shading
    if s.type == 'SOLID':
        return "Textured" if s.color_type == 'TEXTURE' else "Shaded"
    return {'WIREFRAME': "Wireframe", 'MATERIAL': "Material", 'RENDERED': "Rendered"}.get(s.type, s.type.title())


def apply_display(space, mode):
    s = space.shading
    if mode == 'WIREFRAME':
        s.type = 'WIREFRAME'
    elif mode == 'SHADED':
        s.type = 'SOLID'
        s.color_type = 'MATERIAL'
    elif mode == 'TEXTURED':
        s.type = 'SOLID'
        s.color_type = 'TEXTURE'
    else:
        s.type = mode


# --------------------------------------------------------------------------
# Operators used by the headers and menus
# --------------------------------------------------------------------------

class MS_OT_set_view(bpy.types.Operator):
    """Show this viewport from a camera or an axis"""
    bl_idname = "mr_softie.set_view"
    bl_label = "Set View"

    view: EnumProperty(items=(
        ('CAMERA', "Camera", ""), ('USER', "User", ""),
        ('TOP', "Top", ""), ('BOTTOM', "Bottom", ""),
        ('FRONT', "Front", ""), ('BACK', "Back", ""),
        ('RIGHT', "Right", ""), ('LEFT', "Left", ""),
    ))

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        r3d = context.space_data.region_3d
        if self.view == 'CAMERA':
            if context.scene.camera is None:
                self.report({'WARNING'}, "The scene has no camera")
                return {'CANCELLED'}
            r3d.view_perspective = 'CAMERA'
        elif self.view == 'USER':
            r3d.view_perspective = 'PERSP'
        else:
            bpy.ops.view3d.view_axis(type=self.view)
            r3d.view_perspective = 'ORTHO'
        return {'FINISHED'}


class MS_OT_set_display(bpy.types.Operator):
    """Set how this viewport (or all viewports) draws the scene"""
    bl_idname = "mr_softie.set_display"
    bl_label = "Display Mode"

    mode: EnumProperty(items=[(i, l, "") for i, l in _DISPLAY])
    all_views: BoolProperty(default=False, options={'SKIP_SAVE'})

    def execute(self, context):
        if self.all_views or context.area is None or context.area.type != 'VIEW_3D':
            spaces = [a.spaces.active for a in context.screen.areas if a.type == 'VIEW_3D']
        else:
            spaces = [context.space_data]
        for space in spaces:
            apply_display(space, self.mode)
        return {'FINISHED'}


class MS_OT_toggle_all(bpy.types.Operator):
    """Toggle grid or overlays in every viewport"""
    bl_idname = "mr_softie.toggle_all"
    bl_label = "Toggle in All Views"

    what: EnumProperty(items=(('GRID', "Grid", ""), ('OVERLAYS', "Overlays", ""),
                              ('GIZMOS', "Gizmos", "")))

    def execute(self, context):
        spaces = [a.spaces.active for a in context.screen.areas if a.type == 'VIEW_3D']
        if not spaces:
            return {'CANCELLED'}
        if self.what == 'GRID':
            value = not spaces[0].overlay.show_floor
            for s in spaces:
                s.overlay.show_floor = value
                s.overlay.show_ortho_grid = value
        elif self.what == 'OVERLAYS':
            value = not spaces[0].overlay.show_overlays
            for s in spaces:
                s.overlay.show_overlays = value
        else:
            value = not spaces[0].show_gizmo
            for s in spaces:
                s.show_gizmo = value
        return {'FINISHED'}


class MS_OT_maximize(bpy.types.Operator):
    """Maximize this viewport, or restore the four views"""
    bl_idname = "mr_softie.maximize"
    bl_label = "Maximize / Restore"

    def execute(self, context):
        area = context.area
        if area is None or area.type != 'VIEW_3D':
            views = [a for a in context.screen.areas if a.type == 'VIEW_3D']
            if not views:
                return {'CANCELLED'}
            area = next((a for a in views if a.spaces.active.region_3d.view_perspective != 'ORTHO'), views[0])
        with context.temp_override(area=area):
            bpy.ops.screen.screen_full_area()
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Menus
# --------------------------------------------------------------------------

class MS_MT_view_camera(bpy.types.Menu):
    bl_idname = "MS_MT_view_camera"
    bl_label = "View"

    def draw(self, context):
        layout = self.layout
        layout.operator("mr_softie.set_view", text="Camera").view = 'CAMERA'
        layout.operator("mr_softie.set_view", text="User").view = 'USER'
        layout.separator()
        for ident, label in (('TOP', "Top"), ('BOTTOM', "Bottom"), ('FRONT', "Front"),
                             ('BACK', "Back"), ('RIGHT', "Right"), ('LEFT', "Left")):
            layout.operator("mr_softie.set_view", text=label).view = ident
        layout.separator()
        layout.operator("view3d.view_selected", text="Frame Selection")
        layout.operator("view3d.view_all", text="Frame All")


class MS_MT_view_display(bpy.types.Menu):
    bl_idname = "MS_MT_view_display"
    bl_label = "Display"

    def draw(self, context):
        layout = self.layout
        for ident, label in _DISPLAY:
            layout.operator("mr_softie.set_display", text=label).mode = ident
        layout.separator()
        overlay = context.space_data.overlay
        layout.prop(overlay, "show_wireframes", text="Wireframe on Shaded")
        layout.prop(overlay, "show_floor", text="Grid")
        layout.prop(overlay, "show_axis_x", text="Axes")
        layout.prop(context.space_data.shading, "show_xray", text="X-Ray")


class MS_MT_main_edit(bpy.types.Menu):
    bl_idname = "MS_MT_main_edit"
    bl_label = "Edit"

    def draw(self, context):
        layout = self.layout
        layout.operator("ed.undo", text="Undo")
        layout.operator("ed.redo", text="Redo")
        layout.menu("TOPBAR_MT_undo_history")
        layout.separator()
        if context.mode == 'EDIT_MESH':
            button(layout, "Duplicate", "mesh.duplicate_move")
            button(layout, "Delete", "mesh.delete", type='VERT')
        else:
            button(layout, "Duplicate", "object.duplicate_move")
            button(layout, "Duplicate Instance", "object.duplicate_move_linked")
            layout.operator("object.delete", text="Delete")
            layout.separator()
            layout.operator("mr_softie.freeze", text="Freeze Modeling")
            layout.operator("mr_softie.reset_srt", text="Reset All Transforms").kind = 'ALL'
        layout.separator()
        layout.operator("wm.search_menu", text="Command Search...")
        layout.operator("mr_softie.install_app_template", text="Install MR.Softie App Template")
        layout.operator("screen.userpref_show", text="Preferences...")


class MS_MT_main_display(bpy.types.Menu):
    bl_idname = "MS_MT_main_display"
    bl_label = "Display"

    def draw(self, context):
        layout = self.layout
        for ident, label in _DISPLAY:
            op = layout.operator("mr_softie.set_display", text=f"{label} (All Views)")
            op.mode = ident
            op.all_views = True
        layout.separator()
        layout.operator("mr_softie.toggle_all", text="Grid").what = 'GRID'
        layout.operator("mr_softie.toggle_all", text="Overlays").what = 'OVERLAYS'
        layout.operator("mr_softie.toggle_all", text="Gizmos").what = 'GIZMOS'
        layout.separator()
        layout.operator("object.hide_view_set", text="Hide Selection").unselected = False
        layout.operator("object.hide_view_clear", text="Unhide All")
        layout.separator()
        layout.operator("mr_softie.apply_theme", text="Gray Theme")
        layout.operator("mr_softie.reset_theme", text="Blender Theme")


class MS_MT_main_view(bpy.types.Menu):
    bl_idname = "MS_MT_main_view"
    bl_label = "View"

    def draw(self, context):
        layout = self.layout
        layout.operator("mr_softie.build_workspace", text="Classic Layout")
        layout.operator("mr_softie.maximize", text="Maximize / Restore Viewport")
        layout.separator()
        layout.operator("mr_softie.open_explorer", text="Explorer")
        layout.operator("mr_softie.open_schematic", text="Schematic")
        layout.operator("mr_softie.open_ppg", text="Property Page")
        for label, ui_type in (("Animation Editor", 'FCURVES'),
                               ("Dopesheet", 'DOPESHEET'), ("Animation Mixer", 'NLA_EDITOR'),
                               ("Render Tree", 'ShaderNodeTree'), ("ICE Tree (Geometry Nodes)", 'GeometryNodeTree'),
                               ("Texture Editor", 'UV'), ("Property Editor", 'PROPERTIES'),
                               ("Script Log", 'INFO'), ("Script Editor", 'TEXT_EDITOR'),
                               ("Python Console", 'CONSOLE')):
            layout.operator("mr_softie.open_editor", text=label).ui_type = ui_type


# --------------------------------------------------------------------------
# Header / menu bar drawing
# --------------------------------------------------------------------------

def draw_softie_view3d_header(self, context):
    layout = self.layout
    space = context.space_data
    row = layout.row(align=True)
    row.menu("MS_MT_view_camera", text=view_name(space))
    row.menu("MS_MT_view_display", text=display_name(space))
    layout.separator_spacer()
    row = layout.row(align=False)
    row.scale_x = 1.6
    row.prop(space.overlay, "show_overlays", text="", icon='OVERLAY')
    row.separator(factor=0.5)
    row.operator("mr_softie.maximize", text="", icon='FULLSCREEN_ENTER')


def draw_softie_menus(self, context):
    layout = self.layout
    if getattr(context.area, "show_menus", False):
        layout.menu("TOPBAR_MT_blender", text="", icon='BLENDER')
    else:
        layout.menu("TOPBAR_MT_blender", text="Blender")
    layout.menu("TOPBAR_MT_file")
    layout.menu("MS_MT_main_edit")
    layout.menu("MS_MT_main_display")
    layout.menu("MS_MT_main_view")
    layout.menu("TOPBAR_MT_render")
    layout.menu("TOPBAR_MT_window")
    layout.menu("TOPBAR_MT_help")


_wrapped = []   # (cls, original_draw, wrapper)


def _wrap(cls, softie_draw):
    original = cls.draw

    def draw(self, context):
        if in_softie(context):
            softie_draw(self, context)
        else:
            original(self, context)
    draw._mr_softie_original = original
    cls.draw = draw
    _wrapped.append((cls, original, draw))


def _restore(cls, original, wrapper):
    if cls.draw is wrapper:
        cls.draw = original
    else:
        # Someone appended to the header after us: unhook our wrapper from their chain.
        funcs = getattr(cls.draw, "_draw_funcs", None)
        if funcs is not None and wrapper in funcs:
            funcs[funcs.index(wrapper)] = original


def unwrap(cls):
    for entry in [e for e in _wrapped if e[0] is cls][::-1]:
        _wrapped.remove(entry)
        _restore(*entry)


def _unwrap_all():
    while _wrapped:
        _restore(*_wrapped.pop())


classes = (
    MS_OT_set_view,
    MS_OT_set_display,
    MS_OT_toggle_all,
    MS_OT_maximize,
    MS_MT_view_camera,
    MS_MT_view_display,
    MS_MT_main_edit,
    MS_MT_main_display,
    MS_MT_main_view,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    _wrap(bpy.types.VIEW3D_HT_header, draw_softie_view3d_header)
    _wrap(bpy.types.TOPBAR_MT_editor_menus, draw_softie_menus)


def unregister():
    _unwrap_all()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
