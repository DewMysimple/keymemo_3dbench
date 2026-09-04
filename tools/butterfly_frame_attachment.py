"""Shared construction helpers for the Butterfly specimen-frame variants."""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


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
OUTWARD_WING_CENTERS = {"left": -math.pi / 2.0, "right": math.pi / 2.0}


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


def _shift_curve(curve, offset):
    for keyframe in curve.keyframe_points:
        keyframe.co.y += offset
        keyframe.handle_left.y += offset
        keyframe.handle_right.y += offset
    curve.update()


def _wing_role(obj):
    lowered = obj.name.lower()
    if "left" in lowered:
        return "left"
    if "right" in lowered:
        return "right"
    return None


def _rebase_wings_outward(scene, wings):
    """Keep source flap deltas, but mount the flap entirely in front of the panel."""
    original_frame = scene.frame_current
    offsets = {}
    ranges = {}
    for wing in wings:
        role = _wing_role(wing)
        ensure(role in OUTWARD_WING_CENTERS, f"无法识别翅膀方向: {wing.name}")
        ensure(wing.animation_data and wing.animation_data.action, f"翅膀缺少 Action: {wing.name}")
        values = []
        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            values.append(float(wing.rotation_euler.z))
        source_min = min(values)
        source_max = max(values)
        offset = OUTWARD_WING_CENTERS[role] - (source_min + source_max) * 0.5
        curve = next(
            (
                curve
                for curve in _action_fcurves(wing.animation_data.action)
                if curve.data_path == "rotation_euler" and curve.array_index == 2
            ),
            None,
        )
        ensure(curve is not None, f"翅膀 Action 缺少 Z 旋转曲线: {wing.name}")
        _shift_curve(curve, offset)
        wing["frame_attachment_outward_rebase"] = offset
        wing["frame_attachment_outward_center"] = OUTWARD_WING_CENTERS[role]
        wing.animation_data.action["frame_attachment_outward_rebase"] = offset
        wing.animation_data.action["frame_attachment_outward_center"] = OUTWARD_WING_CENTERS[role]
        offsets[role] = offset
        ranges[role] = [source_min + offset, source_max + offset]
    scene.frame_set(original_frame)
    bpy.context.view_layer.update()
    return {"offsets": offsets, "ranges": ranges}


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
    # Preserve the native model proportions.  The wing actions are rebased around
    # outward-facing mount angles below, so the animated geometry never crosses
    # the frame instead of being flattened into a billboard-like layer.
    root.scale = (1.0, 1.0, 1.0)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.45

    fbx_root.location = source_fbx_location
    fbx_root.scale = source_fbx_scale * source_display_scale
    wing_rebase = _rebase_wings_outward(artist, wings)
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
    root["wing_mount_policy"] = "source_flap_deltas_rebased_outward"
    root["wing_outward_rebase_left"] = wing_rebase["offsets"]["left"]
    root["wing_outward_rebase_right"] = wing_rebase["offsets"]["right"]
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
        "wing_outward_rebase": wing_rebase,
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
    wing_rebase = {}
    for wing in wings:
        role = _wing_role(wing)
        offset = wing.get("frame_attachment_outward_rebase")
        ensure(role in OUTWARD_WING_CENTERS and offset is not None, f"翅膀缺少向外安装基准: {wing.name}")
        ensure(abs(float(wing.get("frame_attachment_outward_center")) - OUTWARD_WING_CENTERS[role]) <= 0.0001, f"翅膀向外中心角错误: {wing.name}")
        wing_rebase[role] = float(offset)
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
        "wing_outward_rebase": wing_rebase,
        "packed_file_images": sorted(image.name for image in bpy.data.images if image.source == "FILE" and image.packed_file is not None),
        "external_libraries": 0,
    }
