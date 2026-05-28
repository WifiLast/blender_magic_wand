# Smart 3D Magic Wand

Not tested yet.!!!!
Blender 4.x add-on for topology-aware mesh selection.

## Usage

1. Open a mesh in `Edit Mode`.
2. Launch `Smart 3D Magic Wand` from the `Magic Wand` sidebar tab or the mesh menu.
3. Hover a face, edge, or vertex and left-click to commit the region.
4. Use the toggle in the sidebar to choose the active wheel target.
5. Use the mouse wheel to grow or shrink the active threshold in real time.
6. Hold `Ctrl` while using the mouse wheel to adjust the other threshold.
7. Use `A`, `S`, `R`, `I` to switch between add, subtract, replace, and intersect behavior.

## What it does

- Region grows from the clicked seed element using adjacency-based flood fill.
- Selection stopping rules can lock out hard edges, UV seams, material borders, and sharp curvature changes.
- The preview overlay is non-destructive until commit.

## Extension points

- `analysis.py`: mesh feature extraction
- `adjacency.py`: graph construction
- `similarity.py`: scoring and thresholds
- `region_grow.py`: BFS/DFS traversal
- `operators/edit.py`: modal viewport interaction
- `cache.py`: analysis caching

