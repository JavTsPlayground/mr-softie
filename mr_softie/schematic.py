# SPDX-License-Identifier: GPL-3.0-or-later
"""Schematic view: a live, editable graph of the scene.

A custom node tree with one node per object:
  * white links  = parenting (drag a link to re-parent, cut it to un-parent)
  * orange links = constraints (shown, read-only)
Selection is two-way: pick nodes to select objects and vice versa.
The tree is rebuilt from the scene incrementally; node positions you set are kept.
"""
import bpy
from bpy.props import PointerProperty, StringProperty
from bpy.types import Node, NodeSocket, NodeTree

TREE_ID = "MRSoftieSchematicTree"
NODE_ID = "MRSoftieSchematicNode"
HIER_SOCKET = "MRSoftieHierSocket"
CNS_SOCKET = "MRSoftieCnsSocket"
TREE_NAME = "Schematic"

NODE_W, GAP_X, GAP_Y = 120.0, 70.0, 50.0

TYPE_COLORS = {
    'MESH': (0.55, 0.62, 0.72), 'CAMERA': (0.55, 0.72, 0.55), 'LIGHT': (0.80, 0.76, 0.45),
    'EMPTY': (0.82, 0.82, 0.82), 'CURVE': (0.50, 0.72, 0.72), 'ARMATURE': (0.70, 0.58, 0.76),
    'LATTICE': (0.72, 0.62, 0.52), 'FONT': (0.62, 0.70, 0.58),
}
TYPE_ICONS = {
    'MESH': 'MESH_DATA', 'CAMERA': 'CAMERA_DATA', 'LIGHT': 'LIGHT', 'EMPTY': 'EMPTY_AXIS',
    'CURVE': 'CURVE_DATA', 'ARMATURE': 'ARMATURE_DATA', 'LATTICE': 'LATTICE_DATA', 'FONT': 'FONT_DATA',
}

_state = {"syncing": False, "node_selection": None, "scheduled": False}


# --------------------------------------------------------------------------
# Tree, sockets, node
# --------------------------------------------------------------------------

class MS_SchematicTree(NodeTree):
    """Scene graph: objects, parenting and constraints"""
    bl_idname = TREE_ID
    bl_label = "Schematic"
    bl_icon = 'OUTLINER'

    def update(self):
        if not _state["syncing"]:
            _apply_user_links(self)


class MS_HierSocket(NodeSocket):
    bl_idname = HIER_SOCKET
    bl_label = "Hierarchy"

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    @classmethod
    def draw_color_simple(cls):
        return (0.95, 0.95, 0.95, 1.0)


class MS_CnsSocket(NodeSocket):
    bl_idname = CNS_SOCKET
    bl_label = "Constraint"

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    @classmethod
    def draw_color_simple(cls):
        return (1.0, 0.55, 0.1, 1.0)


class MS_SchematicNode(Node):
    """An object in the scene"""
    bl_idname = NODE_ID
    bl_label = "Object"
    bl_width_default = NODE_W

    obj: PointerProperty(type=bpy.types.Object)

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == TREE_ID

    def init(self, context):
        self.inputs.new(HIER_SOCKET, "Parent")
        cns = self.inputs.new(CNS_SOCKET, "Cns")
        cns.link_limit = 4095
        self.outputs.new(HIER_SOCKET, "Children").link_limit = 4095
        self.outputs.new(CNS_SOCKET, "Cns Target").link_limit = 4095

    def draw_label(self):
        return self.obj.name if self.obj else "(deleted)"

    def draw_buttons(self, context, layout):
        obj = self.obj
        if obj is None:
            return
        row = layout.row(align=True)
        row.label(text=obj.type.title(), icon=TYPE_ICONS.get(obj.type, 'OBJECT_DATA'))
        row.prop(obj, "hide_select", text="", emboss=False)
        row.prop(obj, "hide_render", text="", emboss=False)


# --------------------------------------------------------------------------
# Sync scene -> tree
# --------------------------------------------------------------------------

def get_tree(create=False):
    tree = next((t for t in bpy.data.node_groups if t.bl_idname == TREE_ID), None)
    if tree is None and create:
        tree = bpy.data.node_groups.new(TREE_NAME, TREE_ID)
        tree.use_fake_user = True
    return tree


def _layout_positions(objects):
    """Left-to-right tree: children sit to the right of their parent, siblings stack down.

    Node sockets are on the sides (parent output on the right, child input on the
    left), so this keeps every hierarchy link short and uncrossed.
    """
    children = {}
    roots = []
    names = {o.name for o in objects}
    for obj in sorted(objects, key=lambda o: o.name):
        if obj.parent is not None and obj.parent.name in names:
            children.setdefault(obj.parent.name, []).append(obj)
        else:
            roots.append(obj)
    positions = {}
    row = [0]

    def place(obj, depth):
        positions[obj.name] = (depth * (NODE_W + GAP_X), -row[0] * GAP_Y)
        row[0] += 1
        for kid in children.get(obj.name, []):
            place(kid, depth + 1)

    for root in roots:
        place(root, 0)
    return positions


def sync(tree=None, scene=None, relayout=False):
    tree = tree or get_tree()
    if tree is None:
        return
    scene = scene or bpy.context.scene
    objects = list(scene.objects)
    _state["syncing"] = True
    try:
        nodes = {}
        for node in list(tree.nodes):
            if node.bl_idname != NODE_ID or node.obj is None or node.obj.name not in scene.objects:
                tree.nodes.remove(node)
            else:
                nodes[node.obj.name] = node

        positions = _layout_positions(objects)
        for obj in objects:
            node = nodes.get(obj.name)
            created = node is None
            if created:
                node = tree.nodes.new(NODE_ID)
                node.obj = obj
                node.width = NODE_W
                node.hide = True          # compact name boxes; links still attach
                nodes[obj.name] = node
            if created or relayout:
                node.location = positions.get(obj.name, (0.0, 0.0))
            # Write only on change: every write tags an update.
            if not node.use_custom_color:
                node.use_custom_color = True
            color = TYPE_COLORS.get(obj.type, (0.7, 0.7, 0.7))
            if any(abs(a - b) > 1e-4 for a, b in zip(node.color, color)):
                node.color = color

        # Desired links
        want = set()
        for obj in objects:
            if obj.parent is not None and obj.parent.name in nodes:
                want.add(("H", obj.parent.name, obj.name))
            for con in getattr(obj, "constraints", []):
                target = getattr(con, "target", None)
                if target is not None and target.name in nodes and target != obj:
                    want.add(("C", target.name, obj.name))
        have = {}
        for link in tree.links:
            kind = "H" if link.to_socket.bl_idname == HIER_SOCKET else "C"
            have[(kind, link.from_node.obj.name if link.from_node.obj else "",
                  link.to_node.obj.name if link.to_node.obj else "")] = link
        for key, link in have.items():
            if key not in want:
                tree.links.remove(link)
        for kind, src, dst in want - set(have):
            if kind == "H":
                tree.links.new(nodes[src].outputs["Children"], nodes[dst].inputs["Parent"])
            else:
                tree.links.new(nodes[src].outputs["Cns Target"], nodes[dst].inputs["Cns"])

        for node in nodes.values():
            for sock in (node.inputs["Cns"], node.outputs["Cns Target"]):
                hidden = not sock.is_linked
                if sock.hide != hidden:
                    sock.hide = hidden

        # Selection
        active = bpy.context.view_layer.objects.active if bpy.context.view_layer else None
        for name, node in nodes.items():
            selected = node.obj.select_get()
            if node.select != selected:
                node.select = selected
        if active is not None and active.name in nodes and tree.nodes.active != nodes[active.name]:
            tree.nodes.active = nodes[active.name]
        _state["node_selection"] = _selected_names(tree)
    finally:
        _state["syncing"] = False


def _selected_names(tree):
    return frozenset(n.obj.name for n in tree.nodes if n.bl_idname == NODE_ID and n.select and n.obj)


# --------------------------------------------------------------------------
# Tree -> scene (user edits)
# --------------------------------------------------------------------------

def _is_descendant(obj, maybe_parent):
    p = maybe_parent
    while p is not None:
        if p == obj:
            return True
        p = p.parent
    return False


def _apply_user_links(tree):
    if not MS_SchematicNode.is_registered:
        return
    changed = False
    for node in tree.nodes:
        if node.bl_idname != NODE_ID or node.obj is None:
            continue
        links = node.inputs["Parent"].links
        new_parent = links[0].from_node.obj if links else None
        obj = node.obj
        if new_parent is obj.parent:
            continue
        if new_parent is not None and _is_descendant(obj, new_parent):
            continue  # would create a cycle; the next sync removes the link
        world = obj.matrix_world.copy()
        obj.parent = new_parent
        obj.matrix_world = world
        changed = True
    if changed:
        schedule_sync()


def _poll_node_selection():
    """Push node selection to objects when the user picks nodes."""
    tree = get_tree()
    if tree is None or not _schematic_visible():
        return 0.5
    current = _selected_names(tree)
    if _state["node_selection"] is not None and current != _state["node_selection"]:
        _state["node_selection"] = current
        view_layer = bpy.context.view_layer
        for obj in view_layer.objects:
            want = obj.name in current
            if obj.select_get() != want:
                try:
                    obj.select_set(want)
                except RuntimeError:
                    pass
        active = tree.nodes.active
        if active is not None and active.bl_idname == NODE_ID and active.obj is not None \
                and active.obj.name in view_layer.objects:
            view_layer.objects.active = active.obj
    return 0.25


def _schematic_visible():
    wm = bpy.context.window_manager
    if wm is None:
        return False
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == 'NODE_EDITOR' and area.spaces.active.tree_type == TREE_ID:
                return True
    return False


def _redraw_schematic():
    wm = bpy.context.window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == 'NODE_EDITOR' and area.spaces.active.tree_type == TREE_ID:
                area.tag_redraw()


def schedule_sync():
    if _state["scheduled"]:
        return

    def _run():
        _state["scheduled"] = False
        try:
            sync()
            _redraw_schematic()
        except (RuntimeError, ReferenceError, KeyError) as ex:
            print(f"[MR.Softie] schematic sync failed: {ex}")
        return None
    _state["scheduled"] = True
    bpy.app.timers.register(_run, first_interval=0.05)


@bpy.app.handlers.persistent
def _on_depsgraph_update(_scene, _depsgraph):
    # Only keep the graph live while a Schematic is on screen; opening one syncs it.
    if not _state["syncing"] and get_tree() is not None and _schematic_visible():
        schedule_sync()


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------

class MS_OT_schematic_relayout(bpy.types.Operator):
    """Re-arrange the schematic as a tree"""
    bl_idname = "mr_softie.schematic_relayout"
    bl_label = "Rearrange"

    def execute(self, context):
        sync(get_tree(create=True), context.scene, relayout=True)
        if context.area is not None and context.area.type == 'NODE_EDITOR':
            frame_when_ready(context.window, context.area, tries=3)
        return {'FINISHED'}


class MS_OT_open_schematic(bpy.types.Operator):
    """Open the Schematic view in a floating window"""
    bl_idname = "mr_softie.open_schematic"
    bl_label = "Schematic"

    def execute(self, context):
        from .operators import open_floating_window
        tree = get_tree(create=True)
        sync(tree, context.scene, relayout=len(tree.nodes) == 0)
        window, area = open_floating_window(context, 'NODE_EDITOR')
        if area is None:
            self.report({'WARNING'}, "Could not open a window")
            return {'CANCELLED'}
        area.ui_type = TREE_ID
        space = area.spaces.active
        space.node_tree = tree
        space.show_region_ui = False
        space.show_region_toolbar = False
        frame_when_ready(window, area)
        return {'FINISHED'}


def frame_when_ready(window, area, tries=10):
    """Frame all nodes once the new window has a sized region (retries for ~1s)."""
    attempts = [0]

    def _frame():
        attempts[0] += 1
        try:
            region = next(r for r in area.regions if r.type == 'WINDOW')
            if region.width < 10 and attempts[0] < tries:
                return 0.1
            with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=region):
                bpy.ops.node.view_all()
        except (RuntimeError, StopIteration, ReferenceError):
            if attempts[0] < tries:
                return 0.1
        return None
    bpy.app.timers.register(_frame, first_interval=0.15)


def draw_node_header(self, context):
    space = context.space_data
    if getattr(space, "tree_type", "") == TREE_ID:
        self.layout.operator("mr_softie.schematic_relayout", icon='OUTLINER')


# Sockets and node before the tree: registering the tree makes Blender update
# trees already in the file, and those nodes must be valid by then.
classes = (MS_HierSocket, MS_CnsSocket, MS_SchematicNode, MS_SchematicTree,
           MS_OT_schematic_relayout, MS_OT_open_schematic)


def register():
    _state["syncing"] = True     # ignore tree updates fired during registration
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
    finally:
        _state["syncing"] = False
    bpy.types.NODE_HT_header.append(draw_node_header)
    bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)
    if not bpy.app.timers.is_registered(_poll_node_selection):
        bpy.app.timers.register(_poll_node_selection, first_interval=1.0, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_poll_node_selection):
        bpy.app.timers.unregister(_poll_node_selection)
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
    bpy.types.NODE_HT_header.remove(draw_node_header)
    _state["syncing"] = True
    try:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
    finally:
        _state["syncing"] = False
