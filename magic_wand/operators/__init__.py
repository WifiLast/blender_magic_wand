_needs_reload = "bpy" in locals()

import bpy

from . import edit

if _needs_reload:
    import importlib

    edit = importlib.reload(edit)

from .edit import *
