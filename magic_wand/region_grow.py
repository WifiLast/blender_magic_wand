from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .analysis import MeshAnalysis
from .similarity import SimilaritySettings, evaluate_transition


@dataclass(frozen=True, slots=True)
class RegionGrowResult:
    selected_faces: frozenset[int]
    visited_faces: frozenset[int]
    max_distance: float


def grow_region(
    analysis: MeshAnalysis,
    seed_faces: tuple[int, ...],
    settings: SimilaritySettings,
) -> RegionGrowResult:
    if not seed_faces:
        return RegionGrowResult(frozenset(), frozenset(), 0.0)

    visited: set[int] = set(seed_faces)
    selected: set[int] = set(seed_faces)
    distances: dict[int, float] = {seed_face: 0.0 for seed_face in seed_faces}
    queue = deque(seed_faces)

    while queue:
        face_index = queue.popleft()
        current_distance = distances.get(face_index, 0.0)

        for neighbor in analysis.adjacency.neighbors_by_face[face_index]:
            if neighbor.face_index in visited:
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

            visited.add(neighbor.face_index)
            selected.add(neighbor.face_index)
            distances[neighbor.face_index] = current_distance + neighbor.edge_length
            queue.append(neighbor.face_index)

    return RegionGrowResult(
        selected_faces=frozenset(selected),
        visited_faces=frozenset(visited),
        max_distance=max(distances.values(), default=0.0),
    )
