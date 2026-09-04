"""Shared construction helpers for the Butterfly specimen-frame variants."""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


FRAME_OBJECT_NAME = "SPECIMEN_FRAME_MATERIAL_SLOTS"
FRAME_COLLECTION_NAME = "MODEL_SpecimenFrame_落脚框"
CAMERA_COLLECTION_NAME = "CAMERAS_Butterfly_构图相机"
DISPLAY_ROOT_NAME = "DISPLAY_Butterfly_Master_ROOT"
GROUND_OBJECT_NAME = "蝴蝶_展示台地面"
FRAME_FRONT_X = 0.21
CONTACT_X = 0.212
FRAME_CENTER_Z = 4.55
CORE_HALF_SIZE = 3.55
CORE_FIT_SIZE = 6.50
MIN_NATIVE_DEPTH = 1.0
PANEL_SAFE_WING_RANGES = {
    "left": (math.radians(-160.0), math.radians(-90.0)),
    "right": (math.radians(90.0), math.radians(160.0)),
}
WING_CENTERLINE_TOLERANCE = 0.06
MAX_WING_HINGE_GAP = 0.02


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def _is_descendant(obj, ancestor):
    current = obj
    while current is not None:
        if current == ancestor:
            return True
        current = current.parent
    return False


def _world_bounds(objects):
    points = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    ensure(points, "蝴蝶展示层没有可计算包围盒的网格")
    return {
        "min": Vector(min(point[index] for point in points) for index in range(3)),
        "max": Vector(max(point[index] for point in points) for index in range(3)),
    }


def _animated_bounds(scene, objects):
    minimum = Vector((math.inf, math.inf, math.inf))
    maximum = Vector((-math.inf, -math.inf, -math.inf))
    original_frame = scene.frame_current
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        bounds = _world_bounds(objects)
        for index in range(3):
            minimum[index] = min(minimum[index], bounds["min"][index])
            maximum[index] = max(maximum[index], bounds["max"][index])
    scene.frame_set(original_frame)
    bpy.context.view_layer.update()
    return {"min": minimum, "max": maximum}


def _action_fcurves(action):
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                curves.extend(channelbag.fcurves)
    return curves


def _affine_curve(curve, scale, offset):
    for keyframe in curve.keyframe_points:
        keyframe.co.y = keyframe.co.y * scale + offset
        keyframe.handle_left.y = keyframe.handle_left.y * scale + offset
        keyframe.handle_right.y = keyframe.handle_right.y * scale + offset
    curve.update()


def _wing_role(obj):
    lowered = obj.name.lower()
    if "left" in lowered:
        return "left"
    if "right" in lowered:
        return "right"
    return None


def _retarget_wings_to_panel_safe_ranges(scene, wings):
    """Retarget each flap to its own side of the body without moving the hinge.

    The source animation swings through both sides of its horizontal body plane.
    After mounting the body on a vertical panel, a constant Euler offset makes the
    left and right wings exchange sides during half of the cycle.  Affinely mapping
    the source Z curve into one panel-safe interval preserves its keyframe timing
    and easing while keeping each wing on its anatomical side.
    """
    original_frame = scene.frame_current
    retarget = {}
    for wing in wings:
        role = _wing_role(wing)
        ensure(role in PANEL_SAFE_WING_RANGES, f"无法识别翅膀方向: {wing.name}")
        ensure(wing.animation_data and wing.animation_data.action, f"翅膀缺少 Action: {wing.name}")
        values = []
        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            values.append(float(wing.rotation_euler.z))
        source_min = min(values)
        source_max = max(values)
        ensure(source_max - source_min > 1e-6, f"翅膀 Z 旋转范围异常: {wing.name}")
        target_min, target_max = PANEL_SAFE_WING_RANGES[role]
        scale = (target_max - target_min) / (source_max - source_min)
        offset = target_min - source_min * scale
        curve = next(
            (
                curve
                for curve in _action_fcurves(wing.animation_data.action)
                if curve.data_path == "rotation_euler" and curve.array_index == 2
            ),
            None,
        )
        ensure(curve is not None, f"翅膀 Action 缺少 Z 旋转曲线: {wing.name}")
        _affine_curve(curve, scale, offset)
        metadata = {
            "source_range": [source_min, source_max],
            "target_range": [target_min, target_max],
            "scale": scale,
            "offset": offset,
        }
        wing["frame_attachment_retarget_source_range"] = metadata["source_range"]
        wing["frame_attachment_retarget_target_range"] = metadata["target_range"]
        wing["frame_attachment_retarget_scale"] = scale
        wing["frame_attachment_retarget_offset"] = offset
        wing.animation_data.action["frame_attachment_retarget_source_range"] = metadata["source_range"]
        wing.animation_data.action["frame_attachment_retarget_target_range"] = metadata["target_range"]
        wing.animation_data.action["frame_attachment_retarget_scale"] = scale
        wing.animation_data.action["frame_attachment_retarget_offset"] = offset
        retarget[role] = metadata
    scene.frame_set(original_frame)
    bpy.context.view_layer.update()
    return retarget


def _world_mesh_geometry(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
        return vertices, polygons
    finally:
        evaluated.to_mesh_clear()


def _minimum_surface_distance(source, target):
    source_vertices, _ = _world_mesh_geometry(source)
    target_vertices, target_polygons = _world_mesh_geometry(target)
    tree = BVHTree.FromPolygons(target_vertices, target_polygons, all_triangles=False)
    distances = [nearest[3] for point in source_vertices if (nearest := tree.find_nearest(point))]
    ensure(distances, f"无法测量 {source.name} 与 {target.name} 的表面距离")
    return min(distances)


def _get_or_create_collection(scene, name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    if collection.name not in {child.name for child in scene.collection.children}:
        scene.collection.children.link(collection)
    return collection


def _unlink_collection_from_other_scenes(collection, keep_scene):
    for scene in bpy.data.scenes:
        if scene == keep_scene:
            continue
        for child in list(scene.collection.children):
            if child == collection:
                scene.collection.children.unlink(collection)


def _move_object_to_collection(obj, target):
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    target.objects.link(obj)


def remove_lights_and_legacy_ground(artist):
    removed_lights = sorted(obj.name for obj in bpy.data.objects if obj.type == "LIGHT")
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)
    for light in list(bpy.data.lights):
        if light.users == 0:
            bpy.data.lights.remove(light)

    ground = bpy.data.objects.get(GROUND_OBJECT_NAME)
    removed_ground = ground is not None
    if ground is not None:
        mesh = ground.data if ground.type == "MESH" else None
        bpy.data.objects.remove(ground, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    camera = bpy.data.objects.get("蝴蝶_英雄相机")
    ensure(camera is not None and camera.type == "CAMERA", "缺少蝴蝶英雄相机")
    camera_collection = _get_or_create_collection(artist, CAMERA_COLLECTION_NAME)
    _unlink_collection_from_other_scenes(camera_collection, artist)
    _move_object_to_collection(camera, camera_collection)

    for name in ("LIGHTS_Butterfly_Master_摄影灯光", "ENVIRONMENT_Butterfly_Master_展示环境"):
        collection = bpy.data.collections.get(name)
        if collection is not None and not collection.objects and not collection.children:
            bpy.data.collections.remove(collection)

    ensure(not bpy.data.lights, "删除后仍存在灯光数据块")
    return {
        "removed_lights": removed_lights,
        "removed_legacy_ground": removed_ground,
        "camera_collection": camera_collection.name,
    }


def import_specimen_frame(artist, frame_glb_path):
    frame_glb_path = Path(frame_glb_path).resolve()
    ensure(frame_glb_path.is_file(), f"标本框 GLB 不存在: {frame_glb_path}")

    old_frame = bpy.data.objects.get(FRAME_OBJECT_NAME)
    if old_frame is not None:
        old_mesh = old_frame.data if old_frame.type == "MESH" else None
        bpy.data.objects.remove(old_frame, do_unlink=True)
        if old_mesh is not None and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)

    frame_collection = _get_or_create_collection(artist, FRAME_COLLECTION_NAME)
    _unlink_collection_from_other_scenes(frame_collection, artist)
    for obj in list(frame_collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    before = set(bpy.data.objects)
    if bpy.context.window:
        bpy.context.window.scene = artist
    bpy.ops.import_scene.gltf(filepath=str(frame_glb_path), import_pack_images=True)
    imported = [obj for obj in bpy.data.objects if obj not in before]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    ensure(len(meshes) == 1, f"标本框 GLB 应只导入一个网格，实际为 {len(meshes)}")
    frame = meshes[0]
    frame.name = FRAME_OBJECT_NAME
    frame.data.name = "SPECIMEN_FRAME_MATERIAL_SLOTS_MESH"
    _move_object_to_collection(frame, frame_collection)
    for obj in imported:
        if obj != frame and obj.type == "EMPTY" and not obj.children:
            bpy.data.objects.remove(obj, do_unlink=True)

    frame["asset_role"] = "vertical_landing_surface"
    frame["source_glb"] = "models/SpecimenFrame/source/specimen-frame.glb"
    frame["front_surface_x"] = FRAME_FRONT_X
    ensure(all(abs(left - right) <= 0.0001 for left, right in zip(frame.dimensions, (0.42, 9.1, 9.1))), f"标本框尺寸异常: {tuple(frame.dimensions)}")
    ensure(len(frame.material_slots) == 2, "标本框必须保留外框与内板两个材质槽")
    return frame


def pose_butterfly_on_frame(artist):
    root = bpy.data.objects.get(DISPLAY_ROOT_NAME)
    ensure(root is not None and root.type == "EMPTY", "缺少蝴蝶展示根")
    direct_children = [obj for obj in artist.objects if obj.parent == root]
    ensure(len(direct_children) == 1 and direct_children[0].type == "EMPTY", "展示根下应只有一个 FBX 层级根")
    fbx_root = direct_children[0]
    display_meshes = [obj for obj in artist.objects if obj.type == "MESH" and _is_descendant(obj, root)]
    ensure(len(display_meshes) == 3, f"展示蝴蝶应由身体和左右翅膀三个网格组成，实际为 {len(display_meshes)}")
    body = next((obj for obj in display_meshes if "BODY" in obj.name.upper()), None)
    wings = [obj for obj in display_meshes if "WING" in obj.name.upper()]
    ensure(body is not None and len(wings) == 2, "展示蝴蝶缺少身体或左右翅膀网格")

    if "frame_attachment_source_display_scale" not in root:
        root["frame_attachment_source_display_scale"] = float(root.scale.x)
        root["frame_attachment_source_fbx_location"] = list(fbx_root.location)
        root["frame_attachment_source_fbx_scale"] = list(fbx_root.scale)
    source_display_scale = float(root["frame_attachment_source_display_scale"])
    source_fbx_location = Vector(root["frame_attachment_source_fbx_location"])
    source_fbx_scale = Vector(root["frame_attachment_source_fbx_scale"])

    root.location = (CONTACT_X, 0.0, FRAME_CENTER_Z)
    orientation = Matrix.Rotation(-math.pi / 2.0, 4, "X") @ Matrix.Rotation(-math.pi / 2.0, 4, "Y")
    root.rotation_mode = "XYZ"
    root.rotation_euler = orientation.to_euler("XYZ")
    # Preserve the native model proportions.  The wing actions are retargeted to
    # side-specific panel-safe ranges below, so the animated geometry neither
    # crosses the frame nor exchanges anatomical sides.
    root.scale = (1.0, 1.0, 1.0)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.45

    fbx_root.location = source_fbx_location
    fbx_root.scale = source_fbx_scale * source_display_scale
    wing_retarget = _retarget_wings_to_panel_safe_ranges(artist, wings)
    bpy.context.view_layer.update()
    initial = _animated_bounds(artist, display_meshes)
    span = initial["max"] - initial["min"]
    fit = min(CORE_FIT_SIZE / span.y, CORE_FIT_SIZE / span.z, 1.0)
    ensure(fit > 0.0, f"蝴蝶拟合比例异常: {fit}")
    fbx_root.scale *= fit
    bpy.context.view_layer.update()

    fitted = _animated_bounds(artist, display_meshes)
    center = (fitted["min"] + fitted["max"]) * 0.5
    body_bounds = _world_bounds([body])
    world_shift = Vector((CONTACT_X - body_bounds["min"].x, -center.y, FRAME_CENTER_Z - center.z))
    local_shift = root.matrix_world.inverted().to_3x3() @ world_shift
    fbx_root.location += local_shift
    bpy.context.view_layer.update()
    final = _animated_bounds(artist, display_meshes)

    body_bounds = _world_bounds([body])
    body_center_y = (body_bounds["min"].y + body_bounds["max"].y) * 0.5
    body_line_shift = Vector((0.0, -body_center_y, 0.0))
    fbx_root.location += root.matrix_world.inverted().to_3x3() @ body_line_shift
    bpy.context.view_layer.update()
    final = _animated_bounds(artist, display_meshes)
    body_bounds = _world_bounds([body])
    body_span = body_bounds["max"] - body_bounds["min"]
    body_center_y = (body_bounds["min"].y + body_bounds["max"].y) * 0.5
    final_span = final["max"] - final["min"]

    ensure(abs(body_bounds["min"].x - CONTACT_X) <= 0.0001, f"蝴蝶身体没有贴合框面: x={body_bounds['min'].x}")
    ensure(final["min"].x >= FRAME_FRONT_X, f"翅膀穿入标本框: x={final['min'].x}")
    ensure(final["min"].y >= -CORE_HALF_SIZE and final["max"].y <= CORE_HALF_SIZE, f"蝴蝶 Y 范围超出内芯: {final}")
    ensure(final["min"].z >= FRAME_CENTER_Z - CORE_HALF_SIZE and final["max"].z <= FRAME_CENTER_Z + CORE_HALF_SIZE, f"蝴蝶 Z 范围超出内芯: {final}")
    ensure(abs(body_center_y) <= 0.0001, f"蝴蝶身体没有落在 Y=0 的 Z 向中心线上: y={body_center_y}")
    ensure(body_span.z >= body_span.y * 1.5, f"蝴蝶身体主轴没有沿世界 Z 方向: span={tuple(body_span)}")
    ensure(final_span.x >= MIN_NATIVE_DEPTH, f"蝴蝶三维深度被异常压扁: depth={final_span.x}")

    root["frame_attachment_configured"] = True
    root["placement_role"] = "attached_to_vertical_specimen_frame"
    root["contact_plane_x"] = FRAME_FRONT_X
    root["clearance"] = CONTACT_X - FRAME_FRONT_X
    root["all_animation_frames_fit_core"] = True
    root["body_axis"] = "world_Z"
    root["body_center_y"] = body_center_y
    root["native_proportions_preserved"] = True
    root["wing_mount_policy"] = "source_timing_affine_retargeted_to_anatomical_panel_safe_ranges"
    root["wing_panel_safe_range_left"] = list(PANEL_SAFE_WING_RANGES["left"])
    root["wing_panel_safe_range_right"] = list(PANEL_SAFE_WING_RANGES["right"])
    root["all_frame_bounds_min"] = list(final["min"])
    root["all_frame_bounds_max"] = list(final["max"])
    return {
        "display_root": root.name,
        "fbx_root": fbx_root.name,
        "rotation_euler_degrees": [math.degrees(value) for value in root.rotation_euler],
        "fit_scale": fit,
        "all_frame_bounds_min": list(final["min"]),
        "all_frame_bounds_max": list(final["max"]),
        "all_frame_span": list(final_span),
        "contact_x": CONTACT_X,
        "body_center_y": body_center_y,
        "body_span": list(body_span),
        "body_axis": "world_Z",
        "native_proportions_preserved": True,
        "wing_panel_safe_retarget": wing_retarget,
    }


def _look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_camera_and_world(artist):
    camera = bpy.data.objects.get("蝴蝶_英雄相机")
    ensure(camera is not None and camera.type == "CAMERA", "缺少构图相机")
    camera.location = (18.0, 0.0, FRAME_CENTER_Z)
    _look_at(camera, (0.0, 0.0, FRAME_CENTER_Z))
    camera.data.type = "PERSP"
    camera.data.lens = 54.0
    camera.data.sensor_width = 36.0
    camera.data.dof.use_dof = False
    artist.camera = camera

    world = artist.world
    if world is None:
        world = bpy.data.worlds.new("WORLD_Butterfly_Frame_Attachment")
        artist.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    ensure(background is not None, "World 缺少 Background 节点")
    background.inputs["Color"].default_value = (0.12, 0.14, 0.18, 1.0)
    background.inputs["Strength"].default_value = 1.0
    world.color = (0.12, 0.14, 0.18)
    world["lighting_policy"] = "world_environment_only_no_light_objects"

    artist.render.engine = "BLENDER_EEVEE"
    artist.render.resolution_x = 900
    artist.render.resolution_y = 900
    artist.render.resolution_percentage = 100
    artist.render.image_settings.file_format = "PNG"
    artist.render.film_transparent = False
    artist.render.image_settings.color_mode = "RGBA"
    artist.render.image_settings.color_depth = "8"
    artist.render.fps = 30
    if hasattr(artist, "eevee"):
        artist.eevee.taa_render_samples = 128
    return {"camera": camera.name, "world": world.name, "light_objects": 0}


def configure_attachment(artist, source_scene, frame_glb_path):
    original_frame = artist.frame_current
    if bpy.context.window:
        bpy.context.window.scene = artist
    lighting = remove_lights_and_legacy_ground(artist)
    frame = import_specimen_frame(artist, frame_glb_path)
    placement = pose_butterfly_on_frame(artist)
    presentation = configure_camera_and_world(artist)
    artist["document_type"] = "Butterfly wing-flap attached to vertical specimen frame"
    artist["frame_attachment_source"] = "models/SpecimenFrame/source/specimen-frame.glb"
    artist["frame_is_landing_surface"] = True
    artist["lights_removed"] = True
    artist.frame_set(original_frame)
    bpy.context.view_layer.update()
    if source_scene is not None:
        source_scene["source_reference_policy"] = "源对象与源动画保持不变；标本框仅存在于 ARTIST_EDIT"
    bpy.ops.file.pack_all()
    return {"lighting": lighting, "frame": frame.name, "placement": placement, "presentation": presentation}


def validate_attachment(artist, source_scene):
    ensure(not [obj for obj in bpy.data.objects if obj.type == "LIGHT"], "文件中仍有灯光对象")
    ensure(not bpy.data.lights, "文件中仍有灯光数据块")
    ensure(not bpy.data.libraries, "组合场景不应依赖外部 Blender Library")
    ensure(bpy.data.objects.get(GROUND_OBJECT_NAME) is None, "旧水平展示台仍存在")
    frame = bpy.data.objects.get(FRAME_OBJECT_NAME)
    ensure(frame is not None and frame.type == "MESH", "缺少标本框网格")
    ensure(len(frame.material_slots) == 2, "标本框材质槽数量错误")
    ensure(all(abs(left - right) <= 0.0001 for left, right in zip(frame.dimensions, (0.42, 9.1, 9.1))), f"标本框尺寸错误: {tuple(frame.dimensions)}")
    ensure(FRAME_COLLECTION_NAME in {collection.name for collection in frame.users_collection}, "标本框未归入专用集合")
    if source_scene is not None:
        ensure(frame.name not in {obj.name for obj in source_scene.objects}, "标本框不应链接到 SOURCE_REFERENCE")
    root = bpy.data.objects.get(DISPLAY_ROOT_NAME)
    ensure(root is not None and root.get("frame_attachment_configured") is True, "蝴蝶展示根未配置框内依附")
    expected = Matrix.Rotation(-math.pi / 2.0, 4, "X") @ Matrix.Rotation(-math.pi / 2.0, 4, "Y")
    actual = root.matrix_world.to_3x3().normalized()
    ensure(max(abs(actual[row][column] - expected[row][column]) for row in range(3) for column in range(3)) <= 0.0001, f"蝴蝶展示根旋转错误: {tuple(root.rotation_euler)}")
    ensure(all(abs(left - right) <= 0.0001 for left, right in zip(root.scale, (1.0, 1.0, 1.0))), f"蝴蝶原生比例未保留: {tuple(root.scale)}")
    display_meshes = [obj for obj in artist.objects if obj.type == "MESH" and _is_descendant(obj, root)]
    recomputed = _animated_bounds(artist, display_meshes)
    minimum = recomputed["min"]
    maximum = recomputed["max"]
    stored_minimum = Vector(root["all_frame_bounds_min"])
    stored_maximum = Vector(root["all_frame_bounds_max"])
    ensure(max(abs(left - right) for left, right in zip(minimum, stored_minimum)) <= 0.0001, "重开后动画最小包围盒与构建记录不一致")
    ensure(max(abs(left - right) for left, right in zip(maximum, stored_maximum)) <= 0.0001, "重开后动画最大包围盒与构建记录不一致")
    ensure(minimum.x >= FRAME_FRONT_X, "蝴蝶动画穿入标本框")
    ensure(minimum.y >= -CORE_HALF_SIZE and maximum.y <= CORE_HALF_SIZE, "蝴蝶越出内芯 Y 边界")
    ensure(minimum.z >= FRAME_CENTER_Z - CORE_HALF_SIZE and maximum.z <= FRAME_CENTER_Z + CORE_HALF_SIZE, "蝴蝶越出内芯 Z 边界")
    body = next((obj for obj in artist.objects if obj.type == "MESH" and obj.name.startswith("展示_") and "BODY" in obj.name.upper()), None)
    ensure(body is not None, "缺少展示身体网格")
    body_bounds = _world_bounds([body])
    body_span = body_bounds["max"] - body_bounds["min"]
    body_center_y = (body_bounds["min"].y + body_bounds["max"].y) * 0.5
    ensure(abs(body_center_y) <= 0.0001, f"身体未落在 Y=0 的 Z 向中心线: y={body_center_y}")
    ensure(body_span.z >= body_span.y * 1.5, f"身体主轴未沿世界 Z 方向: span={tuple(body_span)}")
    ensure(abs(body_bounds["min"].x - CONTACT_X) <= 0.0001, "蝴蝶身体未贴合框面")
    ensure(maximum.x - minimum.x >= MIN_NATIVE_DEPTH, "蝴蝶模型被压成平面层")
    wings = [obj for obj in display_meshes if "WING" in obj.name.upper()]
    ensure(len(wings) == 2, "展示层左右翅膀数量错误")
    wing_retarget = {}
    side_extrema = {"left_max_y": -math.inf, "right_min_y": math.inf}
    hinge_gap_max = {"left": 0.0, "right": 0.0}
    rotation_ranges = {"left": [math.inf, -math.inf], "right": [math.inf, -math.inf]}
    for wing in wings:
        role = _wing_role(wing)
        ensure(role in PANEL_SAFE_WING_RANGES, f"无法识别翅膀方向: {wing.name}")
        source_range = wing.get("frame_attachment_retarget_source_range")
        target_range = wing.get("frame_attachment_retarget_target_range")
        scale = wing.get("frame_attachment_retarget_scale")
        offset = wing.get("frame_attachment_retarget_offset")
        ensure(source_range is not None and target_range is not None and scale is not None and offset is not None, f"翅膀缺少面板安全区间重定向记录: {wing.name}")
        ensure(max(abs(float(left) - right) for left, right in zip(target_range, PANEL_SAFE_WING_RANGES[role])) <= 0.0001, f"翅膀目标安全区间错误: {wing.name}")
        wing_retarget[role] = {
            "source_range": [float(value) for value in source_range],
            "target_range": [float(value) for value in target_range],
            "scale": float(scale),
            "offset": float(offset),
        }

    original_frame = artist.frame_current
    for frame_number in range(artist.frame_start, artist.frame_end + 1):
        artist.frame_set(frame_number)
        bpy.context.view_layer.update()
        for wing in wings:
            role = _wing_role(wing)
            bounds = _world_bounds([wing])
            rotation_ranges[role][0] = min(rotation_ranges[role][0], float(wing.rotation_euler.z))
            rotation_ranges[role][1] = max(rotation_ranges[role][1], float(wing.rotation_euler.z))
            hinge_gap_max[role] = max(hinge_gap_max[role], _minimum_surface_distance(wing, body))
            if role == "left":
                side_extrema["left_max_y"] = max(side_extrema["left_max_y"], bounds["max"].y)
            else:
                side_extrema["right_min_y"] = min(side_extrema["right_min_y"], bounds["min"].y)
    artist.frame_set(original_frame)
    bpy.context.view_layer.update()

    ensure(side_extrema["left_max_y"] <= WING_CENTERLINE_TOLERANCE, f"左翼在动画中越过身体中线: y={side_extrema['left_max_y']}")
    ensure(side_extrema["right_min_y"] >= -WING_CENTERLINE_TOLERANCE, f"右翼在动画中越过身体中线: y={side_extrema['right_min_y']}")
    ensure(max(hinge_gap_max.values()) <= MAX_WING_HINGE_GAP, f"翅根在动画中脱离身体: {hinge_gap_max}")
    for role, target_range in PANEL_SAFE_WING_RANGES.items():
        ensure(max(abs(left - right) for left, right in zip(rotation_ranges[role], target_range)) <= 0.0001, f"{role} 翅膀实际旋转范围与安全区间不一致: {rotation_ranges[role]}")
    unpacked_images = [image.name for image in bpy.data.images if image.source == "FILE" and image.packed_file is None]
    ensure(not unpacked_images, f"存在未打包图像: {unpacked_images}")
    return {
        "lights": 0,
        "legacy_ground": False,
        "frame": frame.name,
        "frame_material_slots": [slot.material.name if slot.material else None for slot in frame.material_slots],
        "display_root": root.name,
        "display_root_location": list(root.location),
        "display_root_rotation_degrees": [math.degrees(value) for value in root.rotation_euler],
        "all_frame_bounds_min": list(minimum),
        "all_frame_bounds_max": list(maximum),
        "all_frame_bounds_recomputed_after_reopen": True,
        "source_reference_has_frame": False,
        "body_center_y": body_center_y,
        "body_span": list(body_span),
        "body_axis": "world_Z",
        "native_proportions_preserved": True,
        "panel_normal_depth": maximum.x - minimum.x,
        "wing_panel_safe_retarget": wing_retarget,
        "wing_rotation_ranges": rotation_ranges,
        "wing_centerline_extrema": side_extrema,
        "wing_hinge_gap_max": hinge_gap_max,
        "packed_file_images": sorted(image.name for image in bpy.data.images if image.source == "FILE" and image.packed_file is not None),
        "external_libraries": 0,
    }
