"""Scan every local .blend for unresolved external images, movies and fonts.

This is a read-only Blender validation pass. It deliberately does not save any
opened file; the report is the only output.
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy


WORKBENCH = Path(__file__).resolve().parents[1]
REPORT = WORKBENCH / "reports/all-blend-assets-validation.json"


def scan_datablocks(kind: str, datablocks) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for datablock in datablocks:
        filepath = getattr(datablock, "filepath", "")
        if (
            not filepath
            or filepath == "<builtin>"
            or getattr(datablock, "packed_file", None) is not None
        ):
            continue
        absolute = Path(bpy.path.abspath(filepath)).resolve()
        if not absolute.is_file():
            failures.append(
                {
                    "kind": kind,
                    "name": datablock.name,
                    "filepath": filepath,
                    "resolved": absolute.as_posix(),
                    "reason": "missing",
                }
            )
        if "Verminoble" in absolute.as_posix() or "blender_scenebench" in absolute.as_posix():
            failures.append(
                {
                    "kind": kind,
                    "name": datablock.name,
                    "filepath": filepath,
                    "resolved": absolute.as_posix(),
                    "reason": "legacy-workbench-path",
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
