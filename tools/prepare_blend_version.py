#!/usr/bin/env python3
"""Prepare an independent Blender version from the registered baseline.

The command is intentionally dry-run by default.  ``--create`` is required
before it can ask Blender to open the source and save a rebased copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


WORKBENCH = Path(__file__).resolve().parents[1]
REGISTRY = WORKBENCH / "manifests/version_registry.json"
VARIANT_SCRIPT = WORKBENCH / "tools/apply_blend_version_changes.py"
DEFAULT_BLENDER = Path(os.environ.get("BLENDER_EXECUTABLE", r"F:\Blender\blender.exe"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a registered Blender version without changing its source file."
    )
    parser.add_argument("--version-id", required=True, help="Registered derivative version id.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate and print the plan only.")
    mode.add_argument("--create", action="store_true", help="Create the independent target file.")
    parser.add_argument(
        "--blender",
        type=Path,
        default=DEFAULT_BLENDER,
        help="Blender executable used for a real create operation.",
    )
    return parser.parse_args()


def resolve_workbench_path(relative: str) -> Path:
    candidate = (WORKBENCH / relative).resolve()
    try:
        candidate.relative_to(WORKBENCH.resolve())
    except ValueError as exc:
        raise ValueError(f"Registry path escapes the Blender workbench: {relative}") from exc
    return candidate


def find_version(registry: dict[str, Any], version_id: str) -> dict[str, Any]:
    for version in registry.get("versions", []):
        if version.get("id") == version_id:
            return version
    raise ValueError(f"Unknown version id: {version_id}")


def find_source(registry: dict[str, Any], version: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    source_id = version.get("source_version")
    if not source_id:
        raise ValueError(f"Version {version['id']} has no source_version")
    source = find_version(registry, source_id)
    source_path = resolve_workbench_path(str(source["blend"]))
    return source, source_path


def version_paths(version: dict[str, Any]) -> tuple[Path, Path, Path]:
    target = resolve_workbench_path(str(version["blend"]))
    version_root = resolve_workbench_path(str(version["root"]))
    report = version_root / "reports/version-preparation.json"
    metadata = version_root / "version.json"
    return target, report, metadata


def print_plan(
    version: dict[str, Any],
    source: dict[str, Any],
    source_path: Path,
    target_path: Path,
    report_path: Path,
    metadata_path: Path,
) -> None:
    source_hash = sha256(source_path) if source_path.is_file() else None
    payload = {
        "mode": "dry-run",
        "version_id": version["id"],
        "source_version": source["id"],
        "source": source_path.as_posix(),
        "source_exists": source_path.is_file(),
        "source_sha256": source_hash,
        "target": target_path.as_posix(),
        "target_exists": target_path.exists(),
        "report": report_path.as_posix(),
        "metadata": metadata_path.as_posix(),
        "change_set": version.get("change_set", []),
        "animation_policy": version.get("animation_policy"),
        "writes_files": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def update_registry(registry: dict[str, Any], version_id: str, updates: dict[str, Any]) -> None:
    for version in registry["versions"]:
        if version.get("id") == version_id:
            version.update(updates)
            REGISTRY.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return
    raise ValueError(f"Unknown version id: {version_id}")


def create_version(
    registry: dict[str, Any],
    version: dict[str, Any],
    source: dict[str, Any],
    source_path: Path,
    target_path: Path,
    report_path: Path,
    metadata_path: Path,
    blender: Path,
) -> None:
    if version.get("role") != "derivative":
        raise ValueError("Only derivative versions can be created by this tool")
    if version.get("status") not in {"planned", "failed"}:
        raise ValueError(f"Version {version['id']} is not available for creation: {version.get('status')}")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if target_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing target: {target_path}")
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable not found: {blender}")

    source_hash = sha256(source_path)
    registered_source_hash = source.get("source_sha256")
    if registered_source_hash and source_hash.upper() != str(registered_source_hash).upper():
        raise ValueError(
            f"Source hash does not match the registered {source['id']} baseline: "
            f"{source_hash} != {registered_source_hash}"
        )
    change_set = version.get("change_set", [])
    if change_set != ["remove-all-non-camera-animation"]:
        raise ValueError(
            f"Unsupported change_set for {version['id']}: {change_set}; "
            "only remove-all-non-camera-animation is implemented"
        )
    command = [
        str(blender),
        "--background",
        "--factory-startup",
        "--python",
        str(VARIANT_SCRIPT),
        "--",
        "--source",
        str(source_path),
        "--output",
        str(target_path),
        "--report",
        str(report_path),
        "--variant",
        change_set[0],
        "--frame",
        str(version.get("static_frame", 3586)),
    ]
    completed = subprocess.run(command, check=False, text=True)
    source_unchanged = sha256(source_path) == source_hash
    target_exists = target_path.is_file()
    change_report: dict[str, Any] = {}
    if report_path.is_file():
        try:
            change_report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            change_report = {}
    target_hash = sha256(target_path) if target_exists else None
    passed = (
        completed.returncode == 0
        and source_unchanged
        and target_exists
        and change_report.get("passed") is True
    )
    metadata = {
        "schema_version": 1,
        "version_id": version["id"],
        "source_version": source["id"],
        "source": source_path.relative_to(WORKBENCH).as_posix(),
        "target": target_path.relative_to(WORKBENCH).as_posix(),
        "source_sha256": source_hash,
        "target_sha256": target_hash,
        "source_unchanged": source_unchanged,
        "status": "prepared" if passed else "failed",
        "available": False,
        "requires_validation": True,
        "change_set": version.get("change_set", []),
        "animation_policy": version.get("animation_policy"),
        "change_exit_code": completed.returncode,
        "change_report_passed": change_report.get("passed"),
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_registry(
        registry,
        version["id"],
        {
            "status": "prepared" if passed else "failed",
            "source_sha256": source_hash,
            "prepared_sha256": target_hash,
        },
    )
    if not passed:
        raise RuntimeError(f"Version preparation failed: {metadata}")


def main() -> None:
    args = parse_args()
    registry = load_registry()
    version = find_version(registry, args.version_id)
    source, source_path = find_source(registry, version)
    target_path, report_path, metadata_path = version_paths(version)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if target_path == source_path:
        raise ValueError("Source and target must be different files")

    if not args.create:
        print_plan(version, source, source_path, target_path, report_path, metadata_path)
        return

    create_version(
        registry,
        version,
        source,
        source_path,
        target_path,
        report_path,
        metadata_path,
        args.blender.resolve(),
    )


if __name__ == "__main__":
    try:
        main()
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"[prepare-blend-version] ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
