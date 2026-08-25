from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any


WORKBENCH = Path(__file__).resolve().parents[1]
PROJECT = WORKBENCH.parent
SNAPSHOT = WORKBENCH / "source_snapshot"
CURRENT_XP = PROJECT / "public/wp-content/themes/davidwhyte/resources/assets/xp"
REFERENCE_XP = Path(r"C:/Users/Administrator/Desktop/网页(1)/wp-content/themes/davidwhyte/resources/assets/xp")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def purpose(path: Path) -> str:
    suffix = path.suffix.lower()
    normalized = path.as_posix().lower()
    if suffix == ".glb":
        return "source scene geometry, hierarchy, camera and baked animation"
    if "/videos/" in normalized:
        return "desktop/mobile landscape base or over movie layer"
    if "/sounds/" in normalized:
        return "experience loop or interaction feedback audio"
    if suffix == ".ktx2":
        return "GPU-compressed ground atlas"
    if suffix == ".3dl":
        return "source color lookup table"
    if "/msdf/" in normalized:
        return "MSDF font data or glyph atlas"
    if "/poem/" in normalized:
        return "poem texture used by the WebGL runtime"
    if "/textures/" in normalized:
        return "watercolor, paper, mask, SDF, grass or noise texture"
    if "/fonts/" in normalized:
        return "source UI or canvas font"
    if suffix in {".js", ".ts", ".tsx", ".css"}:
        return "runtime or extracted scene configuration reference"
    return "supporting source asset"


def ffprobe(path: Path) -> dict[str, Any] | None:
    executable = shutil.which("ffprobe")
    if not executable or path.suffix.lower() not in {".mp4", ".mp3"}:
        return None
    selector = "v:0" if path.suffix.lower() == ".mp4" else "a:0"
    fields = "codec_name,width,height,pix_fmt,duration" if selector == "v:0" else "codec_name,sample_rate,channels,duration"
    result = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-select_streams",
            selector,
            "-show_entries",
            f"stream={fields}",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    streams = json.loads(result.stdout).get("streams", [])
    return streams[0] if streams else None


def parse_glb(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    if payload[:4] != b"glTF":
        raise ValueError(f"Not a GLB file: {path}")
    offset = 12
    document: dict[str, Any] | None = None
    while offset < len(payload):
        chunk_length, chunk_type = struct.unpack_from("<II", payload, offset)
        chunk = payload[offset + 8 : offset + 8 + chunk_length]
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8"))
            break
        offset += 8 + chunk_length
    if document is None:
        raise ValueError("GLB JSON chunk was not found")

    animation = document.get("animations", [{}])[0]
    accessors = document.get("accessors", [])
    input_accessor = accessors[animation.get("samplers", [{}])[0].get("input", 0)] if animation.get("samplers") else {}
    return {
        "asset": document.get("asset"),
        "default_scene": document.get("scene"),
        "scenes": document.get("scenes", []),
        "nodes": document.get("nodes", []),
        "meshes": [
            {
                "index": index,
                "name": mesh.get("name"),
                "primitive_count": len(mesh.get("primitives", [])),
                "attributes": mesh.get("primitives", [{}])[0].get("attributes", {}),
            }
            for index, mesh in enumerate(document.get("meshes", []))
        ],
        "cameras": document.get("cameras", []),
        "animations": [
            {
                "name": item.get("name"),
                "channel_count": len(item.get("channels", [])),
                "sampler_count": len(item.get("samplers", [])),
            }
            for item in document.get("animations", [])
        ],
        "animation_sample_count": input_accessor.get("count"),
        "animation_duration_seconds": (input_accessor.get("max") or [None])[0],
    }


def parse_atlas_typescript(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")

    def parse_remap(const_name: str) -> dict[str, dict[str, float]]:
        block_match = re.search(
            rf"{const_name}[^=]*=\s*\{{(?P<body>.*?)\n\}};",
            source,
            re.DOTALL,
        )
        if not block_match:
            raise ValueError(f"Unable to locate {const_name}")
        result: dict[str, dict[str, float]] = {}
        pattern = re.compile(
            r"(?P<name>[A-Za-z0-9_]+):\s*\{\s*x:\s*(?P<x>[\d.]+),\s*y:\s*(?P<y>[\d.]+),\s*width:\s*(?P<width>[\d.]+),\s*height:\s*(?P<height>[\d.]+)\s*\}"
        )
        for match in pattern.finditer(block_match.group("body")):
            result[match.group("name")] = {
                key: float(match.group(key)) for key in ("x", "y", "width", "height")
            }
        return result

    schedule_match = re.search(
        r"watercolorLayerSchedule[^=]*=\s*\{(?P<body>.*?)\n\};",
        source,
        re.DOTALL,
    )
    if not schedule_match:
        raise ValueError("Unable to locate watercolorLayerSchedule")
    schedule = {
        match.group("name"): float(match.group("time"))
        for match in re.finditer(
            r"(?P<name>[A-Za-z0-9_]+):\s*(?P<time>[\d.]+)", schedule_match.group("body")
        )
    }
    # The extracted TypeScript identifiers were named from the earlier R3F
    # prototype, but the legacy runtime is the source of truth.  In app.js,
    # `_importBakedAtlases()` binds the compact table represented by
    # `watercolorSdfRemaps` to atlas/texture and the metadata-rich table
    # represented by `watercolorAtlasRemaps` to atlas/sdf.  Keep the manifest
    # names semantic so Blender cannot accidentally sample the SDF packing as
    # visible colour again.
    return {
        "texture_atlas_remaps": parse_remap("watercolorSdfRemaps"),
        "sdf_atlas_remaps": parse_remap("watercolorAtlasRemaps"),
        "layer_schedule_seconds": schedule,
    }


def parse_legacy_layer_runtime(path: Path) -> dict[str, dict[str, Any]]:
    """Extract per-paper ground settings used by the procedural grass system.

    The runtime configuration is minified, but each paper still starts with a
    stable `name` and `startAt` pair.  Grass is generated from the paper mesh
    bounds plus `ground.edges` and `ground.depth`; no screenshot-derived values
    are introduced here.
    """
    source = path.read_text(encoding="utf-8")
    start = source.find("var oZ=[")
    if start < 0:
        raise ValueError("Unable to locate legacy watercolor layer configuration")
    end = source.find("];function aZ", start)
    if end < 0:
        raise ValueError("Unable to locate the end of legacy watercolor layer configuration")
    block = source[start:end]
    matches = list(
        re.finditer(
            r'name:"(?P<name>[A-Za-z0-9_]+)",startAt:(?P<start>-?[\d.]+)',
            block,
        )
    )
    result: dict[str, dict[str, Any]] = {}
    for index, match in enumerate(matches):
        segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(block)
        segment = block[match.start():segment_end]
        ground_match = re.search(r"ground:\{(?P<body>[^{}]+)\}", segment)
        if not ground_match:
            raise ValueError(f"Missing ground settings for {match.group('name')}")
        ground_body = ground_match.group("body")

        def number(field: str) -> float:
            value = re.search(rf"{field}:(?P<value>-?[\d.]+)", ground_body)
            if not value:
                raise ValueError(f"Missing ground.{field} for {match.group('name')}")
            return float(value.group("value"))

        texture_match = re.search(r'texture:"(?P<value>[^"]+)"', ground_body)
        color_match = re.search(r'color:"(?P<value>#[0-9A-Fa-f]+)"', ground_body)
        has_ground_match = re.search(r"hasGround:!(?P<value>[01])", segment)
        result[match.group("name")] = {
            "start_seconds": float(match.group("start")),
            "ground": {
                "texture": texture_match.group("value") if texture_match else None,
                "color": color_match.group("value") if color_match else None,
                "edges": number("edges"),
                "depth": number("depth"),
            },
            "has_ground": has_ground_match is None or has_ground_match.group("value") == "0",
        }
    if len(result) != 26:
        raise ValueError(f"Expected 26 legacy layer configs, found {len(result)}")
    return result


def normalized_text_equal(left: Path, right: Path) -> bool:
    try:
        a = left.read_text(encoding="utf-8").replace("\r\n", "\n")
        b = right.read_text(encoding="utf-8").replace("\r\n", "\n")
        return a == b
    except (UnicodeDecodeError, OSError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory the isolated GwayLoo scene snapshot")
    parser.add_argument("--reference-root", type=Path, default=REFERENCE_XP)
    args = parser.parse_args()

    manifests = WORKBENCH / "manifests"
    reports = WORKBENCH / "reports"
    manifests.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    files = sorted(path for path in SNAPSHOT.rglob("*") if path.is_file() and path.name != ".gitkeep")
    records: list[dict[str, Any]] = []
    checksum_lines: list[str] = []
    for path in files:
        relative = path.relative_to(WORKBENCH).as_posix()
        digest = sha256(path)
        record: dict[str, Any] = {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": digest,
            "extension": path.suffix.lower(),
            "purpose": purpose(path),
        }
        media = ffprobe(path)
        if media:
            record["media"] = media
        records.append(record)
        checksum_lines.append(f"{digest}  {relative}")

    glb = SNAPSHOT / "assets/models/scene.glb"
    atlas_ts = SNAPSHOT / "runtime/content/atlas.ts"
    watercolor = parse_atlas_typescript(atlas_ts)
    watercolor["legacy_layer_runtime"] = parse_legacy_layer_runtime(
        SNAPSHOT / "runtime/app.js"
    )
    scene_manifest = {
        "schema": 1,
        "source": "current GwayLoo runtime snapshot",
        "fps": 60,
        "landscape_video_duration_seconds": 10,
        "gltf": parse_glb(glb),
        "watercolor": watercolor,
        "hotspots": [
            {"id": 1, "title": "Dales with Cows", "focus_progress": 0.02},
            {"id": 2, "title": "Nidderdale Farm", "focus_progress": 0.14},
            {"id": 3, "title": "North York Moors", "focus_progress": 0.26},
            {"id": 4, "title": "Dales near Aysgarth", "focus_progress": 0.34},
            {"id": 5, "title": "Dales with Sheep", "focus_progress": 0.55},
            {"id": 6, "title": "Ribblehead Viaduct", "focus_progress": 0.66},
        ],
    }

    differences: list[dict[str, str]] = []
    snapshot_assets = SNAPSHOT / "assets"
    if args.reference_root.exists():
        for copied in sorted(path for path in snapshot_assets.rglob("*") if path.is_file()):
            relative = copied.relative_to(snapshot_assets)
            reference = args.reference_root / relative
            current = CURRENT_XP / relative
            if not reference.exists():
                differences.append({"path": relative.as_posix(), "kind": "missing-in-reference"})
                continue
            if sha256(copied) != sha256(reference):
                kind = "newline-only" if normalized_text_equal(copied, reference) else "content-difference"
                differences.append({"path": relative.as_posix(), "kind": kind})
            if not current.exists() or sha256(copied) != sha256(current):
                raise RuntimeError(f"Snapshot no longer matches current project source: {relative}")

    (manifests / "asset_manifest.json").write_text(
        json.dumps({"schema": 1, "file_count": len(records), "files": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (manifests / "scene_manifest.json").write_text(
        json.dumps(scene_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (manifests / "asset_checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    total_bytes = sum(item["bytes"] for item in records)
    legacy_layers = scene_manifest["watercolor"]["legacy_layer_runtime"]
    grass_layer_names = [name for name, runtime in legacy_layers.items() if runtime["has_ground"]]
    difference_rows = "\n".join(
        f"| `{item['path']}` | {item['kind']} |" for item in differences
    ) or "| — | No byte differences detected |"
    report = f"""# Source snapshot extraction report

- Snapshot files: {len(records)}
- Snapshot bytes: {total_bytes}
- XP asset files: {len(list(snapshot_assets.rglob('*.*')))}
- GLB meshes: {len(scene_manifest['gltf']['meshes'])}
- GLB nodes: {len(scene_manifest['gltf']['nodes'])}
- Camera animation samples: {scene_manifest['gltf']['animation_sample_count']}
- Camera animation duration: {scene_manifest['gltf']['animation_duration_seconds']} seconds
- Reference directory was read only: `{args.reference_root}`

## Current snapshot versus read-only reference

| Path | Difference |
| --- | --- |
{difference_rows}

`newline-only` means decoded UTF-8 content is equal after CRLF/LF normalization. The Blender build always uses the current project snapshot copied into this isolated workbench.

## Legacy watercolor runtime extraction

- The minified runtime contains {len(legacy_layers)} ordered watercolor layer configurations, including start time, ground texture, ground color, edge width, depth and `hasGround` state.
- The visible atlas is the compact table bound by the runtime to `atlas/texture`; the metadata-rich table is bound to `atlas/sdf`. Keeping these roles separate fixes the previous black or incorrectly cropped Blender materials.
- Exactly {len(grass_layer_names)} of the {len(legacy_layers)} layers enable a procedural ground component. The disabled source layers are: {', '.join(f'`{name}`' for name, runtime in legacy_layers.items() if not runtime['has_ground'])}.
- Grass source parameters were extracted from the runtime: Poisson-disc spacing 1.8–2.8 with seven tries, 7–24 clustered blades per seed, ten blade-atlas regions, eight gradient groups with three columns each, eight vertical segments, global scale 5, wind displacement 3000, intensity 3 and speed 0.5.
- The Blender generator uses a fixed local seed for reproducibility while retaining the source algorithm and resources. Browser cursor reveal and an uncaptured `Math.random()` outcome cannot be mirrored exactly without recording a specific browser session.

The read-only reference directory was inspected but not written. All extraction and Blender generation use files copied into `blender_scenebench/source_snapshot/`.
"""
    (reports / "source-extraction.md").write_text(report, encoding="utf-8")
    print(f"Wrote {len(records)} asset records ({total_bytes} bytes)")


if __name__ == "__main__":
    main()
