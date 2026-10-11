# SPDX-License-Identifier: GPL-3.0-or-later
"""Property pages: Enter opens a floating, live property page for the selection.

The page follows the active object, or stays on one object when pinned.
Built like the MCP column: a Text Editor whose sidebar fills the window.
"""
import bpy

from .viewport import COLUMN_KEY, column_kind

PIN_KEY = "mr_softie_ppg_pin"


def _ppg_text(context):
    space = context.space_data
    return space.text if space and space.type == 'TEXT_EDITOR' else None


def ppg_object(context):
    text = _ppg_text(context)
    pinned = text.get(PIN_KEY) if text else None
    if pinned:
        return bpy.data.objects.get(pinned)
    return context.active_object


def _is_ppg(context):
    return column_kind(context) == "ppg"


class _PPG:
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "PPG"

    @classmethod
    def poll(cls, context):
        return _is_ppg(context) and ppg_object(context) is not None


class MS_PT_ppg_header(_PPG, bpy.types.Panel):
    bl_idname = "MS_PT_ppg_header"
    bl_label = "Object"
    bl_options = {'HIDE_HEADER'}
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return _is_ppg(context)

    def draw(self, context):
        layout = self.layout
        obj = ppg_object(context)
        text = _ppg_text(context)
        row = layout.row(align=True)
        pinned = bool(text and text.get(PIN_KEY))
        row.operator("mr_softie.ppg_pin", text="", icon='PINNED' if pinned else 'UNPINNED', depress=pinned)
        if obj is None:
            row.label(text="Nothing selected")
            return
        row.prop(obj, "name", text="")
        layout.label(text=f"{obj.type.title()}  ·  {obj.data.name if obj.data else 'no data'}")


class MS_PT_ppg_kinematics(_PPG, bpy.types.Panel):
    bl_idname = "MS_PT_ppg_kinematics"
    bl_label = "Kinematics"
    bl_order = 1

    def draw(self, context):
        obj = ppg_object(context)
        layout = self.layout
        layout.use_property_split = False
        for label, attr in (("Scaling", "scale"), ("Rotation", "rotation_euler"), ("Translation", "location")):
            if attr == "rotation_euler" and obj.rotation_mode in {'QUATERNION', 'AXIS_ANGLE'}:
                layout.prop(obj, "rotation_mode", text="Rotation")
                continue
            layout.label(text=label)
            row = layout.row(align=True)
            for i, axis in enumerate("XYZ"):
                row.prop(obj, attr, index=i, text=axis)
        layout.prop(obj, "rotation_mode", text="Order")
        if obj.parent:
            layout.label(text=f"Parent: {obj.parent.name}", icon='LINKED')


class MS_PT_ppg_visibility(_PPG, bpy.types.Panel):
    bl_idname = "MS_PT_ppg_visibility"
    bl_label = "Visibility"
    bl_order = 2

    def draw(self, context):
        obj = ppg_object(context)
        layout = self.layout
        col = layout.column(align=True)
        col.prop(obj, "hide_viewport", text="Hidden in Viewports", toggle=True, invert_checkbox=False)
        col.prop(obj, "hide_render", text="Hidden in Render", toggle=True)
        col.prop(obj, "hide_select", text="Unselectable", toggle=True)
        layout.prop(obj, "display_type", text="Display")
        row = layout.row(align=True)
        row.prop(obj, "show_wire", text="Wire", toggle=True)
        row.prop(obj, "show_in_front", text="In Front", toggle=True)
        row.prop(obj, "show_name", text="Name", toggle=True)


class MS_PT_ppg_data(_PPG, bpy.types.Panel):
    bl_idname = "MS_PT_ppg_data"
    bl_label = "Geometry"
    bl_order = 3

    def draw_header(self, context):
        obj = ppg_object(context)
        label = {'MESH': "Geometry", 'LIGHT': "Light", 'CAMERA': "Camera", 'CURVE': "Curve",
                 'EMPTY': "Null"}.get(obj.type, "Data")
        self.layout.label(text=label)

    def draw(self, context):
        obj = ppg_object(context)
        layout = self.layout
        data = obj.data
        if obj.type == 'MESH':
            col = layout.column(align=True)
            col.label(text=f"Points {len(data.vertices)}   Edges {len(data.edges)}   Polys {len(data.polygons)}")
            sub = next((m for m in obj.modifiers if m.type == 'SUBSURF'), None)
            if sub is not None:
                row = layout.row(align=True)
                row.prop(sub, "levels", text="Subdiv View")
                row.prop(sub, "render_levels", text="Render")
            else:
                op = layout.operator("object.subdivision_set", text="Add Subdivision")
                op.level, op.relative = 1, False
            # Polygon Reduction (a Decimate modifier), with the live result.
            red = next((m for m in obj.modifiers if m.type == 'DECIMATE'), None)
            box = layout.box()
            box.label(text="Polygon Reduction")
            if red is None:
                box.operator("mr_softie.reduce_polygons", text="Reduce").ratio = 0.5
            else:
                row = box.row(align=True)
                row.prop(red, "ratio", text="Keep", slider=True)
                row.prop(red, "show_viewport", text="", icon='HIDE_OFF')
                box.prop(red, "use_symmetry", text="Keep Symmetry")
                after = _evaluated_polys(context, obj)
                if after is not None:
                    box.label(text=f"Polys {len(data.polygons)}  ->  {after}")
        elif obj.type == 'LIGHT':
            layout.prop(data, "type", text="")
            layout.prop(data, "color")
            layout.prop(data, "energy", text="Intensity")
            if hasattr(data, "shadow_soft_size"):
                layout.prop(data, "shadow_soft_size", text="Softness")
            if data.type == 'SPOT':
                layout.prop(data, "spot_size", text="Cone")
                layout.prop(data, "spot_blend", text="Spread")
        elif obj.type == 'CAMERA':
            layout.prop(data, "lens", text="Focal Length")
            layout.prop(data, "sensor_width", text="Film Width")
            row = layout.row(align=True)
            row.prop(data, "clip_start", text="Near")
            row.prop(data, "clip_end", text="Far")
            layout.prop(data.dof, "use_dof", text="Depth of Field")
        elif obj.type == 'CURVE':
            layout.prop(data, "resolution_u", text="Resolution")
            layout.prop(data, "bevel_depth", text="Bevel")
        elif obj.type == 'EMPTY':
            layout.prop(obj, "empty_display_type", text="Shape")
            layout.prop(obj, "empty_display_size", text="Size")
        else:
            layout.label(text="No page for this type yet")


def _evaluated_polys(context, obj):
    try:
        ev = obj.evaluated_get(context.evaluated_depsgraph_get())
        return len(ev.data.polygons)
    except (AttributeError, RuntimeError, ReferenceError):
        return None


class MS_PT_ppg_material(_PPG, bpy.types.Panel):
    bl_idname = "MS_PT_ppg_material"
    bl_label = "Material"
    bl_order = 4

    @classmethod
    def poll(cls, context):
        obj = ppg_object(context) if _is_ppg(context) else None
        return obj is not None and hasattr(obj.data, "materials")

    def draw(self, context):
        obj = ppg_object(context)
        layout = self.layout
        mat = obj.active_material
        if mat is None:
            layout.operator("mr_softie.add_material", text="New Material")
            return
        layout.prop(mat, "name", text="")
        bsdf = None
        if mat.use_nodes and mat.node_tree:
            bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is None:
            layout.prop(mat, "diffuse_color", text="Color")
            return
        for name, label in (("Base Color", "Color"), ("Roughness", "Roughness"),
                            ("Metallic", "Metallic"), ("Alpha", "Opacity")):
            sock = bsdf.inputs.get(name)
            if sock is not None and not sock.is_linked:
                layout.prop(sock, "default_value", text=label)


class MS_PT_ppg_constraints(_PPG, bpy.types.Panel):
    bl_idname = "MS_PT_ppg_constraints"
    bl_label = "Constraints"
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        obj = ppg_object(context)
        layout = self.layout
        if not obj.constraints:
            layout.label(text="None")
        for con in obj.constraints:
            row = layout.row(align=True)
            row.prop(con, "enabled", text="")
            row.label(text=f"{con.name}  →  {getattr(con, 'target', None).name if getattr(con, 'target', None) else '-'}")


class MS_OT_ppg_pin(bpy.types.Operator):
    """Pin this property page to the current object, or unpin it to follow the selection"""
    bl_idname = "mr_softie.ppg_pin"
    bl_label = "Pin Property Page"

    def execute(self, context):
        text = _ppg_text(context)
        if text is None:
            return {'CANCELLED'}
        if text.get(PIN_KEY):
            del text[PIN_KEY]
        elif context.active_object is not None:
            text[PIN_KEY] = context.active_object.name
        return {'FINISHED'}


class MS_OT_open_ppg(bpy.types.Operator):
    """Property page: a floating, live page for the selected object"""
    bl_idname = "mr_softie.open_ppg"
    bl_label = "Property Page"

    def execute(self, context):
        from .operators import open_floating_window
        # Duplicate the MCP column when there is one, so the page opens narrow and tall.
        source = None
        for area in context.screen.areas:
            text = area.spaces.active.text if area.type == 'TEXT_EDITOR' else None
            if text is not None and text.get(COLUMN_KEY) == "mcp":
                source = area
        window, area = open_floating_window(context, source=source)
        if area is None:
            self.report({'WARNING'}, "Could not open a window")
            return {'CANCELLED'}
        area.type = 'TEXT_EDITOR'
        space = area.spaces.active
        # One text per page so each window can be pinned separately.
        text = bpy.data.texts.new("MR.Softie PPG")
        text[COLUMN_KEY] = "ppg"
        space.text = text
        space.show_region_ui = True
        space.show_region_header = False
        if hasattr(space, "show_region_footer"):
            space.show_region_footer = False
        space.show_line_numbers = False
        return {'FINISHED'}


@bpy.app.handlers.persistent
def _cleanup_ppg_texts(*_args):
    """Remove property-page texts no window shows any more."""
    shown = set()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'TEXT_EDITOR' and area.spaces.active.text:
                shown.add(area.spaces.active.text.name)
    for text in list(bpy.data.texts):
        if text.get(COLUMN_KEY) == "ppg" and text.name not in shown:
            bpy.data.texts.remove(text)


classes = (MS_PT_ppg_header, MS_PT_ppg_kinematics, MS_PT_ppg_visibility, MS_PT_ppg_data,
           MS_PT_ppg_material, MS_PT_ppg_constraints, MS_OT_ppg_pin, MS_OT_open_ppg)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.save_pre.append(_cleanup_ppg_texts)


def unregister():
    if _cleanup_ppg_texts in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(_cleanup_ppg_texts)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
