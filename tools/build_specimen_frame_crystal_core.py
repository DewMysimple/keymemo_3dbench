"""Stage/validate an Eevee crystal core; publish only with explicit --create.

No arguments: back up the target, build a candidate and render multi-view QA.
--create --candidate <run-directory>: publish the inspected, unchanged candidate.
--validate-only: inspect the delivered asset without rewriting it.

The eight three-face edges are intentional interfaces, NOT printable topology.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workbench_paths import GENERATED_ROOT, REPORTS_ROOT, WORKBENCH_ROOT, model_scenes
from build_specimen_frame_scene import make_hdri_world

TARGET = model_scenes("SpecimenFrame") / "Specimen_Frame_Transparent_Default_Material.blend"
RUN_ROOT = GENERATED_ROOT / "SpecimenFrame" / "crystal_core"
REPORT = REPORTS_ROOT / "specimen-frame-default-material-validation.json"
OUTER = "SPECIMEN_OUTER_FRAME"
PANEL = "SPECIMEN_INNER_PANEL"
MATERIALS = ("MAT_OuterFrame_TranslucentWhite", "MAT_InnerPanel_TransparentLavender")
COLORS = ((0.90, 0.96, 1.0, 1.0), (0.64, 0.40, 1.0, 1.0))
CENTER = Vector((0, 0, 4.55))


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(path):
    return Path(path).resolve().relative_to(WORKBENCH_ROOT).as_posix()


def write_report(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def camera_signature(camera):
    return {"name": camera.name, "matrix": [list(row) for row in camera.matrix_world],
            "type": camera.data.type, "lens": camera.data.lens,
            "sensor_width": camera.data.sensor_width}


def build_geometry():
    obj = bpy.data.objects[OUTER]
    ensure(not obj.modifiers, "Unexpected source modifiers; do not discard them.")
    mesh_name = obj.data.name
    loops = [(-4.55, -4.55), (4.55, -4.55), (4.55, 4.55), (-4.55, 4.55),
             (-3.55, -3.55), (3.55, -3.55), (3.55, 3.55), (-3.55, 3.55)]
    verts = [(x, y, z) for x in (-0.21, 0.21) for y, z in loops]
    faces, slots = [], []
    for i in range(4):
        j = (i + 1) % 4
        faces.extend([(8+i, 8+j, 12+j, 12+i), (i, 4+i, 4+j, j), (i, j, 8+j, 8+i)])
        slots.extend([0, 0, 0])
    faces.extend([(12, 13, 14, 15), (7, 6, 5, 4)])
    slots.extend([1, 1])
    for i in range(4):
        j = (i + 1) % 4
        # Unique interface, pointing OUT of the purple cell. Do not add an
        # opposite frame wall or globally recalculate this nonmanifold mesh.
        faces.append((4+i, 4+j, 12+j, 12+i))
        slots.append(1)
    mesh = bpy.data.meshes.new(mesh_name + "_candidate")
    mesh.from_pydata(verts, [], faces)
    for face, slot in zip(mesh.polygons, slots):
        face.material_index = slot
        face.use_smooth = False
    old_mesh = obj.data
    obj.data = mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    mesh.name = mesh_name
    panel = bpy.data.objects.get(PANEL)
    if panel:
        old_mesh = panel.data
        bpy.data.objects.remove(panel, do_unlink=True)
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
    obj.parent = None
    obj.matrix_world = Matrix.Translation(CENTER)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj["origin_role"] = "geometric center"
    obj["asset_role"] = "white frame and closed six-face purple crystal core"
    obj["topology_note"] = "single internal interfaces; eight intentional three-face junction edges"
    obj["render_only_interface"] = True
    mesh.update()
    return obj


def configure_materials(obj):
    obj.data.materials.clear()
    for index, name in enumerate(MATERIALS):
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        shader = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        output.location = (340, 0)
        alpha, rough = ((0.20, 0.12), (0.55, 0.10))[index]
        for key, value in {"Base Color": COLORS[index], "Alpha": alpha, "Roughness": rough,
                           "IOR": 1.45, "Transmission Weight": 0.0, "Coat Weight": 0.35}.items():
            shader.inputs[key].default_value = value
        mat.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
        mat.diffuse_color = (*COLORS[index][:3], alpha)
        mat.surface_render_method = "DITHERED"
        mat.use_backface_culling = False
        if hasattr(mat, "use_raytrace_refraction"):
            mat.use_raytrace_refraction = False
        mat["role"] = "outer frame" if index == 0 else "six-face crystal core"
        mat["eevee_note"] = "alpha and coat highlights; no multilayer refraction"
        obj.data.materials.append(mat)
    # Edit-mode UV generation and clearing slots can clamp unassigned indices.
    # Restore role indices after both materials exist in this deterministic mesh.
    for face in obj.data.polygons:
        face.material_index = 0 if face.index < 12 else 1
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def configure_scene(run):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 512
    scene.eevee.taa_samples = 64
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x = scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.filepath = "//" + os.path.relpath(run / "oblique.png", TARGET.parent).replace("\\", "/")
    # Rebuilds reuse the packed Studio world instead of accumulating .001 images.
    world = scene.world
    environment_images = [n.image for n in world.node_tree.nodes if n.type == "TEX_ENVIRONMENT"] if world and world.use_nodes else []
    if not (len(environment_images) == 1 and environment_images[0].packed_file):
        scene.world = None
        for world in list(bpy.data.worlds):
            if world.users == 0:
                bpy.data.worlds.remove(world)
        scene.world = make_hdri_world()
    for key in list(scene.keys()):
        if any(word in key for word in ("parent", "default_material", "no_material", "removed", "origin", "world_environment")):
            del scene[key]
    scene["asset_name_zh"] = "透明外框与实体紫晶内芯｜单对象双材质槽"
    scene["asset_name_en"] = "Specimen Frame | Eevee Crystal Core"
    scene["modeling_notes"] = "six-face purple core; unique internal interfaces; eight intentional non-manifold junctions"
    scene["output_file"] = relative(TARGET)
    scene["material_roles"] = "white frame 12 faces; purple core 6 faces"
    scene["description_zh"] = "单对象内保留完整紫晶六面，透过半透明白色外框可见内芯侧面。"
    scene["panel_opening_fit"] = "purple material region fills the opening; four unique internal contact faces"
    scene["panel_x_alignment"] = "frame and crystal front/back at X=-0.21 and X=+0.21"
    scene["object_origin_note"] = "SPECIMEN_OUTER_FRAME combined geometric center at (0,0,4.55)"
    scene["frame_overall_size"] = 9.1
    scene["frame_opening_size"] = 7.1
    scene["frame_depth"] = scene["panel_depth"] = 0.42
    scene["panel_recess"] = 0.0
    for area in (a for screen in bpy.data.screens for a in screen.areas if a.type == "VIEW_3D"):
        area.spaces.active.shading.type = "MATERIAL"
        area.spaces.active.shading.use_scene_world = True
        area.spaces.active.shading.use_scene_lights = True
    readme = bpy.data.texts.get("SPECIMEN_FRAME_README") or bpy.data.texts.new("SPECIMEN_FRAME_README")
    readme.clear()
    readme.write("透明外框＋紫晶内芯（Eevee 渲染展示版）\n"
                 "文件名 Default_Material 因路径契约保留；本文件现在已配置晶体材质。\n"
                 "SPECIMEN_OUTER_FRAME 单对象；材质槽1白框12面，槽2紫晶六个完整表面。\n"
                 "16点/32边/18面；8条三面交汇边为有意保留的内部界面，不用于3D打印。\n"
                 "内芯0.42×7.1×7.1，外形0.42×9.1×9.1，前后齐平。\n"
                 "透明和清漆高光用于实时表现，不模拟多层物理折射。\n")


def validate(expected_camera=None):
    scene = bpy.context.scene
    obj = bpy.data.objects[OUTER]
    bpy.context.view_layer.update()
    mesh = obj.data
    points = [obj.matrix_world @ v.co for v in mesh.vertices]
    bbox = [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    degrees = Counter(len(e.link_faces) for e in bm.edges)
    core_faces = [p for p in mesh.polygons if p.material_index == 1]
    core_edges = Counter(tuple(sorted(edge)) for p in core_faces for edge in p.edge_keys)
    core_points = [obj.matrix_world @ mesh.vertices[i].co for p in core_faces for i in p.vertices]
    core_bbox = [min(p[i] for p in core_points) for i in range(3)] + [max(p[i] for p in core_points) for i in range(3)]
    keys = [tuple(sorted(tuple(round(c, 6) for c in mesh.vertices[i].co) for i in p.vertices)) for p in mesh.polygons]
    interface = [p for p in core_faces if abs(p.normal.x) < 0.5]
    exterior = [p for p in mesh.polygons if abs(p.normal.x) < 0.5 and p.material_index == 0]
    uv_areas = []
    if mesh.uv_layers.active:
        for p in mesh.polygons:
            uvs = [mesh.uv_layers.active.data[i].uv for i in p.loop_indices]
            uv_areas.append(abs(sum(a.x*b.y-b.x*a.y for a,b in zip(uvs,uvs[1:]+uvs[:1]))) / 2)
    mats = []
    for m in mesh.materials:
        nodes = m.node_tree.nodes
        shader = nodes.get("Principled BSDF")
        output = nodes.get("Material Output")
        mats.append({"name": m.name, "method": m.surface_render_method,
                     "alpha": shader.inputs["Alpha"].default_value,
                     "roughness": shader.inputs["Roughness"].default_value,
                     "transmission": shader.inputs["Transmission Weight"].default_value,
                     "direct_principled": len(nodes) == 2 and output.inputs["Surface"].is_linked
                     and output.inputs["Surface"].links[0].from_node == shader})
    world = scene.world
    hdri = [n.image for n in world.node_tree.nodes if n.type == "TEX_ENVIRONMENT"] if world and world.use_nodes else []
    close = lambda a,b: len(a) == len(b) and all(abs(x-y) < 1e-5 for x,y in zip(a,b))
    checks = {
        "one_model_object": [o.name for o in scene.objects if o.type == "MESH"] == [OUTER],
        "no_independent_panel": PANEL not in bpy.data.objects,
        "topology_16_32_18": (len(mesh.vertices), len(mesh.edges), len(mesh.polygons)) == (16,32,18),
        "intentional_junctions_only": degrees == {2:24, 3:8},
        "no_open_or_loose_edges": all(len(e.link_faces) >= 2 for e in bm.edges),
        "no_duplicate_faces": len(set(keys)) == len(keys),
        "two_material_slots": [m.name for m in mesh.materials] == list(MATERIALS),
        "face_assignments": Counter(p.material_index for p in mesh.polygons) == {0:12, 1:6},
        "core_closed_six_faces": len(core_faces) == 6 and len(core_edges) == 12 and set(core_edges.values()) == {2},
        "core_normals_outward": all(p.normal.dot(p.center) > 0 for p in core_faces),
        "outer_normals_outward": all(p.normal.dot(p.center) > 0 for p in mesh.polygons if p.material_index == 0),
        "unique_four_core_interface_faces": len(interface) == 4,
        "exterior_walls_remain_white": len(exterior) == 4 and all(abs(max(abs(p.center.y),abs(p.center.z))-4.55)<1e-5 for p in exterior),
        "bounds_preserved": close(bbox, [-0.21,-4.55,0,0.21,4.55,9.1]),
        "core_bounds_flush": close(core_bbox, [-0.21,-3.55,1,0.21,3.55,8.1]),
        "origin_at_geometric_center": close(list(obj.matrix_world.translation), [0,0,4.55]),
        "no_modifiers_or_parent": not obj.modifiers and obj.parent is None,
        "uvs_nonzero_on_all_faces": len(uv_areas) == 18 and min(uv_areas) > 1e-8,
        "eevee_and_samples": scene.render.engine == "BLENDER_EEVEE" and scene.eevee.taa_render_samples == 512 and scene.eevee.taa_samples == 64,
        "material_settings": len(mats) == 2 and all(m["method"] == "DITHERED" and m["direct_principled"] and m["transmission"] == 0 for m in mats)
        and close([m["alpha"] for m in mats], [0.20,0.55]) and close([m["roughness"] for m in mats], [0.12,0.10]),
        "packed_hdri": len(hdri) == 1 and bool(hdri[0].packed_file),
        "no_external_images": all(image.packed_file or not image.filepath for image in bpy.data.images if image.type != "RENDER_RESULT"),
        "transparent_background": scene.render.film_transparent,
        "camera_preserved": scene.camera is not None and (expected_camera is None or camera_signature(scene.camera) == expected_camera),
    }
    bm.free()
    checks["all_passed"] = all(checks.values())
    return {"checks": checks, "bounds": bbox, "core_bounds": core_bbox,
            "topology": {"vertices": len(mesh.vertices), "edges": len(mesh.edges), "faces": len(mesh.polygons),
                         "outer_faces": 12, "core_faces": len(core_faces), "internal_interfaces": len(interface),
                         "note": "eight intentional three-face junction edges; render-only partition mesh"},
            "edge_face_incidence": dict(degrees), "materials": mats, "camera": camera_signature(scene.camera)}


def load_pixels(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    w,h = image.size
    pixels = np.array(image.pixels[:], dtype=np.float32).reshape(h,w,4)
    bpy.data.images.remove(image)
    return pixels


def render_qa(run):
    scene = bpy.context.scene
    camera = scene.camera
    scene.render.filepath = str(run / "oblique.png")
    bpy.ops.render.render(write_still=True)
    views = {"front": (18,0,4.55), "back": (-18,0,4.55), "left": (0,-18,4.55),
             "right": (0,18,4.55), "top": (0,0,22.55), "bottom": (0,0,-13.45),
             "grazing_front_left": (1.57,-17.93,4.55), "grazing_back_left": (-1.57,-17.93,4.55),
             "grazing_front_right": (1.57,17.93,4.55), "grazing_back_right": (-1.57,17.93,4.55)}
    paths, metrics = {"oblique": relative(run / "oblique.png")}, {}
    shader = bpy.data.materials[MATERIALS[1]].node_tree.nodes.get("Principled BSDF")
    for name, location in views.items():
        side = name in {"left", "right", "top", "bottom"}
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = 10.2
        camera.location = location
        camera.rotation_euler = (CENTER-camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.resolution_x, scene.render.resolution_y = (320, 1000) if side else (900,900)
        path = run / (name + ".png")
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        paths[name] = relative(path)
        if side:
            reference = load_pixels(path)
            shader.inputs["Alpha"].default_value = 0
            control = run / (name + "_core_hidden.png")
            scene.render.filepath = str(control)
            bpy.ops.render.render(write_still=True)
            shader.inputs["Alpha"].default_value = 0.55
            hidden = load_pixels(control)
            paths[name + "_core_hidden"] = relative(control)
            h,w,_ = reference.shape
            center = (slice(int(.3*h),int(.7*h)), slice(int(.49*w),int(.51*w)))
            end = (slice(int(.075*h),int(.12*h)), slice(int(.49*w),int(.51*w)))
            delta = np.abs(reference-hidden)
            metrics[name] = {"core_rgba_delta": float(delta[center].mean()),
                             "frame_only_rgba_delta": float(delta[end].mean())}
    passed = all(m["core_rgba_delta"] > .025 and m["frame_only_rgba_delta"] < .015 for m in metrics.values())
    return {"images": paths, "side_controls": metrics, "all_passed": passed}


def stage():
    ensure(TARGET.is_file(), f"Target does not exist: {TARGET}")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_"), dir=RUN_ROOT))
    protected = {relative(p): digest(p) for p in TARGET.parent.glob("*.blend") if p != TARGET}
    before_hash = digest(TARGET)
    backup = run / "before.blend"
    shutil.copy2(TARGET, backup)
    ensure(digest(backup) == before_hash, "Backup checksum mismatch.")
    bpy.ops.wm.open_mainfile(filepath=str(TARGET))
    ensure(bpy.context.scene.camera is not None, "Target has no camera to preserve.")
    expected_camera = camera_signature(bpy.context.scene.camera)
    configure_materials(build_geometry())
    configure_scene(run)
    report = validate(expected_camera)
    ensure(report["checks"]["all_passed"], str(report["checks"]))
    candidate = run / TARGET.name
    bpy.ops.wm.save_as_mainfile(filepath=str(candidate), relative_remap=False)
    qa = render_qa(run)
    ensure(qa["all_passed"], f"Side control tests failed: {qa['side_controls']}")
    bpy.ops.wm.open_mainfile(filepath=str(candidate))
    reopened = validate(expected_camera)
    ensure(reopened["checks"]["all_passed"], str(reopened["checks"]))
    report.update({"asset": "SpecimenFrame Eevee crystal core", "blend": relative(TARGET),
                   "candidate": relative(candidate), "backup": relative(backup),
                   "target_before_sha256": before_hash, "candidate_sha256": digest(candidate),
                   "protected_blends": protected, "reopen_checks": reopened["checks"], "render_qa": qa,
                   "status": "staged_pending_visual_review"})
    write_report(run / "validation.json", report)
    ensure(digest(TARGET) == before_hash, "Target changed during staging.")
    print("STAGED_RUN=" + str(run))
    print(json.dumps(report["checks"]))
    print(json.dumps(qa["side_controls"]))


def publish(directory):
    run = Path(directory).resolve()
    ensure(run.is_relative_to(RUN_ROOT.resolve()), "Candidate must be inside the dedicated staging directory.")
    report = json.loads((run / "validation.json").read_text(encoding="utf-8"))
    report["original_backup"] = report["backup"]
    if REPORT.exists():
        previous = json.loads(REPORT.read_text(encoding="utf-8"))
        if previous.get("published_sha256") == report["target_before_sha256"]:
            report["original_backup"] = previous.get("original_backup", previous["backup"])
    candidate = run / TARGET.name
    ensure(report["checks"]["all_passed"] and report["render_qa"]["all_passed"], "Unvalidated candidate.")
    ensure(digest(candidate) == report["candidate_sha256"], "Candidate changed after QA.")
    ensure(digest(TARGET) == report["target_before_sha256"], "Target changed since staging; will not overwrite.")
    ensure(digest(run / "before.blend") == report["target_before_sha256"], "Original backup missing or invalid.")
    for path, checksum in report["protected_blends"].items():
        ensure(digest(WORKBENCH_ROOT / path) == checksum, f"Other model changed: {path}")
    bpy.ops.wm.open_mainfile(filepath=str(candidate))
    ensure(validate(report["camera"])["checks"]["all_passed"], "Candidate reopen check failed.")
    fd, temp_name = tempfile.mkstemp(prefix=".crystal-publish-", suffix=".tmp", dir=TARGET.parent)
    os.close(fd)
    shutil.copyfile(candidate, temp_name)
    ensure(digest(TARGET) == report["target_before_sha256"], "Target changed before replacement.")
    os.replace(temp_name, TARGET)
    bpy.ops.wm.open_mainfile(filepath=str(TARGET))
    final = validate(report["camera"])
    ensure(final["checks"]["all_passed"], "Published asset failed to reopen; original backup retained.")
    report.update({"status": "published", "published_sha256": digest(TARGET), "published_checks": final["checks"]})
    write_report(REPORT, report)
    write_report(run / "validation.json", report)
    print("PUBLISHED=" + str(TARGET))
    print("BACKUP=" + str(run / "before.blend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    ensure(not (args.validate_only and (args.create or args.candidate)), "Validation cannot be combined with publication flags.")
    if args.validate_only:
        bpy.ops.wm.open_mainfile(filepath=str(TARGET))
        result = validate()
        print(json.dumps(result, indent=2))
        ensure(result["checks"]["all_passed"], "Validation failed.")
    elif args.create:
        ensure(args.candidate is not None, "--create requires an inspected --candidate run-directory.")
        publish(args.candidate)
    else:
        ensure(args.candidate is None, "--candidate requires --create.")
        stage()


if __name__ == "__main__":
    main()
