from __future__ import annotations

import json
import hashlib
import math

import bpy


WING_NAMES = (
    "展示_Butterfly_Master_源_FBX_01_03_BUTTERFLY_IDLE_1_LEFT_WING_",
    "展示_Butterfly_Master_源_FBX_01_04_BUTTERFLY_IDLE_1_RIGHT_WING_",
)


def action_fcurves(action: bpy.types.Action | None) -> list[bpy.types.FCurve]:
    if action is None:
        return []
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    return [
        fcurve
        for layer in action.layers
        for strip in layer.strips
        if hasattr(strip, "channelbags")
        for channelbag in strip.channelbags
        for fcurve in channelbag.fcurves
    ]


def point_payload(point: bpy.types.Keyframe, angular: bool) -> dict[str, object]:
    value = math.degrees(float(point.co.y)) if angular else float(point.co.y)
    return {
        "frame": round(float(point.co.x), 6),
        "value": round(value, 6),
        "interpolation": point.interpolation,
        "easing": point.easing,
        "handle_left_type": point.handle_left_type,
        "handle_right_type": point.handle_right_type,
    }


def curve_digest(fcurve: bpy.types.FCurve) -> str:
    payload = [
        (
            float(point.co.x),
            float(point.co.y),
            point.interpolation,
            point.easing,
            float(point.handle_left.x),
            float(point.handle_left.y),
            float(point.handle_right.x),
            float(point.handle_right.y),
            point.handle_left_type,
            point.handle_right_type,
        )
        for point in fcurve.keyframe_points
    ]
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


payload: dict[str, object] = {
    "file": bpy.data.filepath,
    "scene": bpy.context.scene.name,
    "frame_range": [bpy.context.scene.frame_start, bpy.context.scene.frame_end],
    "current_frame": bpy.context.scene.frame_current,
    "objects": {},
}

for name in WING_NAMES:
    obj = bpy.data.objects.get(name)
    if obj is None:
        payload["objects"][name] = {"missing": True}
        continue
    action = obj.animation_data.action if obj.animation_data else None
    curves = []
    for fcurve in action_fcurves(action):
        angular = fcurve.data_path in {"rotation_euler", "rotation_quaternion"}
        points = [point_payload(point, angular) for point in fcurve.keyframe_points]
        values = [point["value"] for point in points]
        include_points = fcurve.data_path == "rotation_euler" and fcurve.array_index == 2
        curves.append(
            {
                "data_path": fcurve.data_path,
                "array_index": fcurve.array_index,
                "keyframe_sha256": curve_digest(fcurve),
                "keyframe_count": len(points),
                "value_unit": "degrees" if angular else "blender_units",
                "value_min": min(values) if values else None,
                "value_max": max(values) if values else None,
                "unique_values_6dp": len(set(values)),
                "keyframes": points if include_points else [],
            }
        )
    payload["objects"][name] = {
        "type": obj.type,
        "rotation_mode": obj.rotation_mode,
        "rotation_euler_degrees": [round(math.degrees(float(v)), 6) for v in obj.rotation_euler],
        "parent": obj.parent.name if obj.parent else None,
        "action": action.name if action else None,
        "action_slot": (
            getattr(getattr(obj.animation_data, "action_slot", None), "identifier", None)
            if obj.animation_data
            else None
        ),
        "curves": curves,
    }

print("MYBUTTERFLY_WING_INSPECTION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))
