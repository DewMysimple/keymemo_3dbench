import base64
import hashlib
import json
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = PROJECT_ROOT / "blender_scenebench" / "blender_modelbench" / "Butterfly"
SOURCE_ROOT = OUTPUT_ROOT / "source"
BLENDER_ROOT = OUTPUT_ROOT / "blender"
MANIFEST_PATH = OUTPUT_ROOT / "manifests" / "source-files.json"
LEGACY_ARCHIVE_ROOT = OUTPUT_ROOT / "archive" / "legacy"
REPORT_PATH = PROJECT_ROOT / "blender_scenebench" / "reports" / "butterfly-validation.json"


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def source_fbx_paths():
    category_order = {"idle": 0, "follow_path": 1, "slow_flap": 2}

    def sort_key(path):
        relative_parts = path.relative_to(SOURCE_ROOT).parts
        category = relative_parts[1] if len(relative_parts) > 1 else ""
        return (category_order.get(category, 99), str(path).lower())

    return sorted(SOURCE_ROOT.glob("animations/**/*.fbx"), key=sort_key)


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


def mesh_bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    low = Vector((
        min(point.x for point in points),
        min(point.y for point in points),
        min(point.z for point in points),
    ))
    high = Vector((
        max(point.x for point in points),
        max(point.y for point in points),
        max(point.z for point in points),
    ))
    return (low + high) * 0.5


def validate_c4d():
    c4d_text = bpy.data.texts.get("蝴蝶_C4D原始二进制_Base64")
    ensure(c4d_text is not None, "C4D 原始二进制归档缺失")
    c4d_source = SOURCE_ROOT / "project" / "Animated_Butterflies_Project_File_ Travis_Davids.c4d"
    ensure(c4d_source.is_file(), "C4D 源文件缺失")
    sections = c4d_text.as_string().split("\n\n", 1)
    ensure(len(sections) == 2, "C4D Base64 归档格式损坏")
    embedded_c4d = base64.b64decode(sections[1].replace("\n", ""), validate=True)
    ensure(
        hashlib.sha256(embedded_c4d).hexdigest() == hashlib.sha256(c4d_source.read_bytes()).hexdigest(),
        "C4D 内嵌字节校验失败",
    )


def validate_source_manifest():
    ensure(MANIFEST_PATH.is_file(), "源文件哈希清单缺失")
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files = payload.get("files", [])
    ensure(payload.get("source_file_count") == 18 and len(files) == 18, "源文件哈希清单数量错误")
    actual = []
    for item in files:
        path = SOURCE_ROOT / item["path"]
        ensure(path.is_file(), f"源文件缺失: {item['path']}")
        ensure(path.stat().st_size == item["size"], f"源文件大小校验失败: {item['path']}")
        ensure(hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], f"源文件哈希校验失败: {item['path']}")
        actual.append(path)
    ensure(len({path.resolve() for path in actual}) == 18, "源文件清单存在重复路径")


def find_scene_collection(scene, predicate):
    return next((collection for collection in scene.collection.children if predicate(collection)), None)


def validate_one(blend_path, expected_fbx_paths, master):
    ensure(blend_path.is_file(), f"Blend 文件不存在: {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=str(blend_path), load_ui=False)
    ensure({scene.name for scene in bpy.data.scenes} == {"ARTIST_EDIT", "SOURCE_REFERENCE"}, f"场景入口不完整: {blend_path.name}")
    artist = bpy.data.scenes["ARTIST_EDIT"]
    source = bpy.data.scenes["SOURCE_REFERENCE"]
    ensure(artist == bpy.context.window.scene, f"默认场景不是 ARTIST_EDIT: {blend_path.name}")

    source_root = find_scene_collection(
        artist,
        lambda collection: collection.name.startswith("SOURCE_") and collection.name.endswith("_源文件"),
    )
    model = find_scene_collection(
        artist,
        lambda collection: collection.name.startswith("MODEL_") and collection.name.endswith("_展示模型"),
    )
    ensure(source_root is not None and model is not None, f"源文件或展示模型集合缺失: {blend_path.name}")
    fbx_collections = [child for child in source_root.children if child.name.startswith("SOURCE_FBX_")]
    ensure(len(fbx_collections) == len(expected_fbx_paths), f"FBX 源集合数量错误: {blend_path.name}")
    ensure(len(list(source_root.objects)) == 0, f"FBX 源对象脱离分组集合: {blend_path.name}")

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

    expected_object_count = 44 if master else (6 if "FOLLOW_PATH" in expected_fbx_paths[0].upper() else 4)
    expected_action_count = 22 if master else (3 if "FOLLOW_PATH" in expected_fbx_paths[0].upper() else 2)
    ensure(len(source_objects) == expected_object_count, f"FBX 源对象数量错误: {blend_path.name}: {len(source_objects)}")
    ensure(len(source_actions) == expected_action_count, f"源动画 Action 使用数错误: {blend_path.name}: {len(source_actions)}")
    ensure(source_actions, f"源动画 Action 缺失: {blend_path.name}")

    obj_collection = bpy.data.collections.get("SOURCE_OBJ_Butterfly_Body")
    ensure(obj_collection is not None and len(list(obj_collection.objects)) == 1, f"OBJ 身体源对象缺失: {blend_path.name}")
    obj_body = next(iter(obj_collection.objects))
    ensure(obj_body.type == "MESH" and len(obj_body.data.vertices) == 1239 and len(obj_body.data.polygons) == 1229, f"OBJ 身体网格数据不完整: {blend_path.name}")

    packed_images = [image for image in bpy.data.images if image.name != "Render Result" and image.packed_file]
    ensure(len(packed_images) == 4, f"打包图像数量错误: {blend_path.name}: {len(packed_images)}")
    validate_c4d()

    display_root = next((obj for obj in model.objects if obj.name.startswith("DISPLAY_") and obj.type == "EMPTY"), None)
    display_objects = [obj for obj in model.objects if obj.name.startswith("展示_")]
    display_animated = [
        obj for obj in display_objects
        if obj.animation_data and obj.animation_data.action
    ]
    expected_display_count = 4 if master else expected_object_count
    expected_display_action_count = 2 if master else expected_action_count
    ensure(display_root is not None, f"展示根缺失: {blend_path.name}")
    ensure(len(display_objects) == expected_display_count, f"展示对象数量错误: {blend_path.name}")
    ensure(len(display_animated) == expected_display_action_count, f"展示动画数量错误: {blend_path.name}")

    display_meshes = [obj for obj in display_objects if obj.type == "MESH"]
    display_body = [obj for obj in display_meshes if "body" in obj.name.lower()]
    display_wings = [obj for obj in display_meshes if "wing" in obj.name.lower()]
    ensure(len(display_meshes) == 3 and len(display_body) == 1 and len(display_wings) == 2, f"左右翅膀/身体展示网格数量错误: {blend_path.name}")
    showcase_frame = int(artist.get("default_showcase_frame", artist.frame_current))
    artist.frame_set(showcase_frame)
    bpy.context.view_layer.update()
    body_center = mesh_bounds(display_body[0])
    wing_centers = sorted((mesh_bounds(wing).x for wing in display_wings))
    ensure(wing_centers[0] < body_center.x < wing_centers[1], f"左右翅膀没有分居身体两侧: {blend_path.name}")
    ensure(display_root.scale.length > 0.0, f"展示根缩放无效: {blend_path.name}")

    first_frame = int(round(min(action.frame_range[0] for action in source_actions)))
    last_frame = int(round(max(action.frame_range[1] for action in source_actions)))
    signature_first = action_signature(artist, display_animated, first_frame)
    signature_mid = action_signature(artist, display_animated, min(last_frame, 45))
    ensure(signature_first != signature_mid, f"展示动画帧变化缺失: {blend_path.name}")

    motion_path_targets = [
        obj for obj in display_objects
        if obj.type == "EMPTY" and obj.animation_data and obj.animation_data.action and obj.motion_path
    ]
    is_follow_path = (not master) and any("FOLLOW_PATH" in value.upper() for value in expected_fbx_paths)
    if is_follow_path:
        ensure(len(motion_path_targets) == 1, f"Follow Path 展示运动路径缺失: {blend_path.name}")
        ensure(motion_path_targets[0].motion_path.length > 1, f"Follow Path 展示运动路径没有轨迹点: {blend_path.name}")
        source_motion_path_targets = [
            obj for obj in source_objects
            if obj.type == "EMPTY" and obj.animation_data and obj.animation_data.action and obj.motion_path
        ]
        ensure(len(source_motion_path_targets) == 1, f"Follow Path 源运动路径缺失: {blend_path.name}")
        ensure(source_motion_path_targets[0].motion_path.length > 1, f"Follow Path 源运动路径没有轨迹点: {blend_path.name}")

    source_files = [path for path in SOURCE_ROOT.rglob("*") if path.is_file()]
    ensure(len(source_files) == 18, f"源文件数量错误: {len(source_files)}")
    return {
        "blend": str(blend_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "master": master,
        "active_fbx": expected_fbx_paths,
        "scenes": [scene.name for scene in bpy.data.scenes],
        "default_scene": bpy.context.window.scene.name,
        "fbx_source_collections": len(fbx_collections),
        "fbx_source_objects": len(source_objects),
        "source_actions": len(source_actions),
        "source_action_ranges": sorted({tuple(action.frame_range) for action in source_actions}),
        "obj_body_vertices": len(obj_body.data.vertices),
        "obj_body_polygons": len(obj_body.data.polygons),
        "packed_images": [image.name for image in packed_images],
        "embedded_c4d": True,
        "source_files": len(source_files),
        "display_objects": len(display_objects),
        "display_animated_objects": len(display_animated),
        "motion_path": {
            "display_targets": [obj.name for obj in motion_path_targets],
            "display_points": motion_path_targets[0].motion_path.length if motion_path_targets else 0,
        },
        "display_wing_centers_x": wing_centers,
        "animation_signature_changed": True,
        "group_report": group_report,
    }


def validate():
    ensure(not (OUTPUT_ROOT / "source_assets").exists(), "旧 source_assets 重复目录仍存在")
    ensure(not any(OUTPUT_ROOT.glob("*.blend")), "正式根目录仍有未分类 Blender 文件")
    legacy_files = {path.name for path in LEGACY_ARCHIVE_ROOT.glob("*") if path.is_file()}
    ensure(legacy_files == {"Butterfly_legacy_master.blend", "Butterfly_legacy_master.blend1"}, "历史 Butterfly 归档不完整")
    validate_source_manifest()
    source_paths = source_fbx_paths()
    ensure(len(source_paths) == 10, f"源 FBX 数量错误: {len(source_paths)}")
    expected_rel_paths = [str(path.relative_to(SOURCE_ROOT)).replace("\\", "/") for path in source_paths]
    master_path = BLENDER_ROOT / "Butterfly_Master.blend"
    variant_paths = sorted(
        (
            path for path in BLENDER_ROOT.glob("**/*.blend")
            if path.name != master_path.name
        ),
        key=lambda path: path.name.lower(),
    )
    expected_variant_names = {path.stem for path in source_paths}
    ensure({path.stem for path in variant_paths} == expected_variant_names, "独立 Blender 文件没有与 10 个 FBX 一一对应")

    reports = [validate_one(master_path, expected_rel_paths, master=True)]
    expected_by_stem = {path.stem: str(path.relative_to(SOURCE_ROOT)).replace("\\", "/") for path in source_paths}
    for variant_path in variant_paths:
        reports.append(validate_one(variant_path, [expected_by_stem[variant_path.stem]], master=False))

    payload = {
        "output_root": str(OUTPUT_ROOT.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "blender_root": str(BLENDER_ROOT.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_root": str(SOURCE_ROOT.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "blend_file_count": len(reports),
        "validated": reports,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_VALIDATION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    validate()
