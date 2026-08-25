from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))

from portable_blend_assets import make_blend_assets_portable


WORKBENCH = Path(__file__).resolve().parents[1]
DEFAULT_BLEND = WORKBENCH / "blender/Verminoble_Scene_Mirror_5_0.blend"
DEFAULT_REPORT = WORKBENCH / "reports/blender-asset-repair.json"


def parse_script_args() -> argparse.Namespace:
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(
        description="Repair Blender asset paths while optionally saving to a separate target file."
    )
    parser.add_argument(
        "--source",
        "--input",
        dest="source",
        type=Path,
        default=Path(os.environ.get("VERMINOBLE_BLEND_INPUT", str(DEFAULT_BLEND))),
        help="Source .blend to open; defaults to the current full version.",
    )
    output_default = os.environ.get("VERMINOBLE_BLEND_OUTPUT")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(output_default) if output_default else None,
        help="Target .blend to save; defaults to the source file.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(os.environ.get("VERMINOBLE_BLEND_REPAIR_REPORT", str(DEFAULT_REPORT))),
        help="JSON report path.",
    )
    return parser.parse_args(raw_args)


def main() -> None:
    args = parse_script_args()
    source = args.source.resolve()
    output = (args.output or source).resolve()
    report = args.report.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() != ".blend" or output.suffix.lower() != ".blend":
        raise ValueError("Both source and output must be .blend files")

    bpy.ops.wm.open_mainfile(filepath=str(source))
    linked_libraries = sorted(
        library.filepath for library in bpy.data.libraries if library.filepath
    )
    summary = make_blend_assets_portable(output.parent)
    summary.update(
        {
            "source": source.as_posix(),
            "output": output.as_posix(),
            "linked_libraries": linked_libraries,
            "independent_copy": not linked_libraries,
        }
    )
    if linked_libraries:
        summary["passed"] = False
        summary.setdefault("failures", []).append(
            "The source file contains linked Blender libraries; version copies must be independent."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["passed"]:
        raise RuntimeError(f"Unresolved Blender assets: {summary}")


if __name__ == "__main__":
    main()
