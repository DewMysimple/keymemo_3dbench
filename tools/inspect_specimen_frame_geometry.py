"""Inspect specimen-frame opening and inner-panel world-space geometry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def world_vertices(obj: bpy.types.Object) -> list[Vector]:
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def bounds(points: list[Vector]) -> dict[str, list[float]]:
    return {
        "min": [min(point[index] for point in points) for index in range(3)],
        "max": [max(point[index] for point in points) for index in range(3)],
    }


def dimensions(box: dict[str, list[float]]) -> list[float]:
    return [box["max"][index] - box["min"][index] for index in range(3)]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: blender --background --python inspect_specimen_frame_geometry.py -- FILE")
    path = Path(sys.argv[-1]).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    frame = bpy.data.objects.get("SPECIMEN_OUTER_FRAME")
    panel = bpy.data.objects.get("SPECIMEN_INNER_PANEL")
    merged = bpy.data.objects.get("SPECIMEN_FRAME_MERGED")
    result: dict[str, object] = {"file": str(path)}
    if frame and panel:
        frame_points = world_vertices(frame)
        panel_points = world_vertices(panel)
        result["frame"] = {
            "bounds": bounds(frame_points),
            "dimensions": dimensions(bounds(frame_points)),
        }
        result["panel"] = {
            "bounds": bounds(panel_points),
            "dimensions": dimensions(bounds(panel_points)),
            "parent": panel.parent.name if panel.parent else None,
            "size_property": panel.get("size"),
        }
        opening_size = float(frame.get("opening_size", 7.1))
        overall_size = float(frame.get("overall_size", 9.1))
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
        result["fit_deltas"] = {
            key: actual[key] - expected[key] for key in expected
        }
    elif merged:
        points = world_vertices(merged)
        result["merged"] = {
            "bounds": bounds(points),
            "dimensions": dimensions(bounds(points)),
            "vertices": len(merged.data.vertices),
            "polygons": len(merged.data.polygons),
            "material_slots": [material.name if material else None for material in merged.data.materials],
        }
    else:
        raise RuntimeError("Specimen frame model objects were not found.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
