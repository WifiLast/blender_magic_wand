if "bpy" in locals():
    from pathlib import Path
    essentials.reload_recursive(Path(__file__).parent, locals())
else:
    import bpy
    from bpy.props import PointerProperty

    from . import essentials, operators, preferences, ui


classes = essentials.get_classes((operators, preferences, ui))
_registered_classes = []


def _safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError:
        pass


def register():
    _registered_classes.clear()

    try:
        for cls in classes:
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)
    except Exception:
        for cls in reversed(_registered_classes):
            _safe_unregister_class(cls)
        _registered_classes.clear()
        raise

    bpy.types.Scene.smart_3d_magic_wand = PointerProperty(type=preferences.SceneProperties)

    # Menu
    # ---------------------------

    bpy.types.VIEW3D_MT_object.append(ui.draw_smart_wand_menu)
    bpy.types.VIEW3D_MT_edit_mesh.append(ui.draw_smart_wand_menu)


def unregister():
    # Menu
    # ---------------------------

    try:
        bpy.types.VIEW3D_MT_object.remove(ui.draw_smart_wand_menu)
    except ValueError:
        pass

    try:
        bpy.types.VIEW3D_MT_edit_mesh.remove(ui.draw_smart_wand_menu)
    except ValueError:
        pass

    try:
        del bpy.types.Scene.smart_3d_magic_wand
    except AttributeError:
        pass

    active_classes = _registered_classes or classes
    for cls in reversed(active_classes):
        _safe_unregister_class(cls)

    _registered_classes.clear()
