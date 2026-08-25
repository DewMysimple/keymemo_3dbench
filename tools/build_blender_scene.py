from __future__ import annotations

import json
import math
import os
import random
import sys
import traceback
import bmesh
from mathutils import Vector
from pathlib import Path
from typing import Any

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))

from portable_blend_assets import make_blend_assets_portable, relative_to_blend as portable_relative_to_blend


WORKBENCH = Path(__file__).resolve().parents[1]
SNAPSHOT = WORKBENCH / "source_snapshot"
ASSETS = SNAPSHOT / "assets"
GENERATED = WORKBENCH / "generated"
MANIFEST = WORKBENCH / "manifests/scene_manifest.json"
OUTPUT = Path(
    os.environ.get(
        "VERMINOBLE_BLEND_OUTPUT",
        str(WORKBENCH / "blender/Verminoble_Scene_Mirror_5_0.blend"),
    )
).resolve()
REPORT = Path(
    os.environ.get(
        "VERMINOBLE_BLEND_BUILD_REPORT",
        str(WORKBENCH / "reports/blender-build.json"),
    )
).resolve()

FPS = 60
CAMERA_SAMPLE_COUNT = 3587
CAMERA_LOADER_FINAL_Z = 0.4
WORKSPACE_NAMES_ZH_CN = {
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
DEFAULT_WORKSPACE_NAME = WORKSPACE_NAMES_ZH_CN["Layout"]
REVEAL_ALPHA_SECONDS = 0.01
REVEAL_CURVE_SECONDS = 10.0
REVEAL_ROTATION_SECONDS = 7.0
REVEAL_INK_SECONDS = 15.0
CUTOUT_AND_GROUND_SECONDS = 0.4
# Preserved source-runtime timing for a future shader rebuild; no Blender
# shadow object consumes this channel in the current master file.
SOURCE_SHADOW_SECONDS = 1.0
GRASS_REVEAL_SECONDS = 1.0
GRASS_RANDOM_SEED = 20260823
ARTIST_WORLD_COLOR = (0.78, 0.78, 0.74)
GRASS_BLADE_REMAPS = (
    ("blade-1", 0.0078125, 0.0078125, 0.0703125, 0.984375),
    ("blade-7", 0.09375, 0.0078125, 0.0625, 0.953125),
    ("blade-6", 0.171875, 0.0078125, 0.09375, 0.8828125),
    ("blade-2", 0.28125, 0.0078125, 0.0625, 0.8515625),
    ("blade-10", 0.359375, 0.0078125, 0.0625, 0.84375),
    ("blade-4", 0.4375, 0.0078125, 0.0703125, 0.8125),
    ("blade-8", 0.5234375, 0.0078125, 0.0703125, 0.8125),
    ("blade-9", 0.609375, 0.0078125, 0.0546875, 0.8125),
    ("blade-3", 0.6796875, 0.0078125, 0.0625, 0.8046875),
    ("blade-5", 0.7578125, 0.0078125, 0.0546875, 0.7890625),
)


def log(message: str) -> None:
    print(f"[scene-workbench] {message}")


def require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def relative_to_blend(path: Path) -> str:
    return portable_relative_to_blend(path, OUTPUT.parent)


def set_color_management(scene: bpy.types.Scene) -> None:
    scene.display_settings.display_device = "sRGB"
    try:
        scene.view_settings.view_transform = "Standard"
    except TypeError:
        scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0


def set_render(scene: bpy.types.Scene, width: int, height: int, end_frame: int) -> None:
    available_engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available_engines else "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.frame_start = 0
    scene.frame_end = end_frame
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    set_color_management(scene)


def action_fcurves(action: bpy.types.Action | None) -> list[bpy.types.FCurve]:
    if action is None:
        return []
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    return [
        fcurve
        for layer in action.layers
        for strip in layer.strips
        if hasattr(strip, "channelbags")
        for channelbag in strip.channelbags
        for fcurve in channelbag.fcurves
    ]


def set_action_interpolation(obj: bpy.types.Object, interpolation: str = "LINEAR") -> None:
    action = obj.animation_data.action if obj.animation_data else None
    for fcurve in action_fcurves(action):
        for point in fcurve.keyframe_points:
            point.interpolation = interpolation


def keyframe_custom_property(obj: bpy.types.Object, name: str, frame: float, value: float) -> None:
    obj[name] = value
    obj.keyframe_insert(data_path=f'["{name}"]', frame=frame, group="WEB_RUNTIME")


def sample_property(
    obj: bpy.types.Object,
    name: str,
    start_frame: float,
    duration_seconds: float,
    evaluator: Any,
) -> None:
    frame_count = round(duration_seconds * FPS)
    for offset in range(frame_count + 1):
        progress = offset / max(1, frame_count)
        keyframe_custom_property(obj, name, start_frame + offset, float(evaluator(progress)))


def sine_in_out(progress: float) -> float:
    return -(math.cos(math.pi * progress) - 1.0) / 2.0


def sine_out(progress: float) -> float:
    return math.sin(math.pi * progress / 2.0)


def quart_out(progress: float) -> float:
    return 1.0 - (1.0 - progress) ** 4


def back_out(progress: float) -> float:
    # GSAP Back.easeOut default overshoot from the source runtime.
    overshoot = 1.70158
    shifted = progress - 1.0
    return 1.0 + (overshoot + 1.0) * shifted**3 + overshoot * shifted**2


def configure_scene(scene: bpy.types.Scene, name: str, role: str) -> bpy.types.Scene:
    scene.name = name
    set_render(scene, 1920, 1080, 3586)
    scene["workbench_role"] = role
    scene["source_renderer"] = "WebGL custom watercolor runtime"
    scene["ui_note_zh_cn"] = "界面语言跟随 Blender 用户偏好；资产标识保持 ASCII 英文。"
    return scene


def set_world_color(world: bpy.types.World, color: tuple[float, float, float]) -> None:
    """Set both viewport and node-based world colors for deterministic previews."""
    world.color = color
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background") if world.node_tree else None
    if background is not None:
        background.inputs["Color"].default_value = (*color, 1.0)
        background.inputs["Strength"].default_value = 0.8


def localize_workspaces() -> None:
    """Make the saved project workspaces match the Chinese Blender startup UI."""
    for english_name, chinese_name in WORKSPACE_NAMES_ZH_CN.items():
        workspace = bpy.data.workspaces.get(english_name)
        if workspace is not None:
            workspace.name = chinese_name


def clear_file() -> tuple[bpy.types.Scene, bpy.types.Scene, bpy.types.Scene]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    localize_workspaces()
    animation_scene = configure_scene(
        bpy.context.scene,
        "WEB_ANIMATION",
        "source-faithful animated browser scene mirror",
    )
    animation_scene["fidelity_boundary"] = (
        "Geometry, transforms, camera, animation, source media and timing are mirrored. "
        "Custom GLSL/SDF/LUT effects are represented as editable source-driven approximations."
    )
    artist_scene = configure_scene(
        bpy.data.scenes.new("ARTIST_EDIT"),
        "ARTIST_EDIT",
        "default artist workspace sharing the animated mesh and material datablocks",
    )
    artist_scene.world = bpy.data.worlds.new("ARTIST_EDIT_PaperWorld")
    set_world_color(artist_scene.world, ARTIST_WORLD_COLOR)
    artist_scene["background_policy"] = "Warm paper-gray world; atlas black padding must remain transparent"
    artist_scene["editing_note_zh_cn"] = "默认停在全部图层展开帧；网格和材质与动画场景共享。"
    source_scene = configure_scene(
        bpy.data.scenes.new("SOURCE_REFERENCE"),
        "SOURCE_REFERENCE",
        "locked read-only source GLB reference",
    )
    source_scene["reference_note_zh_cn"] = "只读原始 GLB 镜像，不参与创作场景显示或渲染。"
    return animation_scene, artist_scene, source_scene


def new_collection(scene: bpy.types.Scene, name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    return collection


def move_object_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    for owner in list(obj.users_collection):
        if owner != collection:
            owner.objects.unlink(obj)


def authored_world_matrix(obj: bpy.types.Object) -> Any:
    """Resolve authored transforms without relying on a scene's stale depsgraph."""
    local = obj.matrix_parent_inverse @ obj.matrix_basis
    if obj.parent is None:
        return local.copy()
    return authored_world_matrix(obj.parent) @ local


def optimize_watercolor_card_mesh(mesh: bpy.types.Mesh) -> dict[str, float | int]:
    """Clean GLB float noise while preserving the authored 2D silhouette and UVs."""
    original_normal_x = sum(polygon.normal.x for polygon in mesh.polygons)
    working = bmesh.new()
    working.from_mesh(mesh)

    plane_x = sum(vertex.co.x for vertex in working.verts) / max(1, len(working.verts))
    source_plane_span = (
        max(vertex.co.x for vertex in working.verts) - min(vertex.co.x for vertex in working.verts)
        if working.verts
        else 0.0
    )
    for vertex in working.verts:
        vertex.co.x = plane_x

    vertex_count_before = len(working.verts)
    bmesh.ops.remove_doubles(working, verts=list(working.verts), dist=1e-6)
    merged_vertices = vertex_count_before - len(working.verts)

    planar_extent = max(
        max(vertex.co.y for vertex in working.verts) - min(vertex.co.y for vertex in working.verts),
        max(vertex.co.z for vertex in working.verts) - min(vertex.co.z for vertex in working.verts),
    ) if working.verts else 0.0
    area_epsilon = max(1e-12, planar_extent * planar_extent * 1e-10)
    degenerate_faces = [face for face in working.faces if face.calc_area() <= area_epsilon]
    removed_faces = len(degenerate_faces)
    if degenerate_faces:
        bmesh.ops.delete(working, geom=degenerate_faces, context="FACES_ONLY")
    loose_edges = [edge for edge in working.edges if not edge.link_faces]
    if loose_edges:
        bmesh.ops.delete(working, geom=loose_edges, context="EDGES")
    loose_vertices = [vertex for vertex in working.verts if not vertex.link_edges]
    if loose_vertices:
        bmesh.ops.delete(working, geom=loose_vertices, context="VERTS")

    desired_normal_sign = -1.0 if original_normal_x < 0.0 else 1.0
    for face in working.faces:
        face.normal_update()
    reversed_faces = [face for face in working.faces if face.normal.x * desired_normal_sign < 0.0]
    if reversed_faces:
        bmesh.ops.reverse_faces(working, faces=reversed_faces)

    working.normal_update()
    working.to_mesh(mesh)
    mesh.update()
    working.free()
    return {
        "flattened_plane_span": source_plane_span,
        "merged_vertices": merged_vertices,
        "removed_degenerate_faces": removed_faces,
        "reversed_faces": len(reversed_faces),
    }


def load_image(path: Path, color_space: str = "sRGB") -> bpy.types.Image:
    image = bpy.data.images.load(str(require(path)), check_existing=True)
    if image.size[0] == 0 or image.size[1] == 0:
        raise RuntimeError(f"Blender could not decode image: {path}")
    try:
        image.colorspace_settings.name = color_space
    except TypeError:
        pass
    return image


def configure_transparency(
    material: bpy.types.Material,
    render_method: str = "DITHERED",
    transparency_overlap: bool = True,
) -> None:
    if hasattr(material, "surface_render_method"):
        available = {item.identifier for item in material.bl_rna.properties["surface_render_method"].enum_items}
        material.surface_render_method = render_method if render_method in available else "DITHERED"
    elif hasattr(material, "blend_method"):
        material.blend_method = "BLEND"
        material.shadow_method = "NONE"
    # DITHERED does not depend on object/triangle blend order. Keep overlap
    # enabled so alpha holes can reveal other cutout surfaces behind the card.
    material.use_transparency_overlap = transparency_overlap


def add_vector_remap(
    nodes: bpy.types.Nodes,
    links: bpy.types.NodeLinks,
    texcoord: bpy.types.Node,
    remap: dict[str, float],
    x: float,
    y: float,
    label: str,
    clamp_input: bool = False,
) -> bpy.types.Node:
    vector_input = texcoord.outputs["UV"]
    if clamp_input:
        clamp_min = nodes.new("ShaderNodeVectorMath")
        clamp_min.name = f"{label}_UV_CLAMP_MIN"
        clamp_min.label = f"{label} UV clamp minimum"
        clamp_min.operation = "MAXIMUM"
        clamp_min.location = (x - 210, y)
        clamp_min.inputs[1].default_value = (0.0, 0.0, 0.0)
        links.new(vector_input, clamp_min.inputs[0])

        clamp_max = nodes.new("ShaderNodeVectorMath")
        clamp_max.name = f"{label}_UV_CLAMP_MAX"
        clamp_max.label = f"{label} UV clamp maximum"
        clamp_max.operation = "MINIMUM"
        clamp_max.location = (x - 20, y)
        clamp_max.inputs[1].default_value = (1.0, 1.0, 1.0)
        links.new(clamp_min.outputs["Vector"], clamp_max.inputs[0])
        vector_input = clamp_max.outputs["Vector"]

    multiply = nodes.new("ShaderNodeVectorMath")
    multiply.name = f"{label}_UV_SCALE"
    multiply.label = f"{label} UV scale"
    multiply.operation = "MULTIPLY"
    multiply.location = (x, y)
    multiply.inputs[1].default_value = (remap["width"], remap["height"], 1.0)
    add = nodes.new("ShaderNodeVectorMath")
    add.name = f"{label}_UV_OFFSET"
    add.label = f"{label} UV offset"
    add.operation = "ADD"
    add.location = (x + 190, y)
    # The baked WebGL atlas uses flipY=false and stores remap.y from the top
    # edge. Blender's Image Texture node addresses V from the bottom edge. Keep
    # the crop upright by moving its bottom edge to 1 - y - height.
    blender_y = 1.0 - remap["y"] - remap["height"]
    add.inputs[1].default_value = (remap["x"], blender_y, 0.0)
    links.new(vector_input, multiply.inputs[0])
    links.new(multiply.outputs["Vector"], add.inputs[0])
    return add


def create_watercolor_material(
    layer_name: str,
    control: bpy.types.Object,
    atlas: bpy.types.Image,
    mask: bpy.types.Image,
    sdf: bpy.types.Image,
    remap: dict[str, float],
    sdf_remap: dict[str, float] | None,
    reveal_start_seconds: float,
) -> bpy.types.Material:
    material = bpy.data.materials.new(f"WC_{layer_name}")
    material.use_nodes = True
    if hasattr(material, "preview_render_type"):
        material.preview_render_type = "FLAT"
    configure_transparency(material, "DITHERED")
    material.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    material["source_layer"] = layer_name
    material["atlas_remap"] = json.dumps(remap, sort_keys=True)
    material["reveal_start_seconds"] = reveal_start_seconds
    material["mask_edge_clip"] = "ColorRamp 0.02 -> 0.18; atlas padding is transparent"
    material["view_angle_policy"] = (
        "Double-sided 2D card; watercolor color is emitted through Principled BSDF "
        "to avoid view-angle diffuse-light changes; Principled Alpha uses dithered cutout transparency "
        "so atlas holes reveal the ground from front, grazing, and back views."
    )
    material["source_reveal_durations_seconds"] = json.dumps(
        {
            "alpha": REVEAL_ALPHA_SECONDS,
            "curve": REVEAL_CURVE_SECONDS,
            "rotation": REVEAL_ROTATION_SECONDS,
            "ink": REVEAL_INK_SECONDS,
            "cutout_and_ground": CUTOUT_AND_GROUND_SECONDS,
            "shadow": SOURCE_SHADOW_SECONDS,
        },
        sort_keys=True,
    )
    if sdf_remap:
        material["sdf_remap"] = json.dumps(sdf_remap, sort_keys=True)

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1000, 80)
    surface = nodes.new("ShaderNodeBsdfPrincipled")
    surface.name = "WATERCOLOR_SURFACE"
    surface.label = "Atlas color through Blender 5.0 Principled BSDF"
    surface.location = (620, 80)
    surface.inputs["Metallic"].default_value = 0.0
    surface.inputs["Roughness"].default_value = 1.0
    surface.inputs["Specular IOR Level"].default_value = 0.0
    surface.inputs["Emission Strength"].default_value = 1.0
    # Feed alpha directly into Principled instead of mixing a Transparent BSDF
    # with the surface. DITHERED visibility resolves each sample without the
    # per-object sorting used by BLENDED, so black mask regions do not hide a
    # ground or another cutout card behind this triangulated 2D surface.
    links.new(surface.outputs[0], output.inputs["Surface"])

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-900, 160)
    object_info = nodes.new("ShaderNodeObjectInfo")
    object_info.name = "OBJECT_ALPHA"
    object_info.label = "Animated object alpha; material preview remains opaque"
    object_info.location = (120, 20)
    atlas_uv = add_vector_remap(
        nodes,
        links,
        texcoord,
        remap,
        -700,
        240,
        "ATLAS",
        clamp_input=True,
    )

    atlas_node = nodes.new("ShaderNodeTexImage")
    atlas_node.name = "SOURCE_ATLAS"
    atlas_node.label = "Source watercolor atlas"
    atlas_node.image = atlas
    atlas_node.extension = "CLIP"
    atlas_node.interpolation = "Linear"
    atlas_node.location = (-260, 260)
    mask_node = nodes.new("ShaderNodeTexImage")
    mask_node.name = "SOURCE_MASK"
    mask_node.label = "Source watercolor mask"
    mask_node.image = mask
    mask_node.extension = "CLIP"
    mask_node.interpolation = "Linear"
    mask_node.location = (-260, -20)
    links.new(atlas_uv.outputs["Vector"], atlas_node.inputs["Vector"])
    links.new(atlas_uv.outputs["Vector"], mask_node.inputs["Vector"])
    # A watercolor card is a 2D painted surface, not a lit 3D object. Keep the
    # Principled surface for Blender 5.0 compatibility, but remove the diffuse
    # contribution so rotating the camera cannot turn the painting gray because
    # its single authored normal is facing away from the studio light.
    surface.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    links.new(atlas_node.outputs["Color"], surface.inputs["Emission Color"])

    def driven_value(name: str, property_name: str, y: float) -> bpy.types.Node:
        value = nodes.new("ShaderNodeValue")
        value.name = name
        value.label = f"Source runtime {property_name}"
        value.location = (120, y)
        driver = value.outputs[0].driver_add("default_value").driver
        variable = driver.variables.new()
        variable.name = "runtime_value"
        variable.type = "SINGLE_PROP"
        variable.targets[0].id = control
        variable.targets[0].data_path = f'["{property_name}"]'
        driver.expression = "runtime_value"
        return value

    driven_value("WEB_ALPHA_REFERENCE", "web_alpha", -120)
    driven_value("WEB_CURVE_COEF", "web_curve_coef", -230)
    driven_value("WEB_ROTATION_Z", "web_rotation_z", -340)
    driven_value("WEB_REVEAL_PROGRESS", "web_reveal_progress", -450)
    driven_value("WEB_CUTOUT_ALPHA", "web_cutout_alpha", -560)
    driven_value("WEB_GROUND_ALPHA", "web_ground_alpha", -670)
    driven_value("WEB_SHADOW_ALPHA", "web_shadow_alpha", -780)

    alpha_multiply = nodes.new("ShaderNodeMath")
    alpha_multiply.name = "MASK_X_REVEAL"
    alpha_multiply.operation = "MULTIPLY"
    alpha_multiply.location = (390, -60)
    mask_edge = nodes.new("ShaderNodeValToRGB")
    mask_edge.name = "SOURCE_MASK_EDGE_CLIP"
    mask_edge.label = "Suppress atlas padding and dark mask fringes"
    mask_edge.location = (120, -20)
    mask_edge.color_ramp.elements[0].position = 0.02
    mask_edge.color_ramp.elements[1].position = 0.18
    links.new(mask_node.outputs["Color"], mask_edge.inputs["Fac"])
    links.new(mask_edge.outputs["Color"], alpha_multiply.inputs[0])
    links.new(object_info.outputs["Alpha"], alpha_multiply.inputs[1])
    links.new(alpha_multiply.outputs[0], surface.inputs["Alpha"])

    if sdf_remap:
        frame = nodes.new("NodeFrame")
        frame.name = "SDF_REFERENCE_ONLY"
        frame.label = "SDF source input — preserved, not guessed into Blender shader"
        sdf_uv = add_vector_remap(nodes, links, texcoord, sdf_remap, -700, -440, "SDF")
        sdf_node = nodes.new("ShaderNodeTexImage")
        sdf_node.name = "SOURCE_SDF"
        sdf_node.label = "Source SDF (reference input)"
        sdf_node.image = sdf
        sdf_node.extension = "CLIP"
        sdf_node.interpolation = "Linear"
        sdf_node.location = (-260, -430)
        sdf_uv.parent = frame
        sdf_node.parent = frame
        links.new(sdf_uv.outputs["Vector"], sdf_node.inputs["Vector"])

    return material


def create_unlit_image_material(
    name: str,
    image: bpy.types.Image,
    transparent: bool = False,
    alpha_from_luminance: bool = False,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    if transparent:
        configure_transparency(material, "DITHERED")
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (500, 0)
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = image
    image_node.interpolation = "Linear"
    image_node.location = (-300, 0)
    surface = nodes.new("ShaderNodeBsdfPrincipled")
    surface.name = "IMAGE_SURFACE"
    surface.label = "Flat image through Blender 5.0 Principled BSDF"
    surface.location = (120, 60)
    surface.inputs["Metallic"].default_value = 0.0
    surface.inputs["Roughness"].default_value = 1.0
    surface.inputs["Specular IOR Level"].default_value = 0.0
    surface.inputs["Emission Strength"].default_value = 1.0
    links.new(image_node.outputs["Color"], surface.inputs["Base Color"])
    links.new(image_node.outputs["Color"], surface.inputs["Emission Color"])
    if transparent:
        alpha_socket = image_node.outputs["Alpha"]
        if alpha_from_luminance:
            luminance = nodes.new("ShaderNodeRGBToBW")
            luminance.name = "GROUND_PADDING_LUMINANCE"
            luminance.label = "Ground atlas black padding mask"
            luminance.location = (-80, -160)
            edge = nodes.new("ShaderNodeValToRGB")
            edge.name = "GROUND_PADDING_EDGE_CLIP"
            edge.label = "Hide black KTX2 atlas padding"
            edge.location = (100, -220)
            edge.color_ramp.elements[0].position = 0.015
            edge.color_ramp.elements[1].position = 0.06
            links.new(image_node.outputs["Color"], luminance.inputs["Color"])
            links.new(luminance.outputs["Val"], edge.inputs["Fac"])
            alpha_socket = edge.outputs["Color"]
            material["alpha_from_luminance"] = "ColorRamp 0.015 -> 0.06 hides black atlas padding"
        links.new(alpha_socket, surface.inputs["Alpha"])
        links.new(surface.outputs[0], output.inputs["Surface"])
    else:
        links.new(surface.outputs[0], output.inputs["Surface"])
    return material


def poisson_disk_fill(
    shape: tuple[float, float],
    rng: random.Random,
    min_distance: float = 1.8,
    max_distance: float = 2.8,
    tries: int = 7,
) -> list[tuple[float, float]]:
    """Deterministic fixed-density Poisson fill matching runtime module 5966."""
    width, height = shape
    cell_size = min_distance / math.sqrt(2.0)
    grid_width = max(1, math.ceil(width / cell_size))
    grid_height = max(1, math.ceil(height / cell_size))
    grid: list[int] = [-1] * (grid_width * grid_height)
    samples: list[tuple[float, float]] = []
    process: list[tuple[float, float]] = []

    def grid_index(point: tuple[float, float]) -> tuple[int, int]:
        return int(point[0] / cell_size), int(point[1] / cell_size)

    def add(point: tuple[float, float]) -> None:
        samples.append(point)
        process.append(point)
        gx, gy = grid_index(point)
        grid[gy * grid_width + gx] = len(samples) - 1

    def has_neighbour(point: tuple[float, float]) -> bool:
        gx, gy = grid_index(point)
        radius = 2
        for y in range(max(0, gy - radius), min(grid_height, gy + radius + 1)):
            for x in range(max(0, gx - radius), min(grid_width, gx + radius + 1)):
                sample_index = grid[y * grid_width + x]
                if sample_index < 0:
                    continue
                sample = samples[sample_index]
                if (point[0] - sample[0]) ** 2 + (point[1] - sample[1]) ** 2 < min_distance**2:
                    return True
        return False

    add((rng.random() * width, rng.random() * height))
    while process:
        current = process[0]
        accepted = False
        for _ in range(tries):
            distance = min_distance + (max_distance - min_distance) * rng.random()
            angle = rng.random() * math.tau
            candidate = (
                current[0] + math.cos(angle) * distance,
                current[1] + math.sin(angle) * distance,
            )
            if not (0.0 <= candidate[0] < width and 0.0 <= candidate[1] < height):
                continue
            if has_neighbour(candidate):
                continue
            add(candidate)
            accepted = True
            break
        if not accepted:
            process.pop(0)
    return samples


def create_grass_material(
    atlas: bpy.types.Image,
    gradients: bpy.types.Image,
    grass_reference: bpy.types.Image,
    noise_reference: bpy.types.Image,
) -> bpy.types.Material:
    material = bpy.data.materials.new("WC_PROCEDURAL_GRASS")
    material.use_nodes = True
    if hasattr(material, "preview_render_type"):
        material.preview_render_type = "FLAT"
    configure_transparency(material, "DITHERED")
    material.diffuse_color = (0.55, 0.64, 0.31, 1.0)
    material["source_algorithm"] = (
        "legacy app.js Grass: PoissonDiskSampling 1.8/2.8/7, clustered 7-24 blades, "
        "10 blade atlas regions, 24 gradient columns, global scale 5"
    )
    material["source_interaction"] = "cursor proximity reveals in 1s and falls in 3s"
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (900, 80)
    surface = nodes.new("ShaderNodeBsdfPrincipled")
    surface.name = "GRASS_SURFACE"
    surface.label = "Grass atlas through Blender 5.0 Principled BSDF"
    surface.location = (520, 160)
    surface.inputs["Metallic"].default_value = 0.0
    surface.inputs["Roughness"].default_value = 1.0
    surface.inputs["Specular IOR Level"].default_value = 0.0
    surface.inputs["Emission Strength"].default_value = 1.0
    links.new(surface.outputs[0], output.inputs["Surface"])

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-760, 220)
    blade = nodes.new("ShaderNodeTexImage")
    blade.name = "SOURCE_GRASS_BLADE_ATLAS"
    blade.label = "Source grass blade atlas"
    blade.image = atlas
    blade.extension = "CLIP"
    blade.interpolation = "Linear"
    blade.location = (-520, 220)
    links.new(texcoord.outputs["UV"], blade.inputs["Vector"])

    gradient_attribute = nodes.new("ShaderNodeAttribute")
    gradient_attribute.attribute_name = "gradient_u"
    gradient_attribute.location = (-520, -40)
    separate = nodes.new("ShaderNodeSeparateColor")
    separate.mode = "RGB"
    separate.location = (-280, 210)
    combine = nodes.new("ShaderNodeCombineXYZ")
    combine.location = (-60, 100)
    links.new(blade.outputs["Color"], separate.inputs["Color"])
    links.new(gradient_attribute.outputs["Fac"], combine.inputs["X"])
    links.new(separate.outputs["Red"], combine.inputs["Y"])

    gradient = nodes.new("ShaderNodeTexImage")
    gradient.name = "SOURCE_GRASS_COLOR_GRADIENTS"
    gradient.label = "Source 24-column grass gradients"
    gradient.image = gradients
    gradient.extension = "CLIP"
    gradient.interpolation = "Linear"
    gradient.location = (160, 180)
    links.new(combine.outputs["Vector"], gradient.inputs["Vector"])
    links.new(gradient.outputs["Color"], surface.inputs["Base Color"])
    links.new(gradient.outputs["Color"], surface.inputs["Emission Color"])

    object_info = nodes.new("ShaderNodeObjectInfo")
    object_info.name = "OBJECT_ALPHA"
    object_info.location = (160, -120)
    alpha_multiply = nodes.new("ShaderNodeMath")
    alpha_multiply.name = "BLADE_ALPHA_X_REVEAL"
    alpha_multiply.operation = "MULTIPLY"
    alpha_multiply.location = (390, -50)
    links.new(blade.outputs["Alpha"], alpha_multiply.inputs[0])
    links.new(object_info.outputs["Alpha"], alpha_multiply.inputs[1])
    links.new(alpha_multiply.outputs[0], surface.inputs["Alpha"])

    reference_frame = nodes.new("NodeFrame")
    reference_frame.name = "SOURCE_GRASS_REFERENCE_ONLY"
    reference_frame.label = "Source interaction/noise inputs — preserved"
    for index, (name, label, image) in enumerate(
        (
            ("SOURCE_GRASS_STROKES", "Source grassTest interaction texture", grass_reference),
            ("SOURCE_GRASS_NOISE", "Source wind noise", noise_reference),
        )
    ):
        node = nodes.new("ShaderNodeTexImage")
        node.name = name
        node.label = label
        node.image = image
        node.location = (-460 + 260 * index, -330)
        node.parent = reference_frame
    return material


def create_grass_layer(
    collection: bpy.types.Collection,
    layer: bpy.types.Object,
    runtime: dict[str, Any],
    material: bpy.types.Material,
    layer_index: int,
) -> tuple[bpy.types.Object | None, int]:
    if not runtime.get("has_ground", True):
        return None, 0
    vertices = [vertex.co for vertex in layer.data.vertices]
    if not vertices:
        return None, 0
    paper_width = max(vertex.y for vertex in vertices) - min(vertex.y for vertex in vertices)
    ground = runtime["ground"]
    ground_width = paper_width + 2.0 * float(ground["edges"])
    ground_depth = float(ground["depth"])
    if ground_width <= 0.0 or ground_depth <= 0.0:
        return None, 0

    rng = random.Random(GRASS_RANDOM_SEED + layer_index * 1009)
    margin_x, margin_y = 0.6, 0.4
    seeds = poisson_disk_fill(
        (max(ground_width - 2.0 * margin_x, 0.1), max(ground_depth - 2.0 * margin_y, 0.1)),
        rng,
    )
    points: list[tuple[float, float, float, int]] = []
    for seed in seeds:
        center_x = seed[0] + margin_x
        center_y = seed[1] + margin_y
        count = math.floor(7.0 + (25.0 - 7.0) * rng.random())
        cluster = math.floor(8.0 * rng.random())
        for _ in range(count):
            radial = rng.random()
            radius_x = (0.05 * margin_x) + (margin_x - 0.05 * margin_x) * radial
            radius_y = (0.05 * margin_y) + (margin_y - 0.05 * margin_y) * radial
            angle = math.tau * rng.random()
            distance_ratio = math.sqrt(radius_x**2 + radius_y**2) / math.sqrt(
                margin_x**2 + margin_y**2
            )
            inner_random = rng.random()
            inner_ratio_random = rng.random()
            inner_ratio = (1.0 - distance_ratio + inner_ratio_random) / 2.0
            inner_mix = (1.0 - (1.0 - distance_ratio) ** 3) * (1.0 - inner_ratio) + inner_random * inner_ratio
            scale = 1.0 + (0.2 - 1.0) * inner_mix
            points.append(
                (
                    center_x + math.cos(angle) * radius_x,
                    center_y + math.sin(angle) * radius_y,
                    scale,
                    cluster,
                )
            )
        center_random = rng.random()
        center_ratio = (1.0 + rng.random()) / 2.0
        center_mix = 1.0 * (1.0 - center_ratio) + center_random * center_ratio
        points.append((center_x, center_y, 1.0 + (0.2 - 1.0) * center_mix, cluster))

    mesh_vertices: list[tuple[float, float, float]] = []
    wind_vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    loop_uvs: list[tuple[float, float]] = []
    gradient_values: list[float] = []
    segments = 8
    for blade_index, point in enumerate(points):
        point_x, point_y, point_scale, cluster = point
        _, offset_x, offset_y, size_x, size_y = GRASS_BLADE_REMAPS[
            math.floor(len(GRASS_BLADE_REMAPS) * rng.random())
        ]
        aspect = size_x / size_y
        height = 0.5 * point_scale
        width = 1.5 * aspect * point_scale
        tilt = rng.random() - 0.5
        gradient_column = 3 * cluster + math.floor(3.0 * rng.random())
        gradient_u = (gradient_column + 0.5) / 24.0
        ground_x = -ground_depth * (point_y / ground_depth)
        ground_y = -0.5 * ground_width + ground_width * (point_x / ground_width)
        base_index = len(mesh_vertices)
        phase = rng.random() * math.tau
        for segment in range(segments + 1):
            progress = segment / segments
            taper = 1.0 + (0.2 - 1.0) * progress
            for side in (-1.0, 1.0):
                local_y = side * width * 0.5 * taper
                local_z = height * progress
                rotated_y = local_y * math.cos(tilt) - local_z * math.sin(tilt)
                rotated_z = local_y * math.sin(tilt) + local_z * math.cos(tilt)
                vertex = (ground_x, ground_y + rotated_y, rotated_z)
                mesh_vertices.append(vertex)
                wind = 0.12 * math.sin(phase) * progress**2
                wind_vertices.append((vertex[0] + wind, vertex[1], vertex[2]))
                gradient_values.append(gradient_u)
        for segment in range(segments):
            lower_left = base_index + 2 * segment
            lower_right = lower_left + 1
            upper_left = lower_left + 2
            upper_right = lower_left + 3
            faces.extend(
                (
                    (lower_left, lower_right, upper_right),
                    (lower_left, upper_right, upper_left),
                )
            )
            v0 = 1.0 - offset_y - size_y + size_y * (segment / segments)
            v1 = 1.0 - offset_y - size_y + size_y * ((segment + 1) / segments)
            uv_left = offset_x
            uv_right = offset_x + size_x
            loop_uvs.extend(
                (
                    (uv_left, v0),
                    (uv_right, v0),
                    (uv_right, v1),
                    (uv_left, v0),
                    (uv_right, v1),
                    (uv_left, v1),
                )
            )

    mesh = bpy.data.meshes.new(f"GRASS_{layer.name[5:]}_Mesh")
    mesh.from_pydata(mesh_vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="GrassAtlasUV")
    for loop, coordinate in zip(uv_layer.data, loop_uvs, strict=True):
        loop.uv = coordinate
    gradient_attribute = mesh.attributes.new(name="gradient_u", type="FLOAT", domain="POINT")
    for item, value in zip(gradient_attribute.data, gradient_values):
        item.value = value

    obj = bpy.data.objects.new(f"GRASS_{layer.name[5:]}", mesh)
    collection.objects.link(obj)
    obj.matrix_world = layer.matrix_world.copy()
    obj.hide_select = False
    obj.data.materials.append(material)
    obj["source_layer"] = layer.name[5:]
    obj["source_ground_width"] = ground_width
    obj["source_ground_depth"] = ground_depth
    obj["source_seed"] = GRASS_RANDOM_SEED + layer_index * 1009
    obj["source_generation"] = "deterministic mirror of legacy procedural Grass component"
    obj["source_interaction_boundary"] = (
        "Browser reveal follows cursor proximity; Blender timeline shows the authored asset after layer entry."
    )

    obj.shape_key_add(name="Basis", from_mix=False)
    wind_key = obj.shape_key_add(name="SOURCE_WIND", from_mix=False)
    wind_key.slider_min = -1.0
    wind_key.slider_max = 1.0
    for vertex, coordinate in zip(wind_key.data, wind_vertices):
        vertex.co = coordinate
    for frame in range(0, CAMERA_SAMPLE_COUNT, 30):
        phase_index = (frame // 30) % 4
        wind_key.value = (0.0, 1.0, 0.0, -1.0)[phase_index]
        wind_key.keyframe_insert(data_path="value", frame=frame)
    wind_key.value = 0.0
    wind_key.keyframe_insert(data_path="value", frame=CAMERA_SAMPLE_COUNT - 1)
    if mesh.shape_keys and mesh.shape_keys.animation_data and mesh.shape_keys.animation_data.action:
        mesh.shape_keys.animation_data.action.name = f"WEB_GRASS_WIND_{layer.name[5:]}"
        for curve in action_fcurves(mesh.shape_keys.animation_data.action):
            for point in curve.keyframe_points:
                point.interpolation = "SINE"

    start_frame = float(layer.get("source_effective_start_seconds", 0.0)) * FPS
    obj.color = (1.0, 1.0, 1.0, 0.0)
    obj.keyframe_insert(data_path="color", index=3, frame=max(0.0, start_frame - 1.0), group="GRASS_REVEAL")
    obj.color = (1.0, 1.0, 1.0, 1.0)
    obj.keyframe_insert(
        data_path="color",
        index=3,
        frame=start_frame + GRASS_REVEAL_SECONDS * FPS,
        group="GRASS_REVEAL",
    )
    if obj.animation_data and obj.animation_data.action:
        # Blender 5 stores the Object and Shape Key channels in one layered
        # Action with separate slots. Keep both source-derived wind and reveal
        # channels together instead of pretending they are two actions.
        obj.animation_data.action.name = f"WEB_GRASS_ANIMATION_{layer.name[5:]}"
        set_action_interpolation(obj, "SINE")
    return obj, len(points)


def create_reference_empty(collection: bpy.types.Collection, name: str, properties: dict[str, Any]) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 1.5
    collection.objects.link(obj)
    for key, value in properties.items():
        obj[key] = value
    return obj


def add_source_curve_shape_key(obj: bpy.types.Object) -> bool:
    """Bake the source vertex-shader paper curve into an editable shape key.

    The WebGL shader offsets local X by
    cos(((uv.y + .5) * .5) * 2PI) * .2 * sin(2PI * uCurveCoef).
    The shape key stores the UV-dependent term; its value receives the animated
    sin(2PI * quart.out(progress)) coefficient.
    """
    mesh = obj.data
    if not mesh.uv_layers.active or not mesh.vertices:
        return False
    basis = obj.shape_key_add(name="Basis", from_mix=False)
    curve = obj.shape_key_add(name="WEB_SOURCE_CURVE", from_mix=False)
    del basis
    curve.slider_min = -1.0
    curve.slider_max = 1.0

    uv_sums = [[0.0, 0] for _ in mesh.vertices]
    uv_data = mesh.uv_layers.active.data
    for loop in mesh.loops:
        uv_sums[loop.vertex_index][0] += uv_data[loop.index].uv.y
        uv_sums[loop.vertex_index][1] += 1
    for vertex in mesh.vertices:
        total, count = uv_sums[vertex.index]
        uv_y = total / count if count else 0.0
        adjusted_uv_y = (uv_y + 0.5) * 0.5
        source_offset_x = math.cos(adjusted_uv_y * math.pi * 2.0) * 0.2
        curve.data[vertex.index].co.x += source_offset_x

    driver = curve.driver_add("value").driver
    variable = driver.variables.new()
    variable.name = "curve_wave"
    variable.type = "SINGLE_PROP"
    variable.targets[0].id = obj
    variable.targets[0].data_path = '["web_curve_wave"]'
    driver.expression = "curve_wave"
    return True


def animate_watercolor_layer(
    obj: bpy.types.Object,
    layer_name: str,
    start_seconds: float,
    group_stagger_index: int,
) -> dict[str, Any]:
    start_frame = (start_seconds + 0.3 * group_stagger_index) * FPS
    obj["source_layer"] = layer_name
    obj["source_start_seconds"] = start_seconds
    obj["source_group_stagger_seconds"] = 0.3 * group_stagger_index
    obj["source_effective_start_seconds"] = start_frame / FPS
    obj["source_reveal_type"] = "default"
    obj["source_animation_note"] = (
        "Baked from legacy runtime: alpha .01s, quart.out curve 10s, "
        "back.out rotation 7s, linear ink 15s, cutout/ground .4s, shadow 1s"
    )

    for name, initial in (
        ("web_alpha", 0.0),
        ("web_curve_coef", 0.0),
        ("web_curve_wave", 0.0),
        ("web_rotation_z", -math.pi / 2.0),
        ("web_reveal_progress", 0.0),
        ("web_cutout_alpha", 0.0),
        ("web_ground_alpha", 0.0),
        ("web_shadow_alpha", 0.0),
    ):
        obj[name] = initial
        keyframe_custom_property(obj, name, max(0.0, start_frame - 1.0), initial)

    obj.color = (1.0, 1.0, 1.0, 0.0)
    obj.keyframe_insert(
        data_path="color",
        index=3,
        frame=max(0.0, start_frame - 1.0),
        group="WEB_RUNTIME",
    )

    # Source paint instances rotate around WebGL Z. After the glTF Y-up to
    # Blender Z-up conversion this is the local Blender Y axis. The source
    # paint matrix uses -rotationZ, yielding this converted delta rotation.
    obj.rotation_mode = "XYZ"
    obj.delta_rotation_euler = (0.0, -math.pi / 2.0, 0.0)
    obj.keyframe_insert(data_path="delta_rotation_euler", frame=max(0.0, start_frame - 1.0), group="WEB_RUNTIME")

    sample_property(obj, "web_alpha", start_frame, REVEAL_ALPHA_SECONDS, sine_in_out)
    alpha_frames = round(REVEAL_ALPHA_SECONDS * FPS)
    for offset in range(alpha_frames + 1):
        progress = offset / max(1, alpha_frames)
        color = list(obj.color)
        color[3] = sine_in_out(progress)
        obj.color = color
        obj.keyframe_insert(
            data_path="color",
            index=3,
            frame=start_frame + offset,
            group="WEB_RUNTIME",
        )
    sample_property(obj, "web_curve_coef", start_frame, REVEAL_CURVE_SECONDS, quart_out)
    sample_property(
        obj,
        "web_curve_wave",
        start_frame,
        REVEAL_CURVE_SECONDS,
        lambda progress: math.sin(math.pi * 2.0 * quart_out(progress)),
    )
    sample_property(
        obj,
        "web_rotation_z",
        start_frame,
        REVEAL_ROTATION_SECONDS,
        lambda progress: (-math.pi / 2.0) * (1.0 - back_out(progress)),
    )
    rotation_frames = round(REVEAL_ROTATION_SECONDS * FPS)
    for offset in range(rotation_frames + 1):
        progress = offset / max(1, rotation_frames)
        source_rotation = (-math.pi / 2.0) * (1.0 - back_out(progress))
        obj.delta_rotation_euler[1] = source_rotation
        obj.keyframe_insert(data_path="delta_rotation_euler", frame=start_frame + offset, group="WEB_RUNTIME")
    sample_property(
        obj,
        "web_reveal_progress",
        start_frame,
        REVEAL_INK_SECONDS,
        lambda progress: 15.0 * progress,
    )
    sample_property(obj, "web_cutout_alpha", start_frame, CUTOUT_AND_GROUND_SECONDS, sine_in_out)
    sample_property(obj, "web_ground_alpha", start_frame, CUTOUT_AND_GROUND_SECONDS, sine_in_out)
    sample_property(obj, "web_shadow_alpha", start_frame, SOURCE_SHADOW_SECONDS, sine_out)

    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert(data_path="hide_viewport", frame=max(0.0, start_frame - 1.0), group="WEB_RUNTIME")
    obj.keyframe_insert(data_path="hide_render", frame=max(0.0, start_frame - 1.0), group="WEB_RUNTIME")
    obj.hide_viewport = False
    obj.hide_render = False
    obj.keyframe_insert(data_path="hide_viewport", frame=start_frame, group="WEB_RUNTIME")
    obj.keyframe_insert(data_path="hide_render", frame=start_frame, group="WEB_RUNTIME")

    if obj.animation_data and obj.animation_data.action:
        obj.animation_data.action.name = f"WEB_REVEAL_{layer_name}"
    set_action_interpolation(obj, "LINEAR")
    return {
        "layer": layer_name,
        "start_frame": start_frame,
        "end_frame": start_frame + REVEAL_INK_SECONDS * FPS,
        "action": obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None,
    }


def build_runtime_camera_rig(
    animation_scene: bpy.types.Scene,
    source_scene: bpy.types.Scene,
    source_camera: bpy.types.Object,
    collection: bpy.types.Collection,
) -> tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]:
    rig = bpy.data.objects.new("WEB_CAMERA_PATH_RIG", None)
    rig.empty_display_type = "ARROWS"
    rig.empty_display_size = 2.0
    rig.rotation_mode = "QUATERNION"
    rig["source_object"] = "Camera_Animation_Baked"
    rig["source_coordinate_system"] = "glTF/WebGL Y-up; Blender import converted to Z-up"
    rig["baked_samples"] = CAMERA_SAMPLE_COUNT
    collection.objects.link(rig)

    control = bpy.data.objects.new("WEB_CAMERA_INTERACTION_CONTROL", None)
    control.empty_display_type = "CIRCLE"
    control.empty_display_size = 1.0
    control["loader_x"] = 0.0
    # The loader transform happens before the scroll timeline. Keep it as an
    # explicit optional control instead of contaminating the GLB camera path.
    control["loader_z"] = 0.0
    control["loader_final_z"] = CAMERA_LOADER_FINAL_Z
    control["mouse_pitch"] = 0.0
    control["mouse_yaw"] = 0.0
    control["source_loader_start"] = json.dumps({"x": 0.25, "z": -0.85, "yaw_radians": -0.037 * math.pi})
    control["source_loader_end"] = json.dumps({"x": 0.0, "z": 0.4, "yaw_radians": 0.0})
    control["source_loader_duration_seconds"] = 5.0
    control["source_mouse_rotation_degrees"] = json.dumps({"pitch": 2.55, "yaw": 9.2, "damping": 0.3})
    collection.objects.link(control)

    camera = bpy.data.objects.new("WEB_CAMERA_EDITABLE", source_camera.data.copy())
    camera.data.name = "WEB_CAMERA_EDITABLE_Data"
    camera.location = (0.0, 0.0, 0.0)
    camera.rotation_mode = "QUATERNION"
    camera.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    camera.scale = (1.0, 1.0, 1.0)
    camera["source_runtime_model"] = "direct baked camera with optional delta interaction controls"
    camera["source_loader_final_local_z"] = CAMERA_LOADER_FINAL_Z
    camera["main_timeline_loader_offset"] = 0.0
    collection.objects.link(camera)

    for data_path, index, property_name in (
        ("delta_location", 0, "loader_x"),
        ("delta_location", 2, "loader_z"),
        ("delta_rotation_euler", 0, "mouse_pitch"),
        ("delta_rotation_euler", 1, "mouse_yaw"),
    ):
        driver = camera.driver_add(data_path, index).driver
        variable = driver.variables.new()
        variable.name = "runtime_value"
        variable.type = "SINGLE_PROP"
        variable.targets[0].id = control
        variable.targets[0].data_path = f'["{property_name}"]'
        driver.expression = "runtime_value"

    # Bake Blender's evaluated glTF camera world transform onto a clean path
    # rig. Location, rotation and scale are all preserved because Blender's
    # camera view matrix uses the authored GLB object scale.
    source_scene.frame_set(1)
    source_scene.frame_set(0)
    bpy.context.view_layer.update()
    for frame in range(CAMERA_SAMPLE_COUNT):
        bpy.context.window.scene = source_scene
        source_scene.frame_set(frame)
        bpy.context.view_layer.update()
        source_matrix = authored_world_matrix(source_camera)
        location, quaternion, source_scale = source_matrix.decompose()
        rig.location = location
        rig.rotation_quaternion = quaternion
        rig.scale = source_scale
        camera.location = location
        camera.rotation_quaternion = quaternion
        camera.scale = source_scale
        rig.keyframe_insert(data_path="location", frame=frame, group="CAMERA_PATH")
        rig.keyframe_insert(data_path="rotation_quaternion", frame=frame, group="CAMERA_PATH")
        rig.keyframe_insert(data_path="scale", frame=frame, group="CAMERA_PATH")
        camera.keyframe_insert(data_path="location", frame=frame, group="CAMERA_PATH")
        camera.keyframe_insert(data_path="rotation_quaternion", frame=frame, group="CAMERA_PATH")
        camera.keyframe_insert(data_path="scale", frame=frame, group="CAMERA_PATH")
    if rig.animation_data and rig.animation_data.action:
        rig.animation_data.action.name = "WEB_CAMERA_PATH_BAKED"
    if camera.animation_data and camera.animation_data.action:
        camera.animation_data.action.name = "WEB_CAMERA_ACTIVE_BAKED"
    set_action_interpolation(rig, "LINEAR")
    set_action_interpolation(camera, "LINEAR")
    bpy.context.window.scene = animation_scene
    animation_scene.camera = camera
    animation_scene.frame_set(0)
    return rig, camera, control


def build_web_master(
    animation_scene: bpy.types.Scene,
    artist_scene: bpy.types.Scene,
    source_scene: bpy.types.Scene,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    glb_path = require(ASSETS / "models/scene.glb")
    before = set(bpy.data.objects)
    bpy.context.window.scene = source_scene
    bpy.ops.import_scene.gltf(filepath=str(glb_path), import_scene_as_collection=False)
    imported = sorted(set(bpy.data.objects) - before, key=lambda item: item.name)
    if not imported:
        raise RuntimeError("glTF import produced no objects")

    source = new_collection(source_scene, "SOURCE_GLTF_MIRROR")
    for obj in imported:
        move_object_to_collection(obj, source)
        obj.hide_select = True
        obj["source_mirror"] = True
    # The source mirror lives only in SOURCE_REFERENCE. It remains visible there
    # for inspection but is never linked into either artist-facing scene.
    source.hide_viewport = False
    source.hide_render = False
    source["viewport_visibility_reason"] = "Visible only in the locked SOURCE_REFERENCE scene."

    # The glTF watercolor meshes are children of the `layers` transform.  The
    # importer can leave matrix_world stale until the view layer is evaluated;
    # copying before this update silently copies each mesh's local transform and
    # shifts every editable layer away from the authored camera path.
    bpy.context.view_layer.update()

    atlas = load_image(ASSETS / "textures/atlas/texture.jpg", "sRGB")
    mask = load_image(ASSETS / "textures/atlas/texture_mask.jpg", "Non-Color")
    sdf = load_image(ASSETS / "textures/atlas/sdf.png", "Non-Color")
    ground_atlas = load_image(GENERATED / "converted/ground_atlas.png", "sRGB")
    grass_atlas = load_image(ASSETS / "textures/grass/atlas.png", "sRGB")
    grass_gradients = load_image(ASSETS / "textures/grass/color-gradients.jpg", "sRGB")
    grass_reference = load_image(ASSETS / "textures/grassTest.png", "Non-Color")
    grass_noise = load_image(ASSETS / "textures/noise.jpeg", "Non-Color")

    editable = new_collection(animation_scene, "EDITABLE_WATERCOLOR")
    # Ground is intentionally linked only into ARTIST_EDIT. WEB_ANIMATION remains
    # the source-layer mirror; no Blender shadow approximation is added.
    ground_collection = new_collection(artist_scene, "GROUND_AND_PAPER")
    grass_collection = new_collection(animation_scene, "PROCEDURAL_GRASS")
    ground_collection.hide_render = False
    ground_collection.hide_viewport = False
    ground_collection["default_render_state"] = "enabled in ARTIST_EDIT only"
    ground_collection["reason"] = (
        "The source WebGL runtime rebuilds Ground through a custom shader; this editable atlas mirror "
        "is enabled in ARTIST_EDIT and excluded from WEB_ANIMATION."
    )
    hotspots = new_collection(animation_scene, "HOTSPOTS_AND_TITLES")
    camera_collection = new_collection(animation_scene, "CAMERA_RIG")
    references = new_collection(animation_scene, "REFERENCE_ONLY")
    references.hide_render = True

    atlas_remaps = manifest["watercolor"]["texture_atlas_remaps"]
    sdf_remaps = manifest["watercolor"]["sdf_atlas_remaps"]
    schedule = manifest["watercolor"]["layer_schedule_seconds"]
    legacy_runtime = manifest["watercolor"]["legacy_layer_runtime"]
    source_by_name = {obj.name: obj for obj in imported}
    editable_meshes: list[str] = []
    layer_animations: list[dict[str, Any]] = []
    grass_objects: list[str] = []
    grass_blade_count = 0
    schedule_occurrences: dict[float, int] = {}
    grass_material = create_grass_material(
        grass_atlas,
        grass_gradients,
        grass_reference,
        grass_noise,
    )

    for layer_index, (layer_name, remap) in enumerate(atlas_remaps.items()):
        original = source_by_name.get(layer_name)
        if original is None or original.type != "MESH":
            raise RuntimeError(f"Missing source mesh for watercolor layer: {layer_name}")
        duplicate = original.copy()
        duplicate.data = original.data.copy()
        duplicate.animation_data_clear()
        duplicate.hide_select = False
        duplicate.name = f"EDIT_{layer_name}"
        duplicate.data.name = f"EDIT_{layer_name}_Mesh"
        topology_cleanup = optimize_watercolor_card_mesh(duplicate.data)
        source_world_matrix = authored_world_matrix(original)
        duplicate.parent = None
        editable.objects.link(duplicate)
        duplicate.matrix_world = source_world_matrix
        start_seconds = float(schedule[layer_name])
        stagger_index = schedule_occurrences.get(start_seconds, 0)
        schedule_occurrences[start_seconds] = stagger_index + 1
        has_curve_shape_key = add_source_curve_shape_key(duplicate)
        duplicate["has_source_curve_shape_key"] = has_curve_shape_key
        duplicate["flattened_source_plane_span"] = topology_cleanup["flattened_plane_span"]
        duplicate["merged_source_duplicate_vertices"] = topology_cleanup["merged_vertices"]
        duplicate["removed_source_degenerate_faces"] = topology_cleanup["removed_degenerate_faces"]
        duplicate["reversed_source_faces"] = topology_cleanup["reversed_faces"]
        layer_animations.append(
            animate_watercolor_layer(duplicate, layer_name, start_seconds, stagger_index)
        )
        material = create_watercolor_material(
            layer_name,
            duplicate,
            atlas,
            mask,
            sdf,
            remap,
            sdf_remaps.get(layer_name),
            start_seconds,
        )
        duplicate.data.materials.clear()
        duplicate.data.materials.append(material)
        duplicate["source_object"] = original.name
        editable_meshes.append(duplicate.name)
        grass_object, layer_grass_blades = create_grass_layer(
            grass_collection,
            duplicate,
            legacy_runtime[layer_name],
            grass_material,
            layer_index,
        )
        if grass_object is not None:
            grass_objects.append(grass_object.name)
            grass_blade_count += layer_grass_blades
    original_ground = source_by_name.get("Ground")
    if original_ground is None:
        raise RuntimeError("Ground mesh was not found")
    editable_ground = original_ground.copy()
    editable_ground.data = original_ground.data.copy()
    editable_ground.hide_select = False
    editable_ground.name = "EDIT_Ground"
    editable_ground.data.name = "EDIT_Ground_Mesh"
    source_ground_world_matrix = authored_world_matrix(original_ground)
    editable_ground.parent = None
    ground_collection.objects.link(editable_ground)
    editable_ground.matrix_world = source_ground_world_matrix
    ground_material = create_unlit_image_material(
        "WC_Ground_Atlas",
        ground_atlas,
        transparent=True,
        alpha_from_luminance=True,
    )
    ground_material["source_ktx2"] = relative_to_blend(ASSETS / "textures/grounds/atlas.ktx2")
    ground_material["conversion"] = "KTX2 UASTC/Zstd transcoded losslessly to RGBA8 PNG"
    editable_ground.data.materials.clear()
    editable_ground.data.materials.append(ground_material)

    paper_paths = {
        "texture": relative_to_blend(ASSETS / "textures/paper/texture.jpg"),
        "normal": relative_to_blend(ASSETS / "textures/paper/normal.jpg"),
        "matcap": relative_to_blend(ASSETS / "textures/paper/matcap.png"),
    }
    create_reference_empty(
        ground_collection,
        "PAPER_PIPELINE_REFERENCE",
        {"paths": json.dumps(paper_paths), "status": "source inputs preserved; custom WebGL post-process not guessed"},
    )

    source_camera = source_by_name.get("Camera_Animation_Baked")
    if source_camera is None or source_camera.type != "CAMERA":
        raise RuntimeError("Animated source camera was not found")
    source_scene.camera = source_camera
    camera_rig, camera, camera_control = build_runtime_camera_rig(
        animation_scene,
        source_scene,
        source_camera,
        camera_collection,
    )

    converted_font = GENERATED / "converted/CanelaText-Light.ttf"
    font = bpy.data.fonts.load(str(require(converted_font)))
    for hotspot in manifest["hotspots"]:
        title = hotspot["title"]
        source_node = source_by_name.get(title)
        if source_node is None:
            raise RuntimeError(f"Missing title/hotspot node: {title}")
        marker = create_reference_empty(
            hotspots,
            f"HOTSPOT_{hotspot['id']:02d}",
            {
                "scene_id": hotspot["id"],
                "title": title,
                "focus_progress": hotspot["focus_progress"],
                "source_node": title,
            },
        )
        marker.matrix_world = authored_world_matrix(source_node)
        text_curve = bpy.data.curves.new(f"TITLE_{hotspot['id']:02d}_Curve", "FONT")
        text_curve.body = title
        text_curve.font = font
        text_curve.align_x = "CENTER"
        text_curve.size = 1.0
        text_obj = bpy.data.objects.new(f"TITLE_{hotspot['id']:02d}_{title}", text_curve)
        text_obj.matrix_world = authored_world_matrix(source_node)
        text_obj.hide_render = True
        text_obj["annotation_only"] = True
        text_obj["reason"] = "Web runtime renders titles through MSDF; Blender text is an editable annotation"
        hotspots.objects.link(text_obj)

    create_reference_empty(
        references,
        "WEBGL_SHADER_INPUTS",
        {
            "atlas_sdf": relative_to_blend(ASSETS / "textures/atlas/sdf.png"),
            "dry_lut": relative_to_blend(ASSETS / "lut/dry.3DL"),
            "ink_lut": relative_to_blend(ASSETS / "lut/ink.3DL"),
            "paper": json.dumps(paper_paths),
            "noise": relative_to_blend(ASSETS / "textures/noise.jpeg"),
            "status": "preserved as source parameters; no pixel-equivalence claim across renderers",
        },
    )
    create_reference_empty(
        references,
        "SOURCE_RUNTIME_REFERENCE",
        {
            "app_js": relative_to_blend(SNAPSHOT / "runtime/app.js"),
            "scene_manifest": relative_to_blend(MANIFEST),
            "runtime_kind": "legacy WebGL plus extracted R3F configuration",
        },
    )

    shared_collections = (
        editable,
        grass_collection,
        hotspots,
        camera_collection,
        references,
    )
    for collection in shared_collections:
        artist_scene.collection.children.link(collection)
    artist_scene.camera = camera

    runtime_animation = json.dumps(
        {
            "layers": len(layer_animations),
            "alpha_seconds": REVEAL_ALPHA_SECONDS,
            "curve_seconds": REVEAL_CURVE_SECONDS,
            "rotation_seconds": REVEAL_ROTATION_SECONDS,
            "ink_seconds": REVEAL_INK_SECONDS,
            "cutout_and_ground_seconds": CUTOUT_AND_GROUND_SECONDS,
            "source_shadow_seconds": SOURCE_SHADOW_SECONDS,
        },
        sort_keys=True,
    )
    for scene in (animation_scene, artist_scene):
        scene["source_mesh_count"] = len([obj for obj in imported if obj.type == "MESH"])
        scene["source_node_count"] = len(manifest["gltf"]["nodes"])
        scene["camera_animation_samples"] = manifest["gltf"]["animation_sample_count"]
        scene["camera_animation_duration_seconds"] = manifest["gltf"]["animation_duration_seconds"]
        scene["watercolor_runtime_animation"] = runtime_animation
    source_scene["source_mesh_count"] = len([obj for obj in imported if obj.type == "MESH"])
    source_scene["source_node_count"] = len(manifest["gltf"]["nodes"])
    return {
        "imported_objects": len(imported),
        "source_meshes": len([obj for obj in imported if obj.type == "MESH"]),
        "editable_watercolor_meshes": len(editable_meshes),
        "hotspots": len(manifest["hotspots"]),
        "camera": camera.name,
        "camera_rig": camera_rig.name,
        "camera_control": camera_control.name,
        "camera_loader_final_local_z": CAMERA_LOADER_FINAL_Z,
        "camera_main_timeline_loader_offset": 0.0,
        "animated_watercolor_layers": len(layer_animations),
        "procedural_grass_objects": len(grass_objects),
        "procedural_grass_blades": grass_blade_count,
        "procedural_grass_names": grass_objects,
        "artist_world_color": ARTIST_WORLD_COLOR,
        "artist_only_collections": [ground_collection.name],
        "watercolor_animation_actions": [item["action"] for item in layer_animations],
        "watercolor_animation_end_frame": max(item["end_frame"] for item in layer_animations),
        "removed_source_degenerate_faces": sum(
            int(bpy.data.objects[name].get("removed_source_degenerate_faces", 0))
            for name in editable_meshes
        ),
        "merged_source_duplicate_vertices": sum(
            int(bpy.data.objects[name].get("merged_source_duplicate_vertices", 0))
            for name in editable_meshes
        ),
        "reversed_source_faces": sum(
            int(bpy.data.objects[name].get("reversed_source_faces", 0))
            for name in editable_meshes
        ),
    }


def create_video_material(
    name: str,
    movie_path: Path,
    control: bpy.types.Object | None = None,
) -> bpy.types.Material:
    image = bpy.data.images.load(str(require(movie_path)), check_existing=False)
    image.source = "MOVIE"
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (650, 0)
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.image_user.frame_start = 0
    texture.image_user.frame_duration = 600
    texture.image_user.use_auto_refresh = True
    texture.image_user.use_cyclic = True
    texture.location = (-400, 0)
    emission = nodes.new("ShaderNodeEmission")
    emission.location = (0, 80)
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    if control is None:
        links.new(emission.outputs[0], output.inputs["Surface"])
    else:
        configure_transparency(material)
        transparent = nodes.new("ShaderNodeBsdfTransparent")
        transparent.location = (0, -100)
        mix = nodes.new("ShaderNodeMixShader")
        mix.location = (390, 0)
        value = nodes.new("ShaderNodeValue")
        value.name = "OVER_MIX"
        value.label = "Driven by OVER_MIX_CONTROL['mix']"
        value.location = (140, -180)
        driver = value.outputs[0].driver_add("default_value").driver
        variable = driver.variables.new()
        variable.name = "blend_value"
        variable.type = "SINGLE_PROP"
        variable.targets[0].id = control
        variable.targets[0].data_path = '["mix"]'
        driver.expression = "blend_value"
        links.new(value.outputs[0], mix.inputs[0])
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs["Surface"])
    material["source_movie"] = relative_to_blend(movie_path)
    return material


def add_plane(scene: bpy.types.Scene, name: str, width: float, height: float, z: float) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    half_width = width / 2.0
    half_height = height / 2.0
    mesh.from_pydata(
        [(-half_width, -half_height, 0), (half_width, -half_height, 0), (half_width, half_height, 0), (-half_width, half_height, 0)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.uv_layers.new(name="UVMap")
    uv = mesh.uv_layers.active.data
    for loop, coordinate in zip(uv, ((0, 0), (1, 0), (1, 1), (0, 1)), strict=True):
        loop.uv = coordinate
    obj = bpy.data.objects.new(name, mesh)
    obj.location.z = z
    scene.collection.objects.link(obj)
    return obj


def build_video_scene(scene_id: int, device: str, width: int, height: int) -> bpy.types.Scene:
    name = f"LANDSCAPE_{scene_id:02d}_{device.upper()}"
    scene = bpy.data.scenes.new(name)
    set_render(scene, width, height, 600)
    scene["workbench_role"] = "editable base/over landscape movie pair"
    scene["scene_id"] = scene_id
    scene["device"] = device
    scene["over_mix_default"] = 0.0
    scene.world = bpy.data.worlds.new(f"{name}_World")
    scene.world.color = (0.0, 0.0, 0.0)

    aspect = width / height
    camera_data = bpy.data.cameras.new(f"{name}_CameraData")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 2.0
    camera = bpy.data.objects.new(f"{name}_Camera", camera_data)
    camera.location = (0.0, 0.0, 2.0)
    scene.collection.objects.link(camera)
    scene.camera = camera

    control = bpy.data.objects.new("OVER_MIX_CONTROL", None)
    control.empty_display_type = "CIRCLE"
    control["mix"] = 0.0
    control["description"] = "0 shows base, 1 shows over; no transition timing is guessed"
    scene.collection.objects.link(control)

    base_path = ASSETS / f"videos/{device}/base/{scene_id}.mp4"
    over_path = ASSETS / f"videos/{device}/over/{scene_id}.mp4"
    base = add_plane(scene, "BASE_VIDEO", aspect * 2.0, 2.0, 0.0)
    over = add_plane(scene, "OVER_VIDEO", aspect * 2.0, 2.0, 0.001)
    base.data.materials.append(create_video_material(f"{name}_Base", base_path))
    over.data.materials.append(create_video_material(f"{name}_Over", over_path, control))
    scene.frame_set(0)
    return scene


def configure_artist_workspace(
    animation_scene: bpy.types.Scene,
    artist_scene: bpy.types.Scene,
    source_scene: bpy.types.Scene,
) -> str:
    animation_scene.frame_set(0)
    source_scene.frame_set(0)
    artist_scene.frame_set(3586)
    animation_scene.timeline_markers.new("ANIMATION_START", frame=0)
    animation_scene.timeline_markers.new("ALL_LAYERS_REVEALED", frame=3586)
    artist_scene.timeline_markers.new("EDITING_POSE", frame=3586)

    bpy.context.window.scene = artist_scene
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    active = bpy.data.objects.get("EDIT_tree_1")
    if active is None:
        raise RuntimeError("Default editable object EDIT_tree_1 is missing")
    for obj in bpy.data.collections["EDITABLE_WATERCOLOR"].objects:
        obj.hide_select = False
    active.hide_set(False)
    active.select_set(True)
    bpy.context.view_layer.objects.active = active
    artist_scene["default_selected_object"] = active.name

    # The user's Blender language and translation preferences remain untouched.
    # Save only project-local viewport state: a neutral bright studio background
    # and a framed editable tree rather than the hidden custom Ground reference.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                shading = area.spaces.active.shading
                shading.type = "MATERIAL"
                shading.use_scene_world = False
                shading.use_scene_lights = False
                shading.background_type = "VIEWPORT"
                shading.background_color = ARTIST_WORLD_COLOR
    layout = bpy.data.workspaces.get(DEFAULT_WORKSPACE_NAME)
    if layout is not None:
        bpy.context.window.workspace = layout
        for area in bpy.context.screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((item for item in area.regions if item.type == "WINDOW"), None)
            if region is None:
                continue
            with bpy.context.temp_override(area=area, region=region):
                bpy.ops.view3d.view_axis(type="RIGHT", align_active=False)
                bpy.ops.view3d.view_selected(use_all_regions=False)
    return active.name


def main() -> None:
    require(MANIFEST)
    require(GENERATED / "converted/ground_atlas.png")
    require(GENERATED / "converted/CanelaText-Light.ttf")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    animation_scene, artist_scene, source_scene = clear_file()
    web_summary = build_web_master(animation_scene, artist_scene, source_scene, manifest)
    video_scenes = []
    for device, width, height in (("desktop", 1920, 1080), ("mobile", 810, 1080)):
        for scene_id in range(1, 7):
            video_scenes.append(build_video_scene(scene_id, device, width, height).name)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    selected_object = configure_artist_workspace(animation_scene, artist_scene, source_scene)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), check_existing=False)
    portable_assets = make_blend_assets_portable(OUTPUT.parent)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), check_existing=False)
    report = {
        "blender_version": bpy.app.version_string,
        "output": str(OUTPUT),
        "web_animation": web_summary,
        "default_scene": artist_scene.name,
        "default_selected_object": selected_object,
        "animation_collections": sorted(collection.name for collection in animation_scene.collection.children),
        "artist_collections": sorted(collection.name for collection in artist_scene.collection.children),
        "source_collections": sorted(collection.name for collection in source_scene.collection.children),
        "video_scenes": video_scenes,
        "total_scenes": len(bpy.data.scenes),
        "external_images": len(bpy.data.images),
        "external_fonts": len([font for font in bpy.data.fonts if font.filepath and font.filepath != "<builtin>"]),
        "portable_assets": portable_assets,
        "relative_external_paths": all(
            not image.filepath or image.filepath.startswith("//") or image.packed_file
            for image in bpy.data.images
        ) and all(
            not font.filepath or font.filepath == "<builtin>" or font.filepath.startswith("//") or font.packed_file
            for font in bpy.data.fonts
        ),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Saved {OUTPUT}")
    log(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        log(f"ERROR: {error!r}")
        traceback.print_exc()
        sys.stderr.flush()
        sys.stdout.flush()
        os._exit(1)
