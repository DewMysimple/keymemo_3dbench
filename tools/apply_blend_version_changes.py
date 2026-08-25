#!/usr/bin/env python3
"""Apply registered, destructive changes to a copied Blender version.

The script is executed by Blender, not by the regular Python interpreter.  It
always opens the registered source file and saves a separate target file.  The
current supported change set freezes every non-camera animation at the final
artist frame while preserving all camera-related actions.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))

from portable_blend_assets import (
    PUBLIC_ASSETS,
    make_blend_assets_portable,
    public_asset_for,
)


WORKBENCH = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = WORKBENCH / "blender/Verminoble_Scene_Mirror_5_0.blend"
DEFAULT_OUTPUT = WORKBENCH / (
    "versions/no-animation/blender/Verminoble_Scene_Mirror_5_0_no_animation.blend"
)
DEFAULT_REPORT = WORKBENCH / "versions/no-animation/reports/version-preparation.json"
STATIC_FRAME = 3586
CAMERA_RIG_NAMES = {"WEB_CAMERA_PATH_RIG"}


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


def parse_script_args() -> argparse.Namespace:
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(
        description="Freeze all non-camera Blender animation at the final artist frame."
    )
    parser.add_argument("--source", type=Path, default=Path(os.environ.get("VERMINOBLE_BLEND_INPUT", str(DEFAULT_SOURCE))))
    parser.add_argument("--output", type=Path, default=Path(os.environ.get("VERMINOBLE_BLEND_OUTPUT", str(DEFAULT_OUTPUT))))
    parser.add_argument("--report", type=Path, default=Path(os.environ.get("VERMINOBLE_BLEND_VERSION_REPORT", str(DEFAULT_REPORT))))
    parser.add_argument("--variant", default="remove-all-non-camera-animation")
    parser.add_argument("--frame", type=int, default=STATIC_FRAME)
    return parser.parse_args(raw_args)


def is_camera_owner(obj: bpy.types.Object) -> bool:
    return (
        obj.type == "CAMERA"
        or obj.name in CAMERA_RIG_NAMES
        or obj.name.startswith("WEB_CAMERA_")
    )


def copy_value(value: Any) -> Any:
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    try:
        return tuple(value)
    except TypeError:
        return value


def custom_property_name(data_path: str) -> str | None:
    if not data_path.startswith("["):
        return None
    parsed = ast.literal_eval(data_path)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], str):
        return None
    return parsed[0]


def read_path(owner: Any, data_path: str) -> Any:
    property_name = custom_property_name(data_path)
    if property_name is not None:
        return owner[property_name]
    if data_path == 'key_blocks["SOURCE_WIND"].value':
        return owner.key_blocks["SOURCE_WIND"].value
    return getattr(owner, data_path)


def write_path(owner: Any, data_path: str, value: Any) -> None:
    property_name = custom_property_name(data_path)
    if property_name is not None:
        owner[property_name] = value
        return
    if data_path == 'key_blocks["SOURCE_WIND"].value':
        owner.key_blocks["SOURCE_WIND"].value = float(value)
        return
    setattr(owner, data_path, value)


def snapshot_action(owner: Any, action: bpy.types.Action) -> dict[str, Any]:
    snapshots: dict[str, Any] = {}
    for fcurve in action_fcurves(action):
        if fcurve.data_path in snapshots:
            continue
        try:
            snapshots[fcurve.data_path] = copy_value(read_path(owner, fcurve.data_path))
        except AttributeError:
            # Blender can share one action between an object and its shape keys.
            # Each owner only receives the channels that belong to it.
            continue
    return snapshots


def action_signature(action: bpy.types.Action | None) -> str | None:
    if action is None:
        return None
    payload = {
        "name": action.name,
        "frame_range": [round(value, 6) for value in action.frame_range],
        "curves": [],
    }
    for fcurve in action_fcurves(action):
        curve = {
            "data_path": fcurve.data_path,
            "array_index": fcurve.array_index,
            "keys": [
                [round(point.co.x, 6), round(point.co.y, 9), point.interpolation]
                for point in fcurve.keyframe_points
            ],
        }
        payload["curves"].append(curve)
    payload["curves"].sort(key=lambda item: (item["data_path"], item["array_index"]))
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest().upper()


def capture_public_asset_paths() -> dict[str, dict[str, Path]]:
    captured: dict[str, dict[str, Path]] = {"images": {}, "fonts": {}}
    public_root = PUBLIC_ASSETS.resolve()
    for image in bpy.data.images:
        if not image.filepath or image.packed_file is not None:
            continue
        absolute = Path(bpy.path.abspath(image.filepath)).resolve()
        public_path = public_asset_for(absolute)
        if public_path is None:
            try:
                absolute.relative_to(public_root)
            except ValueError:
                continue
            public_path = absolute
        captured["images"][image.name] = public_path.resolve()
    for font in bpy.data.fonts:
        if not font.filepath or font.filepath == "<builtin>" or font.packed_file is not None:
            continue
        absolute = Path(bpy.path.abspath(font.filepath)).resolve()
        public_path = public_asset_for(absolute)
        if public_path is None:
            try:
                absolute.relative_to(public_root)
            except ValueError:
                continue
            public_path = absolute
        captured["fonts"][font.name] = public_path.resolve()
    return captured


def rebase_captured_asset_paths(captured: dict[str, dict[str, Path]]) -> None:
    blend_parent = Path(bpy.data.filepath).resolve().parent
    for image_name, asset_path in captured["images"].items():
        image = bpy.data.images.get(image_name)
        if image is not None:
            relative = os.path.relpath(asset_path, blend_parent).replace("\\", "/")
            image.filepath = f"//{relative}"
    for font_name, asset_path in captured["fonts"].items():
        font = bpy.data.fonts.get(font_name)
        if font is not None:
            relative = os.path.relpath(asset_path, blend_parent).replace("\\", "/")
            font.filepath = f"//{relative}"


def protected_camera_signatures() -> dict[str, str | None]:
    signatures: dict[str, str | None] = {}
    for obj in bpy.data.objects:
        if not is_camera_owner(obj):
            continue
        action = obj.animation_data.action if obj.animation_data else None
        if action is not None:
            signatures[f"object:{obj.name}"] = action_signature(action)
    return signatures


def restore_scene_frames(frames: dict[str, int], default_scene_name: str | None) -> None:
    for scene in bpy.data.scenes:
        if scene.name in frames:
            scene.frame_set(frames[scene.name])
    if default_scene_name:
        default_scene = bpy.data.scenes.get(default_scene_name)
        if default_scene is not None and bpy.context.window is not None:
            bpy.context.window.scene = default_scene


def freeze_non_camera_animation(frame: int) -> dict[str, Any]:
    failures: list[str] = []
    default_scene_name = bpy.context.window.scene.name if bpy.context.window and bpy.context.window.scene else None
    original_frames = {scene.name: scene.frame_current for scene in bpy.data.scenes}
    evaluation_scene = bpy.data.scenes.get("ARTIST_EDIT") or bpy.context.scene
    evaluation_scene.frame_set(frame)
    bpy.context.view_layer.update()

    camera_before = protected_camera_signatures()
    cleared_object_actions: list[str] = []
    cleared_shape_key_actions: list[str] = []
    removed_action_names: set[str] = set()

    for obj in list(bpy.data.objects):
        animation_data = obj.animation_data
        action = animation_data.action if animation_data else None
        if action is None or is_camera_owner(obj):
            continue
        try:
            snapshots = snapshot_action(obj, action)
            for data_path, value in snapshots.items():
                write_path(obj, data_path, value)
        except (AttributeError, KeyError, TypeError, ValueError, SyntaxError) as exc:
            failures.append(f"{obj.name}: cannot freeze action {action.name}: {exc}")
            continue
        cleared_object_actions.append(action.name)
        removed_action_names.add(action.name)
        obj.animation_data_clear()

    for obj in list(bpy.data.objects):
        shape_keys = getattr(obj.data, "shape_keys", None)
        animation_data = shape_keys.animation_data if shape_keys else None
        action = animation_data.action if animation_data else None
        if action is None or is_camera_owner(obj):
            continue
        try:
            snapshots = snapshot_action(shape_keys, action)
            for data_path, value in snapshots.items():
                write_path(shape_keys, data_path, value)
        except (AttributeError, KeyError, TypeError, ValueError, SyntaxError) as exc:
            failures.append(f"{obj.name}: cannot freeze shape-key action {action.name}: {exc}")
            continue
        cleared_shape_key_actions.append(action.name)
        removed_action_names.add(action.name)
        shape_keys.animation_data_clear()

    for action_name in sorted(removed_action_names):
        action = bpy.data.actions.get(action_name)
        if action is None:
            continue
        if action.users:
            failures.append(f"Action {action_name} still has {action.users} users after clearing")
        else:
            bpy.data.actions.remove(action)

    bpy.context.view_layer.update()
    remaining_non_camera: list[str] = []
    for obj in bpy.data.objects:
        if is_camera_owner(obj):
            continue
        if obj.animation_data and (obj.animation_data.action or obj.animation_data.nla_tracks):
            remaining_non_camera.append(f"object:{obj.name}")
        shape_keys = getattr(obj.data, "shape_keys", None)
        if shape_keys and shape_keys.animation_data and (
            shape_keys.animation_data.action or shape_keys.animation_data.nla_tracks
        ):
            remaining_non_camera.append(f"shape_keys:{obj.name}")
    if remaining_non_camera:
        failures.append(f"Non-camera animation remains: {remaining_non_camera}")

    camera_after = protected_camera_signatures()
    if camera_before != camera_after:
        failures.append("Camera action signatures changed while freezing non-camera animation")

    restore_scene_frames(original_frames, default_scene_name)
    return {
        "static_frame": frame,
        "cleared_object_actions": sorted(cleared_object_actions),
        "cleared_shape_key_actions": sorted(cleared_shape_key_actions),
        "removed_action_datablocks": sorted(removed_action_names),
        "remaining_non_camera_animation": remaining_non_camera,
        "camera_actions_before": camera_before,
        "camera_actions_after": camera_after,
        "failures": failures,
        "passed": not failures,
    }


def main() -> None:
    args = parse_script_args()
    source = args.source.resolve()
    output = args.output.resolve()
    report_path = args.report.resolve()
    if args.variant != "remove-all-non-camera-animation":
        raise ValueError(f"Unsupported Blender version variant: {args.variant}")
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() != ".blend" or output.suffix.lower() != ".blend":
        raise ValueError("Both source and output must be .blend files")
    if source == output:
        raise ValueError("Source and output must be different files")

    bpy.ops.wm.open_mainfile(filepath=str(source))
    linked_libraries = sorted(library.filepath for library in bpy.data.libraries if library.filepath)
    if linked_libraries:
        raise RuntimeError(f"Source contains linked Blender libraries: {linked_libraries}")

    captured_assets = capture_public_asset_paths()
    animation_summary = freeze_non_camera_animation(args.frame)
    assets_summary = make_blend_assets_portable(output.parent)
    failures = list(animation_summary["failures"])
    if linked_libraries:
        failures.append("The source file contains linked Blender libraries")
    if not assets_summary["passed"]:
        failures.extend(assets_summary.get("unresolved_images", []))
        failures.extend(assets_summary.get("unresolved_fonts", []))
    if failures:
        raise RuntimeError(json.dumps({"failures": failures}, ensure_ascii=False))

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    rebase_captured_asset_paths(captured_assets)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    report = {
        "schema_version": 1,
        "variant": args.variant,
        "source": source.as_posix(),
        "output": output.as_posix(),
        "independent_copy": not linked_libraries,
        "linked_libraries": linked_libraries,
        "assets": assets_summary,
        **animation_summary,
        "source_unchanged_by_design": True,
        "passed": True,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"[blend-version-change] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
