from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
SCENES_ROOT = WORKBENCH_ROOT / "models" / "Butterfly" / "scenes"
MASTER_PATH = SCENES_ROOT / "MyWork" / "MyButterfly_Master.blend"
SOURCE_DIR = SCENES_ROOT / "follow_path"
OUTPUT_DIR = SCENES_ROOT / "MyWork"
REPORT_PATH = WORKBENCH_ROOT / "reports" / "mybutterfly-follow-path-rotation-only-applied-validation.json"

LEFT_WING = "展示_Butterfly_Master_源_FBX_01_03_BUTTERFLY_IDLE_1_LEFT_WING_"
RIGHT_WING = "展示_Butterfly_Master_源_FBX_01_04_BUTTERFLY_IDLE_1_RIGHT_WING_"
WING_NAMES = {"left": LEFT_WING, "right": RIGHT_WING}
BODY_NAME = "展示_Butterfly_Master_源_FBX_01_01_BASIC_BUTTERFLY_BODY_Travis_Davids_OBJ_1"
ROTATION_PATH = "rotation_euler"
SAFE_Z_HALF_AMPLITUDE_DEGREES = 32.0

VARIANTS = (
    (
        1,
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1_NO_LIGHT_NO_PATH_ROTATION_ONLY.blend",
        "MyButterfly_Master_FollowPath1_RotationOnlyApplied.blend",
    ),
    (
        2,
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2_NO_LIGHT_NO_PATH_ROTATION_ONLY.blend",
        "MyButterfly_Master_FollowPath2_RotationOnlyApplied.blend",
    ),
)


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(WORKBENCH_ROOT.resolve())).replace("\\", "/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def action_curve_handles(action: bpy.types.Action):
    if hasattr(action, "fcurves"):
        for curve in list(action.fcurves):
            yield curve
        return
    for layer in action.layers:
        for strip in layer.strips:
            if not hasattr(strip, "channelbags"):
                continue
            for channelbag in strip.channelbags:
                for curve in list(channelbag.fcurves):
                    yield curve


def action_fcurves(action: bpy.types.Action | None) -> list[bpy.types.FCurve]:
    if action is None:
        return []
    return list(action_curve_handles(action))


def wing_role(name: str) -> str | None:
    lowered = name.lower()
    if "left_wing" in lowered:
        return "left"
    if "right_wing" in lowered:
        return "right"
    return None


def action_for_role(role: str) -> bpy.types.Action:
    matches = [action for action in bpy.data.actions if wing_role(action.name) == role]
    ensure(len(matches) == 1, f"Expected one {role} wing Action, found {[action.name for action in matches]}")
    return matches[0]


def find_curve(action: bpy.types.Action, array_index: int) -> bpy.types.FCurve:
    matches = [
        curve
        for curve in action_fcurves(action)
        if curve.data_path == ROTATION_PATH and curve.array_index == array_index
    ]
    ensure(len(matches) == 1, f"{action.name}: expected one rotation_euler[{array_index}] curve")
    return matches[0]


def curve_payload(curve: bpy.types.FCurve) -> dict[str, object]:
    return {
        "extrapolation": curve.extrapolation,
        "baseline": float(curve.evaluate(1.0)),
        "points": [
            {
                "co": [float(point.co.x), float(point.co.y)],
                "handle_left": [float(point.handle_left.x), float(point.handle_left.y)],
                "handle_right": [float(point.handle_right.x), float(point.handle_right.y)],
                "interpolation": point.interpolation,
                "easing": point.easing,
                "type": point.type,
                "back": float(point.back),
                "amplitude": float(point.amplitude),
                "period": float(point.period),
                "handle_left_type": point.handle_left_type,
                "handle_right_type": point.handle_right_type,
            }
            for point in curve.keyframe_points
        ],
    }


def transform_signature(obj: bpy.types.Object) -> dict[str, object]:
    return {
        "matrix_world": [float(value) for row in obj.matrix_world for value in row],
        "location": [float(value) for value in obj.location],
        "rotation_euler": [float(value) for value in obj.rotation_euler],
        "scale": [float(value) for value in obj.scale],
        "parent": obj.parent.name if obj.parent else None,
    }


def max_transform_difference(first: dict[str, object], second: dict[str, object]) -> float:
    return max(
        abs(left - right)
        for key in ("matrix_world", "location", "rotation_euler", "scale")
        for left, right in zip(first[key], second[key])
    )


def display_snapshot(scene: bpy.types.Scene, frames: tuple[int, ...]) -> dict[int, dict[str, dict[str, object]]]:
    objects = sorted(
        [obj for obj in scene.objects if obj.name.startswith("展示_") or obj.name.startswith("DISPLAY_")],
        key=lambda obj: obj.name,
    )
    result: dict[int, dict[str, dict[str, object]]] = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        result[frame] = {obj.name: transform_signature(obj) for obj in objects}
    return result


def compare_curve(
    source_curve: dict[str, object],
    output_curve: bpy.types.FCurve,
    source_baseline: float,
    target_baseline: float,
    value_scale: float,
) -> None:
    ensure(source_curve["extrapolation"] == output_curve.extrapolation, "Curve extrapolation changed")
    source_points = source_curve["points"]
    output_points = list(output_curve.keyframe_points)
    ensure(len(source_points) == len(output_points), "Rotation keyframe count changed")
    for source_point, output_point in zip(source_points, output_points):
        ensure(abs(source_point["co"][0] - output_point.co.x) <= 1e-6, "Rotation keyframe frame changed")
        expected_value = target_baseline + (source_point["co"][1] - source_baseline) * value_scale
        ensure(abs(expected_value - output_point.co.y) <= 1e-5, "Rotation keyframe affine mapping changed")
        ensure(abs(source_point["handle_left"][0] - output_point.handle_left.x) <= 1e-5, "Left handle time changed")
        ensure(abs(source_point["handle_right"][0] - output_point.handle_right.x) <= 1e-5, "Right handle time changed")
        expected_left_y = target_baseline + (source_point["handle_left"][1] - source_baseline) * value_scale
        expected_right_y = target_baseline + (source_point["handle_right"][1] - source_baseline) * value_scale
        ensure(abs(expected_left_y - output_point.handle_left.y) <= 1e-5, "Left handle value mapping changed")
        ensure(abs(expected_right_y - output_point.handle_right.y) <= 1e-5, "Right handle value mapping changed")
        for property_name in (
            "interpolation",
            "easing",
            "type",
            "back",
            "amplitude",
            "period",
            "handle_left_type",
            "handle_right_type",
        ):
            ensure(
                source_point[property_name] == getattr(output_point, property_name),
                f"Keyframe {property_name} changed",
            )


def mesh_centroid_world(obj: bpy.types.Object) -> Vector:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    return sum(points, Vector()) / len(points)


def validate_geometry(scene: bpy.types.Scene, wings: dict[str, bpy.types.Object]) -> dict[str, object]:
    body = scene.objects.get(BODY_NAME)
    ensure(body is not None and body.type == "MESH", "Display body mesh missing")
    scene.frame_set(1)
    bpy.context.view_layer.update()
    body_center = mesh_centroid_world(body)
    references = {
        role: mesh_centroid_world(wing) - body_center
        for role, wing in wings.items()
    }
    directions = {role: vector.normalized() for role, vector in references.items()}
    lengths = {role: vector.length for role, vector in references.items()}
    z_samples = {"left": [], "right": []}
    ratios = {"left": [], "right": []}
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        body_center = mesh_centroid_world(body)
        for role, wing in wings.items():
            z_degrees = math.degrees(float(wing.rotation_euler.z))
            ratio = (mesh_centroid_world(wing) - body_center).dot(directions[role]) / lengths[role]
            z_samples[role].append((frame, z_degrees))
            ratios[role].append((frame, ratio))
    for frame, value in z_samples["left"]:
        ensure(0.0 < value < 90.0, f"Left wing crossed anatomical side at frame {frame}: {value}°")
    for frame, value in z_samples["right"]:
        ensure(-90.0 < value < 0.0, f"Right wing crossed anatomical side at frame {frame}: {value}°")
    minimum_ratios = {}
    for role in ("left", "right"):
        minimum_ratio, minimum_frame = min((ratio, frame) for frame, ratio in ratios[role])
        ensure(minimum_ratio >= 0.7, f"{role} wing approached body at frame {minimum_frame}: {minimum_ratio}")
        minimum_ratios[role] = minimum_ratio
    return {
        "sampled_frame_count": scene.frame_end - scene.frame_start + 1,
        "z_range_degrees": {
            role: [min(value for _, value in z_samples[role]), max(value for _, value in z_samples[role])]
            for role in ("left", "right")
        },
        "minimum_anatomical_side_projection_ratio": minimum_ratios,
        "wings_stay_on_anatomical_sides": True,
    }


def validate_one(variant: int, source_name: str, output_name: str) -> dict[str, object]:
    source_path = SOURCE_DIR / source_name
    output_path = OUTPUT_DIR / output_name
    ensure(source_path.is_file(), f"Source missing: {source_path}")
    ensure(output_path.is_file(), f"Output missing: {output_path}")
    master_hash = sha256_file(MASTER_PATH)
    source_hash = sha256_file(source_path)

    bpy.ops.wm.open_mainfile(filepath=str(source_path), load_ui=False)
    source_actions = {role: action_for_role(role) for role in ("left", "right")}
    source_curves = {
        role: [curve_payload(find_curve(source_actions[role], axis)) for axis in range(3)]
        for role in ("left", "right")
    }
    source_baselines = {
        role: [float(curve["baseline"]) for curve in source_curves[role]]
        for role in ("left", "right")
    }

    bpy.ops.wm.open_mainfile(filepath=str(MASTER_PATH), load_ui=False)
    master_scene = bpy.data.scenes.get("ARTIST_EDIT")
    ensure(master_scene is not None, "Master ARTIST_EDIT scene missing")
    master_frame_range = [master_scene.frame_start, master_scene.frame_end]
    master_scene.frame_set(1)
    bpy.context.view_layer.update()
    master_wings = {role: master_scene.objects[name] for role, name in WING_NAMES.items()}
    master_baselines = {
        role: [float(obj.rotation_euler[axis]) for axis in range(3)]
        for role, obj in master_wings.items()
    }
    frames = (master_scene.frame_start, (master_scene.frame_start + master_scene.frame_end) // 2, master_scene.frame_end)
    master_snapshot = display_snapshot(master_scene, frames)

    bpy.ops.wm.open_mainfile(filepath=str(output_path), load_ui=False)
    scene = bpy.data.scenes.get("ARTIST_EDIT")
    ensure(scene is not None, f"{output_name}: ARTIST_EDIT scene missing")
    ensure(scene.frame_start == master_frame_range[0] and scene.frame_end == master_frame_range[1], f"{output_name}: frame range changed")
    wings = {role: scene.objects[name] for role, name in WING_NAMES.items()}
    output_snapshot = display_snapshot(scene, frames)
    wing_reports: dict[str, object] = {}
    for role, obj in wings.items():
        ensure(obj.animation_data and obj.animation_data.action, f"{output_name}: {role} wing Action missing")
        action = obj.animation_data.action
        curves = action_fcurves(action)
        ensure(len(curves) == 3, f"{output_name}: {role} wing should have 3 rotation curves")
        ensure(all(curve.data_path == ROTATION_PATH for curve in curves), f"{output_name}: non-rotation curve remains on {role} wing")
        scales = []
        for axis in range(3):
            source_curve = source_curves[role][axis]
            output_curve = find_curve(action, axis)
            source_baseline = source_baselines[role][axis]
            target_baseline = master_baselines[role][axis]
            source_values = [float(point["co"][1]) for point in source_curve["points"]]
            max_delta = max(abs(value - source_baseline) for value in source_values)
            value_scale = 1.0 if axis != 2 else math.radians(SAFE_Z_HALF_AMPLITUDE_DEGREES) / max_delta
            compare_curve(source_curve, output_curve, source_baseline, target_baseline, value_scale)
            scales.append(value_scale)
        wing_reports[role] = {
            "action": action.name,
            "rotation_curve_count": len(curves),
            "keyframe_count_per_curve": [len(find_curve(action, axis).keyframe_points) for axis in range(3)],
            "value_scales": scales,
            "non_rotation_curves_removed": True,
            "rotation_keyframes_preserved": True,
        }
    for frame in frames:
        for name in master_snapshot[frame]:
            if name in WING_NAMES.values():
                continue
            ensure(
                max_transform_difference(master_snapshot[frame][name], output_snapshot[frame][name]) <= 1e-6,
                f"{output_name}: non-wing display transform changed at frame {frame}: {name}",
            )
    scene.frame_set(1)
    bpy.context.view_layer.update()
    for role, name in WING_NAMES.items():
        ensure(
            max_transform_difference(master_snapshot[1][name], output_snapshot[1][name]) <= 1e-6,
            f"{output_name}: {role} wing frame-1 transform changed",
        )
    ensure(not [obj for obj in bpy.data.objects if obj.motion_path], f"{output_name}: Motion Path cache unexpectedly present")
    geometry = validate_geometry(scene, wings)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    return {
        "variant": variant,
        "master": relative(MASTER_PATH),
        "master_sha256": master_hash,
        "source": relative(source_path),
        "source_sha256": source_hash,
        "output": relative(output_path),
        "output_sha256": sha256_file(output_path),
        "frame_range": [scene.frame_start, scene.frame_end],
        "display_wings": WING_NAMES,
        "wing_reports": wing_reports,
        "master_non_wing_transforms_preserved": True,
        "master_wing_frame_one_transforms_preserved": True,
        "motion_path_objects_remaining": [],
        "full_frame_geometry": geometry,
        "follow_path_controller_applied": False,
        "result": "pass",
    }


def main() -> None:
    reports = [validate_one(*variant) for variant in VARIANTS]
    payload = {
        "asset": "Butterfly",
        "variant": "mybutterfly_follow_path_rotation_only_applied",
        "validated_count": len(reports),
        "master_preserved": all(report["master_sha256"] == sha256_file(MASTER_PATH) for report in reports),
        "sources_preserved": all(
            report["source_sha256"] == sha256_file(SOURCE_DIR / VARIANTS[index][1])
            for index, report in enumerate(reports)
        ),
        "validated": reports,
    }
    ensure(payload["master_preserved"], "Master hash changed during validation")
    ensure(payload["sources_preserved"], "Source hash changed during validation")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MYBUTTERFLY_FOLLOW_PATH_ROTATION_ONLY_APPLIED_VALIDATION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
