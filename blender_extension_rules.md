# Blender Extension Rules

This file captures the submission and development rules from `blender_extension_rules.txt` in a structured format.

## Extension Submission Requirements

- Respect Blender's `Allow Online Access` setting.
  - Do not make network connections when `bpy.app.online_access` is `False`.
- Do not interfere with other add-ons.
  - Installing, updating, removing, or otherwise modifying other add-ons is forbidden.
  - If a feature depends on another extension, raise an error only when the dependent functionality is used.
- Keep the add-on self-contained.
  - Do not install Python modules, pip packages, wheels, or similar dependencies at runtime.
  - If extra software is required and cannot be bundled, the user must run it manually.
- Keep module loading inside the add-on namespace.
  - Load modules only as package submodules.
  - Do not alter Python's global module search path or inject modules into the global module dictionary.
- Support system installation and read-only filesystems.
  - Do not write files into the add-on's own directory.
  - Use `bpy.utils.extension_path_user(__package__, create=True)` for user-local storage.

## Python Style Guide

- Follow PEP 8.
- Use four spaces for indentation.
- Use Unix line endings (`LF`).
- Put spaces around operators, except in keyword arguments.
- Use `CamelCase` for classes and exception types.
- Use `underscore_case` for functions, variables, and other identifiers.

## Formatting

- Most Python code is formatted automatically with `autopep8`.
- Use `make format` to format the repository's C/C++ and Python code.

## Additions to PEP 8

### Naming

- Avoid shadowing Python built-ins, constants, types, and exceptions.
  - Prefer `obj` over `object`.
  - Use more specific names instead of generic ones like `list`, `m`, or `c`.
- Avoid overly short names.
  - Prefer `mesh` and `curve` over abbreviations like `me` and `cu`.
- Use type annotations when they improve clarity.

### Unused Variables and Arguments

- Prefix intentionally unused variables or arguments with an underscore.
- Example: `def draw(self, _context):`

## Exceptions to PEP 8

- Maximum line width is `120` characters for all scripts.
- Imports may be placed inside functions or methods.
  - This is intentional to reduce Blender startup overhead.

## Conventions for Core Scripts

These apply to scripts that run at Blender startup, such as `scripts/startup` and modules loaded during startup.

- Postpone imports when possible.
  - Import modules inside functions or methods if that avoids unnecessary startup cost.
- Do not use type annotations unless they are required for `bpy.props`.
- Use `str.format(...)` instead of f-strings or `%` formatting.
  - Prefer positional arguments.
  - Use type specifiers like `{:s}`, `{:d}`, and `{:f}` when appropriate.
- Use single quotes for enumerator literals, such as `ob.type == 'MESH'`.
- Use double quotes for ordinary strings, such as UI labels.

## Add-on Development Setup

- Blender add-ons are written in Python and use Blender's bundled Python runtime.
- External Python installation is only needed for IDE support and tooling.
- Any IDE may be used, but VS Code is the most supported option.
- For code completion, community stub packages such as `fake-bpy-module` are commonly used.
- For local development, install the add-on as an extension through a local repository.
- If the project root does not contain `blender_manifest.toml` and `__init__.py`, symlink the actual add-on directory instead.

## Reloading Scripts

- Keep the import structure clear so Blender can reload the add-on during development.
- In the main `__init__.py`, detect reloads by checking whether `bpy` is already in `locals()`.
- On reload, use `importlib.reload(...)` for submodules.
- If importing subdirectories as modules, set up similar reload detection in their `__init__.py` files as well.

## Python Threads

- Do not use long-lived Python threads in Blender add-ons.
  - Blender's Python integration is not thread-safe.
  - Threads can cause crashes during rendering, drivers, drawing, or background operations.
- If background work is needed, prefer `multiprocessing`.
- If threads are used at all, they must finish before any further Blender API access.

## Edit Mode and Mesh Access

- Be careful when accessing mesh data in Edit Mode.
  - `obj.data` may be out of sync with edit mesh data.
- Safer approaches include:
  - Exit Edit Mode before running the tool.
  - Explicitly sync mesh data with `bmesh.types.BMesh.to_mesh()`.
  - Work directly on edit-mode data with `bmesh.from_edit_mesh()`.
  - Restrict the operator to Object Mode or another valid context.

## Mesh Data Types

Blender exposes three common face representations:

- `bpy.types.MeshPolygon`
  - Object-mode face storage.
  - Efficient for reading/exporting polygons.
  - Poor for editing.
- `bpy.types.MeshLoopTriangle`
  - Tessellated triangle output.
  - Useful when the target format does not support n-gons.
  - Not suitable for editing geometry.
- `bmesh.types.BMFace`
  - Edit-mode face representation.
  - Best choice for editing and creation workflows.

### Practical Guidance

- Use `MeshPolygon` for efficient object-mode storage and export when n-gons are acceptable.
- Use `MeshLoopTriangle` when exporting to triangle-only formats.
- Use `BMesh` when creating or editing geometry one mesh at a time.

## Armature Data Types

Blender exposes bones through three different data structures:

- `EditBone`
  - Available only in Edit Mode.
  - Use for creating bones, changing head/tail, roll, and parenting.
- `Bone`
  - Available in Object Mode and Pose Mode.
  - Read-only for some properties such as head/tail.
  - Use for properties that belong to the armature data itself.
- `PoseBone`
  - Available through `object.pose.bones`.
  - Use for pose state, constraints, IK settings, and animation-related transforms.

## Armature Mode Switching

- Be careful when switching out of Edit Mode.
  - Do not keep references to `EditBone` objects or their vectors after the mode changes.
  - Separate code paths by mode so Blender is not accessed through invalid references.

