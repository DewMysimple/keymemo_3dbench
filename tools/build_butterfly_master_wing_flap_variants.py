import hashlib
import json
from pathlib import Path

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = PROJECT_ROOT / "blender_scenebench" / "blender_modelbench" / "Butterfly"
BLENDER_ROOT = ASSET_ROOT / "blender"
MASTER_PATH = BLENDER_ROOT / "Butterfly_Master.blend"
SOURCE_DIR = BLENDER_ROOT / "follow_path"
OUTPUT_DIR = BLENDER_ROOT / "wing_flap_only"
REPORT_PATH = PROJECT_ROOT / "blender_scenebench" / "reports" / "butterfly-master-wing-flap-variants.json"

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


def wing_actions_in_current_file():
    actions = {}
    for action in bpy.data.actions:
        role = wing_role(action.name)
        if role is not None:
            actions[role] = action
    ensure(set(actions) == {"left", "right"}, "当前文件没有完整的左右翅膀 Action")
    return actions


def append_source_wing_actions(source_path):
    before = set(bpy.data.actions)
    with bpy.data.libraries.load(str(source_path), link=False) as (data_from, data_to):
        names = [name for name in data_from.actions if wing_role(name) is not None]
        ensure(len(names) == 2, f"源文件翅膀 Action 数量错误: {source_path.name}: {names}")
        data_to.actions = names

    loaded = [action for action in data_to.actions if action is not None]
    ensure(len(loaded) == 2, f"无法从源文件载入左右翅膀 Action: {source_path.name}")
    actions = {}
    for action in loaded:
        role = wing_role(action.name)
        ensure(role not in actions, f"源文件存在重复的 {role} 翅膀 Action: {source_path.name}")
        actions[role] = action
    ensure(set(actions) == {"left", "right"}, f"源文件左右翅膀 Action 不完整: {source_path.name}")
    ensure(all(action not in before for action in loaded), "源 Action 载入结果异常")
    return actions, loaded


def transform_signature(obj):
    return {
        "matrix_world": [
            round(value, 8)
            for row in obj.matrix_world
            for value in row
        ],
        "location": [round(value, 8) for value in obj.location],
        "rotation_euler": [round(value, 8) for value in obj.rotation_euler],
        "scale": [round(value, 8) for value in obj.scale],
    }


def transform_difference(first, second):
    return max(
        abs(left - right)
        for key in ("matrix_world", "location", "rotation_euler", "scale")
        for left, right in zip(first[key], second[key])
    )


def artist_transform_snapshot(scene, frames):
    objects = [
        obj
        for obj in scene.objects
        if obj.name.startswith("展示_") or obj.name.startswith("DISPLAY_")
    ]
    snapshot = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        snapshot[frame] = {
            obj.name: transform_signature(obj)
            for obj in objects
        }
    return snapshot


def display_wings(scene):
    wings = {
        role: obj
        for obj in scene.objects
        if obj.name.startswith("展示_")
        and obj.type == "MESH"
        for role in [wing_role(obj.name)]
        if role is not None
    }
    ensure(set(wings) == {"left", "right"}, f"Master 展示层左右翅膀缺失: {list(wings)}")
    return wings


def shift_curve(curve, offset):
    if abs(offset) < 1e-12:
        return
    for keyframe in curve.keyframe_points:
        keyframe.co.y += offset
        keyframe.handle_left.y += offset
        keyframe.handle_right.y += offset
    curve.update()


def make_master_pose_action(source_action, target_baseline, role, variant_index, source_path):
    action = source_action.copy()
    action.name = f"MASTER_WING_FLAP_ONLY_{variant_index:02d}_{role.upper()}"

    target_location = target_baseline["location"]
    target_rotation = target_baseline["rotation_euler"]
    target_scale = target_baseline["scale"]
    for curve in action_fcurves(action):
        if curve.data_path == "location":
            baseline = target_location[curve.array_index]
        elif curve.data_path == "rotation_euler":
            baseline = target_rotation[curve.array_index]
        elif curve.data_path == "scale":
            baseline = target_scale[curve.array_index]
        else:
            continue
        source_frame_one = curve.evaluate(1.0)
        shift_curve(curve, baseline - source_frame_one)

    action["animation_source_file"] = relative(source_path)
    action["animation_source_role"] = role
    action["master_pose_policy"] = "保持 Master 第 1 帧翅膀局部位置与初始旋转，仅替换扇翅变化"
    action["translation_policy"] = "沿用 Master 第 1 帧翅膀位置，不使用 Follow Path 位移"
    return action


def assign_action(target, action):
    target.animation_data_clear()
    target.animation_data_create()
    target.animation_data.action = action
    slots = list(action.slots)
    if slots:
        target.animation_data.action_slot = slots[0]


def write_variant_notes(source_path, output_path, action_names):
    text_name = "蝴蝶_Master_扇翅替换版本说明"
    old = bpy.data.texts.get(text_name)
    if old:
        bpy.data.texts.remove(old)
    text = bpy.data.texts.new(text_name)
    text.write(
        "Butterfly Master 扇翅替换版本\n\n"
        f"Master 基准：{MASTER_PATH.name}\n"
        f"扇翅来源：{source_path.name}\n"
        f"输出文件：{output_path.name}\n"
        "ARTIST_EDIT：保留 Master 的场景、展示根、身体和翅膀第 1 帧位置/旋转；仅替换左右翅膀的扇动变化。\n"
        "Follow Path 的路径控制器不会应用到 Master 展示层，因此不会带入沿路径位移或路径转向。\n"
        "SOURCE_REFERENCE：Master 原有源对象、源 Action 和全部素材保持原样。\n"
        f"新左翅 Action：{action_names['left']}\n"
        f"新右翅 Action：{action_names['right']}\n"
    )


def build_one(source_path, output_path, variant_index):
    ensure(MASTER_PATH.is_file(), f"Master 文件不存在: {MASTER_PATH}")
    ensure(source_path.is_file(), f"Follow Path 源文件不存在: {source_path}")

    master_hash = sha256_file(MASTER_PATH)
    source_hash = sha256_file(source_path)
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_PATH), load_ui=False)
    artist = bpy.data.scenes.get("ARTIST_EDIT")
    source_scene = bpy.data.scenes.get("SOURCE_REFERENCE")
    ensure(artist is not None and source_scene is not None, "Master 缺少 ARTIST_EDIT 或 SOURCE_REFERENCE")
    if bpy.context.window:
        bpy.context.window.scene = artist

    original_frame = artist.frame_current
    artist.frame_set(1)
    bpy.context.view_layer.update()
    wings = display_wings(artist)
    frames = (artist.frame_start, min(artist.frame_end, 45), artist.frame_end)
    before = artist_transform_snapshot(artist, frames)
    artist.frame_set(1)
    bpy.context.view_layer.update()
    wing_baselines = {
        role: {
            "location": tuple(obj.location),
            "rotation_euler": tuple(obj.rotation_euler),
            "scale": tuple(obj.scale),
        }
        for role, obj in wings.items()
    }
    display_names = sorted(before[frames[0]])
    source_actions, loaded_actions = append_source_wing_actions(source_path)

    new_actions = {}
    for role, target in wings.items():
        new_actions[role] = make_master_pose_action(
            source_actions[role],
            wing_baselines[role],
            role,
            variant_index,
            source_path,
        )
        assign_action(target, new_actions[role])

    for action in loaded_actions:
        if action.users == 0:
            bpy.data.actions.remove(action)

    after = artist_transform_snapshot(artist, frames)
    wing_names = {obj.name for obj in wings.values()}
    for frame in frames:
        for name in display_names:
            if name in wing_names:
                continue
            ensure(
                transform_difference(before[frame][name], after[frame][name]) <= 0.000001,
                f"Master 非翅膀变换被修改: {name}, frame {frame}",
            )
    for name in wing_names:
        wing_diff = transform_difference(before[frames[0]][name], after[frames[0]][name])
        ensure(
            wing_diff <= 0.000001,
            f"Master 翅膀第 1 帧位置/旋转被修改: {name}; diff={wing_diff}; before={before[frames[0]][name]}; after={after[frames[0]][name]}",
        )

    artist["document_type"] = "Butterfly Master 扇翅替换版本"
    artist["master_base_file"] = relative(MASTER_PATH)
    artist["wing_flap_source_file"] = relative(source_path)
    artist["wing_flap_only"] = True
    artist["master_transform_policy"] = "Master 场景、展示根、身体以及翅膀第 1 帧位置/旋转保持不变"
    artist["animation_policy"] = "仅替换 ARTIST_EDIT 左右翅膀扇动；不应用 Follow Path 路径控制器"
    artist["source_reference_policy"] = "SOURCE_REFERENCE 保持 Master 原始数据"
    artist["default_showcase_frame"] = original_frame
    write_variant_notes(source_path, output_path, {role: action.name for role, action in new_actions.items()})

    artist.frame_set(original_frame)
    bpy.context.window.scene = artist
    bpy.context.view_layer.update()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path), check_existing=False)
    ensure(output_path.is_file(), f"输出文件未生成: {output_path}")

    return {
        "master_base": relative(MASTER_PATH),
        "master_sha256_before": master_hash,
        "source": relative(source_path),
        "source_sha256_before": source_hash,
        "output": relative(output_path),
        "output_sha256": sha256_file(output_path),
        "display_wings": {role: obj.name for role, obj in wings.items()},
        "new_actions": {role: action.name for role, action in new_actions.items()},
        "frames_checked": list(frames),
        "master_non_wing_transforms_preserved": True,
        "master_wing_frame_one_transforms_preserved": True,
        "follow_path_controller_applied": False,
        "source_reference_kept": True,
        "original_frame_restored": original_frame,
        "output_size": output_path.stat().st_size,
    }


def main():
    ensure(SOURCE_DIR.is_dir(), f"Follow Path 来源目录不存在: {SOURCE_DIR}")
    reports = []
    for index, (source_name, output_name) in enumerate(zip(SOURCE_NAMES, OUTPUT_NAMES), start=1):
        reports.append(build_one(SOURCE_DIR / source_name, OUTPUT_DIR / output_name, index))
    payload = {
        "asset": "Butterfly",
        "variant": "master_wing_flap_replacement",
        "policy": "以 Butterfly_Master.blend 为基准，仅替换 ARTIST_EDIT 左右翅膀扇动；Master 位置/旋转等信息保持不变",
        "outputs": reports,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_MASTER_WING_FLAP_BUILD=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
