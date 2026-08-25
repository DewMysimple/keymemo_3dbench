from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import bpy


WORKBENCH = Path(__file__).resolve().parents[1]
PROJECT_ROOT = WORKBENCH.parent
SOURCE_ASSETS = WORKBENCH / "source_snapshot/assets"
PUBLIC_ASSETS = PROJECT_ROOT / "public/wp-content/themes/davidwhyte/resources/assets/xp"
GENERATED_GROUND = WORKBENCH / "generated/converted/ground_atlas.png"
GENERATED_FONT = WORKBENCH / "generated/converted/CanelaText-Light.ttf"


def _resolved(path: Path) -> Path:
    return path.resolve()


def public_asset_for(path: Path) -> Path | None:
    """Return the tracked public equivalent for a local source snapshot asset."""

    try:
        relative = _resolved(path).relative_to(_resolved(SOURCE_ASSETS))
    except ValueError:
        return None
    candidate = PUBLIC_ASSETS / relative
    return candidate if candidate.is_file() else None


def portable_reference_path(path: Path) -> Path:
    return public_asset_for(path) or path


def relative_to_blend(path: Path, blend_parent: Path) -> str:
    target = portable_reference_path(path)
    relative = os.path.relpath(_resolved(target), _resolved(blend_parent)).replace("\\", "/")
    return f"//{relative}"


def _packed_path(name: str) -> str:
    return f"//__packed__/{name}"


def make_blend_assets_portable(blend_parent: Path) -> dict[str, Any]:
    """Map local source assets to tracked runtime files and pack generated-only data."""

    mapped_images: list[str] = []
    packed_images: list[str] = []
    packed_fonts: list[str] = []
    unresolved_images: list[str] = []
    unresolved_fonts: list[str] = []

    for image in bpy.data.images:
        if not image.filepath:
            continue
        absolute = _resolved(Path(bpy.path.abspath(image.filepath)))
        public_path = public_asset_for(absolute)
        if public_path is not None:
            image.filepath = relative_to_blend(public_path, blend_parent)
            image["portable_asset_path"] = str(public_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            mapped_images.append(image.name)
            continue
        try:
            absolute.relative_to(_resolved(PUBLIC_ASSETS))
        except ValueError:
            pass
        else:
            image.filepath = relative_to_blend(absolute, blend_parent)
            image["portable_asset_path"] = str(absolute.relative_to(PROJECT_ROOT)).replace("\\", "/")
            mapped_images.append(image.name)
            continue
        if absolute == _resolved(GENERATED_GROUND):
            if image.packed_file is None:
                image.pack()
            image.filepath = _packed_path(image.name)
            image["portable_asset_path"] = "packed generated ground atlas"
            packed_images.append(image.name)
            continue
        if image.packed_file is None:
            unresolved_images.append(image.filepath)

    for font in bpy.data.fonts:
        if not font.filepath or font.filepath == "<builtin>":
            continue
        absolute = _resolved(Path(bpy.path.abspath(font.filepath)))
        if absolute == _resolved(GENERATED_FONT):
            if font.packed_file is None:
                font.pack()
            font.filepath = _packed_path(Path(font.name).with_suffix(".ttf").name)
            font["portable_asset_path"] = "packed generated CanelaText-Light.ttf"
            packed_fonts.append(font.name)
        elif font.packed_file is None:
            unresolved_fonts.append(font.filepath)

    return {
        "mapped_images": sorted(mapped_images),
        "packed_images": sorted(packed_images),
        "packed_fonts": sorted(packed_fonts),
        "unresolved_images": sorted(unresolved_images),
        "unresolved_fonts": sorted(unresolved_fonts),
        "passed": not unresolved_images and not unresolved_fonts,
    }
