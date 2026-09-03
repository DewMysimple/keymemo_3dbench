"""Stage the crystal-core asset at the stable Default_Material filename.

Publish a visually inspected run with --create --candidate <run-directory>.
"""

from __future__ import annotations

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).with_name("build_specimen_frame_crystal_core.py")),
        run_name="__main__",
    )
