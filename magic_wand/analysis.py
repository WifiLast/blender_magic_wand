from __future__ import annotations

from dataclasses import dataclass

import bmesh

from .adjacency import AdjacencyGraph, build_adjacency_graph


@dataclass(frozen=True, slots=True)
class MeshAnalysis:
    object_name: str
    vertex_count: int
    edge_count: int
    face_count: int
    face_normals: tuple[tuple[float, float, float], ...]
    face_centers: tuple[tuple[float, float, float], ...]
    face_areas: tuple[float, ...]
    face_materials: tuple[int, ...]
    face_curvatures: tuple[float, ...]
    face_colors: tuple[tuple[float, float, float, float] | None, ...]
    face_vertex_indices: tuple[tuple[int, ...], ...]
    face_edge_indices: tuple[tuple[int, ...], ...]
    edge_face_indices: tuple[tuple[int, ...], ...]
    vertex_face_indices: tuple[tuple[int, ...], ...]
    adjacency: AdjacencyGraph


def _vector_to_tuple(value) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))


def _face_color(face, color_layer) -> tuple[float, float, float, float] | None:
    if color_layer is None:
        return None

    values = []
    for loop in face.loops:
        try:
            values.append(tuple(loop[color_layer].color))
        except Exception:
            return None

    if not values:
        return None

    count = len(values)
    component_count = len(values[0])
    return tuple(sum(component[i] for component in values) / count for i in range(component_count))


def build_mesh_analysis(
    obj,
    bm: bmesh.types.BMesh,
    *,
    uv_layer=None,
    color_layer=None,
) -> MeshAnalysis:
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    face_normals: list[tuple[float, float, float]] = []
    face_centers: list[tuple[float, float, float]] = []
    face_areas: list[float] = []
    face_materials: list[int] = []
    face_colors: list[tuple[float, float, float, float] | None] = []
    face_vertex_indices: list[tuple[int, ...]] = []
    face_edge_indices: list[tuple[int, ...]] = []

    for face in bm.faces:
        face_normals.append(_vector_to_tuple(face.normal))
        face_centers.append(_vector_to_tuple(face.calc_center_median()))
        face_areas.append(float(face.calc_area()))
        face_materials.append(int(face.material_index))
        face_colors.append(_face_color(face, color_layer))
        face_vertex_indices.append(tuple(vertex.index for vertex in face.verts))
        face_edge_indices.append(tuple(edge.index for edge in face.edges))

    adjacency = build_adjacency_graph(bm, uv_layer=uv_layer, face_colors=tuple(face_colors))

    edge_face_indices: list[tuple[int, ...]] = []
    for edge in bm.edges:
        edge_face_indices.append(tuple(face.index for face in edge.link_faces))

    vertex_face_indices: list[tuple[int, ...]] = []
    for vert in bm.verts:
        vertex_face_indices.append(tuple(face.index for face in vert.link_faces))

    face_curvatures: list[float] = []
    for face_index, face_neighbors in enumerate(adjacency.neighbors_by_face):
        if not face_neighbors:
            face_curvatures.append(0.0)
            continue
        face_curvatures.append(sum(neighbor.dihedral_angle for neighbor in face_neighbors) / len(face_neighbors))

    return MeshAnalysis(
        object_name=obj.name,
        vertex_count=len(bm.verts),
        edge_count=len(bm.edges),
        face_count=len(bm.faces),
        face_normals=tuple(face_normals),
        face_centers=tuple(face_centers),
        face_areas=tuple(face_areas),
        face_materials=tuple(face_materials),
        face_curvatures=tuple(face_curvatures),
        face_colors=tuple(face_colors),
        face_vertex_indices=tuple(face_vertex_indices),
        face_edge_indices=tuple(face_edge_indices),
        edge_face_indices=tuple(edge_face_indices),
        vertex_face_indices=tuple(vertex_face_indices),
        adjacency=adjacency,
    )
