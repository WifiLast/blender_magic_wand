from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees
from itertools import combinations

import bmesh


@dataclass(frozen=True, slots=True)
class FaceNeighbor:
    face_index: int
    edge_index: int
    edge_length: float
    dihedral_angle: float
    edge_sharp: bool
    edge_seam: bool
    material_break: bool
    uv_break: bool
    smooth_break: bool
    color_delta: float


@dataclass(frozen=True, slots=True)
class AdjacencyGraph:
    neighbors_by_face: tuple[tuple[FaceNeighbor, ...], ...]
    face_edges: tuple[tuple[int, ...], ...]


def _clamp(value: float, min_value: float = -1.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


def _edge_uv_break(edge: bmesh.types.BMEdge, uv_layer) -> bool:
    if uv_layer is None:
        return False

    uv_values = []
    for loop in edge.link_loops:
        try:
            uv_values.append(tuple(loop[uv_layer].uv))
        except Exception:
            return False

    if len(uv_values) <= 1:
        return False

    first = uv_values[0]
    return any(abs(first[0] - uv[0]) > 1e-5 or abs(first[1] - uv[1]) > 1e-5 for uv in uv_values[1:])


def _face_color_delta(color_a, color_b) -> float:
    if color_a is None or color_b is None:
        return 0.0

    return sum((color_a[i] - color_b[i]) ** 2 for i in range(min(len(color_a), len(color_b)))) ** 0.5


def build_adjacency_graph(
    bm: bmesh.types.BMesh,
    *,
    uv_layer=None,
    face_colors: tuple[tuple[float, float, float, float] | None, ...] | None = None,
) -> AdjacencyGraph:
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    face_edges: list[tuple[int, ...]] = []
    neighbors: list[list[FaceNeighbor]] = [[] for _ in range(len(bm.faces))]

    for face in bm.faces:
        face_edges.append(tuple(edge.index for edge in face.edges))

    for edge in bm.edges:
        linked_faces = list(edge.link_faces)
        if len(linked_faces) < 2:
            continue

        uv_break = _edge_uv_break(edge, uv_layer) or bool(getattr(edge, "seam", False))
        edge_sharp = not bool(getattr(edge, "smooth", True)) or bool(getattr(edge, "sharp", False))
        edge_length = edge.calc_length()

        for face_a, face_b in combinations(linked_faces, 2):
            if face_a.index == face_b.index:
                continue

            if face_a.normal.length > 0.0 and face_b.normal.length > 0.0:
                dot = _clamp(face_a.normal.normalized().dot(face_b.normal.normalized()))
                angle = degrees(acos(dot))
            else:
                angle = 0.0

            color_delta = _face_color_delta(
                None if face_colors is None else face_colors[face_a.index],
                None if face_colors is None else face_colors[face_b.index],
            )

            neighbor_ab = FaceNeighbor(
                face_index=face_b.index,
                edge_index=edge.index,
                edge_length=edge_length,
                dihedral_angle=angle,
                edge_sharp=edge_sharp,
                edge_seam=bool(getattr(edge, "seam", False)),
                material_break=face_a.material_index != face_b.material_index,
                uv_break=uv_break,
                smooth_break=bool(getattr(face_a, "smooth", True)) != bool(getattr(face_b, "smooth", True)),
                color_delta=color_delta,
            )
            neighbor_ba = FaceNeighbor(
                face_index=face_a.index,
                edge_index=edge.index,
                edge_length=edge_length,
                dihedral_angle=angle,
                edge_sharp=edge_sharp,
                edge_seam=bool(getattr(edge, "seam", False)),
                material_break=face_b.material_index != face_a.material_index,
                uv_break=uv_break,
                smooth_break=bool(getattr(face_b, "smooth", True)) != bool(getattr(face_a, "smooth", True)),
                color_delta=color_delta,
            )
            neighbors[face_a.index].append(neighbor_ab)
            neighbors[face_b.index].append(neighbor_ba)

    return AdjacencyGraph(
        neighbors_by_face=tuple(tuple(face_neighbors) for face_neighbors in neighbors),
        face_edges=tuple(face_edges),
    )
