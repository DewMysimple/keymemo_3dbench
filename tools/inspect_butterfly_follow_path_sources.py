from __future__ import annotations

import json

import bpy


def action_fcurves(action: bpy.types.Action) -> list[bpy.types.FCurve]:
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    return [
        curve
        for layer in action.layers
        for strip in layer.strips
        if hasattr(strip, "channelbags")
        for channelbag in strip.channelbags
        for curve in channelbag.fcurves
    ]


def main() -> None:
    payload = {
        "scenes": [
            (scene.name, scene.frame_start, scene.frame_end, scene.camera.name if scene.camera else None)
            for scene in bpy.data.scenes
        ],
        "objects": [
            {
                "name": obj.name,
                "type": obj.type,
                "parent": obj.parent.name if obj.parent else None,
                "constraints": [
                    (
                        constraint.name,
                        constraint.type,
                        constraint.target.name if constraint.target else None,
                    )
                    for constraint in obj.constraints
                ],
                "action": (
                    obj.animation_data.action.name
                    if obj.animation_data and obj.animation_data.action
                    else None
                ),
            }
            for obj in bpy.data.objects
        ],
        "lights": [obj.name for obj in bpy.data.objects if obj.type == "LIGHT"],
        "curves": [obj.name for obj in bpy.data.objects if obj.type == "CURVE"],
        "actions": [
            {
                "name": action.name,
                "users": action.users,
                "fcurves": [
                    {
                        "data_path": curve.data_path,
                        "array_index": curve.array_index,
                        "keyframe_count": len(curve.keyframe_points),
                    }
                    for curve in action_fcurves(action)
                ],
            }
            for action in bpy.data.actions
        ],
    }
    print("BUTTERFLY_FOLLOW_PATH_SOURCE_INSPECTION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
