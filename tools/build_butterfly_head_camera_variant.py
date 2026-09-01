import json
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "blender_scenebench" / "blender_modelbench" / "Butterfly"
BLENDER_ROOT = ASSET_ROOT / "blender"
OUTPUT_ROOT = BLENDER_ROOT / "follow_path" / "head_camera"


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def current_input_path():
    path = Path(bpy.data.filepath).resolve()
    ensure(path.is_file(), "当前 Blender 文件路径无效")
    ensure(path.parent.name == "follow_path", f"输入文件必须来自 follow_path: {path}")
    ensure(
        path.name in {
            "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend",
            "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend",
        },
        f"输入文件不是目标 Follow Path 文件: {path.name}",
    )
    return path


def output_path(input_path):
    return OUTPUT_ROOT / f"{input_path.stem}_HEAD_CAMERA.blend"


def find_collection(scene, prefix, suffix=None):
    collections = [
        collection
        for collection in scene.collection.children
        if collection.name.startswith(prefix)
        and (suffix is None or collection.name.endswith(suffix))
    ]
    ensure(len(collections) == 1, f"集合 {prefix} 数量应为 1，实际为 {len(collections)}")
    return collections[0]


def find_display_body(model_collection):
    bodies = [
        obj
        for obj in model_collection.objects
        if obj.type == "MESH"
        and obj.name.startswith("展示_")
        and "BODY" in obj.name.upper()
    ]
    ensure(len(bodies) == 1, f"展示身体网格数量应为 1，实际为 {len(bodies)}")
    return bodies[0]


def parent_preserve_world(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def body_world_points(body):
    return [body.matrix_world @ vertex.co for vertex in body.data.vertices]


def calculate_head_reference(body, scene):
    points = body_world_points(body)
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
    body_center = (low + high) * 0.5

    reference_camera = scene.camera
    ensure(reference_camera is not None, "原始展示摄像机缺失，无法判断头部方向")
    projected = [
        (world_to_camera_view(scene, reference_camera, point).x, point)
        for point in points
    ]
    projected.sort(key=lambda item: item[0])
    sample_count = max(24, len(projected) // 20)
    head_point = sum((point for _, point in projected[-sample_count:]), Vector()) / sample_count
    forward = head_point - body_center
    ensure(forward.length > 0.05, "无法从身体几何数据确定头部方向")
    forward.normalize()
    return body_center, head_point, forward


def make_empty(name, collection, display_type, display_size):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display_type
    obj.empty_display_size = display_size
    obj.show_in_front = True
    obj.hide_render = True
    collection.objects.link(obj)
    return obj


def matrix_from_location_rotation(location, rotation):
    matrix = rotation.to_matrix().to_4x4()
    matrix.translation = location
    return matrix


def add_head_camera(input_path):
    output = output_path(input_path)
    ensure(not output.exists(), f"输出文件已存在，拒绝覆盖: {output}")
    ensure(not any(output.parent.glob(f"{output.stem}.blend[0-9]*")), f"输出目录已有同名备份: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    artist_scene = bpy.data.scenes.get("ARTIST_EDIT")
    source_scene = bpy.data.scenes.get("SOURCE_REFERENCE")
    ensure(artist_scene is not None and source_scene is not None, "缺少 ARTIST_EDIT 或 SOURCE_REFERENCE 场景")
    bpy.context.window.scene = artist_scene
    artist_scene.frame_set(1)
    bpy.context.view_layer.update()

    model_collection = find_collection(artist_scene, "MODEL_", "_展示模型")
    light_collection = find_collection(artist_scene, "LIGHTS_", "_摄影灯光")
    body = find_display_body(model_collection)
    body_center, head_point, forward = calculate_head_reference(body, artist_scene)

    anchor = make_empty("CAMERA_HEAD_ANCHOR", model_collection, "SPHERE", 0.16)
    anchor["camera_role"] = "蝴蝶头部绑定锚点"
    anchor["bound_body_object"] = body.name
    anchor["head_anchor_method"] = "展示身体网格头部端的相机投影高端采样"
    anchor["head_anchor_frame"] = 1
    parent_preserve_world(anchor, body)
    anchor.matrix_world = Matrix.Translation(head_point)

    look_target = make_empty("CAMERA_HEAD_LOOK_TARGET", model_collection, "CUBE", 0.12)
    look_target["camera_role"] = "第三人称头部摄像机瞄准点"
    look_target["bound_body_object"] = body.name
    parent_preserve_world(look_target, body)
    look_target.matrix_world = Matrix.Translation(body_center)

    camera_data = bpy.data.cameras.new("CAMERA_HEAD_FOLLOW_DATA")
    camera = bpy.data.objects.new("CAMERA_HEAD_FOLLOW", camera_data)
    light_collection.objects.link(camera)
    camera_data.lens = 32.0
    camera_data.sensor_width = 36.0
    camera_data.clip_start = 0.01
    camera_data.clip_end = 1000.0

    world_up = Vector((0.0, 0.0, 1.0))
    if abs(forward.dot(world_up)) > 0.92:
        world_up = Vector((0.0, 1.0, 0.0))
    camera_position = head_point - forward * 5.5 + world_up * 2.25
    camera_rotation = (body_center - camera_position).to_track_quat("-Z", "Y")
    camera.matrix_world = matrix_from_location_rotation(camera_position, camera_rotation)
    parent_preserve_world(camera, anchor)
    camera["camera_role"] = "蝴蝶头部第三人称跟随摄像机"
    camera["bound_to_anchor"] = anchor.name
    camera["look_target"] = look_target.name
    camera["follow_policy"] = "完整继承头部父级变换，包括位置、旋转和翻滚"
    camera["view_policy"] = "第三人称后上方视角"
    camera["edit_note"] = "移动 CAMERA_HEAD_ANCHOR 调整绑定点，移动 CAMERA_HEAD_FOLLOW 调整镜头偏移；保持父级关系即可继续跟随动画。"

    artist_scene.camera = camera
    artist_scene["head_camera_name"] = camera.name
    artist_scene["head_camera_anchor"] = anchor.name
    artist_scene["head_camera_look_target"] = look_target.name
    artist_scene["head_camera_policy"] = "第三人称后上方；完整继承头部旋转和翻滚；原英雄摄像机保留"
    artist_scene["head_camera_source_file"] = str(input_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

    instructions = (
        "# 蝴蝶头部跟随摄像机\n\n"
        f"源文件副本：{input_path.name}\n"
        "默认摄像机：CAMERA_HEAD_FOLLOW\n"
        "绑定链：CAMERA_HEAD_FOLLOW → CAMERA_HEAD_ANCHOR → 展示身体网格 → 原始 FBX 父级动画链\n"
        "镜头模式：第三人称后上方；完整继承头部移动、旋转和翻滚。\n\n"
        "手动调整：\n"
        "1. 在 ARTIST_EDIT 中选中 CAMERA_HEAD_ANCHOR，移动它可改变头部绑定位置。\n"
        "2. 选中 CAMERA_HEAD_FOLLOW，移动或旋转它可改变镜头偏移和视角。\n"
        "3. 不要清除父级关系，否则摄像机不会继续跟随蝴蝶。\n"
        "4. 播放时间轴检查第 1、中间和最后帧的跟随效果。\n"
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
    bpy.ops.wm.save_as_mainfile(filepath=str(output))

    report = {
        "input": str(input_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "output": str(output.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "camera": camera.name,
        "anchor": anchor.name,
        "look_target": look_target.name,
        "bound_body": body.name,
        "head_point_frame_1": [round(value, 6) for value in head_point],
        "forward_frame_1": [round(value, 6) for value in forward],
        "camera_lens_mm": camera_data.lens,
        "default_scene": bpy.context.window.scene.name,
        "default_camera": artist_scene.camera.name,
        "camera_parent": camera.parent.name if camera.parent else None,
        "output_size": output.stat().st_size,
    }
    return report


def main():
    report = add_head_camera(current_input_path())
    print("BUTTERFLY_HEAD_CAMERA_BUILD=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
