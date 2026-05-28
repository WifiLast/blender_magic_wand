from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict

import bmesh

from .analysis import MeshAnalysis, build_mesh_analysis


@dataclass(frozen=True, slots=True)
class CacheKey:
    object_ptr: int
    mesh_ptr: int
    vertex_count: int
    edge_count: int
    face_count: int
    uv_layer_name: str
    color_layer_name: str


@dataclass(slots=True)
class CacheEntry:
    key: CacheKey
    analysis: MeshAnalysis


class AnalysisCache:
    def __init__(self, max_entries: int = 4) -> None:
        self._entries: OrderedDict[CacheKey, CacheEntry] = OrderedDict()
        self._max_entries = max_entries

    def clear(self) -> None:
        self._entries.clear()

    def get_analysis(self, context, obj, *, bm: bmesh.types.BMesh) -> MeshAnalysis:
        uv_layer = bm.loops.layers.uv.active
        color_layer = bm.loops.layers.color.active
        key = CacheKey(
            object_ptr=obj.as_pointer(),
            mesh_ptr=obj.data.as_pointer(),
            vertex_count=len(bm.verts),
            edge_count=len(bm.edges),
            face_count=len(bm.faces),
            uv_layer_name=getattr(uv_layer, "name", ""),
            color_layer_name=getattr(color_layer, "name", ""),
        )

        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)
            return entry.analysis

        analysis = build_mesh_analysis(obj, bm, uv_layer=uv_layer, color_layer=color_layer)
        self._entries[key] = CacheEntry(key=key, analysis=analysis)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        return analysis


GLOBAL_ANALYSIS_CACHE = AnalysisCache()
