# 3D Magic Wand


Blender 4.x add-on for topology-aware mesh selection.

## Usage

1. Open a mesh in `Edit Mode`.
2. Launch `Smart 3D Magic Wand` from the `Magic Wand` sidebar tab (press `N` to toggle).
3. Adjust similarity controls in the sidebar as needed.
4. Hover over a face, edge, or vertex and left-click to select the region.
5. While the tool is active:
   - **Mouse Wheel**: Adjust active threshold in real time
   - **Ctrl + Wheel**: Adjust secondary threshold
   - **A/S/R/I**: Switch between add, subtract, replace, and intersect behavior
   - **Shift**: Use larger adjustment steps
   - **V**: Toggle connected vertex limit
   - **X**: Toggle connected-only mode
   - **L**: Enter lock mode to freeze specific vertices
   - **C**: Clear lock points
   - **Left Click**: Commit selection (or use Space/Enter)
   - **Esc**: Cancel

## Features

### Sidebar Controls
- **Launch Magic Wand**: Start the selection tool
- **Similarity Controls**: Fine-tune thresholds before or during selection
  - Angle Threshold: Control face angle differences
  - Connected Vertex Limit: Restrict selection by vertex count
  - Curvature Sensitivity: Adjust surface curvature detection
  - Max Growth Distance: Limit selection radius
  - Tolerance Falloff: Smooth threshold transitions
  - Vertex Color Tolerance: Match vertex colors

### Selection Algorithm
- Region grows from the clicked seed element using adjacency-based flood fill
- Topology-aware expansion respects mesh structure
- Real-time preview shows what will be selected before committing

### Boundary Locks (during tool operation)
- Hard edges can block selection
- UV seams act as barriers
- Material borders prevent crossing
- Sharp curvature changes stop expansion
- Vertex locks constrain specific areas

## Extension points

- `analysis.py`: mesh feature extraction
- `adjacency.py`: graph construction
- `similarity.py`: scoring and thresholds
- `region_grow.py`: BFS/DFS traversal
- `operators/edit.py`: modal viewport interaction
- `cache.py`: analysis caching

