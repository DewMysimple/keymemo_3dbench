import os
import shutil
import sys
from mathutils import Vector

import bpy


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SOURCE_ROOT = os.path.join(
    PROJECT_ROOT,
    "blender_scenebench",
    "blender_modelbench",
    "杜鹃花",
)
FBX_PATH = os.path.join(SOURCE_ROOT, "source", "Western honey bee.fbx")
TEXTURE_ROOT = os.path.join(SOURCE_ROOT, "textures")
OUTPUT_DIR = os.path.join(
    PROJECT_ROOT,
    "blender",
    "_scenebench",
    "blender",
    "_modelbench",
    "杜鹃花",
)
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "杜鹃花.blend")
EXTERNAL_SOURCE_DIR = os.path.join(OUTPUT_DIR, "source")
EXTERNAL_TEXTURE_DIR = os.path.join(OUTPUT_DIR, "textures")
PREVIEW_PATH = os.path.join(
    PROJECT_ROOT, "blender_scenebench", "generated", "杜鹃花_preview.png"
)


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def localize_workspaces():
    workspace_names = {
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
        workspace.name = workspace_names.get(workspace.name, workspace.name)
    if bpy.context.window:
        layout = bpy.data.workspaces.get("布局")
        if layout:
            bpy.context.window.workspace = layout


def preserve_external_assets():
    os.makedirs(EXTERNAL_SOURCE_DIR, exist_ok=True)
    os.makedirs(EXTERNAL_TEXTURE_DIR, exist_ok=True)
    for filename in ("Western honey bee.fbx", "Western honey bee.max"):
        source = os.path.join(SOURCE_ROOT, "source", filename)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(EXTERNAL_SOURCE_DIR, filename))
    for filename in (
        "rhododendron_color.png",
        "rhododendron_normal.png",
        "rhododendron_rough.png",
        "rhododendron_subsur.png",
    ):
        source = os.path.join(TEXTURE_ROOT, filename)
        ensure(os.path.isfile(source), f"缺少贴图: {source}")
        shutil.copy2(source, os.path.join(EXTERNAL_TEXTURE_DIR, filename))


def make_material(name, base_color, metallic=0.0, roughness=0.5):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (520, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (240, 0)
    shader.inputs["Base Color"].default_value = (*base_color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def build_flower_material():
    material = bpy.data.materials.get("杜鹃花_四通道材质")
    if material is None:
        material = bpy.data.materials.new("杜鹃花_四通道材质")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "材质输出"
    output.location = (720, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "杜鹃花 Principled"
    shader.location = (420, 0)
    shader.inputs["Roughness"].default_value = 0.58
    shader.inputs["Specular IOR Level"].default_value = 0.28
    if shader.inputs.get("Coat Weight"):
        shader.inputs["Coat Weight"].default_value = 0.08
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    files = {
        "颜色": ("rhododendron_color.png", "sRGB"),
        "法线": ("rhododendron_normal.png", "Non-Color"),
        "粗糙度": ("rhododendron_rough.png", "Non-Color"),
        "次表面": ("rhododendron_subsur.png", "Non-Color"),
    }
    textures = {}
    for label, (filename, colorspace) in files.items():
        path = os.path.join(TEXTURE_ROOT, filename)
        ensure(os.path.isfile(path), f"缺少贴图: {path}")
        image = bpy.data.images.load(path, check_existing=False)
        image.name = f"杜鹃花_{label}_{filename}"
        image.colorspace_settings.name = colorspace
        textures[label] = image

    color = nodes.new("ShaderNodeTexImage")
    color.name = "颜色贴图"
    color.label = "颜色 / sRGB"
    color.location = (-600, 180)
    color.image = textures["颜色"]
    links.new(color.outputs["Color"], shader.inputs["Base Color"])

    normal_tex = nodes.new("ShaderNodeTexImage")
    normal_tex.name = "法线贴图"
    normal_tex.label = "法线 / Non-Color"
    normal_tex.location = (-600, -60)
    normal_tex.image = textures["法线"]
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.name = "法线转换"
    normal_map.location = (160, -160)
    normal_map.inputs["Strength"].default_value = 0.72
    links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])

    roughness = nodes.new("ShaderNodeTexImage")
    roughness.name = "粗糙度贴图"
    roughness.label = "粗糙度 / Non-Color"
    roughness.location = (-600, -300)
    roughness.image = textures["粗糙度"]
    links.new(roughness.outputs["Color"], shader.inputs["Roughness"])

    subsurface = nodes.new("ShaderNodeTexImage")
    subsurface.name = "次表面贴图"
    subsurface.label = "次表面 / Non-Color"
    subsurface.location = (-600, -520)
    subsurface.image = textures["次表面"]
    if shader.inputs.get("Subsurface Weight"):
        links.new(subsurface.outputs["Color"], shader.inputs["Subsurface Weight"])
    elif shader.inputs.get("Subsurface"):
        links.new(subsurface.outputs["Color"], shader.inputs["Subsurface"])

    material["asset_role"] = "杜鹃花模型材质"
    material["texture_set"] = "rhododendron_color / normal / rough / subsur"
    return material


def move_to_collection(obj, collection):
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)


def world_bounds(obj):
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return minimum, maximum


def point_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


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
    return light


def add_plinth(collection):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=96,
        radius=0.72,
        depth=0.22,
        location=(0.0, 0.0, 0.11),
    )
    plinth = bpy.context.object
    plinth.name = "展示台_杜鹃花"
    move_to_collection(plinth, collection)
    bevel = plinth.modifiers.new("柔和倒角", "BEVEL")
    bevel.width = 0.075
    bevel.segments = 4
    plinth.data.materials.append(
        make_material("展示台_砂岩", (0.34, 0.17, 0.095), metallic=0.05, roughness=0.38)
    )
    for polygon in plinth.data.polygons:
        polygon.use_smooth = True
    return plinth


def create_scene():
    ensure(os.path.isfile(FBX_PATH), f"缺少模型: {FBX_PATH}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(PREVIEW_PATH), exist_ok=True)
    preserve_external_assets()

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)

    root = bpy.context.scene.collection
    model_collection = bpy.data.collections.new("MODEL_杜鹃花")
    environment_collection = bpy.data.collections.new("ENVIRONMENT_展示环境")
    light_collection = bpy.data.collections.new("LIGHTS_摄影灯光")
    root.children.link(model_collection)
    root.children.link(environment_collection)
    root.children.link(light_collection)

    bpy.ops.import_scene.fbx(filepath=FBX_PATH)
    imported = list(bpy.context.scene.objects)
    model = next((obj for obj in imported if obj.type == "MESH" and obj.name.lower() == "rhododendron"), None)
    ensure(model is not None, "FBX 中未找到 rhododendron 网格")

    for obj in imported:
        if obj == model:
            continue
        if obj.type == "ARMATURE":
            obj.name = "源文件_昆虫骨架_隐藏"
            move_to_collection(obj, model_collection)
            obj.hide_render = True
            obj.hide_set(True)
        else:
            bpy.data.objects.remove(obj, do_unlink=True)

    original_matrix = model.matrix_world.copy()
    model.parent = None
    model.matrix_world = original_matrix
    model.name = "杜鹃花_高模"
    move_to_collection(model, model_collection)
    model.scale = model.scale * 28.0
    bpy.context.view_layer.objects.active = model
    model.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    model.data.materials.clear()
    flower_material = build_flower_material()
    model.data.materials.append(flower_material)
    for polygon in model.data.polygons:
        polygon.use_smooth = True
    model["asset_name"] = "杜鹃花"
    model["source_fbx"] = "blender_scenebench/blender_modelbench/杜鹃花/source/Western honey bee.fbx"
    model["source_mesh"] = "rhododendron"
    model["texture_set"] = "rhododendron_color / normal / rough / subsur"
    model["build_note"] = "FBX 导入后重新绑定贴图，保存前打包图像资源"

    minimum, maximum = world_bounds(model)
    center = (minimum + maximum) * 0.5
    model.location += Vector((-center.x, -center.y, 0.18 - minimum.z))
    minimum, maximum = world_bounds(model)

    plinth = add_plinth(environment_collection)
    floor_material = make_material("背景_深灰蓝", (0.018, 0.026, 0.030), metallic=0.0, roughness=0.66)
    bpy.ops.mesh.primitive_plane_add(size=30.0, location=(0.0, 0.0, -0.012))
    floor = bpy.context.object
    floor.name = "背景地面"
    move_to_collection(floor, environment_collection)
    floor.data.materials.append(floor_material)

    add_area_light(
        light_collection,
        "主光_暖白",
        (3.8, -4.5, 5.5),
        720.0,
        4.0,
        (1.0, 0.73, 0.55),
        (0.0, 0.0, 1.25),
    )
    add_area_light(
        light_collection,
        "辅光_柔和",
        (-4.0, -1.8, 3.4),
        420.0,
        4.5,
        (0.55, 0.72, 1.0),
        (0.0, 0.0, 1.1),
    )
    add_area_light(
        light_collection,
        "轮廓光_冷色",
        (2.6, 3.5, 4.8),
        850.0,
        3.0,
        (0.52, 0.70, 1.0),
        (0.0, 0.0, 1.45),
    )

    camera_data = bpy.data.cameras.new("相机_杜鹃花英雄视角")
    camera = bpy.data.objects.new("相机_杜鹃花英雄视角", camera_data)
    light_collection.objects.link(camera)
    camera.location = (3.65, -5.8, 3.05)
    camera_data.lens = 58.0
    camera_data.sensor_width = 36.0
    point_at(camera, (0.0, 0.0, 1.27))
    bpy.context.scene.camera = camera

    scene = bpy.context.scene
    scene.name = "杜鹃花_模型展示"
    scene.frame_start = 1
    scene.frame_end = 1
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = PREVIEW_PATH
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 64
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except (TypeError, ValueError):
        pass
    world = bpy.data.worlds.new("世界_深夜蓝") if not bpy.data.worlds else bpy.data.worlds[0]
    world.name = "世界_深夜蓝"
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.006, 0.010, 0.014, 1.0)
    background.inputs["Strength"].default_value = 0.24
    scene.world = world

    scene["asset_name"] = "杜鹃花"
    scene["scene_purpose"] = "基于 FBX 与 rhododendron 贴图集的可编辑模型展示文件"
    scene["source_asset_dir"] = "blender_scenebench/blender_modelbench/杜鹃花"
    scene["packed_assets"] = True
    scene["model_object"] = model.name
    scene["render_camera"] = camera.name
    scene["model_dimensions"] = tuple(round(value, 4) for value in model.dimensions)
    scene["build_script"] = "blender_scenebench/tools/build_azalea_scene.py"
    localize_workspaces()
    scene["workspace_language"] = "中文"
    scene["external_asset_copy"] = "source/ 与 textures/"

    for material in list(bpy.data.materials):
        if material.users == 0:
            bpy.data.materials.remove(material)
    for image in list(bpy.data.images):
        if image.name != "Render Result" and image.users == 0:
            bpy.data.images.remove(image)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_PATH)
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_PATH)
    print(f"AZALEA_BLEND={OUTPUT_PATH}")
    print(f"AZALEA_PREVIEW={PREVIEW_PATH}")
    print(f"MODEL_DIMENSIONS={tuple(round(value, 4) for value in model.dimensions)}")
    print(f"PACKED_IMAGES={sum(1 for image in bpy.data.images if image.packed_file)}")
    print(f"OBJECTS={[(obj.name, obj.type) for obj in scene.objects]}")


if __name__ == "__main__":
    create_scene()
