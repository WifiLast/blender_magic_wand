from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .analysis import MeshAnalysis
from .similarity import SimilaritySettings, evaluate_transition


@dataclass(frozen=True, slots=True)
class RegionGrowResult:
    selected_faces: frozenset[int]
    visited_faces: frozenset[int]
    selected_vertices: frozenset[int]
    max_distance: float


def grow_region(
    analysis: MeshAnalysis,
    seed_faces: tuple[int, ...],
    settings: SimilaritySettings,
) -> RegionGrowResult:
    if not seed_faces:
        return RegionGrowResult(frozenset(), frozenset(), frozenset(), 0.0)

    selected: set[int] = set(seed_faces)
    selected_vertices: set[int] = set()
    distances: dict[int, float] = {seed_face: 0.0 for seed_face in seed_faces}
    queue = deque(seed_faces)
    queued: set[int] = set(seed_faces)

    for face_index in seed_faces:
        selected_vertices.update(analysis.face_vertex_indices[face_index])

    while queue:
        face_index = queue.popleft()
        current_distance = distances.get(face_index, 0.0)

        for neighbor in analysis.adjacency.neighbors_by_face[face_index]:
            if neighbor.face_index in queued:
                continue

            allowed, score = evaluate_transition(
                analysis,
                face_index,
                neighbor,
                settings,
                current_distance,
            )
            if not allowed:
                continue

            if settings.lock_points:
                neighbor_vertices = set(analysis.face_vertex_indices[neighbor.face_index])
                if neighbor_vertices & settings.lock_points:
                    continue

            queued.add(neighbor.face_index)

            if settings.use_connected_vertex_threshold:
                candidate_vertices = set(analysis.face_vertex_indices[neighbor.face_index])
                new_vertices = candidate_vertices - selected_vertices

                distance_ratio = (
                    (current_distance + neighbor.edge_length) / max(settings.max_growth_distance, 1e-6)
                    if settings.max_growth_distance > 0
                    else 0
                )
                distance_factor = 1.0 - (settings.vertex_distance_bias * distance_ratio)
                effective_max = int(settings.max_connected_vertices * max(0.3, distance_factor))

                if len(selected_vertices) + len(new_vertices) > effective_max:
                    queue.append(neighbor.face_index)
                    continue

            selected.add(neighbor.face_index)
            selected_vertices.update(analysis.face_vertex_indices[neighbor.face_index])
            distances[neighbor.face_index] = current_distance + neighbor.edge_length
            queue.append(neighbor.face_index)

    return RegionGrowResult(
        selected_faces=frozenset(selected),
        visited_faces=frozenset(queued),
        selected_vertices=frozenset(selected_vertices),
        max_distance=max(distances.values(), default=0.0),
    )
