import json
from pathlib import Path

import bpy

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from workbench_paths import REPORTS_ROOT, WORKBENCH_ROOT, model_root, model_scenes
from butterfly_frame_attachment import DISPLAY_ROOT_NAME

PROJECT_ROOT = WORKBENCH_ROOT
ASSET_ROOT = model_root("Butterfly")
OUTPUT_DIR = model_scenes("Butterfly") / "wing_flap_only"
REPORT_PATH = REPORTS_ROOT / "butterfly-wing-only-validation.json"

EXPECTED_NAMES = (
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1_WING_FLAP_ONLY.blend",
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2_WING_FLAP_ONLY.blend",
)


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def relative(path):
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")


def transform_signature(obj):
    return (
        tuple(round(value, 6) for value in obj.matrix_world.to_translation()),
        tuple(round(value, 6) for value in obj.matrix_world.to_quaternion()),
    )


def changed(first, second, tolerance=0.0001):
    return any(
        abs(left - right) > tolerance
        for group_left, group_right in zip(first, second)
        for left, right in zip(group_left, group_right)
    )


def validate_one(path):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    artist = bpy.data.scenes.get("ARTIST_EDIT")
    source = bpy.data.scenes.get("SOURCE_REFERENCE")
    ensure(artist is not None and source is not None, f"场景入口缺失: {path.name}")
    ensure(bpy.context.window.scene == artist, f"默认场景不是 ARTIST_EDIT: {path.name}")

    display_root = artist.objects.get(DISPLAY_ROOT_NAME)
    ensure(display_root is not None and display_root.type == "EMPTY", f"展示总控根缺失: {path.name}")
    ensure(display_root.animation_data is None, f"展示总控根仍有动画: {path.name}")
    display_children = [obj for obj in artist.objects if obj.parent == display_root]
    ensure(len(display_children) == 3 and all(obj.type == "MESH" for obj in display_children), f"展示总控根未直接绑定身体与双翼: {path.name}")
    legacy_display_empties = [obj for obj in artist.objects if obj.type == "EMPTY" and obj != display_root and obj.name.startswith("展示_")]
    ensure(not legacy_display_empties, f"仍存在旧展示路径/FBX 空对象: {path.name}")

    animated = [
        obj
        for obj in artist.objects
        if obj.name.startswith("展示_") and obj.animation_data and obj.animation_data.action
    ]
    ensure(len(animated) == 2, f"展示动画对象不是 2 个: {path.name}")
    ensure(
        all("wing" in obj.name.lower() or "翅" in obj.name for obj in animated),
        f"展示层包含非翅膀动画: {path.name}",
    )

    source_path = next(
        (
            obj
            for obj in source.objects
            if obj.name.startswith("源_FBX_")
            and obj.type == "EMPTY"
            and obj.animation_data
            and obj.animation_data.action
        ),
        None,
    )
    ensure(source_path is not None, f"SOURCE_REFERENCE 原始路径 Action 缺失: {path.name}")

    body = next(
        (
            obj
            for obj in artist.objects
            if obj.name.startswith("展示_")
            and obj.type == "MESH"
            and "wing" not in obj.name.lower()
            and "翅" not in obj.name
        ),
        None,
    )
    ensure(body is not None, f"展示身体缺失: {path.name}")

    samples = []
    wing_signatures = []
    for frame in (artist.frame_start, min(artist.frame_end, 45), artist.frame_end):
        artist.frame_set(frame)
        bpy.context.view_layer.update()
        samples.append({
            "frame": frame,
            "display_root": transform_signature(display_root),
            "body": transform_signature(body),
        })
        wing_signatures.append(tuple(transform_signature(obj) for obj in animated))

    ensure(all(not changed(samples[0]["display_root"], item["display_root"]) for item in samples[1:]), f"展示总控根仍在变化: {path.name}")
    ensure(all(not changed(samples[0]["body"], item["body"]) for item in samples[1:]), f"身体仍在变化: {path.name}")
    ensure(wing_signatures[0] != wing_signatures[1], f"翅膀拍动动画没有变化: {path.name}")

    return {
        "file": relative(path),
        "default_scene": artist.name,
        "display_animated_objects": [obj.name for obj in animated],
        "source_path_action": source_path.animation_data.action.name,
        "clean_direct_display_hierarchy": True,
        "display_root_and_body_static": True,
        "wing_animation_changed": True,
        "frame_samples": samples,
    }


def main():
    ensure(OUTPUT_DIR.is_dir(), f"输出目录不存在: {OUTPUT_DIR}")
    paths = [OUTPUT_DIR / name for name in EXPECTED_NAMES]
    ensure(all(path.is_file() for path in paths), "两个翅膀扇动版本文件不完整")
    reports = [validate_one(path) for path in paths]
    payload = {
        "asset": "Butterfly",
        "variant": "wing_flap_only",
        "validated_count": len(reports),
        "validated": reports,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_WING_ONLY_VALIDATION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
