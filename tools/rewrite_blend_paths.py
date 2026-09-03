"""Blender-side path and metadata repair for the workbench layout migration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import bpy


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--map", type=Path, required=True)
    return parser.parse_args(raw)


def slash(value: str) -> str:
    return value.replace("\\", "/")


def relpath(path: Path, parent: Path) -> str:
    return "//" + os.path.relpath(path.resolve(), parent.resolve()).replace("\\", "/")


def asset_root_for(blend_path: Path) -> Path | None:
    parts = blend_path.resolve().parts
    if "models" not in parts:
        return None
    index = parts.index("models")
    if index + 1 >= len(parts):
        return None
    return Path(*parts[: index + 2])


def map_repository_text(value: str) -> str:
    text = slash(value)
    legacy_model_dir = "blender_" + "modelbench"
    legacy_scene_dir = "blender_" + "scenebench"

    # These replacements intentionally operate on path fragments rather than
    # absolute paths so the same repair works for embedded properties,
    # reports, and Windows/POSIX copies of the repository.
    for old_root in (
        "blender/_scenebench/blender/_modelbench/",
        legacy_scene_dir + "/blender/_modelbench/",
        legacy_scene_dir + "/" + legacy_model_dir + "/",
        legacy_model_dir + "/",
    ):
        while old_root in text:
            prefix, suffix = text.split(old_root, 1)
            asset, separator, remainder = suffix.partition("/")
            if not separator:
                replacement = "models/" + asset
            elif asset == "Butterfly":
                if remainder.startswith("blender/Butterfly_Master.blend"):
                    remainder = remainder.replace(
                        "blender/Butterfly_Master.blend",
                        "scenes/master/Butterfly_Master.blend",
                        1,
                    )
                elif remainder.startswith("blender/"):
                    remainder = "scenes/" + remainder[len("blender/") :]
                elif remainder.startswith("manifests/"):
                    remainder = "metadata/" + remainder[len("manifests/") :]
                replacement = f"models/{asset}/{remainder}"
            elif asset == "SpecimenFrame" and remainder.startswith("blender/"):
                replacement = f"models/{asset}/scenes/{remainder[len('blender/'):]}"
            elif asset in {"兰花", "杜鹃花"}:
                if remainder.endswith(".blend"):
                    replacement = f"models/{asset}/scenes/{remainder}"
                elif remainder.startswith(("形态1/", "形态2/", "三角梅/")):
                    replacement = f"models/{asset}/source/{remainder}"
                else:
                    replacement = f"models/{asset}/{remainder}"
            elif asset == "水":
                if remainder.endswith(".blend"):
                    replacement = f"models/{asset}/scenes/{remainder}"
                elif remainder.endswith(".uasset") or remainder.startswith("source/"):
                    replacement = f"models/{asset}/source/{remainder.removeprefix('source/')}"
                else:
                    replacement = f"models/{asset}/{remainder}"
            else:
                replacement = f"models/{suffix}"
            text = prefix + replacement

    protected = {
        "__KEYMEMO_FULL__": "scenes/GwayLoo/full/GwayLoo_Scene_5_0.blend",
        "__KEYMEMO_NO_ANIMATION__": "scenes/GwayLoo/versions/no-animation/",
        "__KEYMEMO_SNAPSHOT__": "runtime/source_snapshot/",
    }
    for marker, canonical in protected.items():
        text = text.replace(canonical, marker)

    for old, new in (
        (legacy_scene_dir + "/tools/", "tools/"),
        ("blender/GwayLoo_Scene_5_0.blend", "__KEYMEMO_FULL__"),
        ("versions/no-animation/blender/", "__KEYMEMO_NO_ANIMATION__"),
        ("versions/no-animation/", "__KEYMEMO_NO_ANIMATION__"),
        ("source_snapshot/", "__KEYMEMO_SNAPSHOT__"),
        ("models/Butterfly/scenes/Butterfly_Master.blend", "models/Butterfly/scenes/master/Butterfly_Master.blend"),
        ("models/Butterfly/blender/", "models/Butterfly/scenes/"),
        ("models/Butterfly/manifests/", "models/Butterfly/metadata/"),
        ("models/SpecimenFrame/blender/", "models/SpecimenFrame/scenes/"),
    ):
        text = text.replace(old, new)
    for marker, canonical in protected.items():
        text = text.replace(marker, canonical)
    return text


def search_by_name(root: Path, name: str) -> Path | None:
    if not root.is_dir() or not name:
        return None
    candidates = sorted(path for path in root.rglob(name) if path.is_file())
    return candidates[0] if len(candidates) == 1 else None


def target_for_filepath(value: str, blend_path: Path, root: Path, portable_hint: str | None = None) -> Path | None:
    mapped_hint = map_repository_text(portable_hint or "") if portable_hint else ""
    if mapped_hint.startswith("runtime/source_snapshot/"):
        candidate = root / mapped_hint
        if candidate.is_file():
            return candidate
    text = slash(value)
    mapped = map_repository_text(text)
    if mapped.startswith(("models/", "runtime/", "scenes/", "tools/")):
        candidate = root / mapped
        if candidate.is_file():
            return candidate
    try:
        absolute = Path(bpy.path.abspath(value)).resolve()
    except (OSError, RuntimeError, ValueError):
        absolute = Path()
    if absolute.is_file() and root in absolute.parents:
        return absolute
    asset_root = asset_root_for(blend_path)
    if asset_root:
        candidate = search_by_name(asset_root, Path(text).name)
        if candidate:
            return candidate
    if "source_snapshot" in text or "runtime/source_snapshot" in text:
        return search_by_name(root / "runtime/source_snapshot", Path(text).name)
    return None


def update_path_string(value: str, key: str) -> str:
    mapped = map_repository_text(value)
    if mapped != value:
        return mapped
    if key in {"source_file", "animation_cache_file"} and value.startswith(("形态1/", "形态2/")):
        return "source/" + value
    return value


def structural_fingerprint() -> dict[str, object]:
    def rounded(values: Any) -> tuple[float, ...]:
        return tuple(round(float(value), 7) for value in values)

    return {
        "scenes": sorted(
            (
                scene.name,
                scene.frame_start,
                scene.frame_end,
                scene.frame_current,
                scene.camera.name if scene.camera else None,
            )
            for scene in bpy.data.scenes
        ),
        "collections": sorted(collection.name for collection in bpy.data.collections),
        "objects": sorted(
            (
                obj.name,
                obj.type,
                obj.parent.name if obj.parent else None,
                obj.data.name if obj.data else None,
                rounded(obj.location),
                rounded(obj.rotation_euler),
                rounded(obj.scale),
            )
            for obj in bpy.data.objects
        ),
        "meshes": sorted(
            (mesh.name, len(mesh.vertices), len(mesh.polygons), len(mesh.materials))
            for mesh in bpy.data.meshes
        ),
        "curves": sorted(
            (curve.name, curve.dimensions, len(curve.splines))
            for curve in bpy.data.curves
        ),
        "materials": sorted(
            (material.name, material.use_nodes, rounded(material.diffuse_color))
            for material in bpy.data.materials
        ),
        "actions": sorted(
            (
                action.name,
                rounded(action.frame_range),
                tuple((layer.name, len(layer.strips)) for layer in action.layers),
            )
            for action in bpy.data.actions
        ),
        "cameras": sorted(
            (camera.name, camera.type, round(camera.lens, 7), round(camera.clip_start, 7), round(camera.clip_end, 7))
            for camera in bpy.data.cameras
        ),
        "lights": sorted(
            (light.name, light.type, round(light.energy, 7))
            for light in bpy.data.lights
        ),
    }


def update_id_properties(id_block: Any) -> int:
    changed = 0
    for key in list(id_block.keys()):
        value = id_block[key]
        if isinstance(value, str):
            updated = update_path_string(value, str(key))
            if updated != value:
                id_block[key] = updated
                changed += 1
    return changed


def rewrite_file(path: Path, root: Path) -> dict[str, object]:
    bpy.ops.wm.open_mainfile(filepath=str(path))
    before_structure = structural_fingerprint()
    changed_properties = 0
    changed_paths = 0
    unresolved: list[str] = []

    for collection in (
        bpy.data.scenes,
        bpy.data.objects,
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.actions,
        bpy.data.collections,
    ):
        for item in collection:
            changed_properties += update_id_properties(item)

    for image in bpy.data.images:
        if not image.filepath:
            continue
        target = target_for_filepath(image.filepath, path, root, image.get("portable_asset_path"))
        if target:
            updated = relpath(target, path.parent)
            if slash(image.filepath) != updated:
                image.filepath = updated
                changed_paths += 1
        elif image.packed_file is None and image.name != "Render Result":
            unresolved.append(f"image:{image.name}:{image.filepath}")

    for movie in bpy.data.movieclips:
        if not movie.filepath:
            continue
        target = target_for_filepath(movie.filepath, path, root, movie.get("portable_asset_path"))
        if target:
            updated = relpath(target, path.parent)
            if slash(movie.filepath) != updated:
                movie.filepath = updated
                changed_paths += 1
        elif movie.source != "SEQUENCE" and movie.source != "MOVIE_CLIP":
            unresolved.append(f"movie:{movie.name}:{movie.filepath}")

    for font in bpy.data.fonts:
        if not font.filepath or font.filepath == "<builtin>":
            continue
        target = target_for_filepath(font.filepath, path, root, font.get("portable_asset_path"))
        if target:
            updated = relpath(target, path.parent)
            if slash(font.filepath) != updated:
                font.filepath = updated
                changed_paths += 1
        elif font.packed_file is None:
            unresolved.append(f"font:{font.name}:{font.filepath}")

    for cache_file in bpy.data.cache_files:
        if not cache_file.filepath:
            continue
        target = target_for_filepath(cache_file.filepath, path, root)
        if target:
            updated = relpath(target, path.parent)
            if slash(cache_file.filepath) != updated:
                cache_file.filepath = updated
                changed_paths += 1
        else:
            unresolved.append(f"cache:{cache_file.name}:{cache_file.filepath}")

    if unresolved:
        raise RuntimeError(f"{path}: unresolved paths: {unresolved}")
    after_structure = structural_fingerprint()
    if before_structure != after_structure:
        raise RuntimeError(f"{path}: Blender 数据结构在路径迁移期间发生变化")
    if changed_properties or changed_paths:
        bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
    return {
        "blend": path.relative_to(root).as_posix(),
        "changed_properties": changed_properties,
        "changed_paths": changed_paths,
        "before_structure": before_structure,
        "after_structure": after_structure,
        "structure_unchanged": before_structure == after_structure,
        "unresolved": unresolved,
        "passed": True,
    }


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    blend_files = sorted(
        path for path in root.rglob("*.blend")
        if "generated" not in path.parts and ".git" not in path.parts
    )
    records = [rewrite_file(path, root) for path in blend_files]
    print("LAYOUT_REWRITE=" + json.dumps({"blend_count": len(records), "records": records, "passed": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
