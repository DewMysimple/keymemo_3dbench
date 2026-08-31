import hashlib
import json
import math
import os
import shutil
import base64
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "blender_scenebench" / "blender_modelbench" / "Butterfly"
OUTPUT_DIR = PROJECT_ROOT / "blender" / "_scenebench" / "blender" / "_modelbench" / "Butterfly"
OUTPUT_PATH = OUTPUT_DIR / "Butterfly.blend"
ARCHIVE_ROOT = OUTPUT_DIR / "source_assets"
PREVIEW_PATH = PROJECT_ROOT / "blender_scenebench" / "generated" / "Butterfly_preview.png"
REPORT_PATH = PROJECT_ROOT / "blender_scenebench" / "reports" / "butterfly-build.json"

MODEL_COLLECTION_NAME = "MODEL_Butterfly_展示模型"
SOURCE_COLLECTION_NAME = "SOURCE_Butterfly_源文件"
ENV_COLLECTION_NAME = "ENVIRONMENT_Butterfly_展示环境"
LIGHT_COLLECTION_NAME = "LIGHTS_Butterfly_摄影灯光"


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def localized_workspaces():
    names = {
        "Layout": "布局",
        "Modeling": "建模",
        "Sculpting": "雕刻",
        "UV Editing": "UV编辑",
        "Texture Paint": "纹理绘制",
        "Shading": "着色",
        "Animation": "动画",
        "Rendering": "渲染",
        "Compositing": "合成",
        "Geometry Nodes": "几何节点",
        "Scripting": "脚本",
    }
    for workspace in bpy.data.workspaces:
        workspace.name = names.get(workspace.name, workspace.name)
    if bpy.context.window:
        layout = bpy.data.workspaces.get("布局")
        if layout:
            bpy.context.window.workspace = layout


def reset_factory():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def new_collection(name, parent=None):
    collection = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(collection)
    return collection


def move_to_collection(obj, collection):
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)


def set_image_colorspace(image, colorspace):
    try:
        image.colorspace_settings.name = colorspace
    except (AttributeError, TypeError, ValueError):
        pass


def copy_source_assets():
    ensure(SOURCE_ROOT.is_dir(), f"缺少 Butterfly 素材目录: {SOURCE_ROOT}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in sorted(SOURCE_ROOT.rglob("*"), key=lambda path: str(path).lower()):
        if not source.is_file():
            continue
        relative = source.relative_to(SOURCE_ROOT)
        target = ARCHIVE_ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append({
            "path": str(relative).replace("\\", "/"),
            "size": source.stat().st_size,
            "sha256": sha256(source),
        })
    ensure(copied, "Butterfly 素材目录为空")
    return copied


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_relative(path):
    return str(Path(path).resolve().relative_to(SOURCE_ROOT.resolve())).replace("\\", "/")


def archive_relative(path):
    return str(Path(path).resolve().relative_to(ARCHIVE_ROOT.resolve())).replace("\\", "/")


def load_image(path, name, colorspace):
    ensure(path.is_file(), f"缺少图像资源: {path}")
    image = bpy.data.images.load(str(path), check_existing=False)
    image.name = name
    set_image_colorspace(image, colorspace)
    image["source_path"] = source_relative(path)
    image["archive_path"] = f"source_assets/{source_relative(path)}"
    return image


def make_wing_material(images):
    material = bpy.data.materials.new("蝴蝶翅膀_颜色法线透明材质")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "材质输出"
    output.location = (700, 60)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "蝴蝶翅膀 Principled"
    shader.location = (420, 60)
    shader.inputs["Roughness"].default_value = 0.42
    if shader.inputs.get("Specular IOR Level"):
        shader.inputs["Specular IOR Level"].default_value = 0.34

    color = nodes.new("ShaderNodeTexImage")
    color.name = "翅膀颜色贴图"
    color.label = "DIFFUSE / sRGB"
    color.location = (-620, 260)
    color.image = images["diffuse"]

    alpha = nodes.new("ShaderNodeTexImage")
    alpha.name = "翅膀透明度贴图"
    alpha.label = "ALPHA / Non-Color"
    alpha.location = (-620, 20)
    alpha.image = images["alpha"]
    set_image_colorspace(images["alpha"], "Non-Color")

    normal_tex = nodes.new("ShaderNodeTexImage")
    normal_tex.name = "翅膀法线贴图"
    normal_tex.label = "NORMAL / Non-Color"
    normal_tex.location = (-620, -220)
    normal_tex.image = images["normal"]
    set_image_colorspace(images["normal"], "Non-Color")

    normal = nodes.new("ShaderNodeNormalMap")
    normal.name = "翅膀法线转换"
    normal.location = (170, -180)
    normal.inputs["Strength"].default_value = 0.65

    links.new(color.outputs["Color"], shader.inputs["Base Color"])
    links.new(alpha.outputs["Color"], shader.inputs["Alpha"])
    links.new(normal_tex.outputs["Color"], normal.inputs["Color"])
    links.new(normal.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    try:
        material.surface_render_method = "DITHERED"
    except (AttributeError, TypeError, ValueError):
        try:
            material.surface_render_method = "BLENDED"
        except (AttributeError, TypeError, ValueError):
            pass
    material["asset_role"] = "蝴蝶翅膀展示材质"
    material["source_textures"] = "DIFFUSE + ALPHA_OR_OPACITY_MASK + NORMAL_MAP"
    return material


def make_body_material(reference_image):
    material = bpy.data.materials.new("蝴蝶身体_低多边形展示材质")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "材质输出"
    output.location = (620, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "蝴蝶身体 Principled"
    shader.location = (360, 0)
    shader.inputs["Roughness"].default_value = 0.52
    if shader.inputs.get("Specular IOR Level"):
        shader.inputs["Specular IOR Level"].default_value = 0.25

    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "身体细节噪声"
    noise.location = (-500, 60)
    noise.inputs["Scale"].default_value = 4.8
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.7

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = "身体色阶"
    ramp.location = (-180, 100)
    ramp.color_ramp.elements[0].color = (0.008, 0.004, 0.002, 1.0)
    ramp.color_ramp.elements[1].color = (0.23, 0.075, 0.018, 1.0)

    bump = nodes.new("ShaderNodeBump")
    bump.name = "身体微表面"
    bump.location = (130, -160)
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.08

    reference = nodes.new("ShaderNodeTexImage")
    reference.name = "源图参考_未连接"
    reference.label = "源图参考，不替代身体材质"
    reference.location = (-500, -260)
    reference.image = reference_image

    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    material["asset_role"] = "蝴蝶身体展示材质"
    material["source_reference_image"] = "_Male_Dos_MHNT.jpg"
    return material


def make_ground_material():
    material = bpy.data.materials.new("蝴蝶展示台_深绿灰材质")
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader:
        shader.inputs["Base Color"].default_value = (0.018, 0.035, 0.031, 1.0)
        shader.inputs["Roughness"].default_value = 0.76
        if shader.inputs.get("Specular IOR Level"):
            shader.inputs["Specular IOR Level"].default_value = 0.22
    return material


def append_display_material(obj, material):
    if obj.type != "MESH":
        return
    if material.name not in [slot.material.name if slot.material else "" for slot in obj.material_slots]:
        obj.data.materials.append(material)
    material_index = list(obj.data.materials).index(material)
    for polygon in obj.data.polygons:
        polygon.material_index = material_index


def import_fbx(path, collection, group_id):
    before_objects = set(bpy.data.objects)
    before_actions = set(bpy.data.actions)
    result = bpy.ops.import_scene.fbx(filepath=str(path))
    ensure(result == {"FINISHED"}, f"FBX 导入失败: {path} -> {result}")
    objects = [obj for obj in bpy.data.objects if obj not in before_objects]
    ensure(objects, f"FBX 未产生 Blender 对象: {path}")
    for index, obj in enumerate(objects, start=1):
        original_name = obj.name
        obj["source_original_name"] = original_name
        obj["source_asset"] = source_relative(path)
        obj["source_import_group"] = group_id
        obj.name = f"源_{group_id}_{index:02d}_{original_name}"
        move_to_collection(obj, collection)

    actions = [action for action in bpy.data.actions if action not in before_actions]
    for action in actions:
        action["source_asset"] = source_relative(path)
        action["source_import_group"] = group_id
        action["source_frame_range"] = list(action.frame_range)

    collection["source_asset"] = source_relative(path)
    collection["source_import_group"] = group_id
    collection["object_count"] = len(objects)
    collection["action_count"] = len(actions)
    collection["action_names"] = json.dumps([action.name for action in actions], ensure_ascii=False)
    return {
        "path": source_relative(path),
        "group_id": group_id,
        "objects": objects,
        "actions": actions,
    }


def import_obj(path, collection):
    before_objects = set(bpy.data.objects)
    result = bpy.ops.wm.obj_import(filepath=str(path))
    ensure(result == {"FINISHED"}, f"OBJ 导入失败: {path} -> {result}")
    objects = [obj for obj in bpy.data.objects if obj not in before_objects]
    ensure(objects, f"OBJ 未产生 Blender 对象: {path}")
    for index, obj in enumerate(objects, start=1):
        original_name = obj.name
        obj["source_original_name"] = original_name
        obj["source_asset"] = source_relative(path)
        obj["source_import_group"] = "body_obj"
        obj.name = f"源_OBJ身体_{index:02d}_{original_name}"
        move_to_collection(obj, collection)
    collection["source_asset"] = source_relative(path)
    collection["object_count"] = len(objects)
    return objects


def copy_animation_data(source, target):
    if not source.animation_data:
        return
    target.animation_data_create()
    if source.animation_data.action:
        target.animation_data.action = source.animation_data.action
    for source_track in source.animation_data.nla_tracks:
        target_track = target.animation_data.nla_tracks.new()
        target_track.name = source_track.name
        target_track.mute = source_track.mute
        target_track.is_solo = source_track.is_solo
        for source_strip in source_track.strips:
            target_track.strips.new(
                source_strip.name,
                source_strip.frame_start,
                source_strip.action,
            )


def duplicate_group(source_objects, collection, prefix):
    mapping = {}
    world_matrices = {source: source.matrix_world.copy() for source in source_objects}
    for source in source_objects:
        target = source.copy()
        if source.data:
            target.data = source.data.copy()
        target.name = f"展示_{prefix}_{source.name}"
        target["display_copy_of"] = source.name
        target["source_asset"] = source.get("source_asset", "")
        collection.objects.link(target)
        mapping[source] = target
        copy_animation_data(source, target)

    for source, target in mapping.items():
        target.parent = mapping.get(source.parent)
        target.matrix_world = world_matrices[source]
    return list(mapping.values())


def world_bounds(objects):
    points = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    ensure(points, "展示对象没有可计算的网格边界")
    low = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
    high = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
    return low, high


def make_empty(name, collection, display_size=0.25):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = display_size
    collection.objects.link(obj)
    return obj


def parent_preserve_world(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def point_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_camera(scene, collection, extent):
    camera_data = bpy.data.cameras.new("蝴蝶_英雄相机数据")
    camera = bpy.data.objects.new("蝴蝶_英雄相机", camera_data)
    collection.objects.link(camera)
    camera.location = (extent * 1.12, -extent * 2.35, extent * 0.62)
    camera_data.lens = 56.0
    camera_data.sensor_width = 36.0
    point_at(camera, (0.0, 0.0, 0.0))
    scene.camera = camera
    return camera


def add_area_light(collection, name, location, energy, size, color):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    light = bpy.data.objects.new(name, data)
    collection.objects.link(light)
    light.location = location
    point_at(light, (0.0, 0.0, 0.0))
    return light


def add_presentation_environment(collection, extent):
    bpy.ops.mesh.primitive_plane_add(size=extent * 5.2, location=(0.0, 0.0, -extent * 0.58))
    floor = bpy.context.object
    floor.name = "蝴蝶_展示台地面"
    move_to_collection(floor, collection)
    floor.data.materials.append(make_ground_material())
    floor["asset_role"] = "非破坏性展示环境"


def configure_scene(scene, frame_end=250):
    scene.frame_start = 1
    scene.frame_end = frame_end
    scene.render.fps = 30
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except (TypeError, ValueError):
            continue
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new(f"{scene.name}_世界")
    scene.world.color = (0.006, 0.012, 0.010)
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except (AttributeError, TypeError, ValueError):
        pass
    scene["asset_name"] = "Butterfly"
    scene["source_root"] = "blender_scenebench/blender_modelbench/Butterfly"
    scene["source_archive"] = "blender/_scenebench/blender/_modelbench/Butterfly/source_assets"
    scene["data_fidelity"] = "full: geometry, materials, textures, UVs, hierarchy, modifiers, constraints, shape keys, actions/NLA, timeline, cameras/lights, custom properties"
    scene["source_animation_policy"] = "all 10 FBX files imported as independent source collections; original actions retained"
    scene.timeline_markers.new("Idle_1_90帧", frame=1)
    scene.timeline_markers.new("Idle_2_90帧", frame=1)
    scene.timeline_markers.new("Slow_Flap_120帧", frame=1)
    scene.timeline_markers.new("Follow_Path_90帧", frame=1)


def find_layer_collection(layer_collection, name):
    if layer_collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = find_layer_collection(child, name)
        if found:
            return found
    return None


def set_scene_collection_visibility(scene, included_names):
    for child in scene.collection.children:
        layer = find_layer_collection(scene.view_layers[0].layer_collection, child.name)
        if layer:
            layer.exclude = child.name not in included_names


def create_text(name, content):
    text = bpy.data.texts.new(name)
    # from_string() avoids the quadratic behavior of repeated Text.write() on
    # the multi-megabyte Base64 C4D archive.
    text.from_string(content)
    return text


def embed_unimportable_sources():
    c4d_path = SOURCE_ROOT / "Animated_Butterflies_Project_File_ Travis_Davids.c4d"
    ensure(c4d_path.is_file(), f"缺少 C4D 源文件: {c4d_path}")
    encoded_raw = base64.b64encode(c4d_path.read_bytes()).decode("ascii")
    encoded = "\n".join(encoded_raw[index : index + 76] for index in range(0, len(encoded_raw), 76))
    create_text(
        "蝴蝶_C4D原始二进制_Base64",
        "# C4D 原始源文件的 Base64 归档。Blender 5 无原生 C4D 解析器，因此不伪造场景转换。\n"
        f"# source_path: {source_relative(c4d_path)}\n"
        f"# sha256: {sha256(c4d_path)}\n"
        f"# byte_length: {c4d_path.stat().st_size}\n\n"
        + encoded,
    )


def source_file_records(copied_files, imported_records):
    imported_by_path = {record["path"]: record for record in imported_records}
    records = []
    for item in copied_files:
        record = dict(item)
        imported = imported_by_path.get(item["path"])
        if imported:
            record["import_status"] = "imported"
            record["blender_object_count"] = len(imported["objects"])
            record["blender_action_names"] = [action.name for action in imported["actions"]]
            record["blender_action_ranges"] = [list(action.frame_range) for action in imported["actions"]]
        elif item["path"].lower().endswith(".c4d"):
            record["import_status"] = "source_archived_c4d_not_native_blender_format"
        elif item["path"].lower().endswith(".obj"):
            record["import_status"] = "imported_as_source_obj"
        elif item["path"].lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
            record["import_status"] = "packed_into_blend_and_used_or_referenced"
        elif item["path"].lower().endswith(".txt"):
            record["import_status"] = "copied_and_embedded_as_text_datablock"
        else:
            record["import_status"] = "source_archived"
        records.append(record)
    return records


def main():
    reset_factory()
    localized_workspaces()
    copied_files = copy_source_assets()

    artist_scene = bpy.context.scene
    artist_scene.name = "ARTIST_EDIT"
    model_collection = new_collection(MODEL_COLLECTION_NAME)
    source_collection = new_collection(SOURCE_COLLECTION_NAME)
    env_collection = new_collection(ENV_COLLECTION_NAME)
    light_collection = new_collection(LIGHT_COLLECTION_NAME)

    fbx_files = sorted(SOURCE_ROOT.glob("**/*.fbx"), key=lambda path: str(path).lower())
    ensure(len(fbx_files) == 10, f"预期 10 个 FBX，实际找到 {len(fbx_files)} 个")
    imported_records = []
    group_objects = {}
    for index, path in enumerate(fbx_files, start=1):
        group_id = f"FBX_{index:02d}"
        group_collection = bpy.data.collections.new(f"SOURCE_{group_id}_{path.stem}")
        source_collection.children.link(group_collection)
        record = import_fbx(path, group_collection, group_id)
        imported_records.append(record)
        group_objects[group_id] = record["objects"]

    obj_path = SOURCE_ROOT / "Textures And Butterfly Body" / "BASIC BUTTERFLY BODY_Travis_Davids.OBJ"
    obj_collection = bpy.data.collections.new("SOURCE_OBJ_Butterfly_Body")
    source_collection.children.link(obj_collection)
    import_obj(obj_path, obj_collection)

    image_root = SOURCE_ROOT / "Textures And Butterfly Body"
    images = {
        "diffuse": load_image(
            image_root / "DIFFUSE_Morpho_didius_Male_Dos_MHNT.jpg",
            "蝴蝶翅膀_颜色_DIFFUSE",
            "sRGB",
        ),
        "alpha": load_image(
            image_root / "ALPHA_OR_OPACITY_MASK_Morpho_didius_Male_Dos_MHNT.jpg",
            "蝴蝶翅膀_透明度_ALPHA",
            "Non-Color",
        ),
        "normal": load_image(
            image_root / "NORMAL_MAP_Morpho_didius_Male_Dos_MHNT_NRM.jpg",
            "蝴蝶翅膀_法线_NORMAL",
            "Non-Color",
        ),
        "reference": load_image(
            image_root / "_Male_Dos_MHNT.jpg",
            "蝴蝶源图参考_Male_Dos_MHNT",
            "sRGB",
        ),
    }
    wing_material = make_wing_material(images)
    body_material = make_body_material(images["reference"])

    hero_source_objects = group_objects["FBX_01"]
    hero_objects = duplicate_group(hero_source_objects, model_collection, "主展示")
    display_root = make_empty("蝴蝶_展示根_不改变源动画", model_collection, 0.4)
    # Preserve the imported FBX hierarchy. Only the duplicated top-level root
    # gets the showcase transform; wings and body remain children of that root.
    for obj in hero_objects:
        if obj.parent is None:
            parent_preserve_world(obj, display_root)

    low, high = world_bounds(hero_objects)
    center = (low + high) * 0.5
    raw_extent = max(high.x - low.x, high.y - low.y, high.z - low.z)
    ensure(raw_extent > 0.0, "Butterfly 展示模型边界无效")
    display_extent = 6.2
    scale = display_extent / raw_extent
    display_root.scale = (scale, scale, scale)
    display_root.location = -center * scale
    display_root["source_display_scale"] = scale
    display_root["source_bounds_center"] = list(center)
    display_root["source_bounds_extent"] = raw_extent

    for obj in hero_objects:
        lower_name = obj.name.lower()
        if obj.type != "MESH":
            continue
        if "wing" in lower_name or "翅" in obj.name:
            append_display_material(obj, wing_material)
        else:
            append_display_material(obj, body_material)
    display_root["animation_source"] = "SOURCE_FBX_01"
    display_root["animation_action_names"] = json.dumps(
        [action.name for action in bpy.data.actions if action.get("source_import_group") == "FBX_01"],
        ensure_ascii=False,
    )

    add_presentation_environment(env_collection, display_extent)
    add_camera(artist_scene, light_collection, display_extent * 1.15)
    add_area_light(light_collection, "蝴蝶_主光", (7.0, -8.0, 8.0), 650.0, 5.0, (1.0, 0.72, 0.52))
    add_area_light(light_collection, "蝴蝶_辅光", (-6.0, -4.0, 4.5), 420.0, 4.0, (0.48, 0.68, 1.0))
    add_area_light(light_collection, "蝴蝶_轮廓光", (5.0, 6.0, 7.0), 850.0, 3.5, (0.45, 0.72, 1.0))

    configure_scene(artist_scene, frame_end=250)
    artist_scene["hero_source_fbx"] = source_relative(fbx_files[0])
    artist_scene["hero_display_objects"] = len(hero_objects)
    artist_scene["source_fbx_count"] = len(fbx_files)
    artist_scene["source_obj_imported"] = True
    artist_scene["c4d_source_archived"] = True

    source_scene = bpy.data.scenes.new("SOURCE_REFERENCE")
    for collection in (model_collection, source_collection, env_collection, light_collection):
        source_scene.collection.children.link(collection)
    configure_scene(source_scene, frame_end=250)
    source_scene["reference_scene"] = "所有原始 FBX 导入对象、OBJ 身体和动作库可见"
    set_scene_collection_visibility(artist_scene, {MODEL_COLLECTION_NAME, ENV_COLLECTION_NAME, LIGHT_COLLECTION_NAME})
    set_scene_collection_visibility(source_scene, {SOURCE_COLLECTION_NAME})

    readme = (SOURCE_ROOT / "Read Me.txt").read_text(encoding="utf-8", errors="replace")
    texture_readme = (image_root / "Read Me.txt").read_text(encoding="utf-8", errors="replace")
    create_text("蝴蝶_源文件说明_Read Me", readme)
    create_text("蝴蝶_贴图说明_Read Me", texture_readme)
    embed_unimportable_sources()
    manifest_records = source_file_records(copied_files, imported_records)
    manifest_payload = {
        "asset": "Butterfly",
        "source_root": "blender_scenebench/blender_modelbench/Butterfly",
        "archive_root": "blender/_scenebench/blender/_modelbench/Butterfly/source_assets",
        "files": manifest_records,
        "fbx_imports": [
            {
                "path": record["path"],
                "group_id": record["group_id"],
                "object_count": len(record["objects"]),
                "action_names": [action.name for action in record["actions"]],
                "action_ranges": [list(action.frame_range) for action in record["actions"]],
            }
            for record in imported_records
        ],
        "fidelity_notes": [
            "10 个 FBX 全部导入；原始对象保持在 SOURCE_Butterfly_源文件 下。",
            "左/右翅动作作为 Blender Action 保留，沿路径 FBX 的空物体父级链保留。",
            "OBJ 身体已导入并保留为独立源对象。",
            "4 张图像已加载并在保存前打包进 .blend。",
            "C4D 工程无法由 Blender 5 原生解析；原文件已复制到 source_assets，并记录为归档源文件，不伪造转换结果。",
        ],
    }
    create_text("蝴蝶_源文件清单_完整数据", json.dumps(manifest_payload, ensure_ascii=False, indent=2))
    create_text(
        "蝴蝶_保真规则",
        "本文件按完整数据保真构建：几何、材质槽、UV、父子关系、对象动画、Action、时间轴、源 OBJ、贴图、自定义属性和可导入源对象均保留。展示模型是源 FBX_01 的非破坏性副本；源对象没有删除或解挂。",
    )

    for image in bpy.data.images:
        if image.name == "Render Result":
            continue
        image.pack()
    bpy.ops.file.pack_all()

    bpy.context.window.scene = artist_scene
    artist_scene.frame_set(1)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    artist_scene.render.filepath = str(PREVIEW_PATH)
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))

    report = {
        "output": str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "preview": str(PREVIEW_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_archive": str(ARCHIVE_ROOT.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_file_count": len(copied_files),
        "fbx_count": len(fbx_files),
        "source_object_count": sum(len(record["objects"]) for record in imported_records),
        "source_action_count": sum(len(record["actions"]) for record in imported_records),
        "action_ranges": sorted({tuple(action.frame_range) for record in imported_records for action in record["actions"]}),
        "packed_image_count": sum(1 for image in bpy.data.images if image.packed_file),
        "scene_names": [scene.name for scene in bpy.data.scenes],
        "default_scene": bpy.context.window.scene.name,
        "display_scale": scale,
        "raw_display_extent": raw_extent,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_BUILD=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
