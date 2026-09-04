from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adjust_mybutterfly_wing_animation import (
    LEFT_WING,
    LEFT_Z_KEYS_DEGREES,
    RIGHT_MIRROR_OFFSET_DEGREES,
    RIGHT_WING,
    RIGHT_Z_KEYS_DEGREES,
    object_action_fcurves,
)


EXPECTED = (
    (
        LEFT_WING,
        "MyButterfly_WingMotion_DYNAMIC_LEFT",
        "BUTTERFLY_IDLE_1_LEFT_WING_|CINEMA_4D_Main|Layer0",
        LEFT_Z_KEYS_DEGREES,
    ),
    (
        RIGHT_WING,
        "MyButterfly_WingMotion_DYNAMIC_RIGHT",
        "BUTTERFLY_IDLE_1_RIGHT_WING_|CINEMA_4D_Main|Layer0",
        RIGHT_Z_KEYS_DEGREES,
    ),
)


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


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


def action_fcurves_for_identifier(action: bpy.types.Action, slot_identifier: str | None) -> list[bpy.types.FCurve]:
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    slot = next(
        (
            candidate
            for candidate in getattr(action, "slots", [])
            if getattr(candidate, "identifier", None) == slot_identifier
        ),
        None,
    )
    slot_handle = getattr(slot, "handle", None)
    matching: list[bpy.types.FCurve] = []
    fallback: list[bpy.types.FCurve] = []
    for layer in action.layers:
        for strip in layer.strips:
            if not hasattr(strip, "channelbags"):
                continue
            for channelbag in strip.channelbags:
                curves = list(channelbag.fcurves)
                fallback.extend(curves)
                if slot_handle is not None and getattr(channelbag, "slot_handle", None) == slot_handle:
                    matching.extend(curves)
    return matching or fallback


def keyed_curve(curves: list[bpy.types.FCurve], data_path: str, array_index: int) -> bpy.types.FCurve:
    matches = [
        curve
        for curve in curves
        if curve.data_path == data_path and curve.array_index == array_index
    ]
    ensure(len(matches) == 1, f"Expected one {data_path}[{array_index}] curve, found {len(matches)}")
    return matches[0]


def validate_object(
    object_name: str,
    action_name: str,
    source_action_name: str,
    expected_keys: tuple[tuple[float, float], ...],
) -> dict[str, object]:
    obj = bpy.data.objects.get(object_name)
    ensure(obj is not None, f"Missing object: {object_name}")
    ensure(obj.animation_data is not None, f"Missing animation data: {object_name}")
    ensure(obj.animation_data.action is not None, f"Missing Action: {object_name}")
    ensure(obj.animation_data.action.name == action_name, f"Wrong Action on {object_name}")

    action = obj.animation_data.action
    source_action = bpy.data.actions.get(source_action_name)
    ensure(source_action is not None, f"Source Action was not preserved: {source_action_name}")
    ensure(source_action != action, f"Edited Action is not independent: {object_name}")

    slot_identifier = getattr(getattr(obj.animation_data, "action_slot", None), "identifier", None)
    edited_curves = object_action_fcurves(obj)
    source_curves = action_fcurves_for_identifier(source_action, slot_identifier)
    edited_by_key = {(curve.data_path, curve.array_index): curve for curve in edited_curves}
    source_by_key = {(curve.data_path, curve.array_index): curve for curve in source_curves}
    ensure(set(edited_by_key) == set(source_by_key), f"FCurve channel set changed: {object_name}")

    for key, edited_curve in edited_by_key.items():
        if key == ("rotation_euler", 2):
            continue
        ensure(
            curve_digest(edited_curve) == curve_digest(source_by_key[key]),
            f"Non-Z FCurve changed: {object_name} {key}",
        )

    z_curve = keyed_curve(edited_curves, "rotation_euler", 2)
    ensure(len(z_curve.keyframe_points) == len(expected_keys), f"Wrong Z key count: {object_name}")
    actual_keys = [
        (float(point.co.x), math.degrees(float(point.co.y)))
        for point in z_curve.keyframe_points
    ]
    for actual, expected in zip(actual_keys, expected_keys):
        ensure(abs(actual[0] - expected[0]) < 1e-5, f"Wrong key frame: {object_name}")
        ensure(abs(actual[1] - expected[1]) < 1e-4, f"Wrong key value: {object_name}")
    ensure(
        all(point.interpolation == "BEZIER" for point in z_curve.keyframe_points),
        f"Non-Bezier Z key: {object_name}",
    )
    ensure(
        all(
            point.handle_left_type == "AUTO_CLAMPED" and point.handle_right_type == "AUTO_CLAMPED"
            for point in z_curve.keyframe_points
        ),
        f"Unexpected Z key handles: {object_name}",
    )

    return {
        "object": object_name,
        "parent": obj.parent.name if obj.parent else None,
        "action": action.name,
        "source_action_preserved": source_action.name,
        "source_action_users": source_action.users,
        "z_keyframe_count": len(z_curve.keyframe_points),
        "z_range_degrees": [
            min(value for _, value in actual_keys),
            max(value for _, value in actual_keys),
        ],
        "non_z_curves_match_source": True,
    }


def main() -> None:
    scene = bpy.context.scene
    ensure(scene.frame_start == 1 and scene.frame_end == 91, "Scene range must remain 1-91")
    object_reports = [validate_object(*item) for item in EXPECTED]

    left = bpy.data.objects[LEFT_WING]
    right = bpy.data.objects[RIGHT_WING]
    sampled_values: list[tuple[int, float, float]] = []
    for frame in range(1, 92):
        scene.frame_set(frame)
        left_degrees = math.degrees(float(left.rotation_euler.z))
        right_degrees = math.degrees(float(right.rotation_euler.z))
        ensure(
            abs(left_degrees + right_degrees + RIGHT_MIRROR_OFFSET_DEGREES) < 1e-4,
            f"Wing mirror mismatch at frame {frame}",
        )
        sampled_values.append((frame, left_degrees, right_degrees))

    ensure(abs(sampled_values[0][1] - sampled_values[-1][1]) < 1e-5, "Left loop seam mismatch")
    ensure(abs(sampled_values[0][2] - sampled_values[-1][2]) < 1e-5, "Right loop seam mismatch")

    report = {
        "file": bpy.data.filepath,
        "scene": scene.name,
        "frame_range": [scene.frame_start, scene.frame_end],
        "object_reports": object_reports,
        "sampled_frame_count": len(sampled_values),
        "mirror_offset_degrees": RIGHT_MIRROR_OFFSET_DEGREES,
        "loop_seam_matches": True,
        "result": "pass",
    }
    print("MYBUTTERFLY_WING_VALIDATION=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
