from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import bpy


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
SCENES_ROOT = WORKBENCH_ROOT / "models" / "Butterfly" / "scenes"
MASTER_PATH = SCENES_ROOT / "MyWork" / "MyButterfly_Master.blend"
SOURCE_DIR = SCENES_ROOT / "follow_path"
OUTPUT_DIR = SCENES_ROOT / "MyWork"
STAGING_DIR = WORKBENCH_ROOT / "generated" / "mybutterfly_follow_path_wing_variants" / "staging"
REPORT_PATH = WORKBENCH_ROOT / "reports" / "mybutterfly-follow-path-wing-variants.json"

LEFT_WING = "展示_Butterfly_Master_源_FBX_01_03_BUTTERFLY_IDLE_1_LEFT_WING_"
RIGHT_WING = "展示_Butterfly_Master_源_FBX_01_04_BUTTERFLY_IDLE_1_RIGHT_WING_"
WING_NAMES = {"left": LEFT_WING, "right": RIGHT_WING}
SAFE_HALF_AMPLITUDE_DEGREES = 32.0

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


def append_source_wing_actions(source_path: Path) -> tuple[dict[str, bpy.types.Action], list[bpy.types.Action]]:
    before = set(bpy.data.actions)
    with bpy.data.libraries.load(str(source_path), link=False) as (data_from, data_to):
        names = [name for name in data_from.actions if wing_role(name) is not None]
        ensure(len(names) == 2, f"{source_path.name}: expected two wing Actions, found {names}")
        data_to.actions = names

    loaded = [action for action in data_to.actions if action is not None]
    ensure(len(loaded) == 2, f"{source_path.name}: failed to append both wing Actions")
    ensure(all(action not in before for action in loaded), f"{source_path.name}: appended Action identity collision")
    actions: dict[str, bpy.types.Action] = {}
    for action in loaded:
        role = wing_role(action.name)
        ensure(role is not None and role not in actions, f"{source_path.name}: ambiguous wing Action {action.name}")
        actions[role] = action
    ensure(set(actions) == {"left", "right"}, f"{source_path.name}: incomplete wing Action pair")
    return actions, loaded


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


def display_wings(scene: bpy.types.Scene) -> dict[str, bpy.types.Object]:
    wings = {role: scene.objects.get(name) for role, name in WING_NAMES.items()}
    ensure(all(wings.values()), "MyButterfly Master display wings are missing")
    ensure(all(obj.type == "MESH" for obj in wings.values()), "MyButterfly display wing type changed")
    return wings


def find_curve(action: bpy.types.Action, data_path: str, array_index: int) -> bpy.types.FCurve:
    matches = [
        curve
        for curve in action_fcurves(action)
        if curve.data_path == data_path and curve.array_index == array_index
    ]
    ensure(len(matches) == 1, f"{action.name}: expected one {data_path}[{array_index}] FCurve")
    return matches[0]


def replace_curve_points(
    target_curve: bpy.types.FCurve,
    source_curve: bpy.types.FCurve,
    target_baseline: float,
) -> dict[str, object]:
    source_baseline = float(source_curve.evaluate(1.0))
    source_extrapolation = source_curve.extrapolation
    source_points = [
        {
            "co": (float(point.co.x), float(point.co.y)),
            "handle_left": (float(point.handle_left.x), float(point.handle_left.y)),
            "handle_right": (float(point.handle_right.x), float(point.handle_right.y)),
            "interpolation": point.interpolation,
            "easing": point.easing,
            "type": point.type,
            "back": float(point.back),
            "amplitude": float(point.amplitude),
            "period": float(point.period),
            "handle_left_type": point.handle_left_type,
            "handle_right_type": point.handle_right_type,
        }
        for point in source_curve.keyframe_points
    ]
    source_values = [point["co"][1] for point in source_points]
    source_max_delta = max(abs(value - source_baseline) for value in source_values)
    ensure(source_max_delta > 1e-9, f"{source_curve.data_path}[{source_curve.array_index}] has no motion")
    value_scale = math.radians(SAFE_HALF_AMPLITUDE_DEGREES) / source_max_delta
    while target_curve.keyframe_points:
        target_curve.keyframe_points.remove(target_curve.keyframe_points[-1], fast=True)

    for source_point in source_points:
        target_curve.keyframe_points.insert(
            source_point["co"][0],
            target_baseline + (source_point["co"][1] - source_baseline) * value_scale,
            options={"FAST"},
        )

    for source_point, target_point in zip(source_points, target_curve.keyframe_points):
        target_point.interpolation = source_point["interpolation"]
        target_point.easing = source_point["easing"]
        target_point.type = source_point["type"]
        target_point.back = source_point["back"]
        target_point.amplitude = source_point["amplitude"]
        target_point.period = source_point["period"]
        target_point.handle_left_type = source_point["handle_left_type"]
        target_point.handle_right_type = source_point["handle_right_type"]
        target_point.handle_left = (
            source_point["handle_left"][0],
            target_baseline + (source_point["handle_left"][1] - source_baseline) * value_scale,
        )
        target_point.handle_right = (
            source_point["handle_right"][0],
            target_baseline + (source_point["handle_right"][1] - source_baseline) * value_scale,
        )
    target_curve.extrapolation = source_extrapolation
    target_curve.update()
    target_values = [float(point.co.y) for point in target_curve.keyframe_points]
    return {
        "source_baseline": source_baseline,
        "target_baseline": target_baseline,
        "value_scale": value_scale,
        "source_range": [min(source_values), max(source_values)],
        "target_range": [min(target_values), max(target_values)],
        "safe_half_amplitude_degrees": SAFE_HALF_AMPLITUDE_DEGREES,
    }


def make_master_pose_action(
    master_action: bpy.types.Action,
    source_action: bpy.types.Action,
    target_baseline: dict[str, tuple[float, ...]],
    role: str,
    variant_index: int,
    source_path: Path,
) -> bpy.types.Action:
    action = master_action.copy()
    action.name = f"MYBUTTERFLY_FOLLOW_PATH_{variant_index}_WING_KEYS_{role.upper()}"
    source_z = find_curve(source_action, "rotation_euler", 2)
    target_z = find_curve(action, "rotation_euler", 2)
    target_z_baseline = target_baseline["rotation_euler"][2]
    retarget = replace_curve_points(target_z, source_z, target_z_baseline)

    action["animation_source_file"] = relative(source_path)
    action["animation_source_role"] = role
    action["master_base_file"] = relative(MASTER_PATH)
    action["replacement_policy"] = "仅替换 rotation_euler[2]；来源 Z 曲线仿射缩放到 Master 解剖侧安全区间；其余 8 条 FCurve 保持 Master 原值"
    action["copied_channel"] = "rotation_euler[2]"
    action["z_retarget_scale"] = retarget["value_scale"]
    action["z_retarget_source_range"] = retarget["source_range"]
    action["z_retarget_target_range"] = retarget["target_range"]
    action["z_safe_half_amplitude_degrees"] = SAFE_HALF_AMPLITUDE_DEGREES
    action["follow_path_controller_applied"] = False
    return action


def assign_action(obj: bpy.types.Object, action: bpy.types.Action) -> None:
    obj.animation_data_clear()
    obj.animation_data_create()
    obj.animation_data.action = action
    slots = list(getattr(action, "slots", []))
    if slots:
        obj.animation_data.action_slot = slots[0]


def write_notes(source_path: Path, output_path: Path, actions: dict[str, bpy.types.Action]) -> None:
    name = "MyButterfly_FollowPath_翅膀关键帧替换说明"
    old = bpy.data.texts.get(name)
    if old is not None:
        bpy.data.texts.remove(old)
    text = bpy.data.texts.new(name)
    text.write(
        "MyButterfly Follow Path 翅膀关键帧替换版本\n\n"
        f"Master 原版：{MASTER_PATH.name}\n"
        f"翅膀动作来源：{source_path.name}\n"
        f"当前输出：{output_path.name}\n"
        "仅替换 ARTIST_EDIT 展示层左右翼 rotation_euler[2]（局部 Euler Z）关键帧。\n"
        "location XYZ、rotation_euler X/Y、scale XYZ 共 8 条曲线保持 Master 原值，因此不会带入来源位置、缩放、路径位移或路径转向。\n"
        f"来源 Z 曲线以第 1 帧对齐 Master 的局部 Z 姿态，并缩放到基线正负 {SAFE_HALF_AMPLITUDE_DEGREES:.0f}° 的安全幅度，避免越过身体中线。\n"
        f"左翼 Action：{actions['left'].name}\n"
        f"右翼 Action：{actions['right'].name}\n"
    )


def build_one(variant_index: int, source_name: str, output_name: str) -> dict[str, object]:
    source_path = SOURCE_DIR / source_name
    output_path = OUTPUT_DIR / output_name
    staging_path = STAGING_DIR / output_name
    ensure(MASTER_PATH.is_file(), f"Master file missing: {MASTER_PATH}")
    ensure(source_path.is_file(), f"Follow Path source missing: {source_path}")
    ensure(output_path != MASTER_PATH and output_path != source_path, "Output would overwrite an input")

    master_hash = sha256_file(MASTER_PATH)
    source_hash = sha256_file(source_path)
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_PATH), load_ui=False)
    artist = bpy.data.scenes.get("ARTIST_EDIT")
    source_scene = bpy.data.scenes.get("SOURCE_REFERENCE")
    ensure(artist is not None and source_scene is not None, "Master scene entries are incomplete")
    if bpy.context.window:
        bpy.context.window.scene = artist

    original_frame = artist.frame_current
    frames = (artist.frame_start, min(45, artist.frame_end), artist.frame_end)
    before = display_snapshot(artist, frames)
    artist.frame_set(1)
    bpy.context.view_layer.update()
    wings = display_wings(artist)
    baselines = {
        role: {
            "location": tuple(obj.location),
            "rotation_euler": tuple(obj.rotation_euler),
            "scale": tuple(obj.scale),
        }
        for role, obj in wings.items()
    }
    source_actions, appended_actions = append_source_wing_actions(source_path)

    new_actions: dict[str, bpy.types.Action] = {}
    for role, obj in wings.items():
        ensure(obj.animation_data and obj.animation_data.action, f"Master wing Action missing: {obj.name}")
        action = make_master_pose_action(
            obj.animation_data.action,
            source_actions[role],
            baselines[role],
            role,
            variant_index,
            source_path,
        )
        assign_action(obj, action)
        new_actions[role] = action

    for action in appended_actions:
        if action.users == 0:
            bpy.data.actions.remove(action)

    after = display_snapshot(artist, frames)
    wing_object_names = set(WING_NAMES.values())
    ensure(set(before[frames[0]]) == set(after[frames[0]]), "Display object set changed")
    for frame in frames:
        for name in before[frame]:
            if name in wing_object_names:
                continue
            ensure(
                max_transform_difference(before[frame][name], after[frame][name]) <= 1e-6,
                f"Non-wing display transform changed: {name}, frame {frame}",
            )
    for name in wing_object_names:
        ensure(
            max_transform_difference(before[1][name], after[1][name]) <= 1e-6,
            f"Wing frame-1 transform changed: {name}",
        )
        ensure(before[1][name]["parent"] == after[1][name]["parent"], f"Wing parent changed: {name}")

    artist["document_type"] = "MyButterfly Follow Path 翅膀关键帧替换版本"
    artist["master_base_file"] = relative(MASTER_PATH)
    artist["wing_keyframe_source_file"] = relative(source_path)
    artist["wing_keyframe_replacement_only"] = True
    artist["copied_animation_channel"] = "rotation_euler[2]"
    artist["master_non_z_wing_curves_preserved"] = True
    artist["z_safe_half_amplitude_degrees"] = SAFE_HALF_AMPLITUDE_DEGREES
    artist["follow_path_controller_applied"] = False
    artist["source_reference_policy"] = "保持 MyButterfly Master 原始 SOURCE_REFERENCE"
    write_notes(source_path, output_path, new_actions)

    artist.frame_set(original_frame)
    if bpy.context.window:
        bpy.context.window.scene = artist
    bpy.context.view_layer.update()
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    if staging_path.exists():
        staging_path.unlink()
    action_names = {role: action.name for role, action in new_actions.items()}
    z_target_ranges = {
        role: list(action["z_retarget_target_range"])
        for role, action in new_actions.items()
    }
    z_retarget_scales = {
        role: float(action["z_retarget_scale"])
        for role, action in new_actions.items()
    }
    frame_range = [artist.frame_start, artist.frame_end]
    bpy.ops.wm.save_as_mainfile(filepath=str(staging_path), check_existing=False)
    ensure(staging_path.is_file(), f"Staging file was not created: {staging_path}")

    bpy.ops.wm.open_mainfile(filepath=str(staging_path), load_ui=False)
    saved_artist = bpy.data.scenes.get("ARTIST_EDIT")
    ensure(saved_artist is not None, f"Saved output cannot reopen: {output_name}")
    saved_wings = display_wings(saved_artist)
    ensure(
        {role: obj.animation_data.action.name for role, obj in saved_wings.items()}
        == action_names,
        f"Saved output lost wing Action bindings: {output_name}",
    )

    staging_path.replace(output_path)
    ensure(sha256_file(MASTER_PATH) == master_hash, "Master changed during build")
    ensure(sha256_file(source_path) == source_hash, f"Source changed during build: {source_name}")
    return {
        "variant": variant_index,
        "master": relative(MASTER_PATH),
        "master_sha256": master_hash,
        "source": relative(source_path),
        "source_sha256": source_hash,
        "output": relative(output_path),
        "output_sha256": sha256_file(output_path),
        "output_size": output_path.stat().st_size,
        "frame_range": frame_range,
        "default_frame": original_frame,
        "display_wings": WING_NAMES,
        "new_actions": action_names,
        "master_non_wing_transforms_preserved": True,
        "master_wing_frame_one_transforms_preserved": True,
        "copied_channels": ["rotation_euler[2]"],
        "master_non_z_wing_curves_preserved": True,
        "z_safe_half_amplitude_degrees": SAFE_HALF_AMPLITUDE_DEGREES,
        "z_target_ranges_radians": z_target_ranges,
        "z_retarget_scales": z_retarget_scales,
        "follow_path_controller_applied": False,
        "source_reference_preserved": True,
    }


def main() -> None:
    reports = [build_one(*variant) for variant in VARIANTS]
    payload = {
        "asset": "Butterfly",
        "variant": "mybutterfly_follow_path_wing_key_replacement",
        "policy": "以 MyButterfly_Master.blend 为不变原版，只替换 ARTIST_EDIT 左右翼 rotation_euler[2]（局部 Euler Z）关键帧；来源 Z 曲线以 Master 第 1 帧为基线仿射缩放到正负 32° 安全幅度，避免越过身体中线；其余 8 条曲线保持 Master 原值，不应用路径控制器",
        "outputs": reports,
    }
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MYBUTTERFLY_FOLLOW_PATH_WING_BUILD=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
