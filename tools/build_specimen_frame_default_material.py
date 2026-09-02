"""Run the default-material specimen-frame variant builder.

The implementation is kept in the existing builder module so the revised
variant remains reproducible from one source script.
"""

from __future__ import annotations

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).with_name("build_specimen_frame_no_material.py")),
        run_name="__main__",
    )
