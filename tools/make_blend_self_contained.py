"""Pack a Blender file's supported resources and optionally remove movie/font inputs.

Run this script from Blender with the target file already open.  Movie image
datablocks are removed only when ``--drop-movies`` is supplied because Blender's
normal Pack Resources operator deliberately skips movies and image sequences.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import bpy


def parse_args() -> argparse.Namespace:
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Make the open .blend self-contained.")
    parser.add_argument(
        "--drop-movies",
        action="store_true",
        help="Remove movie image datablocks before packing the remaining resources.",
    )
    parser.add_argument(
        "--drop-fonts",
        action="store_true",
        help="Replace external fonts with Blender's built-in font and remove their datablocks.",
    )
    parser.add_argument("--report", type=Path, required=True, help="JSON report path.")
    return parser.parse_args(raw_args)


def is_packed(datablock: Any) -> bool:
    if getattr(datablock, "packed_file", None) is not None:
        return True
    packed_files = getattr(datablock, "packed_files", None)
    return packed_files is not None and len(packed_files) > 0


def resource_collections() -> Iterable[tuple[str, Iterable[Any]]]:
    yield "images", bpy.data.images
    yield "movieclips", bpy.data.movieclips
    yield "sounds", bpy.data.sounds
    yield "fonts", bpy.data.fonts
    yield "volumes", bpy.data.volumes
    yield "cache_files", bpy.data.cache_files


def resource_record(kind: str, datablock: Any) -> dict[str, Any]:
    filepath = getattr(datablock, "filepath", "")
    packed = is_packed(datablock)
    return {
        "kind": kind,
        "name": datablock.name,
        "source": getattr(datablock, "source", ""),
        "filepath": filepath,
        "packed": packed,
        "external": bool(filepath and filepath != "<builtin>" and not packed),
    }


def audit_resources() -> dict[str, Any]:
    resources = [
        resource_record(kind, datablock)
        for kind, collection in resource_collections()
        for datablock in collection
        if getattr(datablock, "filepath", "")
    ]
    external = [record for record in resources if record["external"]]
    libraries = [
        {"name": library.name, "filepath": library.filepath}
        for library in bpy.data.libraries
    ]
    movie_images = [
        record
        for record in resources
        if record["kind"] == "images" and record["source"] == "MOVIE"
    ]
    external_fonts = [
        record
        for record in resources
        if record["kind"] == "fonts" and record["filepath"] != "<builtin>"
    ]
    return {
        "resources": resources,
        "external_resources": external,
        "libraries": libraries,
        "movie_images": movie_images,
        "external_fonts": external_fonts,
        "packed_resource_count": sum(record["packed"] for record in resources),
        "external_resource_count": len(external),
        "library_count": len(libraries),
        "movie_image_count": len(movie_images),
        "external_font_count": len(external_fonts),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    args = parse_args()
    blend_path = Path(bpy.data.filepath).resolve()
    if not blend_path.is_file():
        raise RuntimeError("The script requires an existing saved .blend file.")

    before = audit_resources()
    removed_movies: list[dict[str, str]] = []
    if args.drop_movies:
        for image in list(bpy.data.images):
            if image.source != "MOVIE":
                continue
            removed_movies.append({"name": image.name, "filepath": image.filepath})
            bpy.data.images.remove(image, do_unlink=True)

    removed_fonts: list[dict[str, Any]] = []
    if args.drop_fonts:
        builtin_font = next(
            (font for font in bpy.data.fonts if font.filepath == "<builtin>"), None
        )
        if builtin_font is None:
            raise RuntimeError("Blender's built-in font datablock is missing.")
        font_slots = ("font", "font_bold", "font_italic", "font_bold_italic")
        for font in list(bpy.data.fonts):
            if not font.filepath or font.filepath == "<builtin>":
                continue
            replaced_slots: list[str] = []
            for curve in bpy.data.curves:
                if not isinstance(curve, bpy.types.TextCurve):
                    continue
                for slot in font_slots:
                    if getattr(curve, slot, None) == font:
                        setattr(curve, slot, builtin_font)
                        replaced_slots.append(f"{curve.name}.{slot}")
            removed_fonts.append(
                {
                    "name": font.name,
                    "filepath": font.filepath,
                    "replaced_slots": sorted(replaced_slots),
                }
            )
            bpy.data.fonts.remove(font, do_unlink=True)

    bpy.ops.file.pack_all()
    after = audit_resources()
    passed = (
        after["external_resource_count"] == 0
        and after["library_count"] == 0
        and (not args.drop_movies or after["movie_image_count"] == 0)
        and (not args.drop_fonts or after["external_font_count"] == 0)
    )
    if not passed:
        raise RuntimeError(
            "Self-contained resource audit failed: "
            f"external={after['external_resource_count']}, "
            f"libraries={after['library_count']}, movies={after['movie_image_count']}, "
            f"fonts={after['external_font_count']}"
        )

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False)
    result = {
        "blender_version": bpy.app.version_string,
        "blend_file": str(blend_path),
        "drop_movies": args.drop_movies,
        "drop_fonts": args.drop_fonts,
        "before": before,
        "removed_movies": removed_movies,
        "removed_movie_count": len(removed_movies),
        "removed_fonts": removed_fonts,
        "removed_font_count": len(removed_fonts),
        "after": after,
        "file_size_bytes": blend_path.stat().st_size,
        "sha256": sha256(blend_path),
        "passed": passed,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("KEYMEMO_SELF_CONTAINED=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
