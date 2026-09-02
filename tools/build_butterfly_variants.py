import json
import re
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_butterfly_scene as base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT  / "blender_modelbench" / "Butterfly"
SOURCE_ROOT = ASSET_ROOT / "source"
OUTPUT_DIR = ASSET_ROOT / "blender"
REPORT_PATH = PROJECT_ROOT  / "reports" / "butterfly-variants-build.json"
LEGACY_REPORT_PATH = PROJECT_ROOT  / "reports" / "butterfly-build.json"
PREVIEW_PATH = PROJECT_ROOT  / "generated" / "Butterfly_preview.png"

# Reuse the audited import/material/metadata helpers, but point every helper at
# the real, single-root Blender workspace requested by the user.
base.SOURCE_ROOT = SOURCE_ROOT
base.OUTPUT_DIR = OUTPUT_DIR
base.PREVIEW_PATH = PREVIEW_PATH
base.REPORT_PATH = REPORT_PATH


def safe_name(value):
    result = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", value).strip("_")
    return result or "Butterfly"


def variant_output_path(path):
    relative_parts = path.relative_to(SOURCE_ROOT).parts
    base.ensure(len(relative_parts) >= 3 and relative_parts[0] == "animations", f"无法确定动画分类: {path}")
    category = relative_parts[1]
    base.ensure(category in {"idle", "follow_path", "slow_flap"}, f"未知 Butterfly 动画分类: {category}")
    return OUTPUT_DIR / category / f"{safe_name(path.stem)}.blend"


def duplicate_group_preserving_animation(source_objects, collection, prefix):
    """Duplicate the complete imported hierarchy without changing its actions."""
    mapping = {}
    world_matrices = {source: source.matrix_world.copy() for source in source_objects}
    parent_inverses = {
        source: source.matrix_parent_inverse.copy()
        for source in source_objects
    }
    for source in source_objects:
        target = source.copy()
        target.animation_data_clear()
        if source.data:
            target.data = source.data.copy()
        target.name = f"展示_{prefix}_{source.name}"
        target["display_copy_of"] = source.name
        target["source_asset"] = source.get("source_asset", "")
        collection.objects.link(target)
        mapping[source] = target

    # Recreate the parent graph before attaching actions. This makes the local
    # transforms match the FBX hierarchy, while the display root remains the
    # only added presentation transform.
    for source, target in mapping.items():
        target.parent = mapping.get(source.parent)
        target.matrix_parent_inverse = parent_inverses[source]
        target.matrix_world = world_matrices[source]
    for source, target in mapping.items():
        base.copy_animation_data(source, target)

    bpy.context.view_layer.update()
    return list(mapping.values())


def image_bundle():
    image_root = SOURCE_ROOT / "textures"
    return {
        "diffuse": base.load_image(
            image_root / "DIFFUSE_Morpho_didius_Male_Dos_MHNT.jpg",
            "蝴蝶翅膀_颜色_DIFFUSE",
            "sRGB",
        ),
        "alpha": base.load_image(
            image_root / "ALPHA_OR_OPACITY_MASK_Morpho_didius_Male_Dos_MHNT.jpg",
            "蝴蝶翅膀_透明度_ALPHA",
            "Non-Color",
        ),
        "normal": base.load_image(
            image_root / "NORMAL_MAP_Morpho_didius_Male_Dos_MHNT_NRM.jpg",
            "蝴蝶翅膀_法线_NORMAL",
            "Non-Color",
        ),
        "reference": base.load_image(
            image_root / "_Male_Dos_MHNT.jpg",
            "蝴蝶源图参考_Male_Dos_MHNT",
            "sRGB",
        ),
    }


def make_source_collection(source_collection, path, group_id):
    group_collection = bpy.data.collections.new(
        f"SOURCE_{group_id}_{safe_name(path.stem)}"
    )
    source_collection.children.link(group_collection)
    return group_collection


def create_document(fbx_paths, output_path, document_label, copied_files, master=False):
    base.reset_factory()
    base.localized_workspaces()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    artist_scene = bpy.context.scene
    artist_scene.name = "ARTIST_EDIT"
    model_collection = base.new_collection(
        f"MODEL_{safe_name(document_label)}_展示模型"
    )
    source_collection = base.new_collection(
        f"SOURCE_{safe_name(document_label)}_源文件"
    )
    env_collection = base.new_collection(
        f"ENVIRONMENT_{safe_name(document_label)}_展示环境"
    )
    light_collection = base.new_collection(
        f"LIGHTS_{safe_name(document_label)}_摄影灯光"
    )

    records = []
    group_objects = {}
    for index, path in enumerate(fbx_paths, start=1):
        group_id = f"FBX_{index:02d}"
        group_collection = make_source_collection(source_collection, path, group_id)
        record = base.import_fbx(path, group_collection, group_id)
        records.append(record)
        group_objects[group_id] = record["objects"]

    obj_path = SOURCE_ROOT / "model" / "BASIC BUTTERFLY BODY_Travis_Davids.OBJ"
    obj_collection = bpy.data.collections.new("SOURCE_OBJ_Butterfly_Body")
    source_collection.children.link(obj_collection)
    body_source_objects = base.import_obj(obj_path, obj_collection)

    images = image_bundle()
    wing_material = base.make_wing_material(images)
    body_material = base.make_body_material(images["reference"])

    # The default artist scene contains one visible model only. All original
    # FBX objects remain in SOURCE_* and are shown in SOURCE_REFERENCE.
    hero_source_objects = group_objects["FBX_01"]
    hero_objects = duplicate_group_preserving_animation(
        hero_source_objects,
        model_collection,
        safe_name(document_label),
    )
    display_root = base.make_empty(
        f"DISPLAY_{safe_name(document_label)}_ROOT",
        model_collection,
        0.4,
    )
    for obj in hero_objects:
        if obj.parent is None:
            base.parent_preserve_world(obj, display_root)

    artist_scene.frame_set(1)
    bpy.context.view_layer.update()
    low, high = base.world_bounds(hero_objects)
    center = (low + high) * 0.5
    raw_extent = max(high.x - low.x, high.y - low.y, high.z - low.z)
    base.ensure(raw_extent > 0.0, "Butterfly 展示模型边界无效")
    display_extent = 6.2
    scale = display_extent / raw_extent
    display_root.scale = (scale, scale, scale)
    display_root.location = -center * scale
    display_root["source_display_scale"] = scale
    display_root["source_bounds_center_frame_1"] = list(center)
    display_root["source_bounds_extent_frame_1"] = raw_extent
    display_root["display_transform_policy"] = "只变更展示副本根节点；SOURCE_* 保持 FBX 导入层级"

    for obj in hero_objects:
        if obj.type != "MESH":
            continue
        if "wing" in obj.name.lower() or "翅" in obj.name:
            base.append_display_material(obj, wing_material)
        else:
            base.append_display_material(obj, body_material)

    action_list = [
        action
        for action in bpy.data.actions
        if action.get("source_import_group") == "FBX_01"
    ]
    max_frame = max(
        [int(round(action.frame_range[1])) for action in action_list] or [1]
    )
    is_path = (not master) and any("FOLLOW_PATH" in path.stem.upper() for path in fbx_paths)
    showcase_frame = min(max_frame, 45) if not is_path else 1
    display_root["animation_source"] = base.source_relative(fbx_paths[0])
    display_root["animation_action_names"] = json.dumps(
        [action.name for action in action_list],
        ensure_ascii=False,
    )
    display_root["showcase_frame"] = showcase_frame

    base.add_presentation_environment(env_collection, display_extent)
    camera = base.add_camera(artist_scene, light_collection, display_extent * 1.15)
    # The imported butterfly's broad wing faces are oriented toward +X/-X.
    # The previous diagonal camera made one wing appear edge-on, which looked
    # like a broken wing in the viewport/render.
    camera.location = (display_extent * 2.95, 0.0, display_extent * 0.34)
    base.point_at(camera, (0.0, 0.0, 0.0))
    base.add_area_light(
        light_collection,
        "蝴蝶_主光",
        (7.0, -8.0, 8.0),
        650.0,
        5.0,
        (1.0, 0.72, 0.52),
    )
    base.add_area_light(
        light_collection,
        "蝴蝶_辅光",
        (-6.0, -4.0, 4.5),
        420.0,
        4.0,
        (0.48, 0.68, 1.0),
    )
    base.add_area_light(
        light_collection,
        "蝴蝶_轮廓光",
        (5.0, 6.0, 7.0),
        850.0,
        3.5,
        (0.45, 0.72, 1.0),
    )
    base.add_area_light(
        light_collection,
        "蝴蝶_背面补光",
        (-10.0, 0.0, 5.0),
        950.0,
        6.0,
        (0.42, 0.62, 1.0),
    )

    base.configure_scene(artist_scene, frame_end=max_frame)
    artist_scene["asset_name"] = document_label
    artist_scene["document_type"] = "Butterfly 独立动画文件" if not master else "Butterfly 全素材总文件"
    artist_scene["hero_source_fbx"] = base.source_relative(fbx_paths[0])
    artist_scene["hero_display_objects"] = len(hero_objects)
    artist_scene["source_fbx_count"] = len(fbx_paths)
    artist_scene["source_obj_imported"] = True
    artist_scene["c4d_source_archived"] = True
    artist_scene["source_directory"] = "blender_modelbench/Butterfly/source"
    artist_scene["source_manifest"] = "blender_modelbench/Butterfly/manifests/source-files.json"
    artist_scene["source_coordinate_policy"] = "原始 FBX 坐标与父子关系不重算；展示根只负责统一可视化尺寸"
    artist_scene["wing_material_policy"] = "保留源材质槽；带贴图材质只追加到展示副本"
    artist_scene["default_showcase_frame"] = showcase_frame

    source_scene = bpy.data.scenes.new("SOURCE_REFERENCE")
    for collection in (model_collection, source_collection, env_collection, light_collection):
        source_scene.collection.children.link(collection)
    base.configure_scene(source_scene, frame_end=max_frame)
    source_scene["asset_name"] = document_label
    source_scene["reference_scene"] = "当前文件对应的 FBX 原始导入对象、OBJ 身体和 Action 数据"
    source_scene["source_directory"] = "blender_modelbench/Butterfly/source"
    source_scene["source_manifest"] = "blender_modelbench/Butterfly/manifests/source-files.json"

    base.set_scene_collection_visibility(
        artist_scene,
        {model_collection.name, env_collection.name, light_collection.name},
    )
    base.set_scene_collection_visibility(source_scene, {source_collection.name})

    display_path_object = next(
        (obj for obj in hero_objects if obj.type == "EMPTY" and obj.animation_data and obj.animation_data.action),
        None,
    )
    source_path_object = next(
        (obj for obj in hero_source_objects if obj.type == "EMPTY" and obj.animation_data and obj.animation_data.action),
        None,
    )
    base.calculate_motion_path(display_path_object, artist_scene, "ARTIST_EDIT")
    base.calculate_motion_path(source_path_object, source_scene, "SOURCE_REFERENCE")

    readme_root = (SOURCE_ROOT / "Read Me.txt").read_text(
        encoding="utf-8",
        errors="replace",
    )
    texture_readme = (SOURCE_ROOT / "textures" / "Read Me.txt").read_text(
        encoding="utf-8",
        errors="replace",
    )
    base.create_text("蝴蝶_源文件说明_Read Me", readme_root)
    base.create_text("蝴蝶_贴图说明_Read Me", texture_readme)
    base.embed_unimportable_sources()

    imported_records = base.source_file_records(copied_files, records)
    manifest_payload = {
        "asset": "Butterfly",
        "document_label": document_label,
        "document_type": "master" if master else "single_fbx_variant",
        "source_root": "blender_modelbench/Butterfly/source",
        "source_manifest": "blender_modelbench/Butterfly/manifests/source-files.json",
        "active_fbx": [base.source_relative(path) for path in fbx_paths],
        "files": imported_records,
        "fbx_imports": [
            {
                "path": record["path"],
                "group_id": record["group_id"],
                "object_count": len(record["objects"]),
                "action_names": [action.name for action in record["actions"]],
                "action_ranges": [list(action.frame_range) for action in record["actions"]],
            }
            for record in records
        ],
        "obj_source_object_count": len(body_source_objects),
        "fidelity_notes": [
            "本文件只在 ARTIST_EDIT 中显示当前文件对应的一个模型，避免多个 FBX 叠加造成翅膀错位观感。",
            "SOURCE_REFERENCE 保留当前 FBX 的原始对象层级、父子关系、网格、UV、材质槽和 Action。",
            "左右翅膀动作保留为 Blender Action；路径动画的空物体父级链不扁平化。",
            "OBJ 身体与 4 张图像均已导入；图像在保存前打包进 .blend。",
            "C4D 工程无法由 Blender 5 原生解析；原始字节保留在 source/project 并嵌入 Base64 文本数据块。",
        ],
    }
    base.create_text(
        "蝴蝶_源文件清单_完整数据",
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
    )
    base.create_text(
        "蝴蝶_保真规则",
        "源 FBX 只做导入，不删除对象、不合并网格、不清除动作。ARTIST_EDIT 使用保持父子关系的非破坏性展示副本；展示副本的根节点只用于居中和统一尺寸。",
    )

    for image in bpy.data.images:
        if image.name != "Render Result":
            image.pack()
    bpy.ops.file.pack_all()

    bpy.context.window.scene = artist_scene
    artist_scene.frame_set(showcase_frame)
    bpy.context.view_layer.update()
    if master:
        artist_scene.render.filepath = str(PREVIEW_PATH)
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))

    return {
        "file": str(output_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "document_label": document_label,
        "document_type": "master" if master else "single_fbx_variant",
        "active_fbx": [base.source_relative(path) for path in fbx_paths],
        "source_fbx_count": len(fbx_paths),
        "source_object_count": sum(len(record["objects"]) for record in records),
        "source_action_count": sum(len(record["actions"]) for record in records),
        "action_ranges": sorted({
            tuple(action.frame_range)
            for record in records
            for action in record["actions"]
        }),
        "source_obj_object_count": len(body_source_objects),
        "packed_image_count": sum(
            1 for image in bpy.data.images if image.packed_file
        ),
        "scene_names": [scene.name for scene in bpy.data.scenes],
        "default_scene": bpy.context.window.scene.name,
        "default_frame": artist_scene.frame_current,
        "display_object_count": len(hero_objects),
        "output_size": output_path.stat().st_size,
    }


def write_readme(reports):
    variants = [item for item in reports if item["document_type"] == "single_fbx_variant"]
    lines = [
        "# Butterfly Blender 文件集",
        "",
        "输出目录：`blender_modelbench/Butterfly`",
        "",
        "此目录现在按每个源 FBX 输出独立 Blender 文件；每个独立文件的 ARTIST_EDIT 只显示一个对应模型，动画可直接播放。",
        "",
        "## 文件",
        "",
        "- `blender/Butterfly_Master.blend`：全素材总文件，包含 10 个源 FBX 的 SOURCE_REFERENCE 数据，默认展示 Butterfly_Idle_1。",
    ]
    for item in variants:
        filename = item["file"].split("/Butterfly/", 1)[-1]
        lines.append(
            f"- `{filename}`：{item['active_fbx'][0]}；源对象 {item['source_object_count']} 个，Action {item['source_action_count']} 个。"
        )
    lines.extend([
        "",
        "## 打开方式",
        "",
        "- 默认场景 `ARTIST_EDIT`：单个已居中的展示模型，展示副本保持左右翅膀的原始父子关系和动作。",
        "- 场景 `SOURCE_REFERENCE`：对应文件的原始 FBX 导入对象；用于核对源数据，不会与其它动画叠加。",
        "- `source/`：18 个源文件的唯一原样来源；4 张图像已同时打包进每个 `.blend`。",
        "- `manifests/source-files.json`：记录每个源文件的大小与 SHA-256。",
        "- C4D 不能被 Blender 5 原生解析；C4D 原始字节保存在 `蝴蝶_C4D原始二进制_Base64` 文本块，并有 SHA-256 记录。",
        "",
        "## 翅膀修正说明",
        "",
        "上一版的问题是把所有 FBX 同时放进一个源场景，并把展示变换叠加到层级中的多个对象上。新版每个文件只显示一个 FBX，展示缩放只施加于单一展示根节点；源对象和 Action 不改名、不合并、不删除。",
        "",
        "构建报告：`reports/butterfly-variants-build.json`",
        "预览图：`generated/Butterfly_preview.png`",
    ])
    (ASSET_ROOT / "README.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main():
    base.ensure(SOURCE_ROOT.is_dir(), f"缺少 Butterfly 素材目录: {SOURCE_ROOT}")
    fbx_files = sorted(
        SOURCE_ROOT.glob("animations/**/*.fbx"),
        key=base.fbx_sort_key,
    )
    base.ensure(len(fbx_files) == 10, f"预期 10 个 FBX，实际找到 {len(fbx_files)} 个")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    copied_files = base.copy_source_assets()

    reports = []
    reports.append(
        create_document(
            fbx_files,
            OUTPUT_DIR / "Butterfly_Master.blend",
            "Butterfly_Master",
            copied_files,
            master=True,
        )
    )
    for path in fbx_files:
        reports.append(
            create_document(
                [path],
                variant_output_path(path),
                path.stem,
                copied_files,
                master=False,
            )
        )

    write_readme(reports)
    payload = {
        "output_root": str(OUTPUT_DIR.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_file_count": len(copied_files),
        "fbx_count": len(fbx_files),
        "blend_file_count": len(reports),
        "reports": reports,
        "preview": str(PREVIEW_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    master_report = dict(reports[0])
    master_report["output"] = master_report.pop("file")
    master_report["preview"] = str(PREVIEW_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/")
    master_report["source_directory"] = "blender_modelbench/Butterfly/source"
    master_report["source_manifest"] = "blender_modelbench/Butterfly/manifests/source-files.json"
    LEGACY_REPORT_PATH.write_text(json.dumps(master_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BUTTERFLY_VARIANTS_BUILD=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
