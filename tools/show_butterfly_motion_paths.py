import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_butterfly_scene as base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "blender_scenebench" / "blender_modelbench" / "Butterfly"
BLENDER_ROOT = ASSET_ROOT / "blender"
REPORT_PATH = PROJECT_ROOT / "blender_scenebench" / "reports" / "butterfly-motion-paths.json"

TARGETS = [
    BLENDER_ROOT / "follow_path" / "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend",
    BLENDER_ROOT / "follow_path" / "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend",
]


def find_animated_empty(prefix):
    candidates = [
        obj
        for obj in bpy.data.objects
        if obj.name.startswith(prefix)
        and obj.type == "EMPTY"
        and obj.animation_data
        and obj.animation_data.action
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"{prefix} 动画空物体数量应为 1，实际为 {len(candidates)}")
    return candidates[0]


def update_file(path):
    if not path.is_file():
        raise RuntimeError(f"Blend 文件不存在: {path}")
    bpy.ops.wm.open_mainfile(filepath=str(path))
    artist_scene = bpy.data.scenes.get("ARTIST_EDIT")
    source_scene = bpy.data.scenes.get("SOURCE_REFERENCE")
    if not artist_scene or not source_scene:
        raise RuntimeError(f"场景入口不完整: {path.name}")

    display_target = find_animated_empty("展示_")
    source_target = find_animated_empty("源_")
    base.calculate_motion_path(display_target, artist_scene, "ARTIST_EDIT")
    base.calculate_motion_path(source_target, source_scene, "SOURCE_REFERENCE")

    artist_scene["animation_path_target"] = display_target.name
    artist_scene["animation_path_display"] = "已计算并显示 Blender Motion Path；选中动画根节点后可编辑关键帧"
    source_scene["animation_path_target"] = source_target.name
    source_scene["animation_path_display"] = "已计算并显示原始 FBX 的 Blender Motion Path"

    bpy.context.window.scene = artist_scene
    artist_scene.frame_set(1)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    return {
        "file": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "artist_edit_target": display_target.name,
        "source_reference_target": source_target.name,
        "artist_edit_frames": [display_target.motion_path.frame_start, display_target.motion_path.frame_end],
        "source_reference_frames": [source_target.motion_path.frame_start, source_target.motion_path.frame_end],
    }


def main():
    reports = [update_file(path) for path in TARGETS]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps({"files": reports}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_MOTION_PATHS=" + json.dumps(reports, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
