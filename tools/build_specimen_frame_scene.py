"""Build the transparent square specimen-frame Blender asset.

The asset is intentionally self-contained: it has a square ring,
an independent inner plate, translucent materials, and an oblique preview
camera.  The model stands in the Y-Z plane with thickness along X. The ring
and plate remain separate objects so an artist can tune their proportions or
materials independently. The panel is parented to the ring; the ring's
bottom-face-center origin is the world origin, so the assembly rises upward.
Lighting comes from a packed Blender Studio HDRI in the World shader.
The 90-degree standing rotation is applied to the mesh, leaving object
rotation values at zero.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workbench_paths import GENERATED_ROOT as GENERATED_BASE, REPORTS_ROOT, WORKBENCH_ROOT as WORKBENCH_BASE, model_root, model_scenes

PROJECT_ROOT = WORKBENCH_BASE
WORKBENCH_ROOT = WORKBENCH_BASE
ASSET_ROOT = model_root("SpecimenFrame")
BLENDER_ROOT = model_scenes("SpecimenFrame")
GENERATED_ROOT = GENERATED_BASE / "SpecimenFrame"
REPORT_ROOT = REPORTS_ROOT
OUTPUT_PATH = BLENDER_ROOT / "Specimen_Frame_Transparent.blend"
PREVIEW_PATH = GENERATED_ROOT / "Specimen_Frame_Transparent_preview.png"
REPORT_PATH = REPORT_ROOT / "specimen-frame-validation.json"

FRAME_OVERALL_SIZE = 9.1
FRAME_OPENING_SIZE = 7.1
FRAME_DEPTH = 0.42
PANEL_DEPTH = FRAME_DEPTH
PANEL_RECESS = 0.0


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def first_input(node: bpy.types.Node, *names: str):
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            return socket
    return None


def set_input(node: bpy.types.Node, names: str | tuple[str, ...], value) -> None:
    candidates = (names,) if isinstance(names, str) else names
    socket = first_input(node, *candidates)
    if socket is not None:
        socket.default_value = value


def localize_workspaces() -> None:
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


def new_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)


def point_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def make_translucent_material(
    name: str,
    color: tuple[float, float, float, float],
    transparent_mix: float,
    transmission: float,
    roughness: float,
    metallic: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = color
    material["asset_role"] = "specimen frame translucent material"
    material["material_color_note"] = "Viewport and render color intentionally differ only through glass transmission."
    # Blender 4.2+ / 5.x replaced blend_method with surface_render_method.
    try:
        material.surface_render_method = "BLENDED"
    except (AttributeError, TypeError, ValueError):
        try:
            material.surface_render_method = "DITHERED"
        except (AttributeError, TypeError, ValueError):
            pass

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "Material Output"
    output.location = (560, 80)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.name = "Translucent Principled"
    principled.label = "透亮材质｜颜色与厚度可调"
    principled.location = (260, 120)
    set_input(principled, "Base Color", color)
    set_input(principled, "Metallic", metallic)
    set_input(principled, "Roughness", roughness)
    set_input(principled, ("IOR",), 1.45)
    set_input(principled, ("Transmission Weight", "Transmission"), transmission)
    set_input(principled, ("Coat Weight", "Clearcoat"), 0.22)
    set_input(principled, ("Coat Roughness", "Clearcoat Roughness"), 0.12)
    set_input(principled, "Alpha", color[3])

    transparent = nodes.new("ShaderNodeBsdfTransparent")
    transparent.name = "Soft Transparency"
    transparent.label = f"透明度混合｜{1.0 - transparent_mix:.0%} 保留"
    transparent.location = (0, -70)

    mix = nodes.new("ShaderNodeMixShader")
    mix.name = "Transparent Mix"
    mix.label = "半透明 + 玻璃高光"
    mix.location = (360, 60)
    mix.inputs[0].default_value = transparent_mix
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(principled.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])

    material["transparent_mix"] = transparent_mix
    material["transmission"] = transmission
    material["roughness"] = roughness
    return material


def make_backdrop_material() -> bpy.types.Material:
    material = bpy.data.materials.new("Backdrop_NeutralBlueGray")
    material.use_nodes = True
    material.diffuse_color = (0.60, 0.64, 0.74, 1.0)
    material["asset_role"] = "preview-only neutral cool backdrop"
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader:
        set_input(shader, "Base Color", (0.32, 0.36, 0.46, 1.0))
        set_input(shader, "Roughness", 0.52)
        set_input(shader, ("Specular IOR Level", "Specular"), 0.12)
    return material


def make_ring_mesh(name: str, outer_half: float, inner_half: float, depth: float) -> bpy.types.Object:
    """Create a closed square ring prism with an actual open center."""
    outer = [
        (-outer_half, -outer_half),
        (outer_half, -outer_half),
        (outer_half, outer_half),
        (-outer_half, outer_half),
    ]
    inner = [
        (-inner_half, -inner_half),
        (inner_half, -inner_half),
        (inner_half, inner_half),
        (-inner_half, inner_half),
    ]
    z_bottom = -depth / 2.0
    z_top = depth / 2.0
    vertices = [(x, y, z) for z in (z_bottom, z_top) for x, y in outer + inner]
    # Layer offsets: bottom outer 0, bottom inner 4, top outer 8, top inner 12.
    faces: list[tuple[int, ...]] = []
    for i in range(4):
        j = (i + 1) % 4
        # Front and back annular surfaces.
        faces.append((8 + i, 8 + j, 12 + j, 12 + i))
        faces.append((i, 4 + i, 4 + j, j))
        # Outer wall and inner reveal wall.
        faces.append((i, j, 8 + j, 8 + i))
        faces.append((4 + i, 12 + i, 12 + j, 4 + j))

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    return obj


def make_beveled_cube(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    bevel_width: float,
    bevel_segments: int,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    move_to_collection(obj, collection)
    obj.data.materials.append(material)
    return obj


def make_ring(
    collection: bpy.types.Collection,
    material: bpy.types.Material,
) -> bpy.types.Object:
    outer_half = FRAME_OVERALL_SIZE / 2.0
    inner_half = FRAME_OPENING_SIZE / 2.0
    depth = FRAME_DEPTH
    frame = make_ring_mesh("SPECIMEN_OUTER_FRAME", outer_half, inner_half, depth)
    collection.objects.link(frame)
    # Stand the frame in the Y-Z plane and apply the 90-degree rotation to
    # the mesh. The mesh is shifted in local X first so the object origin
    # becomes the center of its bottom face.
    frame.data.transform(Matrix.Translation((-outer_half, 0.0, 0.0)))
    frame.data.transform(Matrix.Rotation(math.radians(90.0), 4, "Y"))
    # The bottom-face-center origin is the world origin, so the whole frame
    # occupies positive world Z after it is stood upright.
    frame.location = (0.0, 0.0, 0.0)
    frame.rotation_euler = (0.0, 0.0, 0.0)
    frame.data.materials.append(material)
    frame["asset_role"] = "outer square specimen frame"
    frame["overall_size"] = FRAME_OVERALL_SIZE
    frame["opening_size"] = FRAME_OPENING_SIZE
    frame["thickness"] = depth
    frame["border_width"] = outer_half - inner_half
    frame["material_role"] = "translucent white outer frame"
    frame["origin_role"] = "bottom face center at world origin"
    return frame


def make_panel(
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    # Match the opening in Y-Z and the frame thickness in X. The inner panel
    # therefore fills the opening and meets both front and back frame faces.
    panel = make_beveled_cube(
        "SPECIMEN_INNER_PANEL",
        (0.0, 0.0, 0.0),
        (FRAME_OPENING_SIZE, FRAME_OPENING_SIZE, PANEL_DEPTH),
        PANEL_DEPTH / 2.0,
        6,
        collection,
        material,
    )
    # Apply the standing rotation to the panel mesh and keep its object
    # origin at its geometric center. Its world center sits halfway up the
    # frame and shares the frame's X center.
    panel.data.transform(Matrix.Rotation(math.radians(90.0), 4, "Y"))
    panel.location = (-PANEL_RECESS, 0.0, FRAME_OVERALL_SIZE / 2.0)
    panel.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    panel.parent = parent
    panel.matrix_parent_inverse = parent.matrix_world.inverted()
    panel["asset_role"] = "inner square specimen panel"
    panel["size"] = FRAME_OPENING_SIZE
    panel["thickness"] = PANEL_DEPTH
    panel["opening_fit"] = "perimeter and front/back faces coincident with SPECIMEN_OUTER_FRAME opening"
    panel["material_role"] = "transparent pale lavender center"
    panel["origin_role"] = "geometric center"
    panel["parent_role"] = "follows SPECIMEN_OUTER_FRAME"
    return panel


def make_backdrop(collection: bpy.types.Collection) -> bpy.types.Object:
    backdrop = make_beveled_cube(
        "PREVIEW_BACKDROP",
        (0.0, 0.0, -0.72),
        (28.0, 28.0, 0.18),
        0.30,
        6,
        collection,
        make_backdrop_material(),
    )
    backdrop["asset_role"] = "preview-only backdrop behind specimen frame"
    return backdrop


def make_camera(collection: bpy.types.Collection) -> bpy.types.Camera:
    bpy.ops.object.camera_add(location=(14.0, -5.6, 12.15))
    camera = bpy.context.object
    camera.name = "CAMERA_SPECIMEN_FRAME"
    camera.data.name = "CAMERA_SPECIMEN_FRAME_DATA"
    camera.data.lens = 53
    camera.data.sensor_width = 36
    point_at(camera, (0.0, 0.0, FRAME_OVERALL_SIZE / 2.0))
    move_to_collection(camera, collection)
    camera["asset_role"] = "oblique material preview camera"
    return camera


def make_hdri_world() -> bpy.types.World:
    world = bpy.data.worlds.new("SPECIMEN_FRAME_WORLD")
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputWorld")
    output.name = "World Output"
    output.location = (520, 40)

    background = nodes.new("ShaderNodeBackground")
    background.name = "HDRI Environment Strength"
    background.label = "HDRI 世界环境光"
    background.location = (260, 40)
    background.inputs["Strength"].default_value = 0.65

    hdri = nodes.new("ShaderNodeTexEnvironment")
    hdri.name = "HDRI Studio Environment"
    hdri.label = "Blender Studio HDRI｜已打包进文件"
    hdri.location = (-20, 80)
    hdri_path = Path(bpy.utils.resource_path("LOCAL")) / "datafiles" / "studiolights" / "world" / "studio.exr"
    ensure(hdri_path.is_file(), f"Bundled Blender HDRI not found: {hdri_path}")
    image = bpy.data.images.load(str(hdri_path), check_existing=True)
    image.name = "HDRI_SPECIMEN_FRAME_STUDIO"
    image.pack()
    image.filepath = "//packed_studio.exr"
    hdri.image = image
    links.new(hdri.outputs["Color"], background.inputs["Color"])
    links.new(background.outputs["Background"], output.inputs["Surface"])

    world["asset_role"] = "packed HDRI world environment light"
    world["hdri_name"] = "studio.exr"
    world["hdri_source"] = "Blender bundled Studio HDRI, packed into the .blend"
    world["hdri_strength"] = 0.65
    return world


def configure_scene(scene: bpy.types.Scene, camera: bpy.types.Camera) -> None:
    scene.name = "SPECIMEN_FRAME_WORKBENCH"
    scene.camera = camera
    scene.frame_start = 1
    scene.frame_end = 1
    scene.frame_set(1)
    available_engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
    if "BLENDER_EEVEE_NEXT" in available_engines:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in available_engines:
        scene.render.engine = "BLENDER_EEVEE"
    else:
        scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 760
    scene.render.resolution_y = 760
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(PREVIEW_PATH)
    scene.render.image_settings.color_depth = "8"

    scene.world = make_hdri_world()
    scene.view_settings.look = "AgX - Medium High Contrast"

    scene["asset_name_zh"] = "透明浅紫标本正方形框"
    scene["asset_name_en"] = "Transparent Pale Lavender Specimen Frame"
    scene["description_zh"] = "外框为有一定透明度的白色，中心为透明浅紫色，环体与内板均有真实厚度。"
    scene["modeling_notes"] = "SPECIMEN_OUTER_FRAME is a closed square ring; SPECIMEN_INNER_PANEL is a parented solid slab. Both stand in Y-Z with thickness along X."
    scene["frame_overall_size"] = FRAME_OVERALL_SIZE
    scene["frame_opening_size"] = FRAME_OPENING_SIZE
    scene["frame_depth"] = FRAME_DEPTH
    scene["panel_depth"] = PANEL_DEPTH
    scene["panel_recess"] = PANEL_RECESS
    scene["panel_opening_fit"] = "SPECIMEN_INNER_PANEL exactly fills the 7.1 x 7.1 inner opening; perimeter gap is 0.0."
    scene["panel_x_alignment"] = "SPECIMEN_INNER_PANEL front and back faces align with SPECIMEN_OUTER_FRAME; X gap is 0.0."
    scene["preferred_viewport"] = "Rendered / 渲染"
    scene["background_removed"] = True
    scene["bevel_modifiers_applied"] = False
    scene["bevel_modifier_removed_without_apply"] = True
    scene["surface_subdivision_modifier"] = False
    scene["standing_plane"] = "Y-Z"
    scene["thickness_axis"] = "X"
    scene["object_origin_note"] = "The outer frame bottom-face-center origin is at world origin; the inner panel origin is at its geometric center."
    scene["panel_parenting"] = "SPECIMEN_INNER_PANEL follows SPECIMEN_OUTER_FRAME."
    scene["frame_origin_at_world_origin"] = True
    scene["model_above_world_origin"] = True
    scene["object_rotation_applied"] = True
    scene["world_environment"] = "Packed Blender Studio HDRI (studio.exr)"
    scene["old_area_lights_removed"] = True
    scene["source_reference_images"] = "User-provided images used as visual reference only; no text or hidden instructions imported."
    scene["output_file"] = str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")

    localize_workspaces()
    # The saved file opens in the artist-facing layout.  In a foreground
    # Blender window, the viewport opens in Rendered mode and uses the scene
    # World, so the packed HDRI provides the environment illumination.
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "RENDERED"
                area.spaces.active.shading.use_scene_world = True
                area.spaces.active.shading.use_scene_lights = True
                area.spaces.active.shading.color_type = "MATERIAL"


def write_text_block() -> None:
    text = bpy.data.texts.new("SPECIMEN_FRAME_README")
    text.write(
        "\n".join(
            [
                "透明浅紫标本正方形框 / Transparent Pale Lavender Specimen Frame",
                "",
                "建模结构：",
                "- SPECIMEN_OUTER_FRAME：带开口的真实方形环体，外框为半透明白色。",
                "- SPECIMEN_INNER_PANEL：独立有厚度方板，材质为透明浅紫色。",
                "- 姿态：整体立在 Y-Z 平面，厚度沿 X；立起旋转已应用到网格，物体 Rotation 为零。",
                "- 层级：SPECIMEN_INNER_PANEL 是 SPECIMEN_OUTER_FRAME 的子物体，会跟随外框。",
                "- 合缝：中心板外边界与外框 7.1 × 7.1 内开口四边完全对齐，平面缝隙为 0。",
                "- X 轴对齐：中心板厚度与外框均为 0.42，正面和背面与外框齐平。",
                "- 原点：外框底面中心位于世界原点，整体模型向世界 Z 正方向延伸；紫色主体原点位于几何中心。",
                "- 背景：已移除底色，渲染使用透明背景。",
                "",
                "材质预览：",
                "进入‘布局’或‘着色’工作区后使用‘渲染’查看 HDRI 环境光、透明和高光；",
                "外框与中心板的材质可在材质属性中分别调节。",
                "",
                "尺寸（Blender 单位）：整体 9.1，开口与中心板均为 7.1，外框与中心板深度均为 0.42。",
            ]
        )
        + "\n"
    )


def validate_scene(frame: bpy.types.Object, panel: bpy.types.Object, camera: bpy.types.Object) -> dict[str, object]:
    bpy.context.view_layer.update()
    mesh = frame.data
    panel_mesh = panel.data
    frame_material = frame.data.materials[0]
    panel_material = panel.data.materials[0]
    panel_color = tuple(float(value) for value in panel_material.diffuse_color)
    frame_bounds = [frame.matrix_world @ Vector(corner) for corner in frame.bound_box]
    panel_bounds = [panel.matrix_world @ Vector(corner) for corner in panel.bound_box]
    frame_bottom = min(point.z for point in frame_bounds)
    panel_bottom = min(point.z for point in panel_bounds)
    frame_origin_world = frame.matrix_world.translation
    panel_origin_world = panel.matrix_world.translation
    frame_world_dimensions = tuple(
        max(point[index] for point in frame_bounds) - min(point[index] for point in frame_bounds)
        for index in range(3)
    )
    panel_world_dimensions = tuple(
        max(point[index] for point in panel_bounds) - min(point[index] for point in panel_bounds)
        for index in range(3)
    )
    opening_size = float(frame.get("opening_size", FRAME_OPENING_SIZE))
    overall_size = float(frame.get("overall_size", FRAME_OVERALL_SIZE))
    opening_bounds = {
        "y_min": -opening_size / 2.0,
        "y_max": opening_size / 2.0,
        "z_min": (overall_size - opening_size) / 2.0,
        "z_max": (overall_size + opening_size) / 2.0,
    }
    panel_fit_deltas = {
        "x_min": min(point.x for point in panel_bounds) - (-FRAME_DEPTH / 2.0),
        "x_max": max(point.x for point in panel_bounds) - (FRAME_DEPTH / 2.0),
        "y_min": min(point.y for point in panel_bounds) - opening_bounds["y_min"],
        "y_max": max(point.y for point in panel_bounds) - opening_bounds["y_max"],
        "z_min": min(point.z for point in panel_bounds) - opening_bounds["z_min"],
        "z_max": max(point.z for point in panel_bounds) - opening_bounds["z_max"],
    }
    frame_local_z_min = min(vertex.co.z for vertex in mesh.vertices)
    world_nodes = bpy.context.scene.world.node_tree.nodes if bpy.context.scene.world and bpy.context.scene.world.use_nodes else []
    hdri_nodes = [node for node in world_nodes if node.bl_idname == "ShaderNodeTexEnvironment"]
    hdri_image = hdri_nodes[0].image if hdri_nodes else None
    light_objects = sorted(obj.name for obj in bpy.context.scene.objects if obj.type == "LIGHT")
    report: dict[str, object] = {
        "asset": "Transparent Pale Lavender Specimen Frame",
        "blend": str(OUTPUT_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "scene": bpy.context.scene.name,
        "objects": sorted(obj.name for obj in bpy.context.scene.objects),
        "collections": sorted(collection.name for collection in bpy.context.scene.collection.children),
        "frame": {
            "object": frame.name,
            "vertices": len(mesh.vertices),
            "polygons": len(mesh.polygons),
            "dimensions": [round(value, 4) for value in frame_world_dimensions],
            "local_dimensions": [round(value, 4) for value in frame.dimensions],
            "modifier_names": [modifier.name for modifier in frame.modifiers],
            "material": frame_material.name if frame.data.materials else None,
            "viewport_color": [round(value, 4) for value in frame_material.diffuse_color],
            "rotation_degrees": [round(math.degrees(value), 2) for value in frame.rotation_euler],
            "origin": [round(value, 4) for value in frame_origin_world],
        },
        "panel": {
            "object": panel.name,
            "vertices": len(panel_mesh.vertices),
            "polygons": len(panel_mesh.polygons),
            "dimensions": [round(value, 4) for value in panel_world_dimensions],
            "local_dimensions": [round(value, 4) for value in panel.dimensions],
            "modifier_names": [modifier.name for modifier in panel.modifiers],
            "material": panel_material.name if panel.data.materials else None,
            "viewport_color": [round(value, 4) for value in panel_color],
            "rotation_degrees": [round(math.degrees(value), 2) for value in panel.rotation_euler],
            "origin": [round(value, 4) for value in panel_origin_world],
            "parent": panel.parent.name if panel.parent else None,
            "opening_fit_deltas": {key: round(value, 6) for key, value in panel_fit_deltas.items()},
        },
        "camera": camera.name,
        "world": {
            "name": bpy.context.scene.world.name if bpy.context.scene.world else None,
            "hdri_node": hdri_nodes[0].name if hdri_nodes else None,
            "hdri_image": hdri_image.name if hdri_image else None,
            "hdri_packed": bool(hdri_image and hdri_image.packed_file),
            "light_objects": light_objects,
        },
        "render_preview": str(PREVIEW_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "checks": {
            "frame_has_opening": len(mesh.vertices) == 16 and len(mesh.polygons) == 16,
            "frame_has_depth": frame_world_dimensions[0] > 0.4,
            "panel_has_depth": panel_world_dimensions[0] > 0.25,
            "panel_fills_outer_opening": all(abs(value) < 0.001 for value in panel_fit_deltas.values()),
            "panel_edges_aligned_with_opening": (
                abs(panel_world_dimensions[1] - opening_size) < 0.001
                and abs(panel_world_dimensions[2] - opening_size) < 0.001
            ),
            "panel_front_back_faces_aligned_with_frame": (
                abs(panel_world_dimensions[0] - FRAME_DEPTH) < 0.001
                and abs(panel_fit_deltas["x_min"]) < 0.001
                and abs(panel_fit_deltas["x_max"]) < 0.001
            ),
            "frame_and_panel_separate": frame != panel and frame.data != panel.data,
            "frame_material_is_white_translucent": frame.data.materials[0].name == "MAT_OuterFrame_TranslucentWhite",
            "panel_material_is_lavender_translucent": panel.data.materials[0].name == "MAT_InnerPanel_TransparentLavender",
            "panel_hue_is_lavender_not_pink": panel_color[2] > panel_color[0] * 1.35 and panel_color[2] > panel_color[1] * 1.7,
            "no_modifiers": len(frame.modifiers) == 0 and len(panel.modifiers) == 0,
            "background_removed": bpy.context.scene.render.film_transparent and bpy.data.objects.get("PREVIEW_BACKDROP") is None,
            "standing_in_yz_plane": (
                abs(frame_world_dimensions[1] - frame_world_dimensions[2]) < 0.001
                and abs(panel_world_dimensions[1] - panel_world_dimensions[2]) < 0.001
                and frame_world_dimensions[0] < frame_world_dimensions[1]
                and panel_world_dimensions[0] < panel_world_dimensions[1]
                and all(abs(value) < 0.001 for value in frame.rotation_euler)
                and all(abs(value) < 0.001 for value in panel.rotation_euler)
            ),
            "panel_parent_follows_frame": panel.parent == frame,
            "panel_origin_at_geometric_center": (
                all(
                    abs(min(vertex.co[index] for vertex in panel_mesh.vertices) + max(vertex.co[index] for vertex in panel_mesh.vertices)) < 0.001
                    for index in range(3)
                )
                and abs(panel_origin_world.x - sum(point.x for point in panel_bounds) / 8.0) < 0.001
                and abs(panel_origin_world.y - sum(point.y for point in panel_bounds) / 8.0) < 0.001
                and abs(panel_origin_world.z - sum(point.z for point in panel_bounds) / 8.0) < 0.001
            ),
            "frame_origin_at_world_origin": (
                abs(frame_origin_world.x) < 0.001
                and abs(frame_origin_world.y) < 0.001
                and abs(frame_origin_world.z) < 0.001
                and abs(frame_local_z_min) < 0.001
            ),
            "model_above_world_origin": frame_bottom > -0.001 and panel_bottom > -0.001,
            "object_rotation_applied": all(
                abs(value) < 0.001
                for value in (*frame.rotation_euler, *panel.rotation_euler)
            ),
            "hdri_world_environment_loaded": bool(hdri_image and hdri_image.packed_file),
            "old_lights_removed": not light_objects and not any(name in light_objects for name in ("KEY_SOFTBOX", "FILL_LAVENDER", "RIM_WARM")),
        },
    }
    return report


def main() -> None:
    BLENDER_ROOT.mkdir(parents=True, exist_ok=True)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    model = new_collection("MODEL_SPECIMEN_FRAME")
    environment = new_collection("ENVIRONMENT_SPECIMEN_FRAME")
    helpers = new_collection("HELPERS_SPECIMEN_FRAME")
    helpers.hide_render = True
    helpers.hide_viewport = True

    outer_material = make_translucent_material(
        "MAT_OuterFrame_TranslucentWhite",
        (0.90, 0.96, 1.0, 0.70),
        transparent_mix=0.28,
        transmission=0.50,
        roughness=0.16,
    )
    inner_material = make_translucent_material(
        "MAT_InnerPanel_TransparentLavender",
        (0.64, 0.52, 1.0, 0.74),
        transparent_mix=0.24,
        transmission=0.35,
        roughness=0.12,
    )

    frame = make_ring(model, outer_material)
    panel = make_panel(model, inner_material, frame)
    camera = make_camera(environment)
    configure_scene(bpy.context.scene, camera)
    write_text_block()

    report = validate_scene(frame, panel, camera)
    report["checks"]["all_passed"] = all(report["checks"].values())
    ensure(report["checks"]["all_passed"], "Specimen frame validation failed before saving.")

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH))

    report["preview_bytes"] = PREVIEW_PATH.stat().st_size if PREVIEW_PATH.is_file() else 0
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"SPECIMEN_FRAME_BLEND={OUTPUT_PATH}")
    print(f"SPECIMEN_FRAME_PREVIEW={PREVIEW_PATH}")
    print(f"SPECIMEN_FRAME_REPORT={REPORT_PATH}")
    print(json.dumps(report["checks"], ensure_ascii=False))


if __name__ == "__main__":
    main()
