import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_butterfly_scene as base


from workbench_paths import WORKBENCH_ROOT, model_scenes

PROJECT_ROOT = WORKBENCH_ROOT
BLENDER_ROOT = model_scenes("Butterfly")


def update_current_file():
    path = Path(bpy.data.filepath).resolve()
    if not path.is_file() or BLENDER_ROOT not in path.parents:
        raise RuntimeError(f"当前 Blender 文件不在 models/Butterfly/scenes 目录: {path}")
    base.localized_workspaces()
    artist_scene = bpy.data.scenes.get("ARTIST_EDIT")
    if artist_scene is None:
        raise RuntimeError(f"缺少 ARTIST_EDIT 场景: {path.name}")
    bpy.context.window.scene = artist_scene
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
