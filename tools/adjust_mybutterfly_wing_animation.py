from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy


LEFT_WING = "展示_Butterfly_Master_源_FBX_01_03_BUTTERFLY_IDLE_1_LEFT_WING_"
RIGHT_WING = "展示_Butterfly_Master_源_FBX_01_04_BUTTERFLY_IDLE_1_RIGHT_WING_"

# Eight intentionally uneven beats over the existing 1-91 frame range.  Each
# beat uses a quick closing/power stroke followed by a longer recovery stroke.
# The changing extrema keep the motion alive without adding noise to the rig.
LEFT_Z_KEYS_DEGREES = (
    (1.0, 34.0),
    (6.0, 88.0),
    (15.0, 25.0),
    (20.0, 83.0),
    (27.0, 31.0),
    (31.0, 90.0),
    (37.0, 22.0),
    (40.0, 86.0),
    (45.0, 29.0),
    (48.0, 89.0),
    (54.0, 21.0),
    (58.0, 81.0),
    (65.0, 33.0),
    (70.0, 87.0),
    (78.0, 24.0),
    (83.0, 84.0),
    (91.0, 34.0),
)

# The source FBX uses a stable 2.19029-degree calibration difference between
# the mirrored Z channels.  Keep it so the edited wings remain seated exactly
# as they were in the Master hierarchy.
RIGHT_MIRROR_OFFSET_DEGREES = 2.19029
RIGHT_Z_KEYS_DEGREES = tuple(
    (frame, -(value + RIGHT_MIRROR_OFFSET_DEGREES))
    for frame, value in LEFT_Z_KEYS_DEGREES
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def object_action_fcurves(obj: bpy.types.Object) -> list[bpy.types.FCurve]:
    animation_data = obj.animation_data
    action = animation_data.action if animation_data else None
    if action is None:
        return []
    if hasattr(action, "fcurves"):
        return list(action.fcurves)

    active_slot = getattr(animation_data, "action_slot", None)
    active_handle = getattr(active_slot, "handle", None)
    matching: list[bpy.types.FCurve] = []
    fallback: list[bpy.types.FCurve] = []
    for layer in action.layers:
        for strip in layer.strips:
            if not hasattr(strip, "channelbags"):
                continue
            for channelbag in strip.channelbags:
                curves = list(channelbag.fcurves)
                fallback.extend(curves)
                if active_handle is not None and getattr(channelbag, "slot_handle", None) == active_handle:
                    matching.extend(curves)
    return matching or fallback


def bind_action_copy(obj: bpy.types.Object, name: str) -> tuple[str, bpy.types.Action]:
    if obj.animation_data is None or obj.animation_data.action is None:
        fail(f"{obj.name}: missing source Action")

    source_action = obj.animation_data.action
    source_slot = getattr(obj.animation_data, "action_slot", None)
    source_slot_identifier = getattr(source_slot, "identifier", None)

    action = source_action.copy()
    action.name = name
    obj.animation_data.action = action

    if source_slot_identifier is not None:
        copied_slot = next(
            (
                slot
                for slot in getattr(action, "slots", [])
                if getattr(slot, "identifier", None) == source_slot_identifier
            ),
            None,
        )
        if copied_slot is None:
            fail(f"{obj.name}: copied Action lost slot {source_slot_identifier}")
        obj.animation_data.action_slot = copied_slot

    return source_action.name, action


def replace_z_curve(obj: bpy.types.Object, keys_degrees: tuple[tuple[float, float], ...]) -> dict[str, object]:
    curves = object_action_fcurves(obj)
    z_curves = [
        curve
        for curve in curves
        if curve.data_path == "rotation_euler" and curve.array_index == 2
    ]
    if len(z_curves) != 1:
        fail(f"{obj.name}: expected exactly one Euler Z FCurve, found {len(z_curves)}")

    curve = z_curves[0]
    old_count = len(curve.keyframe_points)
    old_values = [math.degrees(float(point.co.y)) for point in curve.keyframe_points]
    while curve.keyframe_points:
        curve.keyframe_points.remove(curve.keyframe_points[-1], fast=True)

    for frame, value_degrees in keys_degrees:
        point = curve.keyframe_points.insert(
            frame,
            math.radians(value_degrees),
            options={"FAST"},
        )
        point.interpolation = "BEZIER"
        point.handle_left_type = "AUTO_CLAMPED"
        point.handle_right_type = "AUTO_CLAMPED"
    curve.update()

    obj["wing_animation_revision"] = "dynamic-variable-tempo-v1"
    obj["wing_animation_axis"] = "local Euler Z"
    obj["wing_animation_frame_range"] = "1-91"
    obj["wing_animation_notes"] = (
        "8 uneven beats; fast power stroke, slower recovery, varied amplitude; "
        "Bezier AUTO_CLAMPED handles"
    )

    return {
        "old_keyframe_count": old_count,
        "old_range_degrees": [min(old_values), max(old_values)],
        "new_keyframe_count": len(curve.keyframe_points),
        "new_range_degrees": [
            min(value for _, value in keys_degrees),
            max(value for _, value in keys_degrees),
        ],
        "interpolation": sorted({point.interpolation for point in curve.keyframe_points}),
    }


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    output_path = Path(argv[0]).resolve() if argv else Path(bpy.data.filepath).resolve()
    if not output_path:
        fail("No output .blend path was provided")

    scene = bpy.context.scene
    if scene.frame_start != 1 or scene.frame_end != 91:
        fail(f"Unexpected scene frame range: {scene.frame_start}-{scene.frame_end}")

    left = bpy.data.objects.get(LEFT_WING)
    right = bpy.data.objects.get(RIGHT_WING)
    if left is None or right is None:
        fail("Required display wing objects were not both found")

    original_frame = scene.frame_current
    left_source, left_action = bind_action_copy(left, "MyButterfly_WingMotion_DYNAMIC_LEFT")
    right_source, right_action = bind_action_copy(right, "MyButterfly_WingMotion_DYNAMIC_RIGHT")

    report = {
        "file": str(output_path),
        "frame_range": [scene.frame_start, scene.frame_end],
        "left": {
            "object": left.name,
            "source_action_preserved": left_source,
            "new_action": left_action.name,
            **replace_z_curve(left, LEFT_Z_KEYS_DEGREES),
        },
        "right": {
            "object": right.name,
            "source_action_preserved": right_source,
            "new_action": right_action.name,
            **replace_z_curve(right, RIGHT_Z_KEYS_DEGREES),
        },
    }

    scene.frame_set(original_frame)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path), check_existing=False)
    print("MYBUTTERFLY_WING_ADJUSTMENT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
