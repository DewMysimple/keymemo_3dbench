from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector


DISPLAY_PREFIX = "展示_Butterfly_Master_源_FBX_01_"


def world_bounds(scene: bpy.types.Scene, objects: list[bpy.types.Object], frames: list[int]) -> tuple[Vector, Vector]:
    minimum = Vector((float("inf"),) * 3)
    maximum = Vector((float("-inf"),) * 3)
    for frame in frames:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in objects:
            evaluated = obj.evaluated_get(depsgraph)
            for corner in evaluated.bound_box:
                world = evaluated.matrix_world @ Vector(corner)
                for axis in range(3):
                    minimum[axis] = min(minimum[axis], world[axis])
                    maximum[axis] = max(maximum[axis], world[axis])
    return minimum, maximum


def ensure_preview_camera(scene: bpy.types.Scene, objects: list[bpy.types.Object], frames: list[int]) -> None:
    minimum, maximum = world_bounds(scene, objects, frames)
    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    view_axis = min(range(3), key=lambda axis: size[axis])
    view_vector = Vector((0.0, 0.0, 0.0))
    view_vector[view_axis] = 1.0

    camera_data = bpy.data.cameras.new("MyButterfly_WingPreview_Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(size) * 1.15
    camera = bpy.data.objects.new(camera_data.name, camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + view_vector * max(size) * 2.0
    up_axis = "Y" if view_axis != 1 else "X"
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", up_axis).to_euler()
    scene.camera = camera

    key = bpy.data.lights.new("MyButterfly_WingPreview_Key", "AREA")
    key.energy = 1200.0
    key.shape = "DISK"
    key.size = max(size) * 1.5
    key_obj = bpy.data.objects.new(key.name, key)
    scene.collection.objects.link(key_obj)
    key_obj.location = camera.location + Vector((0.0, 0.0, max(size) * 0.5))
    key_obj.rotation_euler = (center - key_obj.location).to_track_quat("-Z", "Y").to_euler()

    if scene.world is None:
        scene.world = bpy.data.worlds.new("MyButterfly_WingPreview_World")
    scene.world.color = (0.04, 0.04, 0.04)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if not argv:
        raise RuntimeError("Expected output directory after --")
    output_dir = Path(argv[0]).resolve()
    frames = [int(value) for value in argv[1:]] if len(argv) > 1 else [1, 6, 15, 31, 37, 48, 54, 70, 78, 91]
    output_dir.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    display_meshes = [
        obj
        for obj in scene.objects
        if obj.type == "MESH" and obj.name.startswith(DISPLAY_PREFIX) and not obj.hide_render
    ]
    if not display_meshes:
        raise RuntimeError("No visible Butterfly Master display meshes were found")
    if scene.camera is None:
        ensure_preview_camera(scene, display_meshes, frames)

    aspect = (scene.render.resolution_y * scene.render.pixel_aspect_y) / max(
        1.0,
        scene.render.resolution_x * scene.render.pixel_aspect_x,
    )
    scene.render.resolution_x = 720
    scene.render.resolution_y = max(1, round(720 * aspect))
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    for frame in frames:
        scene.frame_set(frame)
        scene.render.filepath = str(output_dir / f"wing_preview_{frame:03d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"MYBUTTERFLY_WING_RENDER={frame}:{scene.render.filepath}")


if __name__ == "__main__":
    main()
