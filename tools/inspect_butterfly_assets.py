import json
import os
from pathlib import Path

import bpy

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from workbench_paths import WORKBENCH_ROOT, model_root, model_source

PROJECT_ROOT = WORKBENCH_ROOT
ASSET_ROOT = model_root("Butterfly")
SOURCE_ROOT = model_source("Butterfly")


def object_snapshot(objects):
    result = []
    for obj in objects:
        item = {
            "name": obj.name,
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "dimensions": [round(v, 6) for v in obj.dimensions],
            "location": [round(v, 6) for v in obj.location],
            "hide_viewport": obj.hide_viewport,
            "hide_render": obj.hide_render,
            "custom_properties": sorted(k for k in obj.keys() if k != "_RNA_UI"),
        }
        if obj.type == "MESH":
            item.update({
                "vertices": len(obj.data.vertices),
                "polygons": len(obj.data.polygons),
                "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
                "uv_layers": [layer.name for layer in obj.data.uv_layers],
                "shape_keys": [key.name for key in obj.data.shape_keys.key_blocks] if obj.data.shape_keys else [],
                "vertex_groups": [group.name for group in obj.vertex_groups],
                "modifiers": [modifier.name for modifier in obj.modifiers],
            })
        elif obj.type == "ARMATURE":
            item["bones"] = [bone.name for bone in obj.data.bones]
            item["pose_bones"] = [bone.name for bone in obj.pose.bones]
            item["animation_data"] = bool(obj.animation_data)
            item["action"] = obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None
        result.append(item)
    return result


def action_snapshot():
    result = []
    for action in bpy.data.actions:
        frame_range = list(action.frame_range)
        layers = [layer.name for layer in getattr(action, "layers", [])]
        result.append({
            "name": action.name,
            "users": action.users,
            "frames": frame_range,
            "layers": layers,
        })
    return result


def import_one(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before = set(bpy.data.objects)
    result = bpy.ops.import_scene.fbx(filepath=str(path))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    payload = {
        "file": str(path.relative_to(ASSET_ROOT)).replace("\\", "/"),
        "result": sorted(result),
        "objects": object_snapshot(imported),
        "actions": action_snapshot(),
        "scenes": [scene.name for scene in bpy.data.scenes],
        "frame_start": bpy.context.scene.frame_start,
        "frame_end": bpy.context.scene.frame_end,
        "fps": bpy.context.scene.render.fps,
    }
    print("BUTTERFLY_INSPECTION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main():
    files = sorted(SOURCE_ROOT.glob("animations/**/*.fbx"), key=lambda path: str(path).lower())
    if not files:
        raise RuntimeError(f"No FBX files found under {SOURCE_ROOT}")
    for path in files:
        import_one(path)


if __name__ == "__main__":
    main()
