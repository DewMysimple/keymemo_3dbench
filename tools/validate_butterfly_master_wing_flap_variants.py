import hashlib
import json
from pathlib import Path

import bpy

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from workbench_paths import REPORTS_ROOT, WORKBENCH_ROOT, model_root, model_scenes
from butterfly_frame_attachment import CLEAN_WING_FOLD_RANGES, DISPLAY_ROOT_NAME, validate_attachment

PROJECT_ROOT = WORKBENCH_ROOT
ASSET_ROOT = model_root("Butterfly")
BLENDER_ROOT = model_scenes("Butterfly")
MASTER_PATH = BLENDER_ROOT / "master" / "Butterfly_Master.blend"
SOURCE_DIR = BLENDER_ROOT / "follow_path"
OUTPUT_DIR = BLENDER_ROOT / "wing_flap_only"
BUILD_REPORT_PATH = REPORTS_ROOT / "butterfly-master-wing-flap-variants.json"
REPORT_PATH = REPORTS_ROOT / "butterfly-master-wing-flap-validation.json"
FRAME_GLB_PATH = model_root("SpecimenFrame") / "source" / "specimen-frame.glb"

SOURCE_NAMES = (
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend",
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend",
)
OUTPUT_NAMES = (
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1_WING_FLAP_ONLY.blend",
    "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2_WING_FLAP_ONLY.blend",
)


def ensure(condition, message):
    if not condition:
        raise RuntimeError(message)


def relative(path):
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def action_fcurves(action):
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                curves.extend(channelbag.fcurves)
    return curves


def wing_role(name):
    lowered = name.lower()
    if "left" in lowered:
        return "left"
    if "right" in lowered:
        return "right"
    return None


def object_transform_signature(obj):
    return {
        "matrix_world": [
            round(value, 8)
            for row in obj.matrix_world
            for value in row
        ],
        "location": [round(value, 8) for value in obj.location],
        "rotation_euler": [round(value, 8) for value in obj.rotation_euler],
        "scale": [round(value, 8) for value in obj.scale],
        "parent": obj.parent.name if obj.parent else None,
        "action": obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None,
    }


def max_signature_difference(first, second):
    return max(
        abs(left - right)
        for key in ("matrix_world", "location", "rotation_euler", "scale")
        for left, right in zip(first[key], second[key])
    )


def max_local_signature_difference(first, second):
    return max(
        abs(left - right)
        for key in ("location", "rotation_euler", "scale")
        for left, right in zip(first[key], second[key])
    )


def scene_snapshot(scene, frames, name_filter):
    objects = sorted(
        [obj for obj in scene.objects if name_filter(obj)],
        key=lambda obj: obj.name,
    )
    snapshot = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        snapshot[frame] = {
            obj.name: object_transform_signature(obj)
            for obj in objects
        }
    return snapshot


def action_map(path):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    actions = {}
    for action in bpy.data.actions:
        role = wing_role(action.name)
        if role is not None:
            ensure(role not in actions, f"{path.name} 存在重复的 {role} 翅膀 Action")
            actions[role] = action
    ensure(set(actions) == {"left", "right"}, f"{path.name} 缺少左右翅膀 Action")
    return actions


def action_signature(action):
    curves = {}
    for curve in action_fcurves(action):
        key = f"{curve.data_path}[{curve.array_index}]"
        curves[key] = {
            "frames": [round(keyframe.co.x, 8) for keyframe in curve.keyframe_points],
            "values": [round(keyframe.co.y, 8) for keyframe in curve.keyframe_points],
            "handle_left": [[round(value, 8) for value in keyframe.handle_left] for keyframe in curve.keyframe_points],
            "handle_right": [[round(value, 8) for value in keyframe.handle_right] for keyframe in curve.keyframe_points],
            "interpolation": [keyframe.interpolation for keyframe in curve.keyframe_points],
            "easing": [keyframe.easing for keyframe in curve.keyframe_points],
            "handle_left_type": [keyframe.handle_left_type for keyframe in curve.keyframe_points],
            "handle_right_type": [keyframe.handle_right_type for keyframe in curve.keyframe_points],
        }
    return {
        "name": action.name,
        "frame_range": [round(value, 8) for value in action.frame_range],
        "curves": curves,
    }


def capture_source_action_signatures(source_paths):
    result = {}
    for path in source_paths:
        actions = action_map(path)
        result[path.name] = {
            role: action_signature(action)
            for role, action in actions.items()
        }
    return result


def compare_retargeted_action(source_signature, output_wing, master_frame_one):
    output_action = output_wing.animation_data.action
    source_curves = source_signature["curves"]
    output_curves = {
        (curve.data_path, curve.array_index): curve
        for curve in action_fcurves(output_action)
    }
    ensure(set(output_curves) == {("rotation_euler", 2)}, f"输出 Action 应仅保留 Z 轴铰链曲线: {output_action.name}")
    source_curve = source_curves["rotation_euler[2]"]
    output_curve = output_curves[("rotation_euler", 2)]
    ensure(len(source_curve["frames"]) == len(output_curve.keyframe_points), f"输出 Z 曲线关键帧数量与源 Action 不一致: {output_action.name}")
    source_base = source_curve["values"][source_curve["frames"].index(1.0)]
    scale = float(output_wing["frame_attachment_retarget_scale"])
    offset = float(output_wing["frame_attachment_retarget_offset"])
    for index, (source_frame, source_value, output_key) in enumerate(zip(source_curve["frames"], source_curve["values"], output_curve.keyframe_points)):
        ensure(abs(source_frame - output_key.co.x) <= 0.000001, f"输出 Z 曲线帧号与源 Action 不一致: {output_action.name}")
        ensure(
            abs(source_curve["handle_left"][index][0] - output_key.handle_left.x) <= 0.00001
            and abs(source_curve["handle_right"][index][0] - output_key.handle_right.x) <= 0.00001,
            f"输出 Z 曲线手柄时间被改变: {output_action.name}",
        )
        ensure(
            source_curve["interpolation"][index] == output_key.interpolation
            and source_curve["easing"][index] == output_key.easing
            and source_curve["handle_left_type"][index] == output_key.handle_left_type
            and source_curve["handle_right_type"][index] == output_key.handle_right_type,
            f"输出 Z 曲线缓动或手柄类型被改变: {output_action.name}",
        )
        expected = (master_frame_one["rotation_euler"][2] + source_value - source_base) * scale + offset
        ensure(abs(expected - output_key.co.y) <= 0.00001, f"输出 Z 曲线未按无交叉折叠区间重定向: {output_action.name}")
        for source_handle, output_handle in (
            (source_curve["handle_left"][index], output_key.handle_left),
            (source_curve["handle_right"][index], output_key.handle_right),
        ):
            expected_handle_y = (master_frame_one["rotation_euler"][2] + source_handle[1] - source_base) * scale + offset
            ensure(abs(expected_handle_y - output_handle.y) <= 0.00001, f"输出 Z 曲线手柄未按无交叉折叠区间重定向: {output_action.name}")


def find_display_wings(scene):
    wings = {
        role: obj
        for obj in scene.objects
        if obj.name.startswith("展示_")
        and obj.type == "MESH"
        for role in [wing_role(obj.name)]
        if role is not None
    }
    ensure(set(wings) == {"left", "right"}, f"展示层左右翅膀不完整: {list(wings)}")
    return wings


def validate_one(path, source_path, master_default_frame, master_artist_snapshot, master_source_snapshot, master_frames, source_action_signatures, expected_build):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    artist = bpy.data.scenes.get("ARTIST_EDIT")
    source_scene = bpy.data.scenes.get("SOURCE_REFERENCE")
    ensure(artist is not None and source_scene is not None, f"输出场景入口缺失: {path.name}")
    ensure(bpy.context.window.scene == artist, f"输出默认场景不是 ARTIST_EDIT: {path.name}")
    ensure(artist.frame_current == master_default_frame, f"Master 默认帧未保留: {path.name}")
    ensure(artist.frame_start == master_frames[0] and artist.frame_end == master_frames[-1], f"Master 帧范围未保留: {path.name}")

    output_artist = scene_snapshot(artist, master_frames, lambda obj: obj.name.startswith("展示_") or obj.name.startswith("DISPLAY_"))
    output_source = scene_snapshot(source_scene, master_frames, lambda obj: obj.name.startswith("源_"))
    ensure(set(output_source[master_frames[0]]) == set(master_source_snapshot[master_frames[0]]), f"Master 源对象集合被改变: {path.name}")

    output_wings = find_display_wings(artist)
    wing_names = {obj.name for obj in output_wings.values()}
    display_root = artist.objects.get(DISPLAY_ROOT_NAME)
    ensure(display_root is not None, f"缺少展示根: {path.name}")
    display_mesh_names = {obj.name for obj in artist.objects if obj.type == "MESH" and obj.name.startswith("展示_")}
    ensure(len(display_mesh_names) == 3 and display_mesh_names.issubset(master_artist_snapshot[master_frames[0]]), f"Master 三个展示网格名称被改变: {path.name}")
    ensure({obj.name for obj in artist.objects if obj.parent == display_root} == display_mesh_names, f"展示根未直接绑定身体与双翼: {path.name}")
    for role, output_wing in output_wings.items():
        name = output_wing.name
        master_frame_one = master_artist_snapshot[master_frames[0]][name]
        source_range = output_wing.get("frame_attachment_retarget_source_range")
        target_range = output_wing.get("frame_attachment_retarget_target_range")
        scale = output_wing.get("frame_attachment_retarget_scale")
        offset = output_wing.get("frame_attachment_retarget_offset")
        ensure(source_range is not None and target_range is not None and scale is not None and offset is not None, f"翅膀缺少面板安全区间重定向记录: {path.name}, {name}")
        ensure(max(abs(float(left) - right) for left, right in zip(target_range, CLEAN_WING_FOLD_RANGES[role])) <= 0.0001, f"翅膀目标安全区间错误: {path.name}, {name}")
        ensure(output_wing.parent == display_root, f"翅膀未直接绑定展示根: {path.name}, {name}")
        ensure(output_wing.animation_data and output_wing.animation_data.action, f"输出翅膀缺少 Action: {path.name}, {name}")
        ensure(output_wing.animation_data.action.name.startswith("MASTER_WING_FLAP_ONLY_"), f"输出翅膀未使用 Master 替换 Action: {path.name}, {name}")
        ensure(output_wing.animation_data.action.get("animation_source_file") == relative(source_path), f"输出 Action 来源不匹配: {path.name}, {name}")
        ensure(output_wing.animation_data.action.get("animation_source_role") == role, f"输出 Action 翅膀方向不匹配: {path.name}, {name}")

    display_animated = [
        obj
        for obj in artist.objects
        if obj.name.startswith("展示_") and obj.animation_data and obj.animation_data.action
    ]
    ensure(len(display_animated) == 2 and all(obj.name in wing_names for obj in display_animated), f"展示层存在非翅膀动画: {path.name}")

    source_snapshot_match = True
    for frame in master_frames:
        for name, master_signature in master_source_snapshot[frame].items():
            ensure(
                max_signature_difference(master_signature, output_source[frame][name]) <= 0.000001,
                f"SOURCE_REFERENCE 被改变: {path.name}, {name}, frame {frame}",
            )
            ensure(master_signature["action"] == output_source[frame][name]["action"], f"SOURCE_REFERENCE Action 被改变: {path.name}, {name}")

    for role, source_signature in source_action_signatures.items():
        wing_name = output_wings[role].name
        compare_retargeted_action(
            source_signature,
            output_wings[role],
            master_artist_snapshot[master_frames[0]][wing_name],
        )

    artist.frame_set(1)
    bpy.context.view_layer.update()
    frame_one = {
        role: tuple(round(value, 8) for value in obj.rotation_euler)
        for role, obj in output_wings.items()
    }
    artist.frame_set(min(artist.frame_end, 45))
    bpy.context.view_layer.update()
    frame_45 = {
        role: tuple(round(value, 8) for value in obj.rotation_euler)
        for role, obj in output_wings.items()
    }
    ensure(frame_one != frame_45, f"翅膀扇动没有发生: {path.name}")

    attachment = validate_attachment(artist, source_scene)

    expected_output = expected_build["output"]
    ensure(expected_output == relative(path), f"构建报告与输出文件不匹配: {path.name}")
    return {
        "file": relative(path),
        "source": relative(source_path),
        "default_scene": artist.name,
        "default_frame": artist.frame_current,
        "display_wings": {role: obj.name for role, obj in output_wings.items()},
        "display_animated_objects": [obj.name for obj in display_animated],
        "master_display_meshes_preserved_and_reoriented": True,
        "clean_direct_display_hierarchy": True,
        "wing_animation_outward_fold_retargeted": True,
        "source_reference_unchanged": source_snapshot_match,
        "source_wing_z_keyframe_timing_and_easing_preserved": True,
        "source_wing_z_curve_affinely_retargeted": True,
        "wing_animation_changed": True,
        "frame_attachment": attachment,
    }


def main():
    ensure(BUILD_REPORT_PATH.is_file(), f"缺少构建报告: {BUILD_REPORT_PATH}")
    build_payload = json.loads(BUILD_REPORT_PATH.read_text(encoding="utf-8"))
    ensure(build_payload.get("frame_source") == relative(FRAME_GLB_PATH), "构建报告中的标本框来源路径错误")
    ensure(build_payload.get("frame_source_sha256") == sha256_file(FRAME_GLB_PATH), "标本框 GLB 与构建报告哈希不一致")
    build_by_output = {item["output"]: item for item in build_payload["outputs"]}
    ensure(len(build_by_output) == 2, "构建报告输出数量不是 2")

    master_hash = sha256_file(MASTER_PATH)
    ensure(master_hash == build_payload["outputs"][0]["master_sha256_before"], "Butterfly_Master.blend 在构建后发生变化")
    source_paths = [SOURCE_DIR / name for name in SOURCE_NAMES]
    source_hashes = {relative(path): sha256_file(path) for path in source_paths}
    for item in build_payload["outputs"]:
        ensure(source_hashes[item["source"]] == item["source_sha256_before"], f"Follow Path 源文件在构建后发生变化: {item['source']}")

    bpy.ops.wm.open_mainfile(filepath=str(MASTER_PATH), load_ui=False)
    master_artist = bpy.data.scenes.get("ARTIST_EDIT")
    master_source = bpy.data.scenes.get("SOURCE_REFERENCE")
    ensure(master_artist is not None and master_source is not None, "Master 缺少验证所需场景")
    if bpy.context.window:
        bpy.context.window.scene = master_artist
    master_frames = (master_artist.frame_start, min(master_artist.frame_end, 45), master_artist.frame_end)
    master_default_frame = master_artist.frame_current
    master_artist_snapshot = scene_snapshot(master_artist, master_frames, lambda obj: obj.name.startswith("展示_") or obj.name.startswith("DISPLAY_"))
    master_source_snapshot = scene_snapshot(master_source, master_frames, lambda obj: obj.name.startswith("源_"))
    master_wings = find_display_wings(master_artist)
    source_action_signatures = capture_source_action_signatures(source_paths)

    reports = []
    for source_path, output_name in zip(source_paths, OUTPUT_NAMES):
        output_path = OUTPUT_DIR / output_name
        ensure(output_path.is_file(), f"输出文件不存在: {output_path}")
        reports.append(
            validate_one(
                output_path,
                source_path,
                master_default_frame,
                master_artist_snapshot,
                master_source_snapshot,
                master_frames,
                source_action_signatures[source_path.name],
                build_by_output[relative(output_path)],
            )
        )

    payload = {
        "asset": "Butterfly",
        "variant": "master_wing_flap_vertical_specimen_frame_attachment",
        "validated_count": len(reports),
        "master_sha256_after": sha256_file(MASTER_PATH),
        "source_sha256_after": source_hashes,
        "master_default_frame": master_default_frame,
        "frame_source": relative(FRAME_GLB_PATH),
        "frame_source_sha256": sha256_file(FRAME_GLB_PATH),
        "validated": reports,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_MASTER_WING_FLAP_VALIDATION=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
