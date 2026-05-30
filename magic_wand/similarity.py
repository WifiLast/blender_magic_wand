from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from .adjacency import FaceNeighbor
from .analysis import MeshAnalysis


class SelectionBehavior(str, Enum):
    REPLACE = "REPLACE"
    ADD = "ADD"
    SUBTRACT = "SUBTRACT"
    INTERSECT = "INTERSECT"


class SeedMode(str, Enum):
    AUTO = "AUTO"
    FACE = "FACE"
    EDGE = "EDGE"
    VERTEX = "VERTEX"


class OutputMode(str, Enum):
    AUTO = "AUTO"
    FACE = "FACE"
    EDGE = "EDGE"
    VERTEX = "VERTEX"


@dataclass(frozen=True, slots=True)
class SimilaritySettings:
    angle_threshold: float = 35.0
    use_connected_vertex_threshold: bool = False
    max_connected_vertices: int = 256
    curvature_sensitivity: float = 0.75
    max_growth_distance: float = 1.0e6
    material_lock: bool = True
    uv_boundary_lock: bool = True
    sharp_edge_blocking: bool = True
    connected_only: bool = True
    tolerance_falloff: float = 0.35
    vertex_color_tolerance: float = 0.15
    vertex_distance_bias: float = 0.5
    lock_points: frozenset[int] = frozenset()
    use_face_normal: bool = True
    use_curvature: bool = True
    use_material: bool = True
    use_uv: bool = True
    use_vertex_color: bool = True


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _normalize_distance(distance: float, max_distance: float) -> float:
    if max_distance <= 0.0:
        return 0.0
    return _clamp(distance / max_distance)


def _allowed_angle(settings: SimilaritySettings, distance: float) -> float:
    distance_ratio = _normalize_distance(distance, settings.max_growth_distance)
    falloff = _clamp(1.0 - settings.tolerance_falloff * distance_ratio, 0.15, 1.0)
    return settings.angle_threshold * falloff


def _curvature_limit(settings: SimilaritySettings) -> float:
    return max(0.1, settings.angle_threshold * max(0.1, settings.curvature_sensitivity))


def can_grow_to_neighbor(
    analysis: MeshAnalysis,
    current_face: int,
    neighbor: FaceNeighbor,
    settings: SimilaritySettings,
    current_distance: float,
) -> tuple[bool, float]:
    if settings.max_growth_distance > 0.0 and current_distance + neighbor.edge_length > settings.max_growth_distance:
        return False, 0.0

    if settings.use_material and settings.material_lock and neighbor.material_break:
        return False, 0.0

    if settings.use_uv and settings.uv_boundary_lock and neighbor.uv_break:
        return False, 0.0

    if settings.sharp_edge_blocking and neighbor.edge_sharp:
        return False, 0.0

    curvature_delta = abs(analysis.face_curvatures[current_face] - analysis.face_curvatures[neighbor.face_index])
    curvature_limit = _curvature_limit(settings)
    color_delta = neighbor.color_delta

    if not settings.use_connected_vertex_threshold:
        if settings.use_face_normal:
            if neighbor.dihedral_angle > _allowed_angle(settings, current_distance):
                return False, 0.0

        if settings.use_curvature and curvature_delta > curvature_limit:
            return False, 0.0

    if settings.use_vertex_color and color_delta > settings.vertex_color_tolerance:
        return False, 0.0

    score = 1.0
    if not settings.use_connected_vertex_threshold:
        if settings.use_face_normal:
            normal_score = 1.0 - _clamp(neighbor.dihedral_angle / max(settings.angle_threshold, 1e-6))
            score *= _clamp(normal_score)

        if settings.use_curvature:
            curvature_score = 1.0 - _clamp(curvature_delta / max(curvature_limit, 1e-6))
            score *= _clamp(curvature_score)

    if settings.use_vertex_color:
        color_score = 1.0 - _clamp(color_delta / max(settings.vertex_color_tolerance, 1e-6))
        score *= _clamp(color_score)

    distance_ratio = _normalize_distance(current_distance + neighbor.edge_length, settings.max_growth_distance)
    if settings.max_growth_distance > 0.0:
        score *= 1.0 - settings.tolerance_falloff * distance_ratio

    return score > 0.15, _clamp(score)


def initial_indices(
    analysis: MeshAnalysis,
    *,
    face_index: int,
    edge_index: int | None = None,
    vertex_index: int | None = None,
) -> tuple[int, ...]:
    if vertex_index is not None:
        return tuple(
            face_index
            for face_index, face_vertices in enumerate(analysis.face_vertex_indices)
            if vertex_index in face_vertices
        )

    if edge_index is not None:
        return tuple(
            face_index
            for face_index, face_edges in enumerate(analysis.adjacency.face_edges)
            if edge_index in face_edges
        )

    return (face_index,)
