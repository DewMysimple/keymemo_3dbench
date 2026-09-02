"""Create a merged-object variant from the transparent specimen frame asset.

The source scene is opened as-is. Only the two model components are joined:
the outer frame remains the active object, so its world-origin bottom-face
center and the existing materials are retained. Camera, World HDRI,
transparent background, and the no-modifier state are preserved.
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_ROOT = PROJECT_ROOT 
ASSET_ROOT = WORKBENCH_ROOT / "blender_modelbench" / "SpecimenFrame"
BLENDER_ROOT = ASSET_ROOT / "blender"
GENERATED_ROOT = WORKBENCH_ROOT / "generated" / "SpecimenFrame"
REPORT_ROOT = WORKBENCH_ROOT / "reports"
SOURCE_PATH = BLENDER_ROOT / "Specimen_Frame_Transparent.blend"
OUTPUT_PATH = BLENDER_ROOT / "Specimen_Frame_Transparent_Merged.blend"
PREVIEW_PATH = GENERATED_ROOT / "Specimen_Frame_Transparent_Merged_preview.png"
REPORT_PATH = REPORT_ROOT / "specimen-frame-merged-validation.json"


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def world_bounds(obj: bpy.types.Object) -> list[Vector]:
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]


def panel_opening_fit(merged: bpy.types.Object) -> tuple[dict[str, float], dict[str, list[float]]]:
    """Measure the joined inner-panel vertices against the frame opening."""
    opening_size = float(bpy.context.scene.get("frame_opening_size", 7.1))
    overall_size = float(bpy.context.scene.get("frame_overall_size", 9.1))
    panel_slot = merged.data.materials.find("MAT_InnerPanel_TransparentLavender")
    ensure(panel_slot >= 0, "Joined inner-panel material slot not found.")
    panel_vertex_indices = {
        vertex_index
        for polygon in merged.data.polygons
        if polygon.material_index == panel_slot
        for vertex_index in polygon.vertices
    }
    panel_points = [
        merged.matrix_world @ merged.data.vertices[index].co
        for index in sorted(panel_vertex_indices)
    ]
    ensure(panel_points, "Joined inner-panel geometry not found.")
    expected = {
        "y_min": -opening_size / 2.0,
        "y_max": opening_size / 2.0,
        "z_min": (overall_size - opening_size) / 2.0,
        "z_max": (overall_size + opening_size) / 2.0,
    }
    actual = {
        "y_min": min(point.y for point in panel_points),
        "y_max": max(point.y for point in panel_points),
        "z_min": min(point.z for point in panel_points),
        "z_max": max(point.z for point in panel_points),
    }
    deltas = {key: actual[key] - expected[key] for key in expected}
    panel_box = {
        "min": [min(point[index] for point in panel_points) for index in range(3)],
        "max": [max(point[index] for point in panel_points) for index in range(3)],
    }
    return deltas, panel_box


def validate_scene(merged: bpy.types.Object, source_frame_name: str, source_panel_name: str) -> dict[str, object]:
    bpy.context.view_layer.update()
    bounds = world_bounds(merged)
    dimensions = tuple(
        max(point[index] for point in bounds) - min(point[index] for point in bounds)
        for index in range(3)
    )
    material_slots = [material.name for material in merged.data.materials if material]
    used_materials = sorted(
        {
            merged.data.materials[polygon.material_index].name
            for polygon in merged.data.polygons
            if polygon.material_index < len(merged.data.materials) and merged.data.materials[polygon.material_index]
        }
    )
    model_objects = sorted(
        obj.name
        for obj in bpy.context.scene.objects
        if obj.users_collection and any(collection.name == "MODEL_SPECIMEN_FRAME" for collection in obj.users_collection)
    )
    light_objects = sorted(obj.name for obj in bpy.context.scene.objects if obj.type == "LIGHT")
    world_nodes = bpy.context.scene.world.node_tree.nodes if bpy.context.scene.world and bpy.context.scene.world.use_nodes else []
    hdri_nodes = [node for node in world_nodes if node.bl_idname == "ShaderNodeTexEnvironment"]
    hdri_image = hdri_nodes[0].image if hdri_nodes else None
    panel_fit_deltas, panel_box = panel_opening_fit(merged)

    checks = {
        "source_objects_joined": source_frame_name not in bpy.data.objects and source_panel_name not in bpy.data.objects,
        "one_model_object": model_objects == ["SPECIMEN_FRAME_MERGED"],
        "merged_geometry_present": len(merged.data.vertices) == 24 and len(merged.data.polygons) == 22,
        "standing_dimensions_preserved": all(abs(actual - expected) < 0.001 for actual, expected in zip(dimensions, (0.42, 9.1, 9.1))),
        "inner_panel_fills_outer_opening": all(abs(value) < 0.001 for value in panel_fit_deltas.values()),
        "inner_panel_edges_aligned_with_opening": all(abs(value) < 0.001 for value in panel_fit_deltas.values()),
        "merged_origin_at_geometric_center": all(
            abs(merged.matrix_world.translation[index] - sum(point[index] for point in bounds) / len(bounds)) < 0.001
            for index in range(3)
        ),
        "object_rotation_applied": all(abs(value) < 0.001 for value in merged.rotation_euler),
        "no_modifiers": len(merged.modifiers) == 0,
        "materials_preserved": {
            "MAT_OuterFrame_TranslucentWhite",
            "MAT_InnerPanel_TransparentLavender",
        }.issubset(set(material_slots))
        and set(used_materials) == {
            "MAT_OuterFrame_TranslucentWhite",
            "MAT_InnerPanel_TransparentLavender",
        },
        "parent_removed_by_join": merged.parent is None,
        "background_removed": bpy.context.scene.render.film_transparent and bpy.data.objects.get("PREVIEW_BACKDROP") is None,
        "hdri_world_preserved": bool(hdri_image and hdri_image.packed_file),
        "old_lights_removed": not light_objects,
    }
    report: dict[str, object] = {
        "asset": "Transparent Pale Lavender Specimen Frame - Merged Object Variant",
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "blend": str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "scene": bpy.context.scene.name,
        "model_objects": model_objects,
        "object": {
            "name": merged.name,
            "vertices": len(merged.data.vertices),
            "polygons": len(merged.data.polygons),
            "dimensions": [round(value, 4) for value in dimensions],
            "origin": [round(value, 4) for value in merged.matrix_world.translation],
            "rotation_degrees": [round(value * 180.0 / 3.141592653589793, 2) for value in merged.rotation_euler],
            "modifier_names": [modifier.name for modifier in merged.modifiers],
            "material_slots": material_slots,
            "used_materials": used_materials,
            "parent": merged.parent.name if merged.parent else None,
        },
        "inner_panel": {
            "world_bounds": {
                "min": [round(value, 6) for value in panel_box["min"]],
                "max": [round(value, 6) for value in panel_box["max"]],
            },
            "opening_fit_deltas": {key: round(value, 6) for key, value in panel_fit_deltas.items()},
        },
        "world": {
            "name": bpy.context.scene.world.name if bpy.context.scene.world else None,
            "hdri_node": hdri_nodes[0].name if hdri_nodes else None,
            "hdri_image": hdri_image.name if hdri_image else None,
            "hdri_packed": bool(hdri_image and hdri_image.packed_file),
            "light_objects": light_objects,
        },
        "render_preview": str(PREVIEW_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "checks": checks,
    }
    report["checks"]["all_passed"] = all(checks.values())
    return report


def main() -> None:
    ensure(SOURCE_PATH.is_file(), f"Source blend not found: {SOURCE_PATH}")
    BLENDER_ROOT.mkdir(parents=True, exist_ok=True)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_PATH))
    scene = bpy.context.scene
    frame = bpy.data.objects.get("SPECIMEN_OUTER_FRAME")
    panel = bpy.data.objects.get("SPECIMEN_INNER_PANEL")
    ensure(frame is not None, "Source outer frame object not found.")
    ensure(panel is not None, "Source inner panel object not found.")

    bpy.ops.object.select_all(action="DESELECT")
    frame.select_set(True)
    panel.select_set(True)
    bpy.context.view_layer.objects.active = frame
    bpy.ops.object.join()
    merged = bpy.context.object
    merged.name = "SPECIMEN_FRAME_MERGED"
    merged.data.name = "SPECIMEN_FRAME_MERGED_Mesh"
    # Move the merged object's origin to the center of its combined geometry
    # while preserving the model's world-space position.
    bpy.context.view_layer.update()
    local_bounds = [Vector(corner) for corner in merged.bound_box]
    local_center = sum(local_bounds, Vector()) / len(local_bounds)
    world_center = merged.matrix_world @ local_center
    merged.data.transform(Matrix.Translation(-local_center))
    merged.matrix_world.translation = world_center
    merged["asset_role"] = "merged outer frame and inner specimen panel"
    merged["source_objects"] = "SPECIMEN_OUTER_FRAME + SPECIMEN_INNER_PANEL"
    merged["material_roles"] = "outer translucent white + inner transparent pale lavender"
    merged["origin_role"] = "combined geometry center"
    merged["object_rotation_applied"] = True
    merged["parenting"] = "components merged into one object"

    scene.name = "SPECIMEN_FRAME_MERGED_WORKBENCH"
    scene["asset_name_zh"] = "透明浅紫标本正方形框｜合并物体版本"
    scene["asset_name_en"] = "Transparent Pale Lavender Specimen Frame | Merged Object Variant"
    scene["modeling_notes"] = "The outer frame and inner panel are joined into one mesh object with two material slots; the inner panel perimeter is exactly aligned to the outer opening."
    scene["merged_object"] = True
    scene["merged_origin_at_geometric_center"] = True
    scene["source_blend"] = str(SOURCE_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")
    scene["output_file"] = str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")
    scene.render.filepath = str(PREVIEW_PATH)

    report = validate_scene(merged, "SPECIMEN_OUTER_FRAME", "SPECIMEN_INNER_PANEL")
    ensure(report["checks"]["all_passed"], "Merged specimen frame validation failed before saving.")

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))

    report["preview_bytes"] = PREVIEW_PATH.stat().st_size if PREVIEW_PATH.is_file() else 0
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"SPECIMEN_FRAME_MERGED_BLEND={OUTPUT_PATH}")
    print(f"SPECIMEN_FRAME_MERGED_PREVIEW={PREVIEW_PATH}")
    print(f"SPECIMEN_FRAME_MERGED_REPORT={REPORT_PATH}")
    print(json.dumps(report["checks"], ensure_ascii=False))


if __name__ == "__main__":
    main()
