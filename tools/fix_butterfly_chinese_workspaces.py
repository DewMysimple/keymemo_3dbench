import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_butterfly_scene as base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "blender_scenebench" / "blender_modelbench" / "Butterfly"
BLENDER_ROOT = ASSET_ROOT / "blender"


def update_current_file():
    path = Path(bpy.data.filepath).resolve()
    if not path.is_file() or BLENDER_ROOT not in path.parents:
        raise RuntimeError(f"当前 Blender 文件不在 Butterfly/blender 目录: {path}")
    base.localized_workspaces()
    artist_scene = bpy.data.scenes.get("ARTIST_EDIT")
    if artist_scene is None:
        raise RuntimeError(f"缺少 ARTIST_EDIT 场景: {path.name}")
    bpy.context.window.scene = artist_scene
    if path.parent.name == "follow_path":
        animation_workspace = bpy.data.workspaces.get("动画")
        if animation_workspace:
            bpy.context.window.workspace = animation_workspace
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    return {
        "file": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "workspaces": [workspace.name for workspace in bpy.data.workspaces],
        "default_scene": bpy.context.window.scene.name,
    }


def main():
    report = update_current_file()
    print("BUTTERFLY_CHINESE_WORKSPACES_FIXED=" + str(report))


if __name__ == "__main__":
    main()
