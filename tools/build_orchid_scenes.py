import inspect
import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "blender" / "_scenebench" / "blender" / "_modelbench" / "兰花"
FORM1_ROOT = ASSET_ROOT / "形态1"
FORM2_ROOT = ASSET_ROOT / "形态2"
GENERATED_ROOT = PROJECT_ROOT / "blender_scenebench" / "generated"


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


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


def reset_factory():
    bpy.ops.wm.read_factory_settings(use_empty=True)


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


def make_empty(name, collection, display_size=0.25):
    data = bpy.data.objects.new(name, None)
    data.empty_display_type = "PLAIN_AXES"
    data.empty_display_size = display_size
    collection.objects.link(data)
    return data


def patch_blender_5_fbx_lights():
    """Keep FBX import working on Blender 5.0 without editing Blender's install."""
    from io_scene_fbx import import_fbx as fbx_module

    if getattr(fbx_module, "_gwayloo_blender5_light_patch", False):
        return
    try:
        source = inspect.getsource(fbx_module.blen_read_light)
    except OSError:
        # The function may already be patched in the same Blender process.
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


def imported_objects(import_operation):
    before = set(bpy.data.objects)
    result = import_operation()
    ensure(result == {"FINISHED"} or result == {"FINISHED", "RUNNING_MODAL"}, f"导入失败: {result}")
    return [obj for obj in bpy.data.objects if obj not in before]


def rename_source_objects(objects, prefix):
    for obj in objects:
        original_name = obj.name
        obj["source_original_name"] = original_name
        obj["source_import_group"] = prefix
        obj.name = f"源文件_{prefix}_{original_name}"


def hide_source_collection(collection):
    collection.hide_viewport = True
    collection.hide_render = True


def set_image_colorspace(image, colorspace):
    try:
        image.colorspace_settings.name = colorspace
    except (AttributeError, TypeError, ValueError):
        pass


def source_relative_path(path):
    path = Path(path).resolve()
    relative = path.relative_to(ASSET_ROOT)
    return "//" + str(relative).replace("\\", "/")


def load_image(path, colorspace):
    path = Path(path)
    ensure(path.is_file(), f"缺少贴图: {path}")
    for existing in bpy.data.images:
        if existing.name == "Render Result" or not existing.filepath:
            continue
        existing_path = Path(bpy.path.abspath(existing.filepath)).resolve()
        if existing_path.name.lower() == path.name.lower() and existing_path.is_file():
            set_image_colorspace(existing, colorspace)
            existing.filepath = str(existing_path)
            existing["source_path"] = str(existing_path.relative_to(ASSET_ROOT)).replace("\\", "/")
            return existing
    image = bpy.data.images.load(str(path), check_existing=True)
    set_image_colorspace(image, colorspace)
    image.filepath = str(path.resolve())
    image["source_path"] = str(path.relative_to(ASSET_ROOT)).replace("\\", "/")
    return image


def texture_images_in_data():
    for image in bpy.data.images:
        if image.name == "Render Result" or not image.filepath or image.filepath.startswith("//"):
            continue
        absolute = Path(bpy.path.abspath(image.filepath)).resolve()
        if absolute.is_file():
            image.filepath = source_relative_path(absolute)


def image_node(nodes, name, image, location):
    node = nodes.new("ShaderNodeTexImage")
    node.name = name
    node.label = name
    node.location = location
    node.image = image
    return node


def build_orchid_flower_material(name, diffuse, bump, roughness, transparency=None):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "材质输出"
    output.location = (640, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "兰花花瓣 Principled"
    shader.location = (350, 0)
    shader.inputs["Roughness"].default_value = 0.5
    if shader.inputs.get("Specular IOR Level"):
        shader.inputs["Specular IOR Level"].default_value = 0.32
    if shader.inputs.get("Coat Weight"):
        shader.inputs["Coat Weight"].default_value = 0.05
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    color_node = image_node(nodes, "颜色贴图 / orchid_d", diffuse, (-700, 180))
    links.new(color_node.outputs["Color"], shader.inputs["Base Color"])

    bump_node = image_node(nodes, "法线贴图 / orchid_b", bump, (-700, -40))
    normal = nodes.new("ShaderNodeNormalMap")
    normal.name = "法线转换"
    normal.location = (50, -140)
    normal.inputs["Strength"].default_value = 0.72
    links.new(bump_node.outputs["Color"], normal.inputs["Color"])
    links.new(normal.outputs["Normal"], shader.inputs["Normal"])

    rough_node = image_node(nodes, "粗糙度贴图 / orchid_r", roughness, (-700, -260))
    links.new(rough_node.outputs["Color"], shader.inputs["Roughness"])

    if transparency:
        alpha_node = image_node(nodes, "透明度贴图 / orchid_tr", transparency, (-700, -480))
        if shader.inputs.get("Alpha"):
            links.new(alpha_node.outputs["Color"], shader.inputs["Alpha"])
        try:
            material.surface_render_method = "DITHERED"
        except (AttributeError, TypeError, ValueError):
            pass

    material["asset_role"] = "兰花花瓣材质"
    material["texture_set"] = "orchid_d / orchid_b / orchid_r / orchid_tr"
    return material


def build_orchid_stem_material(name, diffuse):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "材质输出"
    output.location = (520, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "兰花茎 Principled"
    shader.location = (260, 0)
    shader.inputs["Roughness"].default_value = 0.62
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    color = image_node(nodes, "颜色贴图 / orchid_d", diffuse, (-420, 100))
    links.new(color.outputs["Color"], shader.inputs["Base Color"])
    material["asset_role"] = "兰花茎材质"
    material["texture_set"] = "orchid_d"
    return material


def assign_form1_materials(obj, flower_material, stem_material):
    while len(obj.data.materials) < 2:
        obj.data.materials.append(None)
    obj.data.materials[0] = flower_material
    obj.data.materials[1] = stem_material
    obj["source_material_slots"] = "orchid_m1_01=花瓣; orchid_m1_02=茎"


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
    minimum = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
    maximum = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
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
    radius = max(0.72, extent * 0.34)
    depth = max(0.16, extent * 0.075)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=depth, location=(0.0, 0.0, depth / 2.0))
    plinth = bpy.context.object
    plinth.name = "展示台_兰花"
    move_to_collection(plinth, collection)
    bevel = plinth.modifiers.new("柔和倒角", "BEVEL")
    bevel.width = depth * 0.34
    bevel.segments = 4
    plinth.data.materials.append(make_material("展示台_深色砂岩", (0.16, 0.065, 0.035), roughness=0.4, metallic=0.05))
    for polygon in plinth.data.polygons:
        polygon.use_smooth = True
    return plinth


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


def add_presentation_environment(scene, model_collection, environment_collection, light_collection, preview_path, title, visible_meshes):
    minimum, maximum = world_bounds(visible_meshes)
    extent = max(maximum - minimum)
    target_z = max(0.85, (maximum.z - minimum.z) * 0.52)
    add_plinth(environment_collection, extent)

    floor = None
    floor_material = make_material("背景_深灰蓝", (0.012, 0.019, 0.025), roughness=0.7)
    bpy.ops.mesh.primitive_plane_add(size=max(18.0, extent * 8.0), location=(0.0, 0.0, -0.018))
    floor = bpy.context.object
    floor.name = "背景地面"
    move_to_collection(floor, environment_collection)
    floor.data.materials.append(floor_material)

    add_area_light(light_collection, "主光_暖白", (extent * 1.55, -extent * 2.0, extent * 2.25), 680.0, extent * 1.4, (1.0, 0.70, 0.52), (0.0, 0.0, target_z))
    add_area_light(light_collection, "辅光_柔和", (-extent * 1.5, -extent * 0.8, extent * 1.55), 390.0, extent * 1.6, (0.52, 0.70, 1.0), (0.0, 0.0, target_z * 0.82))
    add_area_light(light_collection, "轮廓光_冷色", (extent * 1.25, extent * 1.65, extent * 2.1), 820.0, extent * 1.15, (0.52, 0.68, 1.0), (0.0, 0.0, target_z * 1.05))

    camera_data = bpy.data.cameras.new(f"相机_{title}_英雄视角")
    camera = bpy.data.objects.new(f"相机_{title}_英雄视角", camera_data)
    light_collection.objects.link(camera)
    distance = max(4.8, extent * 2.75)
    camera.location = (distance * 0.72, -distance, max(2.8, extent * 1.15))
    camera_data.lens = 55.0
    camera_data.sensor_width = 36.0
    point_at(camera, (0.0, 0.0, target_z))
    scene.camera = camera

    for render_engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = render_engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = str(preview_path)
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except (TypeError, ValueError):
        pass

    world = bpy.data.worlds.new(f"世界_{title}_深夜蓝")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.004, 0.008, 0.014, 1.0)
    background.inputs["Strength"].default_value = 0.22
    scene.world = world


def add_conversion_text(title, lines):
    text = bpy.data.texts.new(f"转换说明_{title}")
    text.write("\n".join(lines) + "\n")


def configure_scene(scene, title, source_directory, source_formats, output_path):
    scene.name = f"兰花_{title}_模型展示"
    scene.frame_start = 1
    if title == "形态1":
        scene.frame_end = 166
    else:
        scene.frame_end = 1
    if hasattr(scene, "frame_preview_start"):
        scene.frame_preview_start = scene.frame_start
        scene.frame_preview_end = scene.frame_end
    scene["asset_name"] = "兰花"
    scene["asset_form"] = title
    scene["source_asset_dir"] = str(source_directory.relative_to(PROJECT_ROOT)).replace("\\", "/")
    scene["source_formats"] = ", ".join(source_formats)
    scene["external_source_preserved"] = True
    scene["packed_assets"] = True
    scene["workspace_language"] = "中文"
    scene["conversion_policy"] = "完整数据保真：可导入模型、材质、贴图、UV、缓存动画、父子关系和源对象均保留"
    scene["output_file"] = str(output_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    localize_workspaces()


def set_source_paths_and_pack():
    bpy.ops.file.pack_all()


def select_object(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def build_form1():
    reset_factory()
    patch_blender_5_fbx_lights()
    ensure(FORM1_ROOT.is_dir(), f"缺少形态1目录: {FORM1_ROOT}")
    fbx_path = FORM1_ROOT / "FBX" / "FBX" / "FBX_Orchid.fbx"
    abc_path = FORM1_ROOT / "alembic" / "alembic" / "OrchidMeshGrp.abc"
    obj_root = FORM1_ROOT / "Obj" / "Obj"
    for path in (fbx_path, abc_path, obj_root / "Orchid_Close.obj", obj_root / "Orchid_Open.obj", obj_root / "Orchid_SemiClose.obj"):
        ensure(path.is_file(), f"缺少形态1源文件: {path}")

    model_collection = new_collection("MODEL_兰花_形态1")
    environment_collection = new_collection("ENVIRONMENT_兰花_形态1展示环境")
    light_collection = new_collection("LIGHTS_兰花_形态1摄影灯光")
    source_collection = new_collection("SOURCE_形态1原始可导入对象")

    fbx_objects = imported_objects(lambda: bpy.ops.import_scene.fbx(filepath=str(fbx_path)))
    fbx_mesh = next((obj for obj in fbx_objects if obj.type == "MESH" and obj.name == "OrchidMeshGrp"), None)
    ensure(fbx_mesh is not None, "形态1 FBX 未找到 OrchidMeshGrp 网格")
    rename_source_objects(fbx_objects, "形态1_FBX")
    for obj in fbx_objects:
        move_to_collection(obj, source_collection)

    abc_objects = imported_objects(lambda: bpy.ops.wm.alembic_import(filepath=str(abc_path), as_background_job=False, set_frame_range=True))
    abc_mesh = next((obj for obj in abc_objects if obj.type == "MESH"), None)
    ensure(abc_mesh is not None, "形态1 Alembic 未找到动画网格")
    abc_mesh.name = "兰花_形态1_动画缓存"
    move_to_collection(abc_mesh, model_collection)
    abc_mesh["asset_role"] = "主显示模型"
    abc_mesh["animation_source"] = "OrchidMeshGrp.abc"
    abc_mesh["animation_frame_range"] = "1-166"
    abc_mesh["source_vertex_count"] = len(abc_mesh.data.vertices)

    texture_root = FORM1_ROOT / "Textures" / "Textures"
    diffuse = load_image(texture_root / "orchid_d.jpg", "sRGB")
    bump = load_image(texture_root / "orchid_b.jpg", "Non-Color")
    roughness = load_image(texture_root / "orchid_r.jpg", "Non-Color")
    transparency = load_image(texture_root / "orchid_tr.jpg", "Non-Color")
    flower_material = build_orchid_flower_material("兰花_形态1_花瓣材质", diffuse, bump, roughness, transparency)
    stem_material = build_orchid_stem_material("兰花_形态1_茎材质", diffuse)
    assign_form1_materials(abc_mesh, flower_material, stem_material)

    for cache_file in bpy.data.cache_files:
        cache_file.filepath = str(abc_path)
        cache_file["source_cache"] = "形态1/alembic/alembic/OrchidMeshGrp.abc"

    variant_names = {
        "Orchid_Close.obj": "闭合",
        "Orchid_Open.obj": "开放",
        "Orchid_SemiClose.obj": "半闭合",
    }
    for filename, label in variant_names.items():
        path = obj_root / filename
        variant_objects = imported_objects(lambda path=path: bpy.ops.wm.obj_import(filepath=str(path), forward_axis="NEGATIVE_Z", up_axis="Y"))
        variant_root = make_empty(f"源文件_形态1_OBJ_{label}_展示缩放", source_collection, 0.18)
        variant_root["source_file"] = str(path.relative_to(ASSET_ROOT)).replace("\\", "/")
        variant_root["presentation_scale"] = 0.01
        variant_root.scale = (0.01, 0.01, 0.01)
        for obj in variant_objects:
            parent_preserve_world(obj, variant_root)
            move_to_collection(obj, source_collection)
            obj["source_variant"] = label
        move_to_collection(variant_root, source_collection)

    hide_source_collection(source_collection)
    abc_mesh.parent = None
    presentation_root = make_empty("资产根_兰花_形态1_展示缩放", model_collection, 0.25)
    abc_world = abc_mesh.matrix_world.copy()
    abc_mesh.parent = presentation_root
    abc_mesh.matrix_world = abc_world
    presentation_root.scale = (0.01, 0.01, 0.01)
    bpy.context.scene.frame_set(1)
    minimum, maximum = world_bounds([abc_mesh])
    center = (minimum + maximum) * 0.5
    presentation_root.location += Vector((-center.x, -center.y, 0.22 - minimum.z))

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 166
    preview_path = GENERATED_ROOT / "兰花_形态1_preview.png"
    add_presentation_environment(scene, model_collection, environment_collection, light_collection, preview_path, "兰花_形态1", [abc_mesh])
    configure_scene(scene, "形态1", FORM1_ROOT, ["FBX", "Alembic", "OBJ", "C4D", ".mc/.xml"], ASSET_ROOT / "兰花_形态1.blend")
    scene["animation_preserved"] = True
    scene["animation_type"] = "MeshSequenceCache"
    scene["animation_cache_file"] = "形态1/alembic/alembic/OrchidMeshGrp.abc"
    scene["static_variants"] = "Close, Open, SemiClose"
    scene["main_model"] = abc_mesh.name
    scene["presentation_root"] = presentation_root.name
    add_conversion_text("兰花_形态1", [
        "主模型：形态1/alembic/alembic/OrchidMeshGrp.abc",
        "动画：MeshSequenceCache，帧范围 1-166，缓存文件保持外部相对路径",
        "静态源：形态1/FBX/FBX/FBX_Orchid.fbx，以及 Close/Open/SemiClose 三个 OBJ",
        "外部原件：形态1 下的 C4D、FBX PLA、MC/XML 和全部贴图目录均保留",
        "展示整理只使用父级缩放，不修改源网格拓扑和动画缓存",
    ])
    set_source_paths_and_pack()
    scene.render.filepath = str(preview_path)
    select_object(abc_mesh)
    output_path = ASSET_ROOT / "兰花_形态1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    texture_images_in_data()
    for cache_file in bpy.data.cache_files:
        cache_file.filepath = source_relative_path(abc_path)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    bpy.ops.render.render(write_still=True)
    print(f"ORCHID_FORM1_BLEND={output_path}")
    print(f"ORCHID_FORM1_PREVIEW={preview_path}")
    print(f"ORCHID_FORM1_OBJECTS={len(bpy.data.objects)}")
    print(f"ORCHID_FORM1_PACKED_IMAGES={sum(1 for image in bpy.data.images if image.packed_file)}")


def repair_form2_materials():
    for image in bpy.data.images:
        if image.name == "Render Result":
            continue
        filename = Path(image.filepath).name.lower()
        if "bump" in filename or "normal" in filename:
            set_image_colorspace(image, "Non-Color")
        else:
            set_image_colorspace(image, "sRGB")
    for material in bpy.data.materials:
        if material.name not in {"glass", "water"} or not material.use_nodes or not material.node_tree:
            continue
        shader = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
        if shader is None:
            continue
        if shader.inputs.get("Roughness"):
            shader.inputs["Roughness"].default_value = 0.16 if material.name == "glass" else 0.22
        if shader.inputs.get("Transmission Weight"):
            shader.inputs["Transmission Weight"].default_value = 0.82 if material.name == "glass" else 0.55
        if shader.inputs.get("IOR"):
            shader.inputs["IOR"].default_value = 1.45 if material.name == "glass" else 1.33


def build_form2():
    reset_factory()
    patch_blender_5_fbx_lights()
    ensure(FORM2_ROOT.is_dir(), f"缺少形态2目录: {FORM2_ROOT}")
    fbx_path = FORM2_ROOT / "Magnolia2.fbx"
    ensure(fbx_path.is_file(), f"缺少形态2 FBX: {fbx_path}")

    model_collection = new_collection("MODEL_兰花_形态2")
    environment_collection = new_collection("ENVIRONMENT_兰花_形态2展示环境")
    light_collection = new_collection("LIGHTS_兰花_形态2摄影灯光")
    source_collection = new_collection("SOURCE_形态2原始资料索引")

    imported = imported_objects(lambda: bpy.ops.import_scene.fbx(filepath=str(fbx_path)))
    meshes = [obj for obj in imported if obj.type == "MESH"]
    ensure(meshes, "形态2 FBX 未找到网格")
    for obj in imported:
        if obj.type == "MESH":
            move_to_collection(obj, model_collection)
            obj["source_original_name"] = obj.name
            obj["asset_role"] = "形态2主模型部件"
        else:
            move_to_collection(obj, source_collection)
            obj.hide_render = True
            obj.hide_set(True)
            obj["source_original_name"] = obj.name

    repair_form2_materials()

    top_level = [obj for obj in imported if obj.parent is None and obj.type != "CAMERA"]
    presentation_root = make_empty("资产根_兰花_形态2_展示缩放", model_collection, 0.25)
    for obj in top_level:
        parent_preserve_world(obj, presentation_root)
    bpy.context.scene.frame_set(1)
    minimum, maximum = world_bounds(meshes)
    raw_extent = max(maximum - minimum)
    presentation_scale = 2.65 / max(raw_extent, 0.001)
    presentation_root.scale = (presentation_scale, presentation_scale, presentation_scale)
    bpy.context.view_layer.update()
    minimum, maximum = world_bounds(meshes)
    center = (minimum + maximum) * 0.5
    presentation_root.location += Vector((-center.x, -center.y, 0.22 - minimum.z))

    hide_source_collection(source_collection)
    scene = bpy.context.scene
    preview_path = GENERATED_ROOT / "兰花_形态2_preview.png"
    add_presentation_environment(scene, model_collection, environment_collection, light_collection, preview_path, "兰花_形态2", meshes)
    configure_scene(scene, "形态2", FORM2_ROOT, ["FBX", "OBJ", "C4D", ".max"], ASSET_ROOT / "兰花_形态2.blend")
    scene["animation_preserved"] = False
    scene["source_has_animation"] = False
    scene["main_model_parts"] = ", ".join(sorted(obj.name for obj in meshes))
    scene["presentation_root"] = presentation_root.name
    scene["original_sources"] = "形态2/Magnolia2.fbx, Magnolia2.obj, Magnolia2.c4d, Magnolia2 (2011) corona.max, Magnolia2 (2011) vray.max"
    add_conversion_text("兰花_形态2", [
        "主模型：形态2/Magnolia2.fbx，保留花瓣、花蕊、枝干、花盆、玻璃和水等全部 FBX 网格",
        "动画检查：源 FBX 不含骨骼和动作，时间轴固定为 1 帧",
        "材质：保留源材质并修正花瓣、枝干、花蕊贴图及玻璃/水的显示参数",
        "外部原件：形态2 下的 OBJ、C4D、MAX 和全部贴图均保持原样",
        "展示整理只使用父级缩放和展示环境，不修改主模型源变换关系",
    ])
    set_source_paths_and_pack()
    scene.render.filepath = str(preview_path)
    main_object = max(meshes, key=lambda obj: len(obj.data.vertices))
    select_object(main_object)
    output_path = ASSET_ROOT / "兰花_形态2.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    texture_images_in_data()
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    bpy.ops.render.render(write_still=True)
    print(f"ORCHID_FORM2_BLEND={output_path}")
    print(f"ORCHID_FORM2_PREVIEW={preview_path}")
    print(f"ORCHID_FORM2_OBJECTS={len(bpy.data.objects)}")
    print(f"ORCHID_FORM2_PACKED_IMAGES={sum(1 for image in bpy.data.images if image.packed_file)}")


def main():
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    build_form1()
    build_form2()
    print("ORCHID_BUILD_COMPLETE=TRUE")


if __name__ == "__main__":
    main()
