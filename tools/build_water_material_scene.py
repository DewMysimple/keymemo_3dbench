"""Build a Blender 5.0 material preview from the supplied UE5 water assets.

The supplied files are Unreal Engine 5.5 .uasset packages, not Blender
interchange files.  This script preserves the source packages externally and
recreates the exposed material semantics in Blender.  It deliberately records
the missing T_Water_N dependency instead of pretending that it was converted.
"""

from pathlib import Path
import math

import bpy
from mathutils import Vector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WATER_ROOT = PROJECT_ROOT  / "blender_modelbench" / "水"
GENERATED_ROOT = PROJECT_ROOT  / "generated"
OUTPUT_PATH = WATER_ROOT / "水_材质.blend"
PREVIEW_PATH = GENERATED_ROOT / "水_材质_preview.png"

M_SOURCE = WATER_ROOT / "M_Water.uasset"
MI_SOURCE = WATER_ROOT / "MI_Water.uasset"

M_VALUES = {
    "ior": 0.75,
    "absorption_multiplier": 0.1,
    "scattering_multiplier": 0.1,
    "absorption": (0.0350000001, 0.0070000002, 0.0030000000, 1.0),
    "scattering": (0.0007000000, 0.0020999999, 0.0024999999, 1.0),
    "normal_intensity": 0.1,
    "normal_tiling": 2.0,
    "phase_g": 0.1,
}

MI_VALUES = {
    "ior": 1.2000000477,
    "absorption_multiplier": 1.3618619442,
    "scattering_multiplier": 4.5850968361,
    "absorption": (0.3489579856, 0.0272620004, 0.0326239988, 1.0),
    "scattering": (0.0010000000, 0.0010000000, 0.0010000000, 1.0),
    "normal_intensity": 0.1,
    "normal_tiling": 2.0,
    "phase_g": 0.1,
}


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def relative_path(path):
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


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


def new_collection(name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def set_input(node, name, value):
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value
    return socket


def add_value(nodes, name, value, location, label=None):
    node = nodes.new("ShaderNodeValue")
    node.name = name
    node.label = label or name
    node.location = location
    node.outputs[0].default_value = value
    return node


def add_rgb(nodes, name, value, location, label=None):
    node = nodes.new("ShaderNodeRGB")
    node.name = name
    node.label = label or name
    node.location = location
    node.outputs[0].default_value = value
    return node


def build_water_material(name, values, role, source_name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (0.008, 0.055, 0.10, 1.0)
    material["asset_role"] = role
    material["source_asset"] = source_name
    material["source_engine"] = "Unreal Engine 5.5"
    material["source_shading_model"] = "MSM_SingleLayerWater"
    material["source_texture"] = "Game/Japanese_Plants/Textures/T_Water_N"
    material["source_texture_status"] = "缺失：当前水目录没有 T_Water_N.uasset 或纹理导出文件"
    material["conversion_status"] = "参数重建；不是 UE 材质图逐节点原生导入"
    material["source_ior"] = values["ior"]
    material["source_absorption_coefficients"] = ", ".join(f"{v:.10g}" for v in values["absorption"][:3])
    material["source_scattering_coefficients"] = ", ".join(f"{v:.10g}" for v in values["scattering"][:3])
    material["source_absorption_multiplier"] = values["absorption_multiplier"]
    material["source_scattering_multiplier"] = values["scattering_multiplier"]
    material["source_normal_intensity"] = values["normal_intensity"]
    material["source_normal_tiling"] = values["normal_tiling"]
    material["source_phase_g"] = values["phase_g"]

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "材质输出"
    output.label = "Blender 材质输出"
    output.location = (900, 80)

    surface = nodes.new("ShaderNodeBsdfPrincipled")
    surface.name = "水面表面（SingleLayerWater 重建）"
    surface.label = "水面表面｜UE SingleLayerWater 参数重建"
    surface.location = (570, 230)
    set_input(surface, "Base Color", (0.004, 0.035, 0.075, 1.0))
    set_input(surface, "Metallic", 0.0)
    set_input(surface, "Roughness", 0.06)
    set_input(surface, "IOR", values["ior"])
    set_input(surface, "Specular IOR Level", 0.5)
    transmission = surface.inputs.get("Transmission Weight") or surface.inputs.get("Transmission")
    if transmission:
        transmission.default_value = 0.96
    links.new(surface.outputs["BSDF"], output.inputs["Surface"])

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.name = "水面坐标"
    texcoord.label = "UV / Generated 坐标"
    texcoord.location = (-1050, 180)

    mapping = nodes.new("ShaderNodeMapping")
    mapping.name = "法线贴图坐标缩放"
    mapping.label = "Normal_Tiling = 2.0"
    mapping.location = (-830, 180)
    mapping.inputs["Scale"].default_value = (
        values["normal_tiling"], values["normal_tiling"], values["normal_tiling"]
    )
    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])

    missing_texture = nodes.new("ShaderNodeTexImage")
    missing_texture.name = "T_Water_N（源纹理缺失）"
    missing_texture.label = "T_Water_N｜源文件未提供，使用程序法线替代"
    missing_texture.location = (-830, -80)
    missing_texture["source_asset"] = "Game/Japanese_Plants/Textures/T_Water_N"
    missing_texture["status"] = "missing_external_source"

    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "程序法线替代（T_Water_N 缺失）"
    noise.label = "程序法线替代｜仅因 T_Water_N 缺失"
    noise.location = (-610, -40)
    set_input(noise, "Scale", 4.0)
    set_input(noise, "Detail", 3.0)
    set_input(noise, "Roughness", 0.65)
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])

    normal_strength = add_value(
        nodes, "Normal_Intensity", values["normal_intensity"], (-610, -260), "Normal_Intensity = 0.1"
    )
    bump = nodes.new("ShaderNodeBump")
    bump.name = "水面微法线"
    bump.label = "法线强度来自 Normal_Intensity"
    bump.location = (80, -20)
    set_input(bump, "Distance", 0.08)
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(normal_strength.outputs["Value"], bump.inputs["Strength"])
    links.new(bump.outputs["Normal"], surface.inputs["Normal"])

    ior_value = add_value(nodes, "IOR", values["ior"], (60, 260), f"IOR = {values['ior']:.6g}")
    links.new(ior_value.outputs["Value"], surface.inputs["IOR"])

    absorption_rgb = add_rgb(
        nodes, "AbsorptionCoefficients", values["absorption"], (-560, -430), "AbsorptionCoefficients"
    )
    scattering_rgb = add_rgb(
        nodes, "ScatteringCoefficients", values["scattering"], (-560, -650), "ScatteringCoefficients"
    )
    absorption = nodes.new("ShaderNodeVolumeAbsorption")
    absorption.name = "单层水吸收"
    absorption.label = "AbsorptionCoefficients｜UE 参数"
    absorption.location = (230, -390)
    links.new(absorption_rgb.outputs["Color"], absorption.inputs["Color"])
    scattering = nodes.new("ShaderNodeVolumeScatter")
    scattering.name = "单层水散射"
    scattering.label = "ScatteringCoefficients｜UE 参数"
    scattering.location = (230, -610)
    links.new(scattering_rgb.outputs["Color"], scattering.inputs["Color"])

    absorption_multiplier = add_value(
        nodes,
        "AbsorptionCoeficientsMultiply",
        values["absorption_multiplier"],
        (-180, -390),
        f"吸收倍率 = {values['absorption_multiplier']:.6g}",
    )
    absorption_scale = nodes.new("ShaderNodeMath")
    absorption_scale.name = "吸收密度换算"
    absorption_scale.label = "UE 吸收倍率 → Blender 体积密度（0.15）"
    absorption_scale.operation = "MULTIPLY"
    absorption_scale.location = (30, -430)
    absorption_scale.inputs[1].default_value = 0.15
    links.new(absorption_multiplier.outputs["Value"], absorption_scale.inputs[0])
    links.new(absorption_scale.outputs[0], absorption.inputs["Density"])

    scattering_multiplier = add_value(
        nodes,
        "ScatteringCoefficientsMultiply",
        values["scattering_multiplier"],
        (-180, -650),
        f"散射倍率 = {values['scattering_multiplier']:.6g}",
    )
    scattering_scale = nodes.new("ShaderNodeMath")
    scattering_scale.name = "散射密度换算"
    scattering_scale.label = "UE 散射倍率 → Blender 体积密度（0.03）"
    scattering_scale.operation = "MULTIPLY"
    scattering_scale.location = (30, -650)
    scattering_scale.inputs[1].default_value = 0.03
    links.new(scattering_multiplier.outputs["Value"], scattering_scale.inputs[0])
    links.new(scattering_scale.outputs[0], scattering.inputs["Density"])

    phase = add_value(nodes, "PhaseG", values["phase_g"], (-180, -820), f"PhaseG = {values['phase_g']:.6g}")
    links.new(phase.outputs["Value"], scattering.inputs["Anisotropy"])

    volume_add = nodes.new("ShaderNodeAddShader")
    volume_add.name = "单层水体积合成"
    volume_add.label = "吸收 + 散射"
    volume_add.location = (590, -430)
    links.new(absorption.outputs["Volume"], volume_add.inputs[0])
    links.new(scattering.outputs["Volume"], volume_add.inputs[1])
    links.new(volume_add.outputs[0], output.inputs["Volume"])

    return material


def make_source_reference(collection, source_path, asset_class, role):
    empty = bpy.data.objects.new(f"源文件_{source_path.stem}", None)
    empty.empty_display_type = "CUBE"
    empty.empty_display_size = 0.45
    empty.hide_render = True
    collection.objects.link(empty)
    empty.hide_viewport = True
    empty["source_file"] = relative_path(source_path)
    empty["source_asset_class"] = asset_class
    empty["source_role"] = role
    empty["source_preserved_externally"] = True
    return empty


def make_preview_mesh(collection, material):
    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.28))
    water = bpy.context.object
    water.name = "预览水体_MI_Water"
    water.scale = (3.2, 2.2, 0.28)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = water.modifiers.new("水体边缘圆角", "BEVEL")
    bevel.width = 0.18
    bevel.segments = 5
    water.data.materials.append(material)
    for old_collection in list(water.users_collection):
        old_collection.objects.unlink(water)
    collection.objects.link(water)
    water["asset_role"] = "材质预览几何体，不是原始 UE 网格"
    water["assigned_material"] = material.name
    return water


def make_ground(collection):
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0.0, 0.0, -0.06))
    ground = bpy.context.object
    ground.name = "预览地面"
    for old_collection in list(ground.users_collection):
        old_collection.objects.unlink(ground)
    collection.objects.link(ground)
    material = bpy.data.materials.new("预览地面材质")
    material.diffuse_color = (0.035, 0.045, 0.055, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (0.025, 0.035, 0.05, 1.0)
    shader.inputs["Roughness"].default_value = 0.42
    ground.data.materials.append(material)
    return ground


def make_camera_and_lights(environment):
    bpy.ops.object.camera_add(location=(8.8, -9.8, 6.7))
    camera = bpy.context.object
    camera.name = "水材质预览相机"
    camera.data.lens = 52
    camera.data.sensor_width = 36
    point_at(camera, (0.0, 0.0, 0.22))
    for old_collection in list(camera.users_collection):
        old_collection.objects.unlink(camera)
    environment.objects.link(camera)
    bpy.context.scene.camera = camera

    lights = [
        ("主光", "AREA", (4.0, -3.0, 7.0), (720.0, 5.0, 5.0), (0.92, 0.98, 1.0)),
        ("轮廓光", "AREA", (-4.5, 2.0, 4.0), (420.0, 4.0, 4.0), (0.35, 0.65, 1.0)),
        ("暖色补光", "AREA", (2.0, 4.0, 2.7), (260.0, 3.0, 3.0), (1.0, 0.48, 0.2)),
    ]
    for name, light_type, location, shape, color in lights:
        bpy.ops.object.light_add(type=light_type, location=location)
        light = bpy.context.object
        light.name = f"水材质预览_{name}"
        light.data.energy = shape[0]
        light.data.shape = "DISK"
        light.data.size = shape[1]
        light.data.color = color
        point_at(light, (0.0, 0.0, 0.25))
        for old_collection in list(light.users_collection):
            old_collection.objects.unlink(light)
        environment.objects.link(light)


def add_conversion_text():
    text = bpy.data.texts.new("水材质_转换说明")
    text.write(
        "\n".join(
            [
                "水材质转换说明",
                "================",
                f"实例材质：{relative_path(MI_SOURCE)}",
                f"母材质：{relative_path(M_SOURCE)}",
                "源引擎：Unreal Engine 5.5",
                "源模型：MSM_SingleLayerWater（UE 单层水材质）",
                "转换状态：已按可解析的材质实例参数重建为 Blender 节点材质；不是 UE 原生节点图导入。",
                "已重建：IOR、吸收系数、散射系数、吸收/散射倍率、PhaseG、Normal_Intensity、Normal_Tiling。",
                "未完成项：源材质引用的 T_Water_N 法线纹理不在当前目录，使用程序 Noise 法线替代。",
                "如需无损贴图转换，请补充 T_Water_N.uasset（及其 .uexp/.ubulk，如存在）或从 UE 导出 PNG/TGA。",
                "原始 .uasset 文件保持在外部目录，未移动、未覆盖。",
            ]
        )
        + "\n"
    )


def configure_scene(scene):
    scene.name = "水材质展示"
    scene.frame_start = 1
    scene.frame_end = 120
    scene["asset_name"] = "水"
    scene["source_material_instance"] = relative_path(MI_SOURCE)
    scene["source_parent_material"] = relative_path(M_SOURCE)
    scene["source_engine"] = "Unreal Engine 5.5"
    scene["source_shading_model"] = "MSM_SingleLayerWater"
    scene["source_texture_dependency"] = "Game/Japanese_Plants/Textures/T_Water_N"
    scene["source_texture_status"] = "缺失"
    scene["conversion_status"] = "部分参数重建；法线纹理缺失；原始 UAsset 保留"
    scene["external_source_preserved"] = True
    scene["packed_image_count"] = 0
    scene["workspace_language"] = "中文"
    scene["output_file"] = relative_path(OUTPUT_PATH)
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except (TypeError, ValueError):
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(PREVIEW_PATH)
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"

    world = bpy.data.worlds.new("水材质预览世界") if not bpy.data.worlds else bpy.data.worlds[0]
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.003, 0.008, 0.018, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.16
    scene.world = world
    localize_workspaces()


def main():
    ensure(M_SOURCE.is_file(), f"缺少母材质：{M_SOURCE}")
    ensure(MI_SOURCE.is_file(), f"缺少材质实例：{MI_SOURCE}")
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    model_collection = new_collection("MODEL_水材质预览")
    environment = new_collection("ENVIRONMENT_水材质预览")
    source_collection = new_collection("SOURCE_水_UAsset原始资料")

    mother = build_water_material("M_Water_母材质_重建", M_VALUES, "UE 母材质参数重建", M_SOURCE.name)
    instance = build_water_material("MI_Water_实例材质_重建", MI_VALUES, "UE 材质实例参数重建", MI_SOURCE.name)
    mother.use_fake_user = True
    instance["parent_material"] = mother.name
    instance["parent_source"] = relative_path(M_SOURCE)
    instance["override_parameters"] = "IOR, AbsorptionCoeficientsMultiply, ScatteringCoefficientsMultiply, AbsorptionCoeficients, ScatteringCoefficients"

    make_source_reference(source_collection, M_SOURCE, "Material", "母材质")
    make_source_reference(source_collection, MI_SOURCE, "MaterialInstanceConstant", "材质实例")
    water = make_preview_mesh(model_collection, instance)
    water["mother_material"] = mother.name
    make_ground(environment)
    make_camera_and_lights(environment)
    add_conversion_text()
    configure_scene(bpy.context.scene)

    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))

    print(f"WATER_BLEND={OUTPUT_PATH}")
    print(f"WATER_PREVIEW={PREVIEW_PATH}")
    print(f"WATER_MATERIALS={len(bpy.data.materials)}")
    print(f"WATER_OBJECTS={len(bpy.data.objects)}")
    print(f"WATER_PACKED_IMAGES={sum(1 for image in bpy.data.images if image.packed_file)}")
    print("WATER_SOURCE_TEXTURE_STATUS=missing:T_Water_N")


if __name__ == "__main__":
    main()
