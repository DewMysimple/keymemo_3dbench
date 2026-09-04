from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import bpy


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = WORKBENCH_ROOT / "models" / "Butterfly" / "scenes" / "follow_path"
OUTPUT_DIR = SOURCE_DIR
STAGING_DIR = WORKBENCH_ROOT / "generated" / "butterfly_follow_path_rotation_only" / "staging"
REPORT_PATH = WORKBENCH_ROOT / "reports" / "butterfly-follow-path-rotation-only.json"

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


def object_action(obj: bpy.types.Object) -> bpy.types.Action | None:
    return obj.animation_data.action if obj.animation_data else None


def wing_role(obj: bpy.types.Object) -> str | None:
    name = obj.name.lower()
    if "left_wing" in name:
        return "left"
    if "right_wing" in name:
        return "right"
    return None


def clear_non_rotation_curves(action: bpy.types.Action) -> dict[str, int]:
    removed = 0
    retained = 0
    for collection, curve in list(action_curve_handles(action)):
        if curve.data_path in {"rotation_euler", "rotation_quaternion", "rotation_axis_angle"}:
            retained += 1
        else:
            collection.remove(curve)
            removed += 1
    return {"removed": removed, "retained_rotation": retained}


def remove_orphan_actions() -> list[str]:
    removed: list[str] = []
    for action in list(bpy.data.actions):
        if action.users == 0 and not action.use_fake_user:
            removed.append(action.name)
            bpy.data.actions.remove(action)
    return removed


def remove_cleared_actions(action_names: set[str]) -> list[str]:
    removed: list[str] = []
    for name in sorted(action_names):
        action = bpy.data.actions.get(name)
        if action is None:
            continue
        removed.append(name)
        bpy.data.actions.remove(action, do_unlink=True)
    return removed


def remove_lights() -> list[str]:
    light_objects = [obj for obj in bpy.data.objects if obj.type == "LIGHT"]
    removed_names = [obj.name for obj in light_objects]
    for obj in light_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for light_data in list(bpy.data.lights):
        if light_data.users == 0 and not light_data.use_fake_user:
            bpy.data.lights.remove(light_data)
    return removed_names


def remove_motion_paths() -> list[str]:
    path_objects = [obj for obj in bpy.data.objects if obj.motion_path]
    removed_names = [obj.name for obj in path_objects]
    for scene in bpy.data.scenes:
        if bpy.context.window:
            bpy.context.window.scene = scene
            bpy.context.window.view_layer = scene.view_layers[0]
        view_layer = bpy.context.view_layer
        bpy.ops.object.select_all(action="DESELECT")
        scene_path_objects = [
            obj
            for obj in scene.objects
            if obj.motion_path and obj.name in view_layer.objects
        ]
        for obj in scene_path_objects:
            obj.select_set(True)
        if scene_path_objects:
            view_layer.objects.active = scene_path_objects[0]
            bpy.ops.object.paths_clear(only_selected=True)
    if bpy.context.window:
        bpy.context.window.scene = bpy.data.scenes.get("ARTIST_EDIT") or bpy.context.scene
    ensure(not [obj for obj in bpy.data.objects if obj.motion_path], "Motion Path data remains")
    return removed_names


def remove_all_non_wing_animation() -> dict[str, object]:
    cleared_objects: list[str] = []
    cleared_actions: set[str] = set()
    retained_wing_actions: dict[str, str] = {}
    removed_curves = 0
    retained_rotation_curves = 0

    for obj in list(bpy.data.objects):
        action = object_action(obj)
        role = wing_role(obj)
        if action is None:
            continue
        if role is None:
            cleared_actions.add(action.name)
            obj.animation_data_clear()
            cleared_objects.append(obj.name)
            continue
        counts = clear_non_rotation_curves(action)
        removed_curves += counts["removed"]
        retained_rotation_curves += counts["retained_rotation"]
        retained_wing_actions[obj.name] = action.name

    for scene in bpy.data.scenes:
        if scene.animation_data:
            if scene.animation_data.action:
                cleared_actions.add(scene.animation_data.action.name)
            scene.animation_data_clear()

    removed_cleared = remove_cleared_actions(cleared_actions)
    removed_orphan = remove_orphan_actions()
    return {
        "cleared_non_wing_animation_objects": sorted(cleared_objects),
        "cleared_non_wing_action_names": sorted(cleared_actions),
        "removed_non_rotation_fcurve_count": removed_curves,
        "retained_rotation_fcurve_count": retained_rotation_curves,
        "retained_wing_actions": retained_wing_actions,
        "removed_cleared_action_names": sorted(removed_cleared),
        "removed_orphan_action_names": sorted(removed_orphan),
    }


def add_metadata(source_path: Path, output_path: Path, variant: int, report: dict[str, object]) -> None:
    scene = bpy.context.scene
    scene["rotation_only_no_light_no_path_version"] = True
    scene["source_file"] = relative(source_path)
    scene["output_file"] = relative(output_path)
    scene["variant"] = variant
    scene["lights_removed"] = True
    scene["path_animation_removed"] = True
    scene["motion_path_removed"] = True
    scene["non_rotation_animation_removed"] = True
    scene["rotation_keyframes_preserved_only"] = True
    scene["build_report"] = json.dumps(report, ensure_ascii=False, sort_keys=True)

    notes_name = f"BUTTERFLY_ROTATION_ONLY_NO_LIGHT_NO_PATH_NOTES_{variant}"
    notes = bpy.data.texts.get(notes_name) or bpy.data.texts.new(notes_name)
    notes.clear()
    notes.write(
        f"来源：{relative(source_path)}\n"
        f"输出：{relative(output_path)}\n"
        "移除全部灯光对象。\n"
        "清除路径控制层级及其他非翅膀对象的动画，并删除所有 Motion Path 可视化缓存。\n"
        "左右翅仅保留 rotation_euler / rotation_quaternion / rotation_axis_angle 旋转关键帧；\n"
        "Location、Scale 及其他非旋转关键帧已移除。\n"
    )


def build_one(variant: int, source_name: str, output_name: str) -> dict[str, object]:
    source_path = SOURCE_DIR / source_name
    output_path = OUTPUT_DIR / output_name
    ensure(source_path.is_file(), f"Source file missing: {source_path}")
    source_hash = sha256_file(source_path)
    ensure(source_hash, "Source hash unavailable")

    bpy.ops.wm.open_mainfile(filepath=str(source_path), load_ui=False)
    ensure(len(bpy.data.scenes) >= 1, f"{source_name}: no scenes")
    source_lights = [obj.name for obj in bpy.data.objects if obj.type == "LIGHT"]
    pre_actions = {
        action.name: [
            {"data_path": curve.data_path, "array_index": curve.array_index, "keyframe_count": len(curve.keyframe_points)}
            for curve in action_fcurves(action)
        ]
        for action in bpy.data.actions
    }
    animation_report = remove_all_non_wing_animation()
    removed_lights = remove_lights()
    removed_motion_paths = remove_motion_paths()
    ensure(set(removed_lights) == set(source_lights), f"{source_name}: light removal mismatch")
    ensure(not [obj for obj in bpy.data.objects if obj.type == "LIGHT"], f"{source_name}: lights remain")
    add_metadata(
        source_path,
        output_path,
        variant,
        {
            "source": relative(source_path),
            "pre_actions": pre_actions,
            "animation": animation_report,
            "removed_light_objects": removed_lights,
            "removed_motion_path_objects": removed_motion_paths,
        },
    )

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    staging_path = STAGING_DIR / output_name
    if staging_path.exists():
        staging_path.unlink()
    bpy.ops.wm.save_as_mainfile(filepath=str(staging_path), check_existing=False)
    ensure(staging_path.is_file(), f"Staging file was not created: {staging_path}")
    bpy.ops.wm.open_mainfile(filepath=str(staging_path), load_ui=False)
    ensure(not [obj for obj in bpy.data.objects if obj.type == "LIGHT"], f"{output_name}: light remained after reopen")
    ensure(not [obj for obj in bpy.data.objects if obj.motion_path], f"{output_name}: motion path remained after reopen")
    ensure(all(not object_action(obj) for obj in bpy.data.objects if wing_role(obj) is None), f"{output_name}: non-wing action remained")
    ensure(all(
        curve.data_path in {"rotation_euler", "rotation_quaternion", "rotation_axis_angle"}
        for obj in bpy.data.objects
        if wing_role(obj) is not None and object_action(obj)
        for curve in action_fcurves(object_action(obj))
    ), f"{output_name}: non-rotation wing curve remained")
    os.replace(staging_path, output_path)

    output_hash = sha256_file(output_path)
    return {
        "variant": variant,
        "source": relative(source_path),
        "output": relative(output_path),
        "source_sha256": source_hash,
        "output_sha256": output_hash,
        "removed_light_objects": removed_lights,
        "removed_motion_path_objects": removed_motion_paths,
        "path_animation_removed": True,
        "motion_path_removed": True,
        "non_rotation_animation_removed": True,
        "rotation_keyframes_preserved_only": True,
        "pre_actions": pre_actions,
        "animation": animation_report,
        "result": "pass",
    }


def main() -> None:
    reports = [build_one(*variant) for variant in VARIANTS]
    payload = {
        "asset": "Butterfly",
        "variant": "follow_path_rotation_only_no_light_no_path",
        "policy": "从每份 Follow Path 源文件生成独立副本；删除所有灯光、路径/层级控制动画和 Motion Path 缓存及非旋转关键帧，仅保留两翼旋转关键帧；源文件不覆盖",
        "outputs": reports,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_FOLLOW_PATH_ROTATION_ONLY=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
