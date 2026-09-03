"""Scan every local .blend for unresolved external images, movies and fonts.

This is a read-only Blender validation pass. It deliberately does not save any
opened file; the report is the only output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))

from workbench_paths import REPORTS_ROOT, WORKBENCH_ROOT


WORKBENCH = WORKBENCH_ROOT
REPORT = REPORTS_ROOT / "all-blend-assets-validation.json"
LEGACY_PROJECT_NAME = "Vermin" + "oble"
LEGACY_WORKBENCH_NAME = "blender_" + "scenebench"


def scan_datablocks(kind: str, datablocks) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for datablock in datablocks:
        filepath = getattr(datablock, "filepath", "")
        if not filepath or filepath == "<builtin>":
            continue
        normalized = filepath.replace("\\", "/")
        try:
            absolute = Path(bpy.path.abspath(filepath)).resolve()
        except (OSError, RuntimeError, ValueError):
            absolute = Path()
        if LEGACY_PROJECT_NAME in normalized or LEGACY_WORKBENCH_NAME in normalized:
            failures.append(
                {
                    "kind": kind,
                    "name": datablock.name,
                    "filepath": filepath,
                    "resolved": absolute.as_posix() if absolute else "",
                    "reason": "legacy-workbench-path",
                }
            )
        if absolute and not absolute.is_file() and getattr(datablock, "packed_file", None) is None:
            failures.append(
                {
                    "kind": kind,
                    "name": datablock.name,
                    "filepath": filepath,
                    "resolved": absolute.as_posix(),
                    "reason": "missing",
                }
            )
    return failures


def main() -> None:
    blend_files = sorted(
        path
        for path in WORKBENCH.rglob("*.blend")
        if ".git" not in path.parts and "generated" not in path.parts
    )
    records: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for path in blend_files:
        try:
            bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
            file_failures = scan_datablocks("image", bpy.data.images)
            file_failures.extend(scan_datablocks("movie", bpy.data.movieclips))
            file_failures.extend(scan_datablocks("font", bpy.data.fonts))
            failures.extend(
                {"blend": path.relative_to(WORKBENCH).as_posix(), **failure}
                for failure in file_failures
            )
            records.append(
                {
                    "blend": path.relative_to(WORKBENCH).as_posix(),
                    "external_images": sum(
                        1
                        for image in bpy.data.images
                        if image.filepath and image.packed_file is None
                    ),
                    "external_fonts": sum(
                        1
                        for font in bpy.data.fonts
                        if font.filepath and font.filepath != "<builtin>" and font.packed_file is None
                    ),
                    "passed": not file_failures,
                }
            )
        except Exception as exc:  # Blender can reject a damaged legacy file.
            failures.append(
                {
                    "blend": path.relative_to(WORKBENCH).as_posix(),
                    "kind": "blend",
                    "name": path.name,
                    "filepath": str(path),
                    "resolved": str(path),
                    "reason": f"open-failed: {exc}",
                }
            )
    result = {
        "blender_version": bpy.app.version_string,
        "blend_count": len(blend_files),
        "records": records,
        "failures": failures,
        "passed": not failures and len(records) == len(blend_files),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures or len(records) != len(blend_files):
        raise RuntimeError(f"Blend asset scan failed: {len(failures)} failure(s)")


if __name__ == "__main__":
    main()
