"""Create a default-material, origin-centered variant of the specimen frame.

The source blend is opened directly and the original file is never written.
The model geometry remains in the same world-space position.  The outer
frame object's origin is moved to the center of its geometric bounding box,
the custom transparent materials are replaced with Blender's plain default
material, and the source World/HDRI environment is removed.
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT / "blender_modelbench" / "SpecimenFrame"
BLENDER_ROOT = ASSET_ROOT / "blender"
GENERATED_ROOT = PROJECT_ROOT / "generated" / "SpecimenFrame"
REPORT_ROOT = PROJECT_ROOT / "reports"
SOURCE_PATH = BLENDER_ROOT / "Specimen_Frame_Transparent.blend"
OUTPUT_PATH = BLENDER_ROOT / "Specimen_Frame_Transparent_Default_Material.blend"
PREVIEW_PATH = GENERATED_ROOT / "Specimen_Frame_Transparent_Default_Material_preview.png"
REPORT_PATH = REPORT_ROOT / "specimen-frame-default-material-validation.json"


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def world_bounds(obj: bpy.types.Object) -> list[Vector]:
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]


def bounds_center(points: list[Vector]) -> Vector:
    return Vector(
        (
            (min(point.x for point in points) + max(point.x for point in points)) / 2.0,
            (min(point.y for point in points) + max(point.y for point in points)) / 2.0,
            (min(point.z for point in points) + max(point.z for point in points)) / 2.0,
        )
    )


def world_vertex_positions(obj: bpy.types.Object) -> list[Vector]:
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def max_vector_delta(left: list[Vector], right: list[Vector]) -> float:
    ensure(len(left) == len(right), "Vertex count changed while moving the object origin.")
    return max((a - b).length for a, b in zip(left, right)) if left else 0.0


def panel_opening_fit(frame: bpy.types.Object, panel: bpy.types.Object) -> dict[str, float]:
    """Return panel-to-opening edge deltas across X, Y and Z."""
    opening_size = float(frame.get("opening_size", 7.1))
    overall_size = float(frame.get("overall_size", 9.1))
    frame_depth = float(frame.get("thickness", 0.42))
    panel_points = world_vertex_positions(panel)
    expected = {
        "x_min": -frame_depth / 2.0,
        "x_max": frame_depth / 2.0,
        "y_min": -opening_size / 2.0,
        "y_max": opening_size / 2.0,
        "z_min": (overall_size - opening_size) / 2.0,
        "z_max": (overall_size + opening_size) / 2.0,
    }
    actual = {
        "x_min": min(point.x for point in panel_points),
        "x_max": max(point.x for point in panel_points),
        "y_min": min(point.y for point in panel_points),
        "y_max": max(point.y for point in panel_points),
        "z_min": min(point.z for point in panel_points),
        "z_max": max(point.z for point in panel_points),
    }
    return {key: actual[key] - expected[key] for key in expected}


def center_outer_frame(frame: bpy.types.Object) -> tuple[Vector, Vector]:
    """Move the frame origin to its local bounding-box center in place."""
    before_vertices = world_vertex_positions(frame)
    before_bounds = world_bounds(frame)
    local_bounds = [Vector(corner) for corner in frame.bound_box]
    local_center = bounds_center(local_bounds)
    world_center = frame.matrix_world @ local_center

    # Moving mesh coordinates by -local_center and setting the object origin to
    # world_center is the same operation as Blender's Origin to Geometry, but
    # it lets us explicitly preserve child world transforms below.
    frame.data.transform(Matrix.Translation(-local_center))
    frame.matrix_world.translation = world_center
    bpy.context.view_layer.update()

    after_vertices = world_vertex_positions(frame)
    ensure(
        max_vector_delta(before_vertices, after_vertices) < 0.000001,
        "Moving the frame origin changed its world-space geometry.",
    )
    after_bounds = world_bounds(frame)
    ensure(
        max_vector_delta(before_bounds, after_bounds) < 0.000001,
        "Moving the frame origin changed its world-space bounds.",
    )
    return world_center, Vector(local_center)


def remove_materials() -> list[str]:
    removed_slots: list[str] = []
    for obj in bpy.context.scene.objects:
        data = getattr(obj, "data", None)
        materials = getattr(data, "materials", None)
        if materials is None:
            continue
        for material in materials:
            if material:
                removed_slots.append(material.name)
        materials.clear()

    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    return sorted(set(removed_slots))


def make_default_material() -> bpy.types.Material:
    """Create Blender's plain Principled material without custom metadata."""
    material = bpy.data.materials.new("Material")
    material.use_nodes = True
    material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
    return material


def assign_default_material(material: bpy.types.Material) -> None:
    for obj in bpy.context.scene.objects:
        data = getattr(obj, "data", None)
        materials = getattr(data, "materials", None)
        if materials is None or obj.type != "MESH":
            continue
        materials.append(material)


def remove_world_environment(scene: bpy.types.Scene) -> list[str]:
    """Remove the source World, its HDRI, and all image data from the variant."""
    removed_images = sorted(
        image.name for image in bpy.data.images if image.name != "Render Result"
    )
    scene.world = None
    for world in list(bpy.data.worlds):
        bpy.data.worlds.remove(world, do_unlink=True)
    for image in list(bpy.data.images):
        if image.name == "Render Result":
            continue
        image.user_clear()
        bpy.data.images.remove(image, do_unlink=True)
    for key in ("world_environment", "hdri_name", "hdri_source", "hdri_strength"):
        if key in scene:
            del scene[key]
    return removed_images


def persistent_image_names() -> list[str]:
    # Blender creates this transient viewer image after a render; it is not
    # serialized HDRI/texture data and is intentionally excluded.
    return sorted(image.name for image in bpy.data.images if image.name != "Render Result")


def configure_plain_preview(scene: bpy.types.Scene) -> None:
    """Use Blender's material-independent solid preview without a World."""
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
        scene.display.shading.show_shadows = False
    except (AttributeError, TypeError, ValueError):
        pass
    for obj in scene.objects:
        if obj.type == "MESH":
            obj.display_type = "SOLID"
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            shading = area.spaces.active.shading
            shading.type = "SOLID"
            shading.light = "STUDIO"
            shading.color_type = "MATERIAL"
            shading.show_shadows = False
            shading.use_scene_world = False


def update_variant_metadata(scene: bpy.types.Scene, frame: bpy.types.Object) -> None:
    scene["asset_name_zh"] = "标本方框｜默认材质版本"
    scene["asset_name_en"] = "Specimen Frame | Default Material Variant"
    scene["description_zh"] = "保留几何、层级、相机和世界位置；使用 Blender 默认材质。"
    scene["default_material_variant"] = True
    scene["custom_materials_replaced"] = True
    scene["world_environment_removed"] = True
    scene["preferred_viewport"] = "Solid / 实体"
    scene["source_blend"] = str(SOURCE_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")
    scene["output_file"] = str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")
    frame["origin_role"] = "geometric center; world-space geometry position preserved"
    frame["material_role"] = "default Blender material"
    panel = bpy.data.objects.get("SPECIMEN_INNER_PANEL")
    if panel:
        panel["material_role"] = "default Blender material"

    readme = bpy.data.texts.get("SPECIMEN_FRAME_README")
    if readme:
        readme.clear()
        readme.write(
            "\n".join(
                [
                    "标本正方形框｜默认材质版本 / Specimen Frame | Default Material Variant",
                    "",
                    "本版本由 Specimen_Frame_Transparent.blend 派生。",
                    "- 保留 SPECIMEN_OUTER_FRAME 与 SPECIMEN_INNER_PANEL 的几何、层级和世界空间位置。",
                    "- 合缝：中心板外边界与外框内开口四边完全对齐，平面缝隙为 0。",
                    "- X 轴对齐：中心板正面和背面与外框齐平，前后缝隙均为 0。",
                    "- SPECIMEN_OUTER_FRAME 的物体原点位于其几何包围盒中心。",
                    "- 模型使用 Blender 默认材质。",
                    "- 相机和透明背景保持不变；World 与图像数据已移除。",
                    "- 源文件未被覆盖。",
                ]
            )
            + "\n"
        )


def validate_scene(
    scene: bpy.types.Scene,
    frame: bpy.types.Object,
    panel: bpy.types.Object,
    before_frame_vertices: list[Vector],
    before_panel_vertices: list[Vector],
    before_camera_matrix: Matrix,
    source_object_names: list[str],
    removed_slots: list[str],
    removed_images: list[str],
    default_material: bpy.types.Material,
) -> dict[str, object]:
    bpy.context.view_layer.update()
    frame_vertices = world_vertex_positions(frame)
    panel_vertices = world_vertex_positions(panel)
    panel_fit_deltas = panel_opening_fit(frame, panel)
    frame_points = world_bounds(frame)
    center = bounds_center(frame_points)
    scene_object_names = sorted(obj.name for obj in scene.objects)
    material_slots = {
        obj.name: [material.name for material in obj.data.materials if material]
        for obj in scene.objects
        if getattr(obj, "data", None) is not None and hasattr(obj.data, "materials")
    }
    mesh_objects = [obj for obj in scene.objects if obj.type == "MESH"]
    material_nodes = default_material.node_tree.nodes if default_material.use_nodes else []
    principled_nodes = [node for node in material_nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"]
    principled = principled_nodes[0] if principled_nodes else None
    transmission_socket = (
        principled.inputs.get("Transmission Weight") or principled.inputs.get("Transmission")
        if principled
        else None
    )
    alpha_socket = principled.inputs.get("Alpha") if principled else None
    no_transparent_material_nodes = (
        len(material_nodes) == 2
        and not any(node.bl_idname in {"ShaderNodeBsdfTransparent", "ShaderNodeMixShader"} for node in material_nodes)
        and bool(principled)
        and alpha_socket is not None
        and abs(float(alpha_socket.default_value) - 1.0) < 0.000001
        and transmission_socket is not None
        and abs(float(transmission_socket.default_value)) < 0.000001
    )
    checks: dict[str, object] = {
        "source_objects_preserved": scene_object_names == source_object_names,
        "outer_frame_origin_at_geometric_center": all(
            abs(frame.matrix_world.translation[index] - center[index]) < 0.000001
            for index in range(3)
        ),
        "outer_frame_geometry_position_preserved": max_vector_delta(
            before_frame_vertices, frame_vertices
        )
        < 0.000001,
        "inner_panel_geometry_position_preserved": max_vector_delta(
            before_panel_vertices, panel_vertices
        )
        < 0.000001,
        "inner_panel_parent_preserved": panel.parent == frame,
        "inner_panel_fills_outer_opening": all(abs(value) < 0.001 for value in panel_fit_deltas.values()),
        "inner_panel_edges_aligned_with_opening": (
            abs(panel.dimensions.y - float(frame.get("opening_size", 7.1))) < 0.001
            and abs(panel.dimensions.z - float(frame.get("opening_size", 7.1))) < 0.001
        ),
        "inner_panel_front_back_faces_aligned_with_frame": (
            abs(panel.dimensions.x - float(frame.get("thickness", 0.42))) < 0.001
            and abs(panel_fit_deltas["x_min"]) < 0.001
            and abs(panel_fit_deltas["x_max"]) < 0.001
        ),
        "camera_position_preserved": max(
            abs(before_camera_matrix[index][column] - scene.camera.matrix_world[index][column])
            for index in range(4)
            for column in range(4)
        )
        < 0.000001,
        "one_default_material_datablock": len(bpy.data.materials) == 1 and bpy.data.materials[0] == default_material,
        "default_material_assigned": bool(mesh_objects)
        and all(
            len(obj.data.materials) == 1 and obj.data.materials[0] == default_material
            for obj in mesh_objects
        ),
        "no_transparent_material_nodes": no_transparent_material_nodes,
        "world_environment_removed": scene.world is None and len(bpy.data.worlds) == 0,
        "image_datablocks_removed": not persistent_image_names(),
        "transparent_background_preserved": scene.render.film_transparent,
        "no_modifiers": all(len(obj.modifiers) == 0 for obj in (frame, panel)),
    }
    return {
        "asset": "Transparent Specimen Frame - Default Material Variant",
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "blend": str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "scene": scene.name,
        "objects": scene_object_names,
        "frame": {
            "name": frame.name,
            "origin": [round(value, 6) for value in frame.matrix_world.translation],
            "geometric_center": [round(value, 6) for value in center],
            "world_dimensions": [round(value, 6) for value in frame.dimensions],
        },
        "panel": {
            "name": panel.name,
            "world_dimensions": [round(value, 6) for value in panel.dimensions],
            "opening_fit_deltas": {key: round(value, 6) for key, value in panel_fit_deltas.items()},
        },
        "materials_removed": removed_slots,
        "default_material": default_material.name,
        "material_slots": material_slots,
        "images_removed": removed_images,
        "world": {
            "name": None,
            "world_datablocks": 0,
            "image_datablocks": len(persistent_image_names()),
        },
        "render_preview": str(PREVIEW_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "render_engine": scene.render.engine,
        "checks": checks,
    }


def main() -> None:
    ensure(SOURCE_PATH.is_file(), f"Source blend not found: {SOURCE_PATH}")
    BLENDER_ROOT.mkdir(parents=True, exist_ok=True)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_PATH))
    scene = bpy.context.scene
    frame = bpy.data.objects.get("SPECIMEN_OUTER_FRAME")
    panel = bpy.data.objects.get("SPECIMEN_INNER_PANEL")
    ensure(frame is not None and frame.type == "MESH", "Source outer frame mesh not found.")
    ensure(panel is not None and panel.type == "MESH", "Source inner panel mesh not found.")
    ensure(panel.parent == frame, "Source inner panel parent relationship is not preserved.")
    ensure(scene.camera is not None, "Source camera not found.")

    source_object_names = sorted(obj.name for obj in scene.objects)
    before_frame_vertices = world_vertex_positions(frame)
    before_panel_vertices = world_vertex_positions(panel)
    before_panel_matrix = panel.matrix_world.copy()
    before_camera_matrix = scene.camera.matrix_world.copy()
    center_outer_frame(frame)
    # The panel is parented to the frame. Restore its world matrix after the
    # parent origin moves so its actual world-space position is unchanged.
    panel.matrix_world = before_panel_matrix
    bpy.context.view_layer.update()
    removed_slots = remove_materials()
    default_material = make_default_material()
    assign_default_material(default_material)
    removed_images = remove_world_environment(scene)
    update_variant_metadata(scene, frame)
    configure_plain_preview(scene)
    scene.render.filepath = str(PREVIEW_PATH)

    report = validate_scene(
        scene,
        frame,
        panel,
        before_frame_vertices,
        before_panel_vertices,
        before_camera_matrix,
        source_object_names,
        removed_slots,
        removed_images,
        default_material,
    )
    report["checks"]["all_passed"] = all(report["checks"].values())
    ensure(report["checks"]["all_passed"], "Default-material specimen frame validation failed before saving.")

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))

    # Re-open the generated file to ensure the origin, empty material state,
    # and removed environment survive serialization.
    bpy.ops.wm.open_mainfile(filepath=str(OUTPUT_PATH))
    reopened_scene = bpy.context.scene
    reopened_frame = bpy.data.objects.get("SPECIMEN_OUTER_FRAME")
    reopened_panel = bpy.data.objects.get("SPECIMEN_INNER_PANEL")
    ensure(reopened_frame is not None and reopened_panel is not None, "Generated objects missing after reopen.")
    reopened_mesh_material_slots = [
        material.name
        for obj in reopened_scene.objects
        if obj.type == "MESH" and getattr(obj, "data", None) is not None and hasattr(obj.data, "materials")
        for material in obj.data.materials
        if material
    ]
    reopened_default_material = bpy.data.materials.get("Material")
    ensure(
        reopened_default_material is not None
        and len(bpy.data.materials) == 1
        and reopened_mesh_material_slots == ["Material", "Material"],
        "Default material did not survive after reopen.",
    )
    reopened_nodes = reopened_default_material.node_tree.nodes if reopened_default_material.use_nodes else []
    reopened_principled = next(
        (node for node in reopened_nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"), None
    )
    reopened_transmission = (
        reopened_principled.inputs.get("Transmission Weight")
        or reopened_principled.inputs.get("Transmission")
        if reopened_principled
        else None
    )
    reopened_alpha = reopened_principled.inputs.get("Alpha") if reopened_principled else None
    ensure(
        len(reopened_nodes) == 2
        and not any(node.bl_idname in {"ShaderNodeBsdfTransparent", "ShaderNodeMixShader"} for node in reopened_nodes)
        and reopened_principled is not None
        and reopened_alpha is not None
        and abs(float(reopened_alpha.default_value) - 1.0) < 0.000001
        and reopened_transmission is not None
        and abs(float(reopened_transmission.default_value)) < 0.000001,
        "Transparent material settings reappeared after reopen.",
    )
    ensure(reopened_scene.world is None and len(bpy.data.worlds) == 0, "World environment reappeared after reopen.")
    reopened_image_names = persistent_image_names()
    ensure(not reopened_image_names, "Image data reappeared after reopen.")
    reopened_center = bounds_center(world_bounds(reopened_frame))
    reopened_panel_fit_deltas = panel_opening_fit(reopened_frame, reopened_panel)
    ensure(
        (reopened_frame.matrix_world.translation - reopened_center).length < 0.000001,
        "Outer frame origin is not at geometric center after reopen.",
    )
    report["reopen_checks"] = {
        "one_default_material_datablock": len(bpy.data.materials) == 1 and reopened_default_material is not None,
        "default_material_assigned": reopened_mesh_material_slots == ["Material", "Material"],
        "no_transparent_material_nodes": (
            len(reopened_nodes) == 2
            and not any(
                node.bl_idname in {"ShaderNodeBsdfTransparent", "ShaderNodeMixShader"}
                for node in reopened_nodes
            )
            and reopened_alpha is not None
            and abs(float(reopened_alpha.default_value) - 1.0) < 0.000001
            and reopened_transmission is not None
            and abs(float(reopened_transmission.default_value)) < 0.000001
        ),
        "world_environment_removed": reopened_scene.world is None and len(bpy.data.worlds) == 0,
        "image_datablocks_removed": not reopened_image_names,
        "outer_frame_origin_at_geometric_center": (
            reopened_frame.matrix_world.translation - reopened_center
        ).length
        < 0.000001,
        "inner_panel_parent_preserved": reopened_panel.parent == reopened_frame,
        "inner_panel_fills_outer_opening": all(abs(value) < 0.001 for value in reopened_panel_fit_deltas.values()),
        "inner_panel_edges_aligned_with_opening": (
            abs(reopened_panel.dimensions.y - float(reopened_frame.get("opening_size", 7.1))) < 0.001
            and abs(reopened_panel.dimensions.z - float(reopened_frame.get("opening_size", 7.1))) < 0.001
        ),
        "inner_panel_front_back_faces_aligned_with_frame": (
            abs(reopened_panel.dimensions.x - float(reopened_frame.get("thickness", 0.42))) < 0.001
            and abs(reopened_panel_fit_deltas["x_min"]) < 0.001
            and abs(reopened_panel_fit_deltas["x_max"]) < 0.001
        ),
    }
    report["reopen_checks"]["all_passed"] = all(report["reopen_checks"].values())
    ensure(report["reopen_checks"]["all_passed"], "Default-material specimen frame reopen validation failed.")
    report["preview_bytes"] = PREVIEW_PATH.stat().st_size if PREVIEW_PATH.is_file() else 0
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"SPECIMEN_FRAME_DEFAULT_MATERIAL_BLEND={OUTPUT_PATH}")
    print(f"SPECIMEN_FRAME_DEFAULT_MATERIAL_PREVIEW={PREVIEW_PATH}")
    print(f"SPECIMEN_FRAME_DEFAULT_MATERIAL_REPORT={REPORT_PATH}")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
