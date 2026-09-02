import json
from pathlib import Path

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT  / "blender_modelbench" / "Butterfly"
SOURCE_DIR = ASSET_ROOT / "blender" / "follow_path"
OUTPUT_DIR = ASSET_ROOT / "blender" / "wing_flap_only"
REPORT_PATH = PROJECT_ROOT  / "reports" / "butterfly-wing-only-variants.json"

SOURCE_NAMES = (
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend",
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend",
)


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def relative(path):
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")


def find_artist_scene():
    scene = bpy.data.scenes.get("ARTIST_EDIT")
    ensure(scene is not None, "缺少 ARTIST_EDIT 场景")
    if bpy.context.window:
        bpy.context.window.scene = scene
    return scene


def find_display_path_object(scene):
    candidates = [
        obj
        for obj in scene.objects
        if obj.name.startswith("展示_")
        and obj.type == "EMPTY"
        and obj.animation_data
        and obj.animation_data.action
    ]
    ensure(len(candidates) == 1, f"展示路径控制器数量错误: {len(candidates)}")
    return candidates[0]


def find_source_path_object():
    candidates = [
        obj
        for obj in bpy.data.objects
        if obj.name.startswith("源_FBX_")
        and obj.type == "EMPTY"
        and obj.animation_data
        and obj.animation_data.action
    ]
    ensure(len(candidates) == 1, f"源路径控制器数量错误: {len(candidates)}")
    return candidates[0]


def find_display_body(scene):
    candidates = [
        obj
        for obj in scene.objects
        if obj.name.startswith("展示_")
        and obj.type == "MESH"
        and "wing" not in obj.name.lower()
        and "翅" not in obj.name
    ]
    ensure(len(candidates) == 1, f"展示身体数量错误: {len(candidates)}")
    return candidates[0]


def display_animated_objects(scene):
    return [
        obj
        for obj in scene.objects
        if obj.name.startswith("展示_")
        and obj.animation_data
        and obj.animation_data.action
    ]


def clear_motion_path(obj):
    if not obj.motion_path:
        return
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    result = bpy.ops.object.paths_clear()
    ensure(result == {"FINISHED"}, f"清除展示运动路径失败: {obj.name}")


def transform_signature(obj):
    return {
        "location": [round(value, 6) for value in obj.matrix_world.to_translation()],
        "rotation": [round(value, 6) for value in obj.matrix_world.to_quaternion()],
    }


def transform_changed(first, second, tolerance=0.0001):
    return any(
        abs(left - right) > tolerance
        for key in ("location", "rotation")
        for left, right in zip(first[key], second[key])
    )


def write_variant_notes(source_path, output_path, source_action_name):
    text_name = "蝴蝶_仅翅膀扇动版本说明"
    old = bpy.data.texts.get(text_name)
    if old:
        bpy.data.texts.remove(old)
    text = bpy.data.texts.new(text_name)
    text.write(
        "蝴蝶仅翅膀扇动版本\n\n"
        f"来源：{source_path.name}\n"
        f"输出：{output_path.name}\n"
        "ARTIST_EDIT：保留左右翅膀拍动；路径控制器的位置和旋转固定为第 1 帧。\n"
        "SOURCE_REFERENCE：保留原始 Follow Path 源对象和原始 Action，供核对。\n"
        f"原始路径 Action：{source_action_name}\n"
    )


def build_one(source_path):
    output_path = OUTPUT_DIR / f"{source_path.stem}_WING_FLAP_ONLY.blend"
    ensure(source_path.is_file(), f"来源文件不存在: {source_path}")
    ensure(not output_path.exists(), f"拒绝覆盖已有输出: {output_path}")

    bpy.ops.wm.open_mainfile(filepath=str(source_path), load_ui=False)
    artist = find_artist_scene()
    source_path_object = find_source_path_object()
    display_path_object = find_display_path_object(artist)
    display_body = find_display_body(artist)

    artist.frame_set(1)
    bpy.context.view_layer.update()
    static_basis = display_path_object.matrix_basis.copy()
    source_action_name = source_path_object.animation_data.action.name
    ensure(display_path_object.animation_data.action.name == source_action_name, "展示与源路径 Action 不一致")

    # The source and display path objects share the imported Action. Clearing
    # animation data on the display object only keeps SOURCE_REFERENCE intact.
    display_path_object.animation_data_clear()
    display_path_object.matrix_basis = static_basis
    clear_motion_path(display_path_object)
    bpy.context.view_layer.update()

    animated = display_animated_objects(artist)
    ensure(len(animated) == 2, f"展示动画对象数量错误: {len(animated)}")
    ensure(
        all("wing" in obj.name.lower() or "翅" in obj.name for obj in animated),
        "展示层仍存在非翅膀动画",
    )
    ensure(display_path_object.animation_data is None, "展示路径控制器仍有动画数据")
    ensure(source_path_object.animation_data and source_path_object.animation_data.action, "源路径 Action 未保留")
    ensure(display_path_object.motion_path is None, "展示路径运动轨迹未清除")

    samples = []
    for frame in (artist.frame_start, min(artist.frame_end, 45), artist.frame_end):
        artist.frame_set(frame)
        bpy.context.view_layer.update()
        samples.append({
            "frame": frame,
            "path_controller": transform_signature(display_path_object),
            "body": transform_signature(display_body),
        })

    path_reference = samples[0]["path_controller"]
    body_reference = samples[0]["body"]
    ensure(
        all(not transform_changed(path_reference, sample["path_controller"]) for sample in samples[1:]),
        "展示路径控制器仍发生位移或旋转变化",
    )
    ensure(
        all(not transform_changed(body_reference, sample["body"]) for sample in samples[1:]),
        "展示身体仍发生位移或旋转变化",
    )

    artist["document_type"] = "Butterfly 仅翅膀扇动版本"
    artist["source_variant"] = relative(source_path)
    artist["wing_flap_only"] = True
    artist["animation_policy"] = "仅保留左右翅膀拍动；路径控制器位置和旋转固定在第 1 帧"
    artist["source_path_action_preserved"] = source_action_name
    artist["default_showcase_frame"] = artist.frame_start
    write_variant_notes(source_path, output_path, source_action_name)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    ensure(output_path.is_file(), f"输出文件未生成: {output_path}")

    return {
        "source": relative(source_path),
        "output": relative(output_path),
        "source_path_action": source_action_name,
        "display_animated_objects": [obj.name for obj in animated],
        "display_path_animation_removed": True,
        "display_motion_path_removed": True,
        "path_and_body_static": True,
        "frame_samples": samples,
        "output_size": output_path.stat().st_size,
    }


def main():
    ensure(SOURCE_DIR.is_dir(), f"Follow Path 来源目录不存在: {SOURCE_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reports = [build_one(SOURCE_DIR / name) for name in SOURCE_NAMES]
    payload = {
        "asset": "Butterfly",
        "variant": "wing_flap_only",
        "policy": "保留左右翅膀拍动，移除沿路径的位移和旋转；SOURCE_REFERENCE 保留原始源数据",
        "outputs": reports,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_WING_ONLY_BUILD=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
