from __future__ import annotations

import json

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


BODY = "展示_Butterfly_Master_源_FBX_01_01_BASIC_BUTTERFLY_BODY_Travis_Davids_OBJ_1"
WINGS = {
    "left": "展示_Butterfly_Master_源_FBX_01_03_BUTTERFLY_IDLE_1_LEFT_WING_",
    "right": "展示_Butterfly_Master_源_FBX_01_04_BUTTERFLY_IDLE_1_RIGHT_WING_",
}


def world_vertices(obj: bpy.types.Object) -> list[Vector]:
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def centroid(points: list[Vector]) -> Vector:
    return sum(points, Vector()) / len(points)


scene = bpy.context.scene
body = scene.objects[BODY]
wings = {role: scene.objects[name] for role, name in WINGS.items()}

scene.frame_set(1)
bpy.context.view_layer.update()
body_center = centroid(world_vertices(body))
reference_directions = {
    role: (centroid(world_vertices(wing)) - body_center).normalized()
    for role, wing in wings.items()
}

samples = []
for frame in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    body_points = world_vertices(body)
    body_center = centroid(body_points)
    tree = KDTree(len(body_points))
    for index, point in enumerate(body_points):
        tree.insert(point, index)
    tree.balance()

    wing_payload = {}
    for role, wing in wings.items():
        points = world_vertices(wing)
        center = centroid(points)
        minimum = Vector((min(point[i] for point in points) for i in range(3)))
        maximum = Vector((max(point[i] for point in points) for i in range(3)))
        nearest = min(tree.find(point)[2] for point in points)
        direction = center - body_center
        wing_payload[role] = {
            "z_degrees": float(wing.rotation_euler.z * 180.0 / 3.141592653589793),
            "centroid": [float(value) for value in center],
            "centroid_distance": float(direction.length),
            "reference_direction_dot": float(direction.dot(reference_directions[role])),
            "nearest_body_vertex_distance": float(nearest),
            "bbox_size": [float(value) for value in maximum - minimum],
        }
    samples.append({"frame": frame, "wings": wing_payload})

summary = {}
for role in WINGS:
    role_samples = [(sample["frame"], sample["wings"][role]) for sample in samples]
    summary[role] = {
        "z_degrees_min": min((item[1]["z_degrees"], item[0]) for item in role_samples),
        "z_degrees_max": max((item[1]["z_degrees"], item[0]) for item in role_samples),
        "reference_direction_dot_min": min(
            (item[1]["reference_direction_dot"], item[0]) for item in role_samples
        ),
        "nearest_body_vertex_distance_max": max(
            (item[1]["nearest_body_vertex_distance"], item[0]) for item in role_samples
        ),
        "centroid_distance_range": [
            min(item[1]["centroid_distance"] for item in role_samples),
            max(item[1]["centroid_distance"] for item in role_samples),
        ],
    }

print(
    "MYBUTTERFLY_WING_GEOMETRY="
    + json.dumps(
        {
            "file": bpy.data.filepath,
            "frame_range": [scene.frame_start, scene.frame_end],
            "summary": summary,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
