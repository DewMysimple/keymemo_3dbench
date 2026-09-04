"""Build one sorted Blender showcase file per OBJ model category.

The source directory contains standalone OBJ files and small preview images.
Only OBJ geometry is imported; the resulting .blend files contain the mesh
data, display environment, labels, camera and lights, so they do not depend on
the source directory after saving.
"""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import bpy
from mathutils import Vector


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = WORKBENCH_ROOT / "models" / "othermodel" / "source"
OUTPUT_ROOT = WORKBENCH_ROOT / "models" / "othermodel" / "scenes"
DEFAULT_REPORT = WORKBENCH_ROOT / "models" / "othermodel" / "reports" / "build.json"

CATEGORY_ORDER = (
    "Envelope",
    "Bookmark",
    "Card",
    "CardHolder",
    "BubbleMailer",
    "FoodPackaging",
    "PaperBackdrop",
)


def parse_args() -> argparse.Namespace:
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Build one Blender file per OBJ category.")
    parser.add_argument(
        "--category",
        choices=CATEGORY_ORDER,
        action="append",
        help="Build only the selected category; repeat for multiple categories.",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Render one PNG preview per generated category file.",
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(raw_args)


def natural_key(path: Path) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.stem)]


def classify(path: Path) -> str:
    stem = path.stem.lower()
    if "envelope" in stem or "envelop" in stem:
        return "Envelope"
    if "bookmark" in stem:
        return "Bookmark"
    if "card-holder" in stem:
        return "CardHolder"
    if "bubble-mailer" in stem:
        return "BubbleMailer"
    if "food-packaging" in stem:
        return "FoodPackaging"
    if "paper-backdrop" in stem:
        return "PaperBackdrop"
    if "card" in stem:
        return "Card"
    raise ValueError(f"Unclassified OBJ source: {path.name}")


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def clear_scene() -> bpy.types.Scene:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for datablock_collection in (
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.curves,
        bpy.data.meshes,
    ):
        for datablock in list(datablock_collection):
            if datablock.users == 0:
                datablock_collection.remove(datablock)
    scene = bpy.context.scene
    scene.name = "MODEL_SHOWCASE"
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    else:
        raise RuntimeError("No Eevee render engine is available in this Blender build")
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = ""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background") if world.node_tree else None
    if background is not None:
        background.inputs["Color"].default_value = (0.008, 0.012, 0.022, 1.0)
        background.inputs["Strength"].default_value = 0.22
    return scene


def make_collection(name: str, parent: bpy.types.Collection) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)


def make_material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    nodes = material.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.38
        principled.inputs["Metallic"].default_value = metallic
    return material


def ensure_mesh_materials(objects: Iterable[bpy.types.Object], material: bpy.types.Material) -> None:
    for obj in objects:
        if obj.type != "MESH":
            continue
        if not obj.data.materials:
            obj.data.materials.append(material)
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def model_bounds(objects: Iterable[bpy.types.Object]) -> tuple[Vector, Vector]:
    corners: list[Vector] = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        corners.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    ensure(corners, "Imported OBJ produced no mesh bounds")
    minimum = Vector((min(point.x for point in corners), min(point.y for point in corners), min(point.z for point in corners)))
    maximum = Vector((max(point.x for point in corners), max(point.y for point in corners), max(point.z for point in corners)))
    return minimum, maximum


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_text(
    body: str,
    name: str,
    location: Vector,
    size: float,
    collection: bpy.types.Collection,
    *,
    billboard_camera: bpy.types.Object | None = None,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(name + "_Curve", type="FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = 0.008
    curve.bevel_depth = 0.002
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj.location = location
    if billboard_camera is not None:
        # Text faces local +Z (unlike cameras/lights, which face -Z); tracking
        # +Z keeps the category header upright while facing the camera.
        direction = billboard_camera.location - obj.location
        obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    else:
        obj.rotation_euler = (0.0, 0.0, 0.0)
    return obj


def add_area_light(
    name: str,
    location: tuple[float, float, float],
    energy: float,
    size: float,
    target: Vector,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    return obj


def add_floor(
    width: float,
    depth: float,
    environment: bpy.types.Collection,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, -0.015))
    floor = bpy.context.object
    floor.name = "DISPLAY_FLOOR"
    move_to_collection(floor, environment)
    floor.scale = (width / 2.0, depth / 2.0, 1.0)
    floor.data.materials.append(make_material("DISPLAY_FLOOR_Material", (0.018, 0.026, 0.050, 1.0), metallic=0.1))
    return floor


def add_camera(
    width: float,
    depth: float,
    max_dimension: float,
    environment: bpy.types.Collection,
) -> bpy.types.Object:
    camera_data = bpy.data.cameras.new("SHOWCASE_CAMERA_Data")
    camera_data.type = "ORTHO"
    # Blender's orthographic scale follows the camera width in this render
    # aspect.  Keep both dimensions inside the frame so edge models are not
    # cropped when a category has several columns.
    camera_data.ortho_scale = max(10.0, width * 1.20, depth * 1.45)
    camera = bpy.data.objects.new("SHOWCASE_CAMERA", camera_data)
    environment.objects.link(camera)
    camera.location = (0.0, -max(18.0, depth * 1.15), max(15.0, depth * 1.05, max_dimension * 5.0))
    look_at(camera, Vector((0.0, 0.0, max_dimension * 0.35)))
    return camera


def add_environment(
    scene: bpy.types.Scene,
    category: str,
    model_count: int,
    columns: int,
    rows: int,
    max_dimension: float,
    cell_x: float,
    cell_y: float,
    root_collection: bpy.types.Collection,
) -> tuple[bpy.types.Object, bpy.types.Collection]:
    environment = make_collection("DISPLAY_ENVIRONMENT", root_collection)
    display_width = columns * cell_x + 4.0
    display_depth = rows * cell_y + 5.0
    add_floor(display_width, display_depth, environment)
    camera = add_camera(display_width, display_depth, max_dimension, environment)
    target = Vector((0.0, 0.0, max_dimension * 0.35))
    add_area_light("LIGHT_KEY", (0.0, -display_depth * 0.35, max(7.0, max_dimension * 4.0)), 1250.0, 8.0, target, environment)
    add_area_light("LIGHT_FILL", (-display_width * 0.4, display_depth * 0.2, max(5.0, max_dimension * 2.5)), 850.0, 7.0, target, environment)
    add_area_light("LIGHT_RIM", (display_width * 0.38, display_depth * 0.35, max(6.0, max_dimension * 3.5)), 1100.0, 6.0, target, environment)
    title = add_text(
        f"{category}  ·  {model_count} models",
        f"TITLE_{category}",
        Vector((0.0, display_depth * 0.5 - 1.0, max(2.8, max_dimension * 1.55))),
        min(0.72, max(0.34, 10.0 / max(len(category) + 16, 16))),
        environment,
        billboard_camera=camera,
    )
    title["category"] = category
    title["model_count"] = model_count
    scene.camera = camera
    scene.render.filepath = str(WORKBENCH_ROOT / "generated" / "othermodel" / f"{category}.png")
    return camera, environment


def import_model(path: Path, index: int, category: str, model_collection: bpy.types.Collection) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    before = set(bpy.data.objects)
    result = bpy.ops.wm.obj_import(filepath=str(path))
    ensure(result == {"FINISHED"}, f"OBJ import failed: {path.name}: {result}")
    imported = sorted((obj for obj in bpy.data.objects if obj not in before), key=lambda obj: obj.name.lower())
    ensure(imported, f"OBJ import produced no objects: {path.name}")
    source_rel = path.relative_to(WORKBENCH_ROOT).as_posix()
    for part_index, obj in enumerate(imported, start=1):
        original_name = obj.name
        obj.name = f"{index:02d}_{path.stem}__{part_index:02d}_{original_name}"
        obj["source_obj"] = source_rel
        obj["source_model_index"] = index
        obj["source_part_index"] = part_index
        obj["display_category"] = category
        move_to_collection(obj, model_collection)
    root = bpy.data.objects.new(f"MODEL_{index:02d}_{path.stem}", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.15
    root["source_obj"] = source_rel
    root["source_model_index"] = index
    root["display_category"] = category
    model_collection.objects.link(root)
    minimum, maximum = model_bounds(imported)
    pivot = Vector(((minimum.x + maximum.x) * 0.5, (minimum.y + maximum.y) * 0.5, minimum.z))
    root.location = pivot
    root_matrix = root.matrix_world.copy()
    inverse = root_matrix.inverted()
    for obj in imported:
        world_matrix = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_parent_inverse = inverse
        obj.matrix_world = world_matrix
    dimensions = maximum - minimum
    max_dimension = max(dimensions.x, dimensions.y, dimensions.z, 1e-6)
    root["source_bounds"] = [float(value) for value in (*minimum, *maximum)]
    root["source_dimensions"] = [float(value) for value in dimensions]
    root["display_max_dimension"] = float(max_dimension)
    return root, imported


def layout_model(
    root: bpy.types.Object,
    model_objects: list[bpy.types.Object],
    index: int,
    columns: int,
    cell_x: float,
    cell_y: float,
    rows: int,
    max_dimension: float,
    model_collection: bpy.types.Collection,
    environment: bpy.types.Collection,
    category: str,
    camera: bpy.types.Object,
) -> None:
    col = index % columns
    row = index // columns
    x = (col - (columns - 1) / 2.0) * cell_x
    y = (row - (rows - 1) / 2.0) * cell_y
    scale = 2.0 / max(max_dimension, 1e-6)
    root.scale = (scale, scale, scale)
    root.location = (x, y, 0.0)
    color = colorsys.hsv_to_rgb((index * 0.61803398875) % 1.0, 0.38, 0.76)
    material = make_material(
        f"MODEL_{index + 1:02d}_Material",
        (color[0], color[1], color[2], 1.0),
        metallic=0.03,
    )
    ensure_mesh_materials(model_objects, material)
    label_size = min(0.24, max(0.10, 2.6 / max(len(root.name) - 8, 8)))
    label = add_text(
        root.name.split("_", 2)[-1].replace("-", " "),
        f"LABEL_{index + 1:02d}_{category}",
        Vector((x, y - 1.28, 0.01)),
        label_size,
        environment,
    )
    label["source_obj"] = root["source_obj"]
    label["model_index"] = index + 1
    label["display_category"] = category


def audit_resources() -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    for kind, collection in (
        ("images", bpy.data.images),
        ("movieclips", bpy.data.movieclips),
        ("sounds", bpy.data.sounds),
        ("fonts", bpy.data.fonts),
        ("volumes", bpy.data.volumes),
        ("cache_files", bpy.data.cache_files),
    ):
        for datablock in collection:
            filepath = getattr(datablock, "filepath", "")
            if not filepath or filepath == "<builtin>":
                continue
            packed = getattr(datablock, "packed_file", None) is not None or bool(getattr(datablock, "packed_files", []))
            resources.append({"kind": kind, "name": datablock.name, "filepath": filepath, "packed": packed})
    return {"external_resources": resources, "libraries": [library.filepath for library in bpy.data.libraries]}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def build_category(category: str, paths: list[Path], output_root: Path, render: bool) -> dict[str, Any]:
    scene = clear_scene()
    root_collection = scene.collection
    model_collection = make_collection(f"MODELS_{category}", root_collection)
    model_data: list[tuple[bpy.types.Object, list[bpy.types.Object], Path]] = []
    dimensions: list[float] = []
    for index, path in enumerate(paths):
        root, imported = import_model(path, index, category, model_collection)
        dimensions.append(float(root["display_max_dimension"]))
        model_data.append((root, imported, path))
    max_dimension = max(dimensions or [1.0])
    columns = min(5, max(1, len(paths)))
    rows = math.ceil(len(paths) / columns)
    cell_x = 3.8
    cell_y = 3.25
    camera, environment = add_environment(
        scene,
        category,
        len(paths),
        columns,
        rows,
        max_dimension,
        cell_x,
        cell_y,
        root_collection,
    )
    for index, (root, imported, _path) in enumerate(model_data):
        layout_model(
            root,
            imported,
            index,
            columns,
            cell_x,
            cell_y,
            rows,
            max_dimension,
            model_collection,
            environment,
            category,
            camera,
        )
    scene["workbench_role"] = "sorted OBJ model category showcase"
    scene["display_category"] = category
    scene["model_count"] = len(paths)
    scene["source_root"] = SOURCE_ROOT.relative_to(WORKBENCH_ROOT).as_posix()
    scene["source_order"] = json.dumps([path.relative_to(WORKBENCH_ROOT).as_posix() for path in paths], ensure_ascii=False)
    scene["external_assets"] = False
    scene["layout_columns"] = columns
    scene["layout_rows"] = rows
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = camera
    camera.select_set(True)
    bpy.ops.file.pack_all()
    resources = audit_resources()
    ensure(not resources["external_resources"], f"External resources remain in {category}: {resources['external_resources']}")
    ensure(not resources["libraries"], f"Linked Blender libraries remain in {category}: {resources['libraries']}")
    output = output_root / f"{category}.blend"
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    preview = None
    if render:
        preview = WORKBENCH_ROOT / "generated" / "othermodel" / f"{category}.png"
        preview.parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(preview)
        bpy.ops.render.render(write_still=True)
    return {
        "category": category,
        "blend": output.relative_to(WORKBENCH_ROOT).as_posix(),
        "source_objs": [path.relative_to(WORKBENCH_ROOT).as_posix() for path in paths],
        "model_count": len(paths),
        "layout": {"columns": columns, "rows": rows, "cell_x": cell_x, "cell_y": cell_y},
        "object_count": len([obj for obj in bpy.data.objects if obj.type == "MESH"]),
        "material_count": len(bpy.data.materials),
        "scene_count": len(bpy.data.scenes),
        "external_resources": resources["external_resources"],
        "libraries": resources["libraries"],
        "preview": preview.relative_to(WORKBENCH_ROOT).as_posix() if preview else None,
        "file_size_bytes": output.stat().st_size,
        "sha256": sha256(output),
        "passed": True,
    }


def main() -> None:
    args = parse_args()
    ensure(SOURCE_ROOT.is_dir(), f"Missing OBJ source directory: {SOURCE_ROOT}")
    all_paths = sorted(SOURCE_ROOT.glob("*.obj"), key=natural_key)
    ensure(all_paths, f"No OBJ files found under {SOURCE_ROOT}")
    grouped: dict[str, list[Path]] = {category: [] for category in CATEGORY_ORDER}
    for path in all_paths:
        grouped[classify(path)].append(path)
    selected = args.category or list(CATEGORY_ORDER)
    records = [
        build_category(category, grouped[category], OUTPUT_ROOT, args.render)
        for category in selected
        if grouped[category]
    ]
    result = {
        "blender_version": bpy.app.version_string,
        "source_root": SOURCE_ROOT.relative_to(WORKBENCH_ROOT).as_posix(),
        "total_obj_count": len(all_paths),
        "category_counts": {category: len(grouped[category]) for category in CATEGORY_ORDER if grouped[category]},
        "selected_categories": selected,
        "files": records,
        "passed": len(records) == len(selected) and all(record["passed"] for record in records),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("KEYMEMO_OTHERMODEL_BUILD=" + json.dumps(result, ensure_ascii=False))
    if not result["passed"]:
        raise RuntimeError("One or more OBJ category builds failed")


if __name__ == "__main__":
    main()
