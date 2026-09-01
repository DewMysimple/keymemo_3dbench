import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_butterfly_head_camera_variant as builder


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "blender_scenebench" / "blender_modelbench" / "Butterfly"
HEAD_CAMERA_ROOT = ASSET_ROOT / "blender" / "follow_path" / "head_camera"
EXPECTED_NAMES = {
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1_HEAD_CAMERA.blend",
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2_HEAD_CAMERA.blend",
}


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def current_output_path():
    path = Path(bpy.data.filepath).resolve()
    ensure(path.parent == HEAD_CAMERA_ROOT.resolve(), f"输入文件必须来自 head_camera: {path}")
    ensure(path.name in EXPECTED_NAMES, f"输入文件不是目标头部摄像机副本: {path.name}")
    return path


def update_view(path):
    artist_scene = bpy.data.scenes.get("ARTIST_EDIT")
    ensure(artist_scene is not None, "缺少 ARTIST_EDIT 场景")
    bpy.context.window.scene = artist_scene
    artist_scene.frame_set(1)
    bpy.context.view_layer.update()

    model_collection = builder.find_collection(artist_scene, "MODEL_", "_展示模型")
    body = builder.find_display_body(model_collection)
    display_meshes = [
        obj for obj in model_collection.objects
        if obj.type == "MESH" and obj.name.startswith("展示_")
    ]
    ensure(len(display_meshes) == 3, f"展示蝴蝶网格数量应为 3，实际为 {len(display_meshes)}")

    camera = bpy.data.objects.get("CAMERA_HEAD_FOLLOW")
    anchor = bpy.data.objects.get("CAMERA_HEAD_ANCHOR")
    look_target = bpy.data.objects.get("CAMERA_HEAD_LOOK_TARGET")
    ensure(camera is not None and camera.type == "CAMERA", "头部跟随摄像机缺失")
    ensure(anchor is not None and anchor.type == "EMPTY", "头部绑定锚点缺失")
    ensure(look_target is not None and look_target.type == "EMPTY", "头部瞄准点缺失")
    ensure(camera.parent == anchor, "头部摄像机父级不是 CAMERA_HEAD_ANCHOR")
    ensure(anchor.parent == body, "头部绑定锚点父级不是展示身体网格")

    display_target, camera_position = builder.apply_top_view(
        camera,
        anchor,
        look_target,
        body,
        display_meshes,
    )
    camera["camera_role"] = "蝴蝶头部正面第三人称跟随摄像机"
    camera["follow_policy"] = "头部位置跟随；使用 DAMPED_TRACK 持续旋转对准蝴蝶；保持正面展开构图"
    camera["view_policy"] = "自上而下的蝴蝶展开视角；画面上方对准头部方向；持续对准蝴蝶"
    camera["rotation_policy"] = "通过 CAMERA_HEAD_TRACK_TO 持续旋转对准 CAMERA_HEAD_LOOK_TARGET"
    camera["edit_note"] = "移动 CAMERA_HEAD_ANCHOR 调整绑定点，移动 CAMERA_HEAD_FOLLOW 调整正面镜头偏移；保持父级和 DAMPED_TRACK 约束即可继续跟随动画。"
    artist_scene.camera = camera
    artist_scene["head_camera_policy"] = "正面第三人称；头部位置跟随；持续旋转对准蝴蝶；原英雄摄像机保留"
    artist_scene["head_camera_view_mode"] = "TOP_DOWN_BUTTERFLY_PROFILE_TRACKED"

    instructions = (
        "# 蝴蝶正面第三人称跟随摄像机\n\n"
        f"文件：{path.name}\n"
        "默认摄像机：CAMERA_HEAD_FOLLOW\n"
        "绑定链：CAMERA_HEAD_FOLLOW → CAMERA_HEAD_ANCHOR → 展示身体网格 → 原始 FBX 父级动画链\n"
        "镜头模式：自上而下的正面展开第三人称；头部位置跟随，摄像机持续旋转对准蝴蝶。\n\n"
        "手动调整：\n"
        "1. 在 ARTIST_EDIT 中选中 CAMERA_HEAD_ANCHOR，移动它可改变头部绑定位置。\n"
        "2. 选中 CAMERA_HEAD_FOLLOW，移动或旋转它可改变固定正面镜头的偏移和视角。\n"
        "3. 不要清除 CAMERA_HEAD_FOLLOW → CAMERA_HEAD_ANCHOR 父级关系或 DAMPED_TRACK 约束，否则摄像机不会继续对准蝴蝶。\n"
        "4. 播放时间轴检查摄像机是否保持正面展开构图。\n"
    )
    text = bpy.data.texts.get("蝴蝶_头部摄像机说明") or bpy.data.texts.new("蝴蝶_头部摄像机说明")
    text.clear()
    text.write(instructions)

    bpy.context.window.scene = artist_scene
    bpy.ops.object.select_all(action="DESELECT")
    camera.select_set(True)
    bpy.context.view_layer.objects.active = camera
    artist_scene.frame_set(1)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(path))

    return {
        "input": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "camera": camera.name,
        "anchor": anchor.name,
        "look_target": look_target.name,
        "default_scene": bpy.context.window.scene.name,
        "default_camera": artist_scene.camera.name,
        "camera_parent": camera.parent.name if camera.parent else None,
        "camera_type": camera.data.type,
        "ortho_scale": camera.data.ortho_scale,
        "camera_position_frame_1": [round(value, 6) for value in camera_position],
        "display_target_frame_1": [round(value, 6) for value in display_target],
        "view_mode": artist_scene["head_camera_view_mode"],
        "output_size": path.stat().st_size,
    }


def main():
    report = update_view(current_output_path())
    print("BUTTERFLY_HEAD_CAMERA_VIEW_UPDATE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
