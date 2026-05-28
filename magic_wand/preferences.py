from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty
from bpy.types import AddonPreferences, PropertyGroup


class SmartWandPreferences(AddonPreferences):
    bl_idname = __package__ or "magic_wand"

    default_preview_strength: FloatProperty(
        name="Preview Strength",
        description="Global preview opacity used by the modal overlay",
        default=0.35,
        min=0.05,
        max=1.0,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Smart 3D Magic Wand")
        layout.label(text="Selection settings are stored per scene.")


class SceneProperties(PropertyGroup):
    seed_mode: EnumProperty(
        name="Seed From",
        description="Choose the element type used to seed region growth",
        items=(
            ("AUTO", "Auto", "Use Blender's current mesh select mode"),
            ("FACE", "Face", "Seed from the face under the cursor"),
            ("EDGE", "Edge", "Seed from the closest edge under the cursor"),
            ("VERTEX", "Vertex", "Seed from the closest vertex under the cursor"),
        ),
        default="AUTO",
    )

    output_mode: EnumProperty(
        name="Output",
        description="Which mesh element type receives the final selection",
        items=(
            ("AUTO", "Auto", "Match Blender's current selection mode"),
            ("FACE", "Face", "Select faces"),
            ("EDGE", "Edge", "Select edges derived from the region"),
            ("VERTEX", "Vertex", "Select vertices derived from the region"),
        ),
        default="AUTO",
    )

    selection_behavior: EnumProperty(
        name="Selection Mode",
        description="How the new region affects the current selection",
        items=(
            ("REPLACE", "Replace", "Replace the current selection"),
            ("ADD", "Add", "Add the region to the current selection"),
            ("SUBTRACT", "Subtract", "Remove the region from the current selection"),
            ("INTERSECT", "Intersect", "Keep only the overlap with the current selection"),
        ),
        default="REPLACE",
    )

    angle_threshold: FloatProperty(
        name="Angle Threshold",
        description="Maximum face-normal angle difference that can still grow the selection",
        default=35.0,
        min=0.0,
        max=180.0,
    )

    curvature_sensitivity: FloatProperty(
        name="Curvature Sensitivity",
        description="How aggressively local curvature changes block growth",
        default=0.75,
        min=0.0,
        max=4.0,
    )

    max_growth_distance: FloatProperty(
        name="Maximum Growth Distance",
        description="Stop growing once geodesic distance exceeds this value",
        default=0.0,
        min=0.0,
        subtype="DISTANCE",
    )

    tolerance_falloff: FloatProperty(
        name="Tolerance Falloff",
        description="Reduce tolerance as the region grows away from the seed",
        default=0.35,
        min=0.0,
        max=1.0,
    )

    vertex_color_tolerance: FloatProperty(
        name="Vertex Color Tolerance",
        description="Maximum color delta allowed across a transition",
        default=0.15,
        min=0.0,
        max=1.0,
    )

    material_lock: BoolProperty(
        name="Material Lock",
        description="Do not cross material borders",
        default=True,
    )

    uv_boundary_lock: BoolProperty(
        name="UV Boundary Lock",
        description="Do not cross UV seams",
        default=True,
    )

    sharp_edge_blocking: BoolProperty(
        name="Sharp Edge Blocking",
        description="Do not cross sharp or explicitly marked hard edges",
        default=True,
    )

    connected_only: BoolProperty(
        name="Connected Only",
        description="Restrict growth to adjacent topology",
        default=True,
    )

    use_vertex_color: BoolProperty(
        name="Use Vertex Colors",
        description="Use vertex color similarity as a growth signal",
        default=True,
    )

    use_face_normal: BoolProperty(
        name="Use Face Normals",
        description="Use face-normal similarity as a growth signal",
        default=True,
    )

    use_curvature: BoolProperty(
        name="Use Curvature",
        description="Use curvature continuity as a growth signal",
        default=True,
    )

    use_material: BoolProperty(
        name="Use Materials",
        description="Use material similarity as a growth signal",
        default=True,
    )

    use_uv: BoolProperty(
        name="Use UVs",
        description="Use UV seam locking as a growth signal",
        default=True,
    )

    symmetry_aware: BoolProperty(
        name="Symmetry Aware",
        description="Optional future hook for mirrored growth",
        default=False,
    )

    symmetry_axis: EnumProperty(
        name="Symmetry Axis",
        description="Axis used by symmetry-aware growth",
        items=(
            ("X", "X", "Mirror across local X"),
            ("Y", "Y", "Mirror across local Y"),
            ("Z", "Z", "Mirror across local Z"),
        ),
        default="X",
    )

    screen_space_similarity: BoolProperty(
        name="Screen-Space Similarity",
        description="Optional future hook for view-dependent similarity scoring",
        default=False,
    )
