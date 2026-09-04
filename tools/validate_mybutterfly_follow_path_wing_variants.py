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
BUILD_REPORT_PATH = WORKBENCH_ROOT / "reports" / "mybutterfly-follow-path-wing-variants.json"
REPORT_PATH = WORKBENCH_ROOT / "reports" / "mybutterfly-follow-path-wing-validation.json"

LEFT_WING = "展示_Butterfly_Master_源_FBX_01_03_BUTTERFLY_IDLE_1_LEFT_WING_"
RIGHT_WING = "展示_Butterfly_Master_源_FBX_01_04_BUTTERFLY_IDLE_1_RIGHT_WING_"
WING_NAMES = {"left": LEFT_WING, "right": RIGHT_WING}
Z_CURVE_KEY = "rotation_euler[2]"
BODY_NAME = "展示_Butterfly_Master_源_FBX_01_01_BASIC_BUTTERFLY_BODY_Travis_Davids_OBJ_1"
EXPECTED_SAFE_HALF_AMPLITUDE_DEGREES = 32.0

VARIANTS = (
    (
        1,
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend",
        "MyButterfly_Master_FollowPath1_WingKeys.blend",
    ),
    (
        2,
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend",
        "MyButterfly_Master_FollowPath2_WingKeys.blend",
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


def wing_role(name: str) -> str | None:
    lowered = name.lower()
    if "left" in lowered:
        return "left"
    if "right" in lowered:
        return "right"
    return None


def action_signature(action: bpy.types.Action) -> dict[str, object]:
    curves: dict[str, object] = {}
    for curve in action_fcurves(action):
        key = f"{curve.data_path}[{curve.array_index}]"
        curves[key] = {
            "baseline": float(curve.evaluate(1.0)),
            "extrapolation": curve.extrapolation,
            "points": [
                {
                    "co": [float(point.co.x), float(point.co.y)],
                    "handle_left": [float(point.handle_left.x), float(point.handle_left.y)],
                    "handle_right": [float(point.handle_right.x), float(point.handle_right.y)],
                    "interpolation": point.interpolation,
                    "easing": point.easing,
                    "handle_left_type": point.handle_left_type,
                    "handle_right_type": point.handle_right_type,
                    "type": point.type,
                    "back": float(point.back),
                    "amplitude": float(point.amplitude),
                    "period": float(point.period),
                }
                for point in curve.keyframe_points
            ],
        }
    return {
        "name": action.name,
        "frame_range": [float(value) for value in action.frame_range],
        "curves": curves,
    }


def source_action_signatures(source_path: Path) -> dict[str, dict[str, object]]:
    bpy.ops.wm.open_mainfile(filepath=str(source_path), load_ui=False)
    actions: dict[str, bpy.types.Action] = {}
    for action in bpy.data.actions:
        role = wing_role(action.name)
        if role is None:
            continue
        ensure(role not in actions, f"{source_path.name}: duplicate {role} wing Actions")
        actions[role] = action
    ensure(set(actions) == {"left", "right"}, f"{source_path.name}: incomplete wing Action pair")
    return {role: action_signature(action) for role, action in actions.items()}


def object_signature(obj: bpy.types.Object) -> dict[str, object]:
    return {
        "matrix_world": [float(value) for row in obj.matrix_world for value in row],
        "location": [float(value) for value in obj.location],
        "rotation_euler": [float(value) for value in obj.rotation_euler],
        "scale": [float(value) for value in obj.scale],
        "parent": obj.parent.name if obj.parent else None,
        "action": obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None,
    }


def max_transform_difference(first: dict[str, object], second: dict[str, object]) -> float:
    return max(
        abs(left - right)
        for key in ("matrix_world", "location", "rotation_euler", "scale")
        for left, right in zip(first[key], second[key])
    )


def max_wing_non_z_difference(first: dict[str, object], second: dict[str, object]) -> float:
    differences = [
        abs(left - right)
        for key in ("location", "scale")
        for left, right in zip(first[key], second[key])
    ]
    differences.extend(
        abs(first["rotation_euler"][axis] - second["rotation_euler"][axis])
        for axis in (0, 1)
    )
    return max(differences)


def scene_snapshot(
    scene: bpy.types.Scene,
    frames: tuple[int, ...],
    predicate,
) -> dict[int, dict[str, dict[str, object]]]:
    if bpy.context.window:
        bpy.context.window.scene = scene
    objects = sorted([obj for obj in scene.objects if predicate(obj)], key=lambda obj: obj.name)
    result: dict[int, dict[str, dict[str, object]]] = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        result[frame] = {obj.name: object_signature(obj) for obj in objects}
    return result


def display_wings(scene: bpy.types.Scene) -> dict[str, bpy.types.Object]:
    wings = {role: scene.objects.get(name) for role, name in WING_NAMES.items()}
    ensure(all(wings.values()), f"{scene.name}: display wing objects missing")
    return wings


def mesh_centroid_world(obj: bpy.types.Object) -> Vector:
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    return sum(points, Vector()) / len(points)


def validate_full_frame_wing_geometry(
    scene: bpy.types.Scene,
    wings: dict[str, bpy.types.Object],
) -> dict[str, object]:
    body = scene.objects.get(BODY_NAME)
    ensure(body is not None and body.type == "MESH", "Display body mesh missing")
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    body_center = mesh_centroid_world(body)
    reference_vectors = {
        role: mesh_centroid_world(wing) - body_center
        for role, wing in wings.items()
    }
    reference_directions = {
        role: vector.normalized()
        for role, vector in reference_vectors.items()
    }
    reference_projections = {
        role: vector.length
        for role, vector in reference_vectors.items()
    }

    z_samples = {"left": [], "right": []}
    side_ratios = {"left": [], "right": []}
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        body_center = mesh_centroid_world(body)
        for role, wing in wings.items():
            z_degrees = math.degrees(float(wing.rotation_euler.z))
            z_samples[role].append((frame, z_degrees))
            projection = (mesh_centroid_world(wing) - body_center).dot(reference_directions[role])
            side_ratios[role].append((frame, projection / reference_projections[role]))

    for frame, value in z_samples["left"]:
        ensure(0.0 < value < 90.0, f"Left wing crossed anatomical side at frame {frame}: {value}°")
    for frame, value in z_samples["right"]:
        ensure(-90.0 < value < 0.0, f"Right wing crossed anatomical side at frame {frame}: {value}°")
    for role in ("left", "right"):
        minimum_ratio, minimum_frame = min((ratio, frame) for frame, ratio in side_ratios[role])
        ensure(
            minimum_ratio >= 0.7,
            f"{role} wing centroid approached/crossed the body side at frame {minimum_frame}: ratio={minimum_ratio}",
        )

    return {
        "sampled_frame_count": scene.frame_end - scene.frame_start + 1,
        "z_range_degrees": {
            role: [
                min(value for _, value in z_samples[role]),
                max(value for _, value in z_samples[role]),
            ]
            for role in ("left", "right")
        },
        "minimum_anatomical_side_projection_ratio": {
            role: min(ratio for _, ratio in side_ratios[role])
            for role in ("left", "right")
        },
        "wings_stay_on_anatomical_sides": True,
    }


def compare_rebased_action(
    source: dict[str, object],
    master: dict[str, object],
    output: bpy.types.Action,
) -> dict[str, object]:
    output_signature = action_signature(output)
    output_curves = output_signature["curves"]
    source_curves = source["curves"]
    master_curves = master["curves"]
    ensure(set(output_curves) == set(master_curves), f"{output.name}: FCurve channel set differs from Master")
    ensure(Z_CURVE_KEY in source_curves and Z_CURVE_KEY in output_curves, f"{output.name}: Euler Z FCurve missing")

    non_z_keys = set(master_curves) - {Z_CURVE_KEY}
    for key in non_z_keys:
        ensure(output_curves[key] == master_curves[key], f"{output.name}: Master non-Z FCurve changed: {key}")

    source_curve = source_curves[Z_CURVE_KEY]
    output_curve = output_curves[Z_CURVE_KEY]
    source_points = source_curve["points"]
    output_points = output_curve["points"]
    ensure(len(source_points) == len(output_points), f"{output.name}: Z keyframe count differs from source")
    source_base = source_curve["baseline"]
    output_base = output_curve["baseline"]
    value_scale = float(output.get("z_retarget_scale", 0.0))
    ensure(0.0 < value_scale < 1.0, f"{output.name}: invalid Z retarget scale")
    ensure(source_curve["extrapolation"] == output_curve["extrapolation"], f"{output.name}: Z extrapolation changed")
    for source_point, output_point in zip(source_points, output_points):
        ensure(abs(source_point["co"][0] - output_point["co"][0]) <= 1e-6, f"{output.name}: Z keyframe frame changed")
        ensure(
            abs((source_point["co"][1] - source_base) * value_scale - (output_point["co"][1] - output_base)) <= 1e-5,
            f"{output.name}: Z keyframe affine mapping changed",
        )
        ensure(
            abs(source_point["handle_left"][0] - output_point["handle_left"][0]) <= 1e-5
            and abs(source_point["handle_right"][0] - output_point["handle_right"][0]) <= 1e-5,
            f"{output.name}: Z handle time changed",
        )
        ensure(
            abs((source_point["handle_left"][1] - source_base) * value_scale - (output_point["handle_left"][1] - output_base)) <= 1e-5
            and abs((source_point["handle_right"][1] - source_base) * value_scale - (output_point["handle_right"][1] - output_base)) <= 1e-5,
            f"{output.name}: Z handle affine mapping changed",
        )
        for property_name in (
            "interpolation",
            "easing",
            "handle_left_type",
            "handle_right_type",
            "type",
            "back",
            "amplitude",
            "period",
        ):
            ensure(
                source_point[property_name] == output_point[property_name],
                f"{output.name}: Z metadata changed: {property_name}",
            )
    return {
        "source_action": source["name"],
        "master_action": master["name"],
        "output_action": output.name,
        "copied_channel": Z_CURVE_KEY,
        "z_keyframe_point_count": len(output_points),
        "z_retarget_scale": value_scale,
        "z_target_range_degrees": [
            math.degrees(min(point["co"][1] for point in output_points)),
            math.degrees(max(point["co"][1] for point in output_points)),
        ],
        "master_non_z_curve_count": len(non_z_keys),
        "master_non_z_keyframe_point_count": sum(
            len(output_curves[key]["points"])
            for key in non_z_keys
        ),
        "source_z_curve_shape_and_timing_preserved": True,
        "source_z_handle_timing_and_easing_preserved": True,
        "master_non_z_curves_preserved": True,
    }


def validate_one(
    variant_index: int,
    source_path: Path,
    output_path: Path,
    build_item: dict[str, object],
    master_frames: tuple[int, ...],
    master_default_frame: int,
    master_artist_snapshot: dict[int, dict[str, dict[str, object]]],
    master_source_snapshot: dict[int, dict[str, dict[str, object]]],
    source_signatures: dict[str, dict[str, object]],
    master_action_signatures: dict[str, dict[str, object]],
) -> dict[str, object]:
    bpy.ops.wm.open_mainfile(filepath=str(output_path), load_ui=False)
    artist = bpy.data.scenes.get("ARTIST_EDIT")
    source_scene = bpy.data.scenes.get("SOURCE_REFERENCE")
    ensure(artist is not None and source_scene is not None, f"{output_path.name}: scene entries missing")
    ensure(artist.frame_start == master_frames[0] and artist.frame_end == master_frames[-1], f"{output_path.name}: frame range changed")
    ensure(artist.frame_current == master_default_frame, f"{output_path.name}: default frame changed")
    ensure(artist.get("wing_keyframe_source_file") == relative(source_path), f"{output_path.name}: source metadata mismatch")
    ensure(artist.get("follow_path_controller_applied") is False, f"{output_path.name}: path controller policy mismatch")
    ensure(artist.get("copied_animation_channel") == Z_CURVE_KEY, f"{output_path.name}: copied channel metadata mismatch")
    ensure(artist.get("master_non_z_wing_curves_preserved") is True, f"{output_path.name}: non-Z preservation metadata missing")
    ensure(
        abs(float(artist.get("z_safe_half_amplitude_degrees", 0.0)) - EXPECTED_SAFE_HALF_AMPLITUDE_DEGREES) <= 1e-6,
        f"{output_path.name}: safe Z amplitude metadata mismatch",
    )

    output_artist_snapshot = scene_snapshot(
        artist,
        master_frames,
        lambda obj: obj.name.startswith("展示_") or obj.name.startswith("DISPLAY_"),
    )
    output_source_snapshot = scene_snapshot(
        source_scene,
        master_frames,
        lambda obj: obj.name.startswith("源_"),
    )
    ensure(set(output_artist_snapshot[master_frames[0]]) == set(master_artist_snapshot[master_frames[0]]), f"{output_path.name}: display object set changed")
    ensure(set(output_source_snapshot[master_frames[0]]) == set(master_source_snapshot[master_frames[0]]), f"{output_path.name}: source object set changed")

    wing_names = set(WING_NAMES.values())
    for frame in master_frames:
        for name, master_signature in master_artist_snapshot[frame].items():
            if name in wing_names:
                continue
            ensure(
                max_transform_difference(master_signature, output_artist_snapshot[frame][name]) <= 1e-6,
                f"{output_path.name}: non-wing transform changed: {name}, frame {frame}",
            )
        for name, master_signature in master_source_snapshot[frame].items():
            output_signature = output_source_snapshot[frame][name]
            ensure(
                max_transform_difference(master_signature, output_signature) <= 1e-6,
                f"{output_path.name}: SOURCE_REFERENCE transform changed: {name}, frame {frame}",
            )
            ensure(master_signature["action"] == output_signature["action"], f"{output_path.name}: SOURCE_REFERENCE Action changed: {name}")

    wings = display_wings(artist)
    action_reports: dict[str, object] = {}
    for role, wing in wings.items():
        master_frame_one = master_artist_snapshot[1][wing.name]
        output_frame_one = output_artist_snapshot[1][wing.name]
        ensure(max_transform_difference(master_frame_one, output_frame_one) <= 1e-6, f"{output_path.name}: frame-1 wing pose changed: {wing.name}")
        ensure(master_frame_one["parent"] == output_frame_one["parent"], f"{output_path.name}: wing parent changed: {wing.name}")
        for frame in master_frames:
            ensure(
                max_wing_non_z_difference(
                    master_artist_snapshot[frame][wing.name],
                    output_artist_snapshot[frame][wing.name],
                )
                <= 1e-6,
                f"{output_path.name}: wing non-Z transform changed: {wing.name}, frame {frame}",
            )
        ensure(wing.animation_data and wing.animation_data.action, f"{output_path.name}: wing Action missing: {wing.name}")
        action = wing.animation_data.action
        ensure(action.name == f"MYBUTTERFLY_FOLLOW_PATH_{variant_index}_WING_KEYS_{role.upper()}", f"{output_path.name}: wrong wing Action: {role}")
        ensure(action.get("animation_source_file") == relative(source_path), f"{output_path.name}: Action source mismatch: {role}")
        ensure(action.get("animation_source_role") == role, f"{output_path.name}: Action role mismatch: {role}")
        ensure(action.get("copied_channel") == Z_CURVE_KEY, f"{output_path.name}: Action copied channel mismatch: {role}")
        ensure(
            abs(float(action.get("z_safe_half_amplitude_degrees", 0.0)) - EXPECTED_SAFE_HALF_AMPLITUDE_DEGREES) <= 1e-6,
            f"{output_path.name}: Action safe Z amplitude mismatch: {role}",
        )
        action_reports[role] = compare_rebased_action(
            source_signatures[role],
            master_action_signatures[role],
            action,
        )

    geometry_report = validate_full_frame_wing_geometry(artist, wings)

    animated_display = [
        obj.name
        for obj in artist.objects
        if obj.name.startswith("展示_") and obj.animation_data and obj.animation_data.action
    ]
    ensure(set(animated_display) == wing_names, f"{output_path.name}: non-wing display animation introduced")
    ensure(build_item["output"] == relative(output_path), f"{output_path.name}: build report output mismatch")
    ensure(build_item["output_sha256"] == sha256_file(output_path), f"{output_path.name}: output hash mismatch")

    return {
        "variant": variant_index,
        "file": relative(output_path),
        "source": relative(source_path),
        "output_sha256": sha256_file(output_path),
        "default_scene": artist.name,
        "default_frame": master_default_frame,
        "frame_range": [artist.frame_start, artist.frame_end],
        "display_wings": WING_NAMES,
        "action_reports": action_reports,
        "master_non_wing_transforms_preserved": True,
        "master_wing_frame_one_transforms_preserved": True,
        "copied_channels": [Z_CURVE_KEY],
        "master_non_z_wing_curves_preserved": True,
        "full_frame_geometry": geometry_report,
        "source_reference_preserved": True,
        "follow_path_controller_applied": False,
        "result": "pass",
    }


def main() -> None:
    ensure(BUILD_REPORT_PATH.is_file(), f"Build report missing: {BUILD_REPORT_PATH}")
    build_payload = json.loads(BUILD_REPORT_PATH.read_text(encoding="utf-8"))
    build_by_output = {item["output"]: item for item in build_payload["outputs"]}
    ensure(len(build_by_output) == 2, "Build report must contain two outputs")

    master_hash = sha256_file(MASTER_PATH)
    source_paths = [SOURCE_DIR / source_name for _, source_name, _ in VARIANTS]
    source_hashes = {relative(path): sha256_file(path) for path in source_paths}
    for item in build_payload["outputs"]:
        ensure(item["master_sha256"] == master_hash, "Master hash differs from build input")
        ensure(item["source_sha256"] == source_hashes[item["source"]], f"Source hash differs: {item['source']}")

    signatures = {
        source_path.name: source_action_signatures(source_path)
        for source_path in source_paths
    }
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_PATH), load_ui=False)
    master_artist = bpy.data.scenes.get("ARTIST_EDIT")
    master_source = bpy.data.scenes.get("SOURCE_REFERENCE")
    ensure(master_artist is not None and master_source is not None, "Master scene entries missing")
    master_wings = display_wings(master_artist)
    master_action_signatures = {}
    for role, wing in master_wings.items():
        ensure(wing.animation_data and wing.animation_data.action, f"Master wing Action missing: {wing.name}")
        master_action_signatures[role] = action_signature(wing.animation_data.action)
    master_frames = (master_artist.frame_start, min(45, master_artist.frame_end), master_artist.frame_end)
    master_default_frame = master_artist.frame_current
    master_artist_snapshot = scene_snapshot(
        master_artist,
        master_frames,
        lambda obj: obj.name.startswith("展示_") or obj.name.startswith("DISPLAY_"),
    )
    master_source_snapshot = scene_snapshot(
        master_source,
        master_frames,
        lambda obj: obj.name.startswith("源_"),
    )

    reports = []
    for variant_index, source_name, output_name in VARIANTS:
        source_path = SOURCE_DIR / source_name
        output_path = OUTPUT_DIR / output_name
        ensure(output_path.is_file(), f"Output missing: {output_path}")
        reports.append(
            validate_one(
                variant_index,
                source_path,
                output_path,
                build_by_output[relative(output_path)],
                master_frames,
                master_default_frame,
                master_artist_snapshot,
                master_source_snapshot,
                signatures[source_name],
                master_action_signatures,
            )
        )

    ensure(sha256_file(MASTER_PATH) == master_hash, "Master changed during validation")
    ensure(
        {relative(path): sha256_file(path) for path in source_paths} == source_hashes,
        "A Follow Path source changed during validation",
    )
    source_wing_curves_identical = all(
        signatures[source_paths[0].name][role]["curves"]
        == signatures[source_paths[1].name][role]["curves"]
        for role in ("left", "right")
    )
    payload = {
        "asset": "Butterfly",
        "variant": "mybutterfly_follow_path_wing_key_replacement",
        "validated_count": len(reports),
        "master": relative(MASTER_PATH),
        "master_sha256": master_hash,
        "master_preserved": True,
        "source_sha256": source_hashes,
        "sources_preserved": True,
        "source_wing_curve_data_identical_between_variants": source_wing_curves_identical,
        "validated": reports,
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MYBUTTERFLY_FOLLOW_PATH_WING_VALIDATION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
