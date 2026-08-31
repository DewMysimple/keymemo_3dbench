import base64
import hashlib
import json
from pathlib import Path

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLEND_PATH = PROJECT_ROOT / "blender" / "_scenebench" / "blender" / "_modelbench" / "Butterfly" / "Butterfly.blend"
ARCHIVE_ROOT = BLEND_PATH.parent / "source_assets"
REPORT_PATH = PROJECT_ROOT / "blender_scenebench" / "reports" / "butterfly-validation.json"


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def action_signature(scene, objects, frame):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return [
        (
            obj.name,
            tuple(round(value, 5) for value in obj.matrix_world.to_translation()),
            tuple(round(value, 5) for value in obj.matrix_world.to_euler()),
        )
        for obj in objects
        if obj.animation_data and obj.animation_data.action
    ]


def validate():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_PATH))
    ensure(BLEND_PATH.is_file(), f"Blend 文件不存在: {BLEND_PATH}")
    ensure({scene.name for scene in bpy.data.scenes} == {"ARTIST_EDIT", "SOURCE_REFERENCE"}, "场景入口不完整")
    artist = bpy.data.scenes["ARTIST_EDIT"]
    source = bpy.data.scenes["SOURCE_REFERENCE"]
    ensure(artist == bpy.context.window.scene, "默认场景不是 ARTIST_EDIT")

    source_root = bpy.data.collections.get("SOURCE_Butterfly_源文件")
    model = bpy.data.collections.get("MODEL_Butterfly_展示模型")
    ensure(source_root is not None and model is not None, "源文件或展示模型集合缺失")
    fbx_collections = [child for child in source_root.children if child.name.startswith("SOURCE_FBX_")]
    ensure(len(fbx_collections) == 10, f"FBX 源集合数量错误: {len(fbx_collections)}")
    ensure(len(list(source_root.objects)) == 0, "FBX 源对象不应脱离其分组集合")

    source_objects = []
    source_actions = []
    group_report = []
    for collection in sorted(fbx_collections, key=lambda item: item.name):
        objects = list(collection.objects)
        actions = [
            obj.animation_data.action
            for obj in objects
            if obj.animation_data and obj.animation_data.action
        ]
        ensure(objects, f"源集合为空: {collection.name}")
        ensure(all(obj.get("source_asset") for obj in objects), f"源对象缺少 source_asset: {collection.name}")
        ensure(all(obj.parent is None or obj.parent in objects for obj in objects), f"父子关系跨源集合: {collection.name}")
        source_objects.extend(objects)
        source_actions.extend(actions)
        group_report.append({
            "collection": collection.name,
            "objects": len(objects),
            "animated_objects": len(actions),
            "action_ranges": [list(action.frame_range) for action in actions],
        })

    ensure(len(source_objects) == 44, f"FBX 源对象总数错误: {len(source_objects)}")
    ensure(len(source_actions) == 22, f"源动画 Action 使用数错误: {len(source_actions)}")
    ensure({tuple(action.frame_range) for action in source_actions} == {(1.0, 85.0), (1.0, 91.0), (1.0, 121.0)}, "动作帧范围不完整")

    obj_collection = bpy.data.collections.get("SOURCE_OBJ_Butterfly_Body")
    ensure(obj_collection is not None and len(list(obj_collection.objects)) == 1, "OBJ 身体源对象缺失")
    obj_body = next(iter(obj_collection.objects))
    ensure(obj_body.type == "MESH" and len(obj_body.data.vertices) == 1239 and len(obj_body.data.polygons) == 1229, "OBJ 身体网格数据不完整")

    packed_images = [image for image in bpy.data.images if image.name != "Render Result" and image.packed_file]
    ensure(len(packed_images) == 4, f"打包图像数量错误: {len(packed_images)}")
    c4d_text = bpy.data.texts.get("蝴蝶_C4D原始二进制_Base64")
    ensure(c4d_text is not None, "C4D 原始二进制归档缺失")
    c4d_archive = ARCHIVE_ROOT / "Animated_Butterflies_Project_File_ Travis_Davids.c4d"
    c4d_lines = c4d_text.as_string().split("\n\n", 1)
    ensure(len(c4d_lines) == 2, "C4D Base64 归档格式损坏")
    embedded_c4d = base64.b64decode(c4d_lines[1].replace("\n", ""), validate=True)
    ensure(c4d_archive.is_file(), "C4D 源文件归档缺失")
    ensure(hashlib.sha256(embedded_c4d).hexdigest() == hashlib.sha256(c4d_archive.read_bytes()).hexdigest(), "C4D 内嵌字节校验失败")

    display_root = bpy.data.objects.get("蝴蝶_展示根_不改变源动画")
    ensure(display_root is not None, "展示根缺失")
    display_objects = [obj for obj in model.objects if obj.name.startswith("展示_")]
    display_animated = [
        obj for obj in display_objects if obj.animation_data and obj.animation_data.action
    ]
    ensure(len(display_objects) == 4 and len(display_animated) == 2, "展示副本或展示动画缺失")
    signature_1 = action_signature(artist, display_animated, 1)
    signature_45 = action_signature(artist, display_animated, 45)
    ensure(signature_1 != signature_45, "展示动画在第 1 与第 45 帧没有变化")

    archive_files = [path for path in ARCHIVE_ROOT.rglob("*") if path.is_file()]
    ensure(len(archive_files) == 18, f"源文件归档数量错误: {len(archive_files)}")
    for image in packed_images:
        ensure(image.packed_file is not None, f"图像未打包: {image.name}")

    artist.frame_set(1)
    source.frame_set(1)
    report = {
        "blend": str(BLEND_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "scenes": [scene.name for scene in bpy.data.scenes],
        "default_scene": bpy.context.window.scene.name,
        "fbx_source_collections": len(fbx_collections),
        "fbx_source_objects": len(source_objects),
        "source_actions": len(source_actions),
        "obj_body_vertices": len(obj_body.data.vertices),
        "obj_body_polygons": len(obj_body.data.polygons),
        "packed_images": [image.name for image in packed_images],
        "embedded_c4d": True,
        "archived_source_files": len(archive_files),
        "group_report": group_report,
        "animation_signature_changed_1_to_45": True,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_VALIDATION=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    validate()
