"""Compatibility entrypoint; never strip approved crystal materials or walls.

No arguments stages a candidate. Publish with --create --candidate <run-dir>.
"""

from pathlib import Path
import runpy


def main():
    runpy.run_path(
        str(Path(__file__).with_name("build_specimen_frame_crystal_core.py")),
        run_name="__main__",
    )


if __name__ == "__main__":
    main()
