from __future__ import annotations

from dataclasses import dataclass
import time

import bmesh
import bpy
import blf
import gpu
from bpy.types import Operator
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils.bvhtree import BVHTree

from ..cache import GLOBAL_ANALYSIS_CACHE
from ..region_grow import RegionGrowResult, grow_region
from ..similarity import OutputMode, SeedMode, SelectionBehavior, SimilaritySettings


@dataclass(slots=True)
class _PreviewState:
    seed_face: int | None = None
    seed_edge: int | None = None
    seed_vertex: int | None = None
    region: RegionGrowResult | None = None
    mouse_position: tuple[int, int] | None = None


@dataclass(slots=True)
class _PreviewBatches:
    signature: object | None = None
    shader: object | None = None
    tri_batch: object | None = None
    line_batch: object | None = None


_PREVIEW_SHADER = None


def _get_preview_shader():
    global _PREVIEW_SHADER
    if _PREVIEW_SHADER is None:
        _PREVIEW_SHADER = gpu.shader.from_builtin("UNIFORM_COLOR" if bpy.app.version >= (4, 0, 0) else "3D_UNIFORM_COLOR")
    return _PREVIEW_SHADER


class MESH_OT_smart_3d_magic_wand(Operator):
    bl_idname = "mesh.smart_3d_magic_wand"
    bl_label = "Smart 3D Magic Wand"
    bl_description = "Grow a topology-aware mesh selection from a clicked seed element"
    bl_options = {"REGISTER", "UNDO"}

    seed_mode: bpy.props.EnumProperty(
        name="Seed Mode",
        items=(
            ("AUTO", "Auto", "Use Blender's current mesh select mode"),
            ("FACE", "Face", "Seed from the clicked face"),
            ("EDGE", "Edge", "Seed from the closest edge on the clicked face"),
            ("VERTEX", "Vertex", "Seed from the closest vertex on the clicked face"),
        ),
        default="AUTO",
    )

    output_mode: bpy.props.EnumProperty(
        name="Output Mode",
        items=(
            ("AUTO", "Auto", "Match Blender's current mesh select mode"),
            ("FACE", "Face", "Select faces"),
            ("EDGE", "Edge", "Select edges"),
            ("VERTEX", "Vertex", "Select vertices"),
        ),
        default="AUTO",
    )

    selection_behavior: bpy.props.EnumProperty(
        name="Selection Behavior",
        items=(
            ("REPLACE", "Replace", "Replace the current selection"),
            ("ADD", "Add", "Add to the current selection"),
            ("SUBTRACT", "Subtract", "Subtract from the current selection"),
            ("INTERSECT", "Intersect", "Intersect with the current selection"),
        ),
        default="REPLACE",
    )

    def invoke(self, context, event):
        obj = context.object
        if obj is None or obj.type != "MESH" or context.mode != "EDIT_MESH":
            self.report({"ERROR"}, "Open the mesh in Edit Mode first")
            return {"CANCELLED"}

        self._obj = obj
        self._bm = bmesh.from_edit_mesh(obj.data)
        self._bm.verts.ensure_lookup_table()
        self._bm.edges.ensure_lookup_table()
        self._bm.faces.ensure_lookup_table()
        self._bvh = BVHTree.FromBMesh(self._bm)
        self._analysis = GLOBAL_ANALYSIS_CACHE.get_analysis(context, obj, bm=self._bm)
        self._preview = _PreviewState()
        self._preview_handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_preview,
            (context,),
            "WINDOW",
            "POST_VIEW",
        )
        self._ui_handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_overlay,
            (context,),
            "WINDOW",
            "POST_PIXEL",
        )
        self._initial_selection = self._capture_selection()
        self._last_preview_signature = None
        self._last_preview_update_time = 0.0
        self._preview_batches = _PreviewBatches()
        self._overlay_font_id = 0
        try:
            blf.size(self._overlay_font_id, 14)
        except TypeError:
            blf.size(self._overlay_font_id, 14, 72)
        self._update_from_event(context, event)
        self._set_status_text(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._restore_selection()
            self._finish(context)
            return {"CANCELLED"}

        if event.type in {"RET", "NUMPAD_ENTER", "SPACE", "LEFTMOUSE"} and event.value == "PRESS":
            self._apply_preview_selection(context)
            self._finish(context)
            return {"FINISHED"}

        if event.type == "MOUSEMOVE":
            self._update_from_event(context, event)
            return {"RUNNING_MODAL", "PASS_THROUGH"}

        if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} and event.value == "PRESS":
            self._adjust_threshold(context, grow=(event.type == "WHEELUPMOUSE"), event=event)
            self._update_from_event(context, event, force=True)
            return {"RUNNING_MODAL"}

        if event.value == "PRESS" and event.type in {"A", "S", "R", "I"}:
            self._set_selection_behavior(event.type)
            self._update_from_event(context, event, force=True)
            return {"RUNNING_MODAL"}

        if event.value == "PRESS" and event.type == "X":
            props = context.scene.smart_3d_magic_wand
            props.connected_only = not props.connected_only
            self._update_from_event(context, event, force=True)
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL", "PASS_THROUGH"}

    def cancel(self, context):
        self._restore_selection()
        self._finish(context)

    def execute(self, context):
        if not hasattr(self, "_preview") or self._preview.region is None:
            return {"CANCELLED"}
        self._apply_preview_selection(context)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        props = context.scene.smart_3d_magic_wand
        layout.prop(self, "seed_mode")
        layout.prop(self, "output_mode")
        layout.prop(self, "selection_behavior")
        layout.separator()
        layout.prop(props, "angle_threshold")
        layout.prop(props, "curvature_sensitivity")
        layout.prop(props, "max_growth_distance")
        layout.prop(props, "tolerance_falloff")

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def _capture_selection(self):
        return {
            "faces": {face.index for face in self._bm.faces if face.select},
            "edges": {edge.index for edge in self._bm.edges if edge.select},
            "verts": {vert.index for vert in self._bm.verts if vert.select},
        }

    def _restore_selection(self):
        if not hasattr(self, "_bm"):
            return

        self._set_selection_from_sets(
            faces=self._initial_selection["faces"],
            edges=self._initial_selection["edges"],
            verts=self._initial_selection["verts"],
        )
        bmesh.update_edit_mesh(self._obj.data, loop_triangles=False, destructive=False)

    def _finish(self, context):
        handle = getattr(self, "_preview_handle", None)
        if handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
            self._preview_handle = None

        handle = getattr(self, "_ui_handle", None)
        if handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
            self._ui_handle = None

        self._preview_batches = _PreviewBatches()

        if getattr(context, "workspace", None) is not None:
            context.workspace.status_text_set(None)

        if context.area is not None:
            context.area.tag_redraw()

    def _set_status_text(self, context):
        if getattr(context, "workspace", None) is None:
            return

        props = context.scene.smart_3d_magic_wand
        region_size = len(self._preview.region.selected_faces) if self._preview.region else 0
        context.workspace.status_text_set(
            (
                f"Smart 3D Magic Wand | Threshold: {props.angle_threshold:.1f}° | "
                f"Behavior: {self.selection_behavior} | Region faces: {region_size} | "
                "Wheel: threshold | A/S/R/I: add/subtract/replace/intersect | Esc: cancel"
            )
        )

    def _set_selection_behavior(self, key: str):
        mapping = {
            "A": "ADD",
            "S": "SUBTRACT",
            "R": "REPLACE",
            "I": "INTERSECT",
        }
        self.selection_behavior = mapping.get(key, self.selection_behavior)

    @staticmethod
    def _q(value: float, places: int = 5) -> float:
        return round(float(value), places)

    def _preview_signature(self, context, seed_face, seed_edge, seed_vertex):
        props = context.scene.smart_3d_magic_wand
        return (
            seed_face,
            seed_edge,
            seed_vertex,
            self.seed_mode,
            self.output_mode,
            self.selection_behavior,
            self._q(props.angle_threshold),
            self._q(props.curvature_sensitivity),
            self._q(props.max_growth_distance),
            props.material_lock,
            props.uv_boundary_lock,
            props.sharp_edge_blocking,
            props.connected_only,
            self._q(props.tolerance_falloff),
            self._q(props.vertex_color_tolerance),
        )

    def _resolve_seed_mode(self, context) -> SeedMode:
        if self.seed_mode != "AUTO":
            return SeedMode(self.seed_mode)

        mode = getattr(context.tool_settings, "mesh_select_mode", (False, False, True))
        if mode[0]:
            return SeedMode.VERTEX
        if mode[1]:
            return SeedMode.EDGE
        return SeedMode.FACE

    def _resolve_output_mode(self, context) -> OutputMode:
        if self.output_mode != "AUTO":
            return OutputMode(self.output_mode)

        mode = getattr(context.tool_settings, "mesh_select_mode", (False, False, True))
        if mode[0]:
            return OutputMode.VERTEX
        if mode[1]:
            return OutputMode.EDGE
        return OutputMode.FACE

    def _settings(self, context) -> SimilaritySettings:
        props = context.scene.smart_3d_magic_wand
        return SimilaritySettings(
            angle_threshold=props.angle_threshold,
            curvature_sensitivity=props.curvature_sensitivity,
            max_growth_distance=props.max_growth_distance,
            material_lock=props.material_lock,
            uv_boundary_lock=props.uv_boundary_lock,
            sharp_edge_blocking=props.sharp_edge_blocking,
            connected_only=props.connected_only,
            tolerance_falloff=props.tolerance_falloff,
            vertex_color_tolerance=props.vertex_color_tolerance,
            use_face_normal=props.use_face_normal,
            use_curvature=props.use_curvature,
            use_material=props.use_material,
            use_uv=props.use_uv,
            use_vertex_color=props.use_vertex_color,
        )

    def _pick_seed(self, context, event) -> tuple[int | None, int | None, int | None]:
        region = context.region
        rv3d = context.region_data
        if region is None or rv3d is None:
            return None, None, None

        coord = (event.mouse_region_x, event.mouse_region_y)
        origin_world = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        direction_world = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        origin = self._obj.matrix_world.inverted() @ origin_world
        direction = (self._obj.matrix_world.inverted().to_3x3() @ direction_world).normalized()
        location, normal, face_index, distance = self._bvh.ray_cast(origin, direction)
        if face_index is None:
            return None, None, None

        face = self._bm.faces[face_index]
        seed_mode = self._resolve_seed_mode(context)
        if seed_mode == SeedMode.FACE:
            return face.index, None, None

        if seed_mode == SeedMode.EDGE:
            closest_edge = min(
                face.edges,
                key=lambda edge: (edge.calc_center_median() - location).length,
            )
            return face.index, closest_edge.index, None

        if seed_mode == SeedMode.VERTEX:
            closest_vert = min(
                face.verts,
                key=lambda vert: (vert.co - location).length,
            )
            return face.index, None, closest_vert.index

        return face.index, None, None

    def _build_preview(self, context, event, *, force: bool = False):
        seed_face, seed_edge, seed_vertex = self._pick_seed(context, event)
        signature = self._preview_signature(context, seed_face, seed_edge, seed_vertex)
        if not force and signature == self._last_preview_signature:
            return

        self._last_preview_signature = signature

        if seed_face is None:
            self._preview = _PreviewState(mouse_position=(event.mouse_region_x, event.mouse_region_y))
            self._preview_batches = _PreviewBatches()
            return

        self._preview.seed_face = seed_face
        self._preview.seed_edge = seed_edge
        self._preview.seed_vertex = seed_vertex
        self._preview.mouse_position = (event.mouse_region_x, event.mouse_region_y)

        analysis = self._analysis
        if seed_vertex is not None:
            seeds = tuple(analysis.vertex_face_indices[seed_vertex])
        elif seed_edge is not None:
            seeds = tuple(analysis.edge_face_indices[seed_edge])
        else:
            seeds = (seed_face,)

        self._preview.region = grow_region(analysis, seeds, self._settings(context))
        self._rebuild_preview_batches()

    def _update_from_event(self, context, event, *, force: bool = False):
        if event.type == "MOUSEMOVE" and not force:
            now = time.monotonic()
            if now - getattr(self, "_last_preview_update_time", 0.0) < 0.016:
                return
            self._last_preview_update_time = now

        self._build_preview(context, event, force=force)
        self._set_status_text(context)
        if context.area is not None:
            context.area.tag_redraw()

    def _adjust_threshold(self, context, *, grow: bool, event):
        props = context.scene.smart_3d_magic_wand
        step = max(0.5, props.angle_threshold * 0.05)
        if event.shift:
            step *= 5.0
        if event.ctrl:
            step *= 0.2
        props.angle_threshold = max(0.0, min(180.0, props.angle_threshold + step if grow else props.angle_threshold - step))

    def _selected_sets_from_preview(self):
        if self._preview.region is None:
            return set(), set(), set()

        faces = set(self._preview.region.selected_faces)
        edges = set()
        verts = set()
        for face_index in faces:
            edges.update(self._analysis.face_edge_indices[face_index])
            verts.update(self._analysis.face_vertex_indices[face_index])
        return faces, edges, verts

    def _combine(self, current: set[int], new: set[int]) -> set[int]:
        behavior = SelectionBehavior(self.selection_behavior)
        if behavior == SelectionBehavior.REPLACE:
            return set(new)
        if behavior == SelectionBehavior.ADD:
            return set(current) | set(new)
        if behavior == SelectionBehavior.SUBTRACT:
            return set(current) - set(new)
        if behavior == SelectionBehavior.INTERSECT:
            return set(current) & set(new)
        return set(new)

    def _derive_sets_from_faces(self, face_indices: set[int]) -> tuple[set[int], set[int], set[int]]:
        faces = set(face_indices)
        edges = set()
        verts = set()
        for face_index in faces:
            edges.update(self._analysis.face_edge_indices[face_index])
            verts.update(self._analysis.face_vertex_indices[face_index])
        return faces, edges, verts

    def _derive_sets_from_edges(self, edge_indices: set[int]) -> tuple[set[int], set[int], set[int]]:
        edges = set(edge_indices)
        faces = set()
        verts = set()
        for edge_index in edges:
            faces.update(self._analysis.edge_face_indices[edge_index])
            edge = self._bm.edges[edge_index]
            verts.update(vertex.index for vertex in edge.verts)
        return faces, edges, verts

    def _derive_sets_from_verts(self, vert_indices: set[int]) -> tuple[set[int], set[int], set[int]]:
        verts = set(vert_indices)
        faces = set()
        edges = set()
        for vert_index in verts:
            faces.update(self._analysis.vertex_face_indices[vert_index])
            vert = self._bm.verts[vert_index]
            edges.update(edge.index for edge in vert.link_edges)
        return faces, edges, verts

    def _rebuild_preview_batches(self):
        if self._preview.region is None:
            self._preview_batches = _PreviewBatches()
            return

        signature = self._preview.region.selected_faces
        if self._preview_batches.signature == signature and self._preview_batches.tri_batch is not None:
            return

        triangles = []
        outlines = []
        for face_index in signature:
            face = self._bm.faces[face_index]
            world_verts = [self._obj.matrix_world @ vert.co for vert in face.verts]
            if len(world_verts) < 3:
                continue

            base = world_verts[0]
            for i in range(1, len(world_verts) - 1):
                triangles.extend((base, world_verts[i], world_verts[i + 1]))

            for i in range(len(world_verts)):
                outlines.extend((world_verts[i], world_verts[(i + 1) % len(world_verts)]))

        shader = _get_preview_shader()
        tri_batch = batch_for_shader(shader, "TRIS", {"pos": triangles}) if triangles else None
        line_batch = batch_for_shader(shader, "LINES", {"pos": outlines}) if outlines else None
        self._preview_batches = _PreviewBatches(signature=signature, shader=shader, tri_batch=tri_batch, line_batch=line_batch)

    def _set_selection_from_sets(self, *, faces: set[int], edges: set[int], verts: set[int]):
        for face in self._bm.faces:
            face.select = face.index in faces
        for edge in self._bm.edges:
            edge.select = edge.index in edges
        for vert in self._bm.verts:
            vert.select = vert.index in verts

    def _apply_preview_selection(self, context):
        preview_faces, preview_edges, preview_verts = self._selected_sets_from_preview()

        current = self._capture_selection()
        output_mode = self._resolve_output_mode(context)

        if output_mode == OutputMode.FACE:
            selected_faces = self._combine(current["faces"], preview_faces)
            faces, edges, verts = self._derive_sets_from_faces(selected_faces)
        elif output_mode == OutputMode.EDGE:
            selected_edges = self._combine(current["edges"], preview_edges)
            faces, edges, verts = self._derive_sets_from_edges(selected_edges)
        else:
            selected_verts = self._combine(current["verts"], preview_verts)
            faces, edges, verts = self._derive_sets_from_verts(selected_verts)

        self._set_selection_from_sets(faces=faces, edges=edges, verts=verts)

        bmesh.update_edit_mesh(self._obj.data, loop_triangles=False, destructive=False)

    def _draw_preview(self, context):
        if self._preview.region is None:
            return

        batches = getattr(self, "_preview_batches", None)
        if batches is None or batches.tri_batch is None:
            return

        shader = batches.shader or _get_preview_shader()

        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        shader.bind()
        shader.uniform_float("color", (1.0, 0.78, 0.12, 0.20))
        batches.tri_batch.draw(shader)
        shader.uniform_float("color", (1.0, 0.85, 0.2, 0.90))
        gpu.state.line_width_set(2.0)
        if batches.line_batch is not None:
            batches.line_batch.draw(shader)
        gpu.state.line_width_set(1.0)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")

    def _draw_overlay(self, context):
        if context.region is None:
            return

        props = context.scene.smart_3d_magic_wand
        region_size = len(self._preview.region.selected_faces) if self._preview.region else 0

        lines = [
            f"Smart 3D Magic Wand  |  Threshold {props.angle_threshold:.1f}°  |  Region faces {region_size}",
            f"Mode {self.selection_behavior}  |  LMB/Enter commit  |  Wheel adjust  |  Esc cancel",
        ]

        font_id = getattr(self, "_overlay_font_id", 0)
        x = 20
        y = 48

        pad_x = 12
        pad_y = 10
        line_height = 16
        width = max(blf.dimensions(font_id, line)[0] for line in lines) + pad_x * 2
        height = len(lines) * line_height + pad_y * 2

        shader = _get_preview_shader()
        background = [
            (x - pad_x, y - pad_y),
            (x - pad_x + width, y - pad_y),
            (x - pad_x + width, y - pad_y + height),
            (x - pad_x, y - pad_y + height),
        ]
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", (0.05, 0.05, 0.06, 0.72))
        batch_for_shader(shader, "TRIS", {"pos": background[:3] + [background[0], background[2], background[3]]}).draw(shader)
        shader.uniform_float("color", (0.95, 0.84, 0.18, 0.90))
        batch_for_shader(shader, "LINE_STRIP", {"pos": background + [background[0]]}).draw(shader)
        gpu.state.blend_set("NONE")

        y_cursor = y + height - pad_y - 14
        for line in lines:
            blf.position(font_id, x, y_cursor, 0)
            blf.color(font_id, 1.0, 1.0, 1.0, 0.95)
            blf.draw(font_id, line)
            y_cursor -= line_height
