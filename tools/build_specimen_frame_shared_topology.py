"""Build a render-safe SpecimenFrame with shared topology and two material slots.

The original outer frame and inner panel are independent closed solids. When
their boundaries are perfectly aligned, four pairs of opposite coplanar side
faces occupy the same space. This variant replaces them with one continuous,
closed mesh. The front and back surfaces are subdivided at the frame opening,
so the outer frame and inner panel remain independently assignable through
material slots without any internal duplicate faces.
"""

from __future__ import annotations

import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT / "blender_modelbench" / "SpecimenFrame"
BLENDER_ROOT = ASSET_ROOT / "blender"
GENERATED_ROOT = PROJECT_ROOT / "generated" / "SpecimenFrame"
REPORT_ROOT = PROJECT_ROOT / "reports"

SOURCE_PATH = BLENDER_ROOT / "Specimen_Frame_Transparent.blend"
OUTPUT_PATH = BLENDER_ROOT / "Specimen_Frame_Shared_Topology_Material_Slots.blend"
PREVIEW_PATH = GENERATED_ROOT / "Specimen_Frame_Shared_Topology_Material_Slots_preview.png"
REPORT_PATH = REPORT_ROOT / "specimen-frame-shared-topology-material-slots-validation.json"

OBJECT_NAME = "SPECIMEN_FRAME_MATERIAL_SLOTS"
MESH_NAME = "SPECIMEN_FRAME_MATERIAL_SLOTS_Mesh"
OUTER_MATERIAL = "MAT_OuterFrame_TranslucentWhite"
INNER_MATERIAL = "MAT_InnerPanel_TransparentLavender"

OVERALL_SIZE = 9.1
OPENING_SIZE = 7.1
DEPTH = 0.42
HALF_OUTER = OVERALL_SIZE / 2.0
HALF_INNER = OPENING_SIZE / 2.0
HALF_DEPTH = DEPTH / 2.0
INNER_Z_MIN = (OVERALL_SIZE - OPENING_SIZE) / 2.0
INNER_Z_MAX = INNER_Z_MIN + OPENING_SIZE


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def create_shared_mesh(
    collection: bpy.types.Collection,
    outer_material: bpy.types.Material,
    inner_material: bpy.types.Material,
) -> bpy.types.Object:
    """Create one rectangular prism with a material boundary on both X faces."""
    outer_yz = [
        (-HALF_OUTER, 0.0),
        (HALF_OUTER, 0.0),
        (HALF_OUTER, OVERALL_SIZE),
        (-HALF_OUTER, OVERALL_SIZE),
    ]
    inner_yz = [
        (-HALF_INNER, INNER_Z_MIN),
        (HALF_INNER, INNER_Z_MIN),
        (HALF_INNER, INNER_Z_MAX),
        (-HALF_INNER, INNER_Z_MAX),
    ]

    # Index layout per X layer: outer loop 0..3, inner loop 4..7.
    # Back layer is 0..7 and front layer is 8..15.
    vertices = [
        (x, y, z)
        for x in (-HALF_DEPTH, HALF_DEPTH)
        for y, z in outer_yz + inner_yz
    ]
    faces: list[tuple[int, ...]] = []
    material_indices: list[int] = []

    # Front ring and center, normal +X.
    for i in range(4):
        j = (i + 1) % 4
        faces.append((8 + i, 8 + j, 12 + j, 12 + i))
        material_indices.append(0)
    faces.append((12, 13, 14, 15))
    material_indices.append(1)

    # Back ring and center, normal -X.
    for i in range(4):
        j = (i + 1) % 4
        faces.append((i, 4 + i, 4 + j, j))
        material_indices.append(0)
    faces.append((7, 6, 5, 4))
    material_indices.append(1)

    # Only the four exterior walls remain. There are no walls at the inner
    # material boundary, so no coincident interface polygons can z-fight.
    for i in range(4):
        j = (i + 1) % 4
        faces.append((i, j, 8 + j, 8 + i))
        material_indices.append(0)

    mesh = bpy.data.meshes.new(MESH_NAME)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(outer_material)
    mesh.materials.append(inner_material)
    for polygon, material_index in zip(mesh.polygons, material_indices):
        polygon.material_index = material_index

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(OBJECT_NAME, mesh)
    collection.objects.link(obj)
    obj.location = (0.0, 0.0, 0.0)
    obj["asset_role"] = "shared-topology specimen frame with material regions"
    obj["material_slots"] = "outer frame + inner panel"
    obj["topology_note"] = "one closed manifold; no coincident internal interface faces"
    obj["standing_plane"] = "Y-Z"
    obj["thickness_axis"] = "X"

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)
    return obj


def replace_source_geometry() -> bpy.types.Object:
    frame = bpy.data.objects.get("SPECIMEN_OUTER_FRAME")
    panel = bpy.data.objects.get("SPECIMEN_INNER_PANEL")
    ensure(frame is not None and frame.type == "MESH", "Source outer frame not found.")
    ensure(panel is not None and panel.type == "MESH", "Source inner panel not found.")
    ensure(frame.data.materials.get(OUTER_MATERIAL) is not None, "Source outer material not found.")
    ensure(panel.data.materials.get(INNER_MATERIAL) is not None, "Source inner material not found.")

    outer_material = bpy.data.materials[OUTER_MATERIAL]
    inner_material = bpy.data.materials[INNER_MATERIAL]
    model_collection = bpy.data.collections.get("MODEL_SPECIMEN_FRAME")
    ensure(model_collection is not None, "MODEL_SPECIMEN_FRAME collection not found.")

    old_meshes = [frame.data, panel.data]
    bpy.data.objects.remove(panel, do_unlink=True)
    bpy.data.objects.remove(frame, do_unlink=True)
    for mesh in old_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    return create_shared_mesh(model_collection, outer_material, inner_material)


def topology_metrics(obj: bpy.types.Object) -> dict[str, object]:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    material_boundary_edges = [
        edge
        for edge in bm.edges
        if len(edge.link_faces) == 2
        and {face.material_index for face in edge.link_faces} == {0, 1}
    ]
    nonmanifold_edges = [edge for edge in bm.edges if not edge.is_manifold]
    boundary_edges = [edge for edge in bm.edges if edge.is_boundary]
    duplicate_face_keys = []
    seen_faces: set[tuple[tuple[float, float, float], ...]] = set()
    for face in bm.faces:
        key = tuple(sorted(tuple(round(value, 6) for value in vert.co) for vert in face.verts))
        if key in seen_faces:
            duplicate_face_keys.append(key)
        seen_faces.add(key)

    metrics = {
        "vertices": len(bm.verts),
        "edges": len(bm.edges),
        "polygons": len(bm.faces),
        "manifold_edges": sum(1 for edge in bm.edges if edge.is_manifold),
        "nonmanifold_edges": len(nonmanifold_edges),
        "boundary_edges": len(boundary_edges),
        "material_boundary_edges": len(material_boundary_edges),
        "duplicate_faces": len(duplicate_face_keys),
    }
    bm.free()
    return metrics


def internal_interface_face_count(obj: bpy.types.Object) -> int:
    """Count forbidden side faces on the frame/panel contact planes."""
    count = 0
    for polygon in obj.data.polygons:
        normal = polygon.normal
        points = [obj.data.vertices[index].co for index in polygon.vertices]
        if abs(normal.y) > 0.9:
            plane_y = sum(point.y for point in points) / len(points)
            if abs(abs(plane_y) - HALF_INNER) < 0.000001:
                count += 1
        elif abs(normal.z) > 0.9:
            plane_z = sum(point.z for point in points) / len(points)
            if abs(plane_z - INNER_Z_MIN) < 0.000001 or abs(plane_z - INNER_Z_MAX) < 0.000001:
                count += 1
    return count


def validate(obj: bpy.types.Object) -> dict[str, object]:
    bpy.context.view_layer.update()
    metrics = topology_metrics(obj)
    bounds = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    dimensions = [
        max(point[index] for point in bounds) - min(point[index] for point in bounds)
        for index in range(3)
    ]
    material_slots = [material.name if material else None for material in obj.data.materials]
    material_face_counts = {
        material_slots[index]: sum(1 for polygon in obj.data.polygons if polygon.material_index == index)
        for index in range(len(material_slots))
    }
    model_objects = sorted(
        item.name
        for item in bpy.data.collections["MODEL_SPECIMEN_FRAME"].objects
        if item.type == "MESH"
    )
    internal_faces = internal_interface_face_count(obj)
    world_nodes = (
        bpy.context.scene.world.node_tree.nodes
        if bpy.context.scene.world and bpy.context.scene.world.use_nodes
        else []
    )
    hdri_nodes = [node for node in world_nodes if node.bl_idname == "ShaderNodeTexEnvironment"]
    hdri_image = hdri_nodes[0].image if hdri_nodes else None

    checks = {
        "one_model_object": model_objects == [OBJECT_NAME],
        "expected_shared_topology": (
            metrics["vertices"] == 16
            and metrics["edges"] == 28
            and metrics["polygons"] == 14
        ),
        "closed_manifold_mesh": (
            metrics["nonmanifold_edges"] == 0
            and metrics["boundary_edges"] == 0
            and metrics["manifold_edges"] == metrics["edges"]
        ),
        "no_duplicate_faces": metrics["duplicate_faces"] == 0,
        "no_internal_interface_faces": internal_faces == 0,
        "shared_material_boundary_on_both_sides": metrics["material_boundary_edges"] == 8,
        "two_material_slots_in_role_order": material_slots == [OUTER_MATERIAL, INNER_MATERIAL],
        "outer_and_inner_material_faces_assigned": material_face_counts == {
            OUTER_MATERIAL: 12,
            INNER_MATERIAL: 2,
        },
        "dimensions_preserved": all(
            abs(actual - expected) < 0.001
            for actual, expected in zip(dimensions, (DEPTH, OVERALL_SIZE, OVERALL_SIZE))
        ),
        "uv_map_present": len(obj.data.uv_layers) > 0 and len(obj.data.uv_layers.active.data) == len(obj.data.loops),
        "no_modifiers": len(obj.modifiers) == 0,
        "camera_preserved": bpy.context.scene.camera is not None,
        "render_engine_supports_nodes": bpy.context.scene.render.engine in {"BLENDER_EEVEE", "CYCLES"},
        "hdri_world_preserved": bool(hdri_image and hdri_image.packed_file),
        "transparent_background_preserved": bpy.context.scene.render.film_transparent,
    }
    checks["all_passed"] = all(checks.values())
    return {
        "asset": "Specimen Frame - Shared Topology Material Slots",
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "blend": str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "scene": bpy.context.scene.name,
        "object": {
            "name": obj.name,
            "mesh": obj.data.name,
            "dimensions": [round(value, 6) for value in dimensions],
            "origin": [round(value, 6) for value in obj.matrix_world.translation],
            "material_slots": material_slots,
            "material_face_counts": material_face_counts,
            "uv_layers": [layer.name for layer in obj.data.uv_layers],
            "modifiers": [modifier.name for modifier in obj.modifiers],
        },
        "topology": {
            **metrics,
            "internal_interface_faces": internal_faces,
            "description": "one closed manifold with shared front/back material boundaries and no coincident inner walls",
        },
        "render": {
            "engine": bpy.context.scene.render.engine,
            "preview": str(PREVIEW_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "world": bpy.context.scene.world.name if bpy.context.scene.world else None,
            "hdri_image": hdri_image.name if hdri_image else None,
            "hdri_packed": bool(hdri_image and hdri_image.packed_file),
            "film_transparent": bpy.context.scene.render.film_transparent,
        },
        "checks": checks,
    }


def write_readme() -> None:
    old_readme = bpy.data.texts.get("SPECIMEN_FRAME_README")
    if old_readme is not None:
        bpy.data.texts.remove(old_readme)
    readme = bpy.data.texts.new("SPECIMEN_FRAME_MATERIAL_SLOTS_README")
    readme.write(
        "\n".join(
            [
                "标本方框｜共享拓扑双材质槽版本",
                "",
                "- 单一对象：SPECIMEN_FRAME_MATERIAL_SLOTS。",
                "- 材质槽 1：MAT_OuterFrame_TranslucentWhite（外框）。",
                "- 材质槽 2：MAT_InnerPanel_TransparentLavender（内板）。",
                "- 正反面外框与内板使用共享边，四周内部重复侧面已删除。",
                "- 网格为封闭流形；没有共面重叠面或开放边界。",
                "- X/Y/Z 尺寸保持 0.42 × 9.1 × 9.1。",
                "- 已生成 UVMap，可替换为图片纹理或程序材质。",
                "- Eevee、透明背景和打包 HDRI 环境光已保留。",
            ]
        )
        + "\n"
    )


def configure_scene(obj: bpy.types.Object) -> None:
    scene = bpy.context.scene
    scene.name = "SPECIMEN_FRAME_MATERIAL_SLOTS_WORKBENCH"
    scene["asset_name_zh"] = "标本方框｜共享拓扑双材质槽版本"
    scene["asset_name_en"] = "Specimen Frame | Shared Topology Material Slots"
    scene["modeling_notes"] = (
        "One closed manifold mesh. Outer-frame and inner-panel regions share "
        "front/back boundary edges; no coincident internal side faces remain."
    )
    scene["object_name"] = obj.name
    scene["frame_overall_size"] = OVERALL_SIZE
    scene["frame_opening_size"] = OPENING_SIZE
    scene["frame_depth"] = DEPTH
    scene["material_slots"] = f"{OUTER_MATERIAL} + {INNER_MATERIAL}"
    scene["render_safe_interface"] = True
    scene["source_blend"] = str(SOURCE_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")
    scene["output_file"] = str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")
    scene.render.filepath = str(PREVIEW_PATH)
    scene.render.resolution_x = 760
    scene.render.resolution_y = 760
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True


def main() -> None:
    ensure(SOURCE_PATH.is_file(), f"Source blend not found: {SOURCE_PATH}")
    BLENDER_ROOT.mkdir(parents=True, exist_ok=True)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_PATH))
    obj = replace_source_geometry()
    configure_scene(obj)
    write_readme()

    report = validate(obj)
    ensure(report["checks"]["all_passed"], "Shared-topology validation failed before save.")

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))

    bpy.ops.wm.open_mainfile(filepath=str(OUTPUT_PATH))
    reopened = bpy.data.objects.get(OBJECT_NAME)
    ensure(reopened is not None, "Shared-topology object missing after reopen.")
    reopen_report = validate(reopened)
    ensure(reopen_report["checks"]["all_passed"], "Shared-topology validation failed after reopen.")

    report["reopen_checks"] = reopen_report["checks"]
    report["preview_bytes"] = PREVIEW_PATH.stat().st_size if PREVIEW_PATH.is_file() else 0
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"SPECIMEN_FRAME_SHARED_TOPOLOGY_BLEND={OUTPUT_PATH}")
    print(f"SPECIMEN_FRAME_SHARED_TOPOLOGY_PREVIEW={PREVIEW_PATH}")
    print(f"SPECIMEN_FRAME_SHARED_TOPOLOGY_REPORT={REPORT_PATH}")
    print(json.dumps(report["checks"], ensure_ascii=False))


if __name__ == "__main__":
    main()
