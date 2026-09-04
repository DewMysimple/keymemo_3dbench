from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bpy


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = WORKBENCH_ROOT / "models" / "Butterfly" / "scenes" / "follow_path"
OUTPUT_DIR = SOURCE_DIR
REPORT_PATH = WORKBENCH_ROOT / "reports" / "butterfly-follow-path-rotation-only-validation.json"

VARIANTS = (
    (
        1,
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend",
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1_NO_LIGHT_NO_PATH_ROTATION_ONLY.blend",
    ),
    (
        2,
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend",
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2_NO_LIGHT_NO_PATH_ROTATION_ONLY.blend",
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
            yield action.fcurves, curve
        return
    for layer in action.layers:
        for strip in layer.strips:
            if not hasattr(strip, "channelbags"):
                continue
            for channelbag in strip.channelbags:
                for curve in list(channelbag.fcurves):
                    yield channelbag.fcurves, curve


def action_fcurves(action: bpy.types.Action | None) -> list[bpy.types.FCurve]:
    if action is None:
        return []
    return [curve for _, curve in action_curve_handles(action)]


def wing_role(obj: bpy.types.Object) -> str | None:
    name = obj.name.lower()
    if "left_wing" in name:
        return "left"
    if "right_wing" in name:
        return "right"
    return None


def curve_signature(curve: bpy.types.FCurve) -> dict[str, object]:
    return {
        "data_path": curve.data_path,
        "array_index": curve.array_index,
        "extrapolation": curve.extrapolation,
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


def wing_rotation_signatures() -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {"left": [], "right": []}
    seen_actions: set[str] = set()
    for obj in bpy.data.objects:
        role = wing_role(obj)
        if role is None:
            continue
        action = obj.animation_data.action if obj.animation_data else None
        ensure(action is not None, f"{obj.name}: wing action missing")
        if action.name in seen_actions:
            continue
        seen_actions.add(action.name)
        result[role] = [
            curve_signature(curve)
            for curve in action_fcurves(action)
            if curve.data_path in {"rotation_euler", "rotation_quaternion", "rotation_axis_angle"}
        ]
    ensure(all(result.values()), "Expected both left and right wing actions")
    return result


def action_summary() -> list[dict[str, object]]:
    return [
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
    ]


def object_transform_sample(scene: bpy.types.Scene, roles: dict[str, list[bpy.types.Object]]) -> dict[str, object]:
    frames = [scene.frame_start, (scene.frame_start + scene.frame_end) // 2, scene.frame_end]
    values: dict[str, list[list[float]]] = {role: [] for role in roles}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for role, objects in roles.items():
            values[role].append([float(obj.rotation_euler.z) for obj in objects])
    ensure(
        any(values[role][0] != values[role][-1] for role in ("left", "right")),
        "Wing rotation animation is not changing across sampled frames",
    )
    return {"frames": frames, "rotation_z_radians": values}


def validate_one(variant: int, source_name: str, output_name: str) -> dict[str, object]:
    source_path = SOURCE_DIR / source_name
    output_path = OUTPUT_DIR / output_name
    ensure(source_path.is_file(), f"Source file missing: {source_path}")
    ensure(output_path.is_file(), f"Output file missing: {output_path}")
    source_hash = sha256_file(source_path)

    bpy.ops.wm.open_mainfile(filepath=str(source_path), load_ui=False)
    source_signatures = wing_rotation_signatures()
    source_action_summary = action_summary()

    bpy.ops.wm.open_mainfile(filepath=str(output_path), load_ui=False)
    scene = bpy.data.scenes.get("ARTIST_EDIT") or bpy.context.scene
    ensure(scene is not None, f"{output_name}: ARTIST_EDIT scene missing")
    ensure(scene.frame_start == 1 and scene.frame_end == 91, f"{output_name}: frame range changed")
    ensure(not [obj for obj in bpy.data.objects if obj.type == "LIGHT"], f"{output_name}: light objects remain")

    non_wing_action_objects = [
        obj.name
        for obj in bpy.data.objects
        if wing_role(obj) is None and obj.animation_data and obj.animation_data.action
    ]
    ensure(not non_wing_action_objects, f"{output_name}: non-wing animation remains: {non_wing_action_objects}")

    output_signatures = wing_rotation_signatures()
    ensure(output_signatures == source_signatures, f"{output_name}: wing rotation keyframes changed")

    non_rotation_curves = [
        {
            "action": action.name,
            "data_path": curve.data_path,
            "array_index": curve.array_index,
        }
        for action in bpy.data.actions
        for curve in action_fcurves(action)
        if curve.data_path not in {"rotation_euler", "rotation_quaternion", "rotation_axis_angle"}
    ]
    ensure(not non_rotation_curves, f"{output_name}: non-rotation keyframes remain: {non_rotation_curves}")

    follow_path_constraints = [
        {"object": obj.name, "constraint": constraint.name}
        for obj in bpy.data.objects
        for constraint in obj.constraints
        if constraint.type == "FOLLOW_PATH"
    ]
    ensure(not follow_path_constraints, f"{output_name}: Follow Path constraint remains")

    wing_objects = {"left": [], "right": []}
    for obj in bpy.data.objects:
        role = wing_role(obj)
        if role is not None:
            wing_objects[role].append(obj)
    sample = object_transform_sample(scene, wing_objects)
    scene.frame_set(1)
    bpy.context.view_layer.update()

    report = {
        "variant": variant,
        "source": relative(source_path),
        "output": relative(output_path),
        "source_sha256": source_hash,
        "output_sha256": sha256_file(output_path),
        "lights_remaining": [],
        "path_animation_removed": True,
        "non_wing_action_objects": [],
        "follow_path_constraints_remaining": [],
        "non_rotation_curves_remaining": [],
        "source_action_summary": source_action_summary,
        "output_action_summary": action_summary(),
        "wing_rotation_keyframes_preserved": True,
        "sampled_wing_rotation": sample,
        "result": "pass",
    }
    return report


def main() -> None:
    reports = [validate_one(*variant) for variant in VARIANTS]
    payload = {
        "asset": "Butterfly",
        "variant": "follow_path_rotation_only_no_light_no_path",
        "validated_count": len(reports),
        "sources_preserved": all(
            report["source_sha256"] == sha256_file(SOURCE_DIR / VARIANTS[index][1])
            for index, report in enumerate(reports)
        ),
        "validated": reports,
    }
    ensure(payload["sources_preserved"], "Source file hash changed during validation")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_FOLLOW_PATH_ROTATION_ONLY_VALIDATION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
