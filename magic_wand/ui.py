from __future__ import annotations

import bpy
from bpy.types import Menu, Panel


def draw_smart_wand_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.menu("VIEW3D_MT_smart_3d_magic_wand")


class VIEW3D_MT_smart_3d_magic_wand(Menu):
    bl_label = "Smart 3D Magic Wand"

    def draw(self, context):
        props = context.scene.smart_3d_magic_wand
        layout = self.layout

        op = layout.operator("mesh.smart_3d_magic_wand", text="Smart 3D Magic Wand")
        op.seed_mode = props.seed_mode
        op.output_mode = props.output_mode
        op.selection_behavior = props.selection_behavior


class SMART3DWAND_PT_main(Panel):
    bl_label = "Smart 3D Magic Wand"
    bl_category = "Magic Wand"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        props = context.scene.smart_3d_magic_wand
        obj = context.object

        if obj is None or obj.type != "MESH":
            layout.label(text="Select a mesh object to begin")
            return

        col = layout.column(align=True)
        op = col.operator("mesh.smart_3d_magic_wand", text="Launch Magic Wand", icon="RESTRICT_SELECT_OFF")
        op.seed_mode = props.seed_mode
        op.output_mode = props.output_mode
        op.selection_behavior = props.selection_behavior

        box = layout.box()
        box.label(text="Similarity Controls")
        box.prop(props, "angle_threshold")
        box.prop(props, "use_connected_vertex_threshold", toggle=True)
        box.prop(props, "max_connected_vertices")
        box.prop(props, "curvature_sensitivity")
        box.prop(props, "max_growth_distance")
        box.prop(props, "tolerance_falloff")
        box.prop(props, "vertex_color_tolerance")
