import inspect
import json
import os
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT  / "blender_modelbench" / "杜鹃花"
FORM_ROOT = ASSET_ROOT / "形态2"
FBX_PATH = FORM_ROOT / "as17-rhododendron-ponticum-common-rhododendron.fbx"
OUTPUT_PATH = ASSET_ROOT / "杜鹃花_形态2.blend"
PREVIEW_PATH = PROJECT_ROOT  / "generated" / "杜鹃花_形态2_preview.png"


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def reset_factory():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def localize_workspaces():
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


def patch_blender_5_fbx_lights():
    """Keep FBX import working on Blender 5.0 without editing Blender's install."""
    from io_scene_fbx import import_fbx as fbx_module

    if getattr(fbx_module, "_gwayloo_blender5_light_patch", False):
        return
    try:
        source = inspect.getsource(fbx_module.blen_read_light)
    except OSError:
        fbx_module._gwayloo_blender5_light_patch = True
        return
    deprecated_block = (
        '    if hasattr(lamp, "cycles"):\n'
        "        lamp.cycles.cast_shadow = lamp.use_shadow\n"
    )
    if deprecated_block in source:
        source = source.replace(deprecated_block, "")
        exec(compile(source, "<blender_5_fbx_light_compat>", "exec"), fbx_module.__dict__)
    fbx_module._gwayloo_blender5_light_patch = True


def new_collection(name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def move_to_collection(obj, collection):
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)


def parent_preserve_world(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def imported_objects(import_operation):
    before = set(bpy.data.objects)
    result = import_operation()
    ensure(result == {"FINISHED"} or result == {"FINISHED", "RUNNING_MODAL"}, f"导入失败: {result}")
    return [obj for obj in bpy.data.objects if obj not in before]


def source_relative_path(path):
    path = Path(path).resolve()
    relative = path.relative_to(ASSET_ROOT)
    return "//" + str(relative).replace("\\", "/")


def normalize_image_paths():
    for image in bpy.data.images:
        if image.name == "Render Result" or not image.filepath or image.filepath.startswith("//"):
            continue
        absolute = Path(bpy.path.abspath(image.filepath)).resolve()
        if absolute.is_file() and ASSET_ROOT in absolute.parents:
            image.filepath = source_relative_path(absolute)


def set_image_colorspaces():
    for image in bpy.data.images:
        if image.name == "Render Result":
            continue
        filename = Path(image.filepath).name.lower()
        if any(token in filename for token in ("_nml_", "_gls_", "_trp_", "_alp_", "normal", "rough")):
            try:
                image.colorspace_settings.name = "Non-Color"
            except (AttributeError, TypeError, ValueError):
                pass
        else:
            try:
                image.colorspace_settings.name = "sRGB"
            except (AttributeError, TypeError, ValueError):
                pass


def world_bounds(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
        evaluated.to_mesh_clear()
    ensure(points, "场景中没有可计算边界的网格")
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return minimum, maximum


def point_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_material(name, color, roughness=0.5, metallic=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return material


def add_plinth(collection, extent):
    radius = max(0.9, extent * 0.34)
    depth = max(0.18, extent * 0.065)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=depth, location=(0.0, 0.0, depth / 2.0))
    plinth = bpy.context.object
    plinth.name = "展示台_杜鹃花_形态2"
    move_to_collection(plinth, collection)
    bevel = plinth.modifiers.new("柔和倒角", "BEVEL")
    bevel.width = depth * 0.34
    bevel.segments = 4
    plinth.data.materials.append(make_material("展示台_深色砂岩_形态2", (0.16, 0.065, 0.035), roughness=0.4, metallic=0.05))
    for polygon in plinth.data.polygons:
        polygon.use_smooth = True


def add_area_light(collection, name, location, energy, size, color, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    light = bpy.data.objects.new(name, data)
    collection.objects.link(light)
    light.location = location
    point_at(light, target)


def add_environment(scene, environment_collection, light_collection, visible_meshes):
    minimum, maximum = world_bounds(visible_meshes)
    extent = max(maximum - minimum)
    height = maximum.z - minimum.z
    target_z = max(0.8, height * 0.5)
    add_plinth(environment_collection, extent)

    bpy.ops.mesh.primitive_plane_add(size=max(18.0, extent * 7.0), location=(0.0, 0.0, -0.02))
    floor = bpy.context.object
    floor.name = "背景地面_杜鹃花_形态2"
    move_to_collection(floor, environment_collection)
    floor.data.materials.append(make_material("背景_深灰蓝_形态2", (0.012, 0.019, 0.025), roughness=0.7))

    add_area_light(light_collection, "主光_暖白_杜鹃花_形态2", (extent * 1.6, -extent * 2.0, extent * 2.2), 920.0, extent * 1.35, (1.0, 0.72, 0.52), (0.0, 0.0, target_z))
    add_area_light(light_collection, "辅光_柔和_杜鹃花_形态2", (-extent * 1.4, -extent * 0.8, extent * 1.6), 520.0, extent * 1.55, (0.5, 0.7, 1.0), (0.0, 0.0, target_z * 0.82))
    add_area_light(light_collection, "轮廓光_冷色_杜鹃花_形态2", (extent * 1.25, extent * 1.65, extent * 2.0), 1100.0, extent * 1.1, (0.5, 0.68, 1.0), (0.0, 0.0, target_z * 1.05))

    camera_data = bpy.data.cameras.new("相机_杜鹃花_形态2_英雄视角")
    camera = bpy.data.objects.new("相机_杜鹃花_形态2_英雄视角", camera_data)
    light_collection.objects.link(camera)
    distance = max(5.2, extent * 2.7)
    camera.location = (distance * 0.72, -distance, max(2.6, extent * 1.15))
    camera_data.lens = 55.0
    camera_data.sensor_width = 36.0
    point_at(camera, (0.0, 0.0, target_z))
    scene.camera = camera

    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except (TypeError, ValueError):
        pass
    world = bpy.data.worlds.new("世界_杜鹃花_形态2_深夜蓝")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.004, 0.008, 0.014, 1.0)
    background.inputs["Strength"].default_value = 0.22
    scene.world = world


def rename_imported_objects(objects, root_object):
    names = {
        "Bark01_7_Bark01_SHD_0": "杜鹃花_形态2_树皮",
        "Branch01_7_Branch01_SHD_0": "杜鹃花_形态2_枝条",
        "Leaf01_7_Leaf01_su_SHD_0": "杜鹃花_形态2_叶片01",
        "Leaf02_7_Leaf02_su_SHD_0": "杜鹃花_形态2_叶片02",
        "Leaf03_7_Leaf03_su_SHD_0": "杜鹃花_形态2_叶片03",
        "Flower01_7_Flower01_su_SHD_0": "杜鹃花_形态2_花朵01",
        "Flower02_7_Flower02_su_SHD_0": "杜鹃花_形态2_花朵02",
        "Flower02_7_Flower02_su_SHD_0.001": "杜鹃花_形态2_花朵02_副本",
        "Flower03_7_Flower03_su_SHD_0": "杜鹃花_形态2_花朵03",
    }
    for obj in objects:
        original_name = obj.name
        obj["source_original_name"] = original_name
        obj["source_fbx"] = str(FBX_PATH.relative_to(ASSET_ROOT)).replace("\\", "/")
        if obj == root_object:
            obj.name = "源文件_杜鹃花_形态2_AS17根节点"
            obj["asset_role"] = "源文件层级根节点"
        elif original_name in names:
            obj.name = names[original_name]
            obj["asset_role"] = "主模型网格部件"
        else:
            obj.name = f"源文件_形态2_{original_name}"


def add_conversion_text(lines):
    text = bpy.data.texts.new("转换说明_杜鹃花_形态2")
    text.write("\n".join(lines) + "\n")


def select_object(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def build():
    reset_factory()
    patch_blender_5_fbx_lights()
    ensure(FBX_PATH.is_file(), f"缺少形态2 FBX: {FBX_PATH}")
    GENERATED_ROOT = PREVIEW_PATH.parent
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)

    model_collection = new_collection("MODEL_杜鹃花_形态2")
    environment_collection = new_collection("ENVIRONMENT_杜鹃花_形态2展示环境")
    light_collection = new_collection("LIGHTS_杜鹃花_形态2摄影灯光")
    source_collection = new_collection("SOURCE_杜鹃花_形态2原始资料索引")

    imported = imported_objects(lambda: bpy.ops.import_scene.fbx(filepath=str(FBX_PATH)))
    meshes = [obj for obj in imported if obj.type == "MESH"]
    ensure(len(meshes) == 9, f"形态2 FBX 网格数量异常: {len(meshes)}")
    root_object = next((obj for obj in imported if obj.type == "EMPTY" and obj.parent is None), None)
    ensure(root_object is not None, "形态2 FBX 未找到根节点")
    rename_imported_objects(imported, root_object)
    for obj in imported:
        move_to_collection(obj, model_collection)

    presentation_root = bpy.data.objects.new("资产根_杜鹃花_形态2_展示定位", None)
    presentation_root.empty_display_type = "PLAIN_AXES"
    presentation_root.empty_display_size = 0.3
    model_collection.objects.link(presentation_root)
    parent_preserve_world(root_object, presentation_root)
    presentation_root["presentation_scale"] = 1.0
    presentation_root["source_transform_preserved"] = True

    for mesh in meshes:
        mesh.data["source_object_name"] = mesh.get("source_original_name", mesh.name)
        mesh.data["source_fbx"] = str(FBX_PATH.relative_to(ASSET_ROOT)).replace("\\", "/")
        for polygon in mesh.data.polygons:
            polygon.use_smooth = True

    set_image_colorspaces()
    bpy.context.scene.frame_set(1)
    minimum, maximum = world_bounds(meshes)
    center = (minimum + maximum) * 0.5
    presentation_root.location += Vector((-center.x, -center.y, 0.22 - minimum.z))

    source_index = bpy.data.objects.new("原始资料索引_杜鹃花_形态2", None)
    source_collection.objects.link(source_index)
    source_index.hide_viewport = True
    source_index.hide_render = True
    source_index["source_directory"] = "blender_modelbench/杜鹃花/形态2"
    source_index["source_fbx"] = str(FBX_PATH.relative_to(ASSET_ROOT)).replace("\\", "/")
    source_index["source_file_count"] = sum(1 for path in FORM_ROOT.rglob("*") if path.is_file())
    source_index["source_files"] = json.dumps(
        [str(path.relative_to(ASSET_ROOT)).replace("\\", "/") for path in sorted(FORM_ROOT.rglob("*")) if path.is_file()],
        ensure_ascii=False,
    )
    source_collection.hide_viewport = True
    source_collection.hide_render = True

    scene = bpy.context.scene
    scene.name = "杜鹃花_形态2_模型展示"
    scene.frame_start = 1
    scene.frame_end = 1
    if hasattr(scene, "frame_preview_start"):
        scene.frame_preview_start = 1
        scene.frame_preview_end = 1
    scene["asset_name"] = "杜鹃花"
    scene["asset_form"] = "形态2"
    scene["source_asset_dir"] = "blender_modelbench/杜鹃花/形态2"
    scene["source_fbx"] = str(FBX_PATH.relative_to(ASSET_ROOT)).replace("\\", "/")
    scene["source_formats"] = "FBX"
    scene["source_mesh_count"] = len(meshes)
    scene["source_has_armature"] = False
    scene["source_has_animation"] = False
    scene["animation_preserved"] = False
    scene["external_source_preserved"] = True
    scene["packed_assets"] = True
    scene["workspace_language"] = "中文"
    scene["conversion_policy"] = "完整数据保真：保留 FBX 网格、材质、贴图、UV、父子关系和自定义属性"
    scene["main_model_objects"] = ", ".join(sorted(mesh.name for mesh in meshes))
    scene["presentation_root"] = presentation_root.name
    scene["output_file"] = str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")
    localize_workspaces()

    preview_path = PREVIEW_PATH
    add_environment(scene, environment_collection, light_collection, meshes)
    scene.render.filepath = str(preview_path)
    add_conversion_text([
        "主模型：形态2/as17-rhododendron-ponticum-common-rhododendron.fbx",
        "FBX 网格：9 个；源文件不含骨骼和动画，时间轴为第 1 帧",
        "材质：保留 Bark、Branch、Flower01/02/03、Leaf01/02/03 源材质与贴图连接",
        "贴图：颜色、法线、透明度、光泽和 Alpha 贴图均从形态2/textures 读取并打包",
        "原始形态2目录保持外部保留；展示定位通过父级空对象完成，不修改源网格变换",
    ])

    bpy.ops.file.pack_all()
    select_object(max(meshes, key=lambda obj: len(obj.data.vertices)))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    normalize_image_paths()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    bpy.ops.render.render(write_still=True)
    print(f"AZALEA_FORM2_BLEND={OUTPUT_PATH}")
    print(f"AZALEA_FORM2_PREVIEW={preview_path}")
    print(f"AZALEA_FORM2_MESHES={len(meshes)}")
    print(f"AZALEA_FORM2_PACKED_IMAGES={sum(1 for image in bpy.data.images if image.packed_file)}")


if __name__ == "__main__":
    build()
