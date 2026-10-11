# SPDX-License-Identifier: GPL-3.0-or-later
"""Light-gray, black-text interface theme in the spirit of classic DCC apps.

Applied on request only (it edits the user's theme preferences).
Blender's "Reset to Default Theme" restores everything.
"""
import bpy

UI_GRAY = (0.69, 0.69, 0.69)        # panels / widgets
UI_GRAY_DARK = (0.58, 0.58, 0.58)   # region backgrounds
HEADER_GRAY = (0.62, 0.62, 0.62)
VIEWPORT_GRAY = (0.50, 0.50, 0.50)
TEXT = (0.0, 0.0, 0.0)
TEXT_HI = (1.0, 1.0, 1.0)
SELECT_BLUE = (0.30, 0.42, 0.62)
WHITE = (1.0, 1.0, 1.0)
BLACK = (0.0, 0.0, 0.0)


def _set(obj, attr, value):
    """Set a color, matching RGB vs RGBA length. Silently skip unknown attrs."""
    if obj is None or not hasattr(obj, attr):
        return False
    try:
        current = getattr(obj, attr)
        if hasattr(current, "__len__") and len(current) == 4 and len(value) == 3:
            value = (*value, current[3])
        setattr(obj, attr, value)
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def _iter_spaces(theme):
    for prop in theme.bl_rna.properties:
        if prop.type != 'POINTER':
            continue
        sub = getattr(theme, prop.identifier, None)
        space = getattr(sub, "space", None)
        if space is not None:
            yield sub, space


def apply(theme=None):
    theme = theme or bpy.context.preferences.themes[0]
    changed = 0

    # Widgets: light gray with black text, blue when active.
    ui = theme.user_interface
    for prop in ui.bl_rna.properties:
        if not prop.identifier.startswith("wcol_"):
            continue
        wcol = getattr(ui, prop.identifier)
        changed += _set(wcol, "inner", UI_GRAY)
        changed += _set(wcol, "inner_sel", SELECT_BLUE)
        changed += _set(wcol, "item", (0.45, 0.45, 0.45))
        changed += _set(wcol, "text", TEXT)
        changed += _set(wcol, "text_sel", TEXT_HI)
        changed += _set(wcol, "outline", (0.35, 0.35, 0.35))
    # Text fields and menus read better a touch lighter.
    for name in ("wcol_text", "wcol_num", "wcol_numslider"):
        changed += _set(getattr(ui, name, None), "inner", (0.80, 0.80, 0.80))
    for name in ("wcol_menu_back", "wcol_tooltip", "wcol_pulldown"):
        changed += _set(getattr(ui, name, None), "inner", (0.74, 0.74, 0.74))

    # Every editor: gray backgrounds, black text.
    for _editor, space in _iter_spaces(theme):
        changed += _set(space, "back", UI_GRAY_DARK)
        changed += _set(space, "header", HEADER_GRAY)
        changed += _set(space, "header_text", TEXT)
        changed += _set(space, "text", TEXT)
        changed += _set(space, "text_hi", TEXT_HI)
        changed += _set(space, "title", TEXT)
        changed += _set(space, "button", UI_GRAY)
        changed += _set(space, "button_text", TEXT)
        changed += _set(space, "button_title", TEXT)
        changed += _set(space, "tab_back", UI_GRAY_DARK)
        changed += _set(space, "tab_inactive", (0.52, 0.52, 0.52))
        changed += _set(space, "tab_active", UI_GRAY)
        panel = getattr(space, "panelcolors", None)
        changed += _set(panel, "header", HEADER_GRAY)
        changed += _set(panel, "back", UI_GRAY)
        changed += _set(panel, "sub_back", (0.64, 0.64, 0.64))

    # Panels and region backgrounds (Blender 4.x/5.x keep these outside the editors).
    changed += _set(ui, "panel_header", HEADER_GRAY)
    changed += _set(ui, "panel_back", UI_GRAY)
    changed += _set(ui, "panel_sub_back", (0.64, 0.64, 0.64, 1.0))
    changed += _set(ui, "panel_title", TEXT)
    changed += _set(ui, "panel_text", TEXT)
    changed += _set(ui, "panel_outline", (0.4, 0.4, 0.4, 1.0))
    changed += _set(ui, "editor_border", (0.36, 0.36, 0.36))
    regions = getattr(theme, "regions", None)
    if regions is not None:
        sidebars = getattr(regions, "sidebars", None)
        changed += _set(sidebars, "back", (*UI_GRAY_DARK, 1.0))
        changed += _set(sidebars, "tab_back", (*HEADER_GRAY, 1.0))
        for name in ("channels", "scrubbing"):
            sub = getattr(regions, name, None)
            changed += _set(sub, "back", HEADER_GRAY)
            changed += _set(sub, "text", TEXT)
    text_editor = getattr(theme, "text_editor", None)
    changed += _set(text_editor, "line_numbers_background", UI_GRAY_DARK)

    # 3D viewport: flat gray background, black wire, white selection.
    v3d = theme.view_3d
    grad = getattr(v3d.space, "gradients", None)
    if grad is not None:
        try:
            grad.background_type = 'SINGLE_COLOR'
        except (TypeError, AttributeError):
            pass
        changed += _set(grad, "high_gradient", VIEWPORT_GRAY)
    changed += _set(v3d, "wire", BLACK)
    changed += _set(v3d, "wire_edit", BLACK)
    changed += _set(v3d, "object_selected", WHITE)
    changed += _set(v3d, "object_active", WHITE)
    changed += _set(v3d, "grid", (0.40, 0.40, 0.40))
    changed += _set(v3d, "edge_select", (1.0, 0.55, 0.0))
    changed += _set(v3d, "vertex_select", (1.0, 0.55, 0.0))
    changed += _set(v3d, "face_select", (1.0, 0.55, 0.0))
    return changed
