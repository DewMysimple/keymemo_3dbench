"""Reopen and validate every generated othermodel OBJ showcase file."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_othermodel_obj_collections import (  # noqa: E402
    CATEGORY_ORDER,
    OUTPUT_ROOT,
    SOURCE_ROOT,
    classify,
    natural_key,
)


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
REPORT = WORKBENCH_ROOT / "models" / "othermodel" / "reports" / "validation.json"


def check_resources() -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    collections = (
        ("images", bpy.data.images),
        ("movieclips", bpy.data.movieclips),
        ("sounds", bpy.data.sounds),
        ("fonts", bpy.data.fonts),
        ("volumes", bpy.data.volumes),
        ("cache_files", bpy.data.cache_files),
    )
    for kind, collection in collections:
        for datablock in collection:
            filepath = getattr(datablock, "filepath", "")
            if not filepath or filepath == "<builtin>":
                continue
            packed = getattr(datablock, "packed_file", None) is not None or bool(getattr(datablock, "packed_files", []))
            if not packed:
                failures.append({"kind": kind, "name": datablock.name, "filepath": filepath})
    for library in bpy.data.libraries:
        failures.append({"kind": "library", "name": library.name, "filepath": library.filepath})
    return failures


def validate_category(category: str, source_paths: list[Path]) -> dict[str, Any]:
    blend_path = OUTPUT_ROOT / f"{category}.blend"
    if not blend_path.is_file():
        raise RuntimeError(f"Missing generated blend: {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=str(blend_path), load_ui=False)
    failures: list[str] = []
    resources = check_resources()
    if resources:
        failures.append(f"external resources: {resources}")
    scene = bpy.context.scene
    if len(bpy.data.scenes) != 1:
        failures.append(f"expected one scene, got {len(bpy.data.scenes)}")
    collection = bpy.data.collections.get(f"MODELS_{category}")
    roots = sorted(
        [obj for obj in collection.objects] if collection else [],
        key=lambda obj: obj.name.lower(),
    )
    roots = [obj for obj in roots if obj.name.startswith("MODEL_")]
    if len(roots) != len(source_paths):
        failures.append(f"expected {len(source_paths)} model roots, got {len(roots)}")
    expected_order = [path.relative_to(WORKBENCH_ROOT).as_posix() for path in source_paths]
    try:
        saved_order = json.loads(scene.get("source_order", "[]"))
    except json.JSONDecodeError as exc:
        saved_order = []
        failures.append(f"source_order is invalid JSON: {exc}")
    if saved_order != expected_order:
        failures.append("source_order does not match natural source ordering")
    root_sources = [root.get("source_obj") for root in roots]
    if sorted(root_sources, key=lambda value: natural_key(Path(value))) != expected_order:
        failures.append("model root source paths do not match source ordering")
    mesh_count = sum(obj.type == "MESH" for obj in bpy.data.objects)
    if mesh_count == 0:
        failures.append("no mesh objects found")
    labels = [obj for obj in bpy.data.objects if obj.name.startswith("LABEL_")]
    if len(labels) != len(source_paths):
        failures.append(f"expected {len(source_paths)} labels, got {len(labels)}")
    camera = scene.camera
    if camera is None or camera.name != "SHOWCASE_CAMERA":
        failures.append("SHOWCASE_CAMERA is not the active scene camera")
    root_locations = {(round(obj.location.x, 6), round(obj.location.y, 6)) for obj in roots}
    if len(root_locations) != len(roots):
        failures.append("model roots are not placed at unique sorted display positions")
    return {
        "category": category,
        "blend": blend_path.relative_to(WORKBENCH_ROOT).as_posix(),
        "source_obj_count": len(source_paths),
        "model_root_count": len(roots),
        "mesh_object_count": mesh_count,
        "label_count": len(labels),
        "scene_count": len(bpy.data.scenes),
        "external_resources": resources,
        "camera": camera.name if camera else None,
        "source_order": expected_order,
        "failures": failures,
        "passed": not failures,
    }


def main() -> None:
    source_paths = sorted(SOURCE_ROOT.glob("*.obj"), key=natural_key)
    grouped: dict[str, list[Path]] = {category: [] for category in CATEGORY_ORDER}
    for path in source_paths:
        grouped[classify(path)].append(path)
    records = [validate_category(category, grouped[category]) for category in CATEGORY_ORDER]
    result = {
        "blender_version": bpy.app.version_string,
        "source_root": SOURCE_ROOT.relative_to(WORKBENCH_ROOT).as_posix(),
        "total_obj_count": len(source_paths),
        "category_counts": {category: len(grouped[category]) for category in CATEGORY_ORDER},
        "files": records,
        "passed": all(record["passed"] for record in records),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("KEYMEMO_OTHERMODEL_VALIDATION=" + json.dumps(result, ensure_ascii=False))
    if not result["passed"]:
        raise RuntimeError("Othermodel validation failed")


if __name__ == "__main__":
    main()
