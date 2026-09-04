from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector


DISPLAY_PREFIX = "展示_Butterfly_Master_源_FBX_01_"
AXIS_NAMES = ("x", "y", "z")


def world_bounds(
    scene: bpy.types.Scene,
    objects: list[bpy.types.Object],
    frames: list[int],
) -> tuple[Vector, Vector]:
    minimum = Vector((float("inf"),) * 3)
    maximum = Vector((float("-inf"),) * 3)
    for frame in frames:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in objects:
            evaluated = obj.evaluated_get(depsgraph)
            for corner in evaluated.bound_box:
                point = evaluated.matrix_world @ Vector(corner)
                for axis in range(3):
                    minimum[axis] = min(minimum[axis], point[axis])
                    maximum[axis] = max(maximum[axis], point[axis])
    return minimum, maximum


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if not argv:
        raise RuntimeError("Expected output directory after --")
    output_dir = Path(argv[0]).resolve()
    frames = [int(value) for value in argv[1:]] if len(argv) > 1 else [1, 2, 17, 32, 45, 55, 75, 91]
    output_dir.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    meshes = [
        obj
        for obj in scene.objects
        if obj.type == "MESH" and obj.name.startswith(DISPLAY_PREFIX) and not obj.hide_render
    ]
    if not meshes:
        raise RuntimeError("No visible MyButterfly display meshes found")
    minimum, maximum = world_bounds(scene, meshes, frames)
    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    extent = max(size)

    camera_data = bpy.data.cameras.new("MyButterfly_Multiview_Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = extent * 1.2
    camera = bpy.data.objects.new(camera_data.name, camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    key = bpy.data.lights.new("MyButterfly_Multiview_Key", "AREA")
    key.energy = 1400.0
    key.size = extent * 1.5
    key_obj = bpy.data.objects.new(key.name, key)
    scene.collection.objects.link(key_obj)

    if scene.world is None:
        scene.world = bpy.data.worlds.new("MyButterfly_Multiview_World")
    scene.world.color = (0.04, 0.04, 0.04)
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    for axis, axis_name in enumerate(AXIS_NAMES):
        direction = Vector((0.0, 0.0, 0.0))
        direction[axis] = 1.0
        camera.location = center + direction * extent * 2.0
        up_axis = "Y" if axis != 1 else "X"
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", up_axis).to_euler()
        key_obj.location = camera.location
        key_obj.rotation_euler = camera.rotation_euler
        for frame in frames:
            scene.frame_set(frame)
            scene.render.filepath = str(output_dir / f"{axis_name}_frame_{frame:03d}.png")
            bpy.ops.render.render(write_still=True)
            print(f"MYBUTTERFLY_MULTIVIEW={axis_name}:{frame}:{scene.render.filepath}")


if __name__ == "__main__":
    main()
