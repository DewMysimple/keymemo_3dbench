#!/usr/bin/env python3
"""Migrate the workbench from the legacy split layout to the canonical layout.

The command is deliberately dry-run by default.  ``--apply`` moves files on
the same volume, preserving names and bytes, then invokes Blender's path
metadata repair pass.  It never creates compatibility copies or links.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
OLD_BLENDER_ROOT = WORKBENCH_ROOT / "blender"
OLD_MODEL_ROOT = WORKBENCH_ROOT / ("blender_" + "modelbench")
OLD_VERSIONS_ROOT = WORKBENCH_ROOT / "versions"
OLD_SOURCE_SNAPSHOT = WORKBENCH_ROOT / "source_snapshot"

NEW_SCENES_ROOT = WORKBENCH_ROOT / "scenes"
NEW_GWAYLOO_ROOT = NEW_SCENES_ROOT / "GwayLoo"
NEW_GWAYLOO_FULL_ROOT = NEW_GWAYLOO_ROOT / "full"
NEW_GWAYLOO_VERSIONS_ROOT = NEW_GWAYLOO_ROOT / "versions"
NEW_MODELS_ROOT = WORKBENCH_ROOT / "models"
NEW_RUNTIME_ROOT = WORKBENCH_ROOT / "runtime"

LOCAL_ASSETS_MANIFEST = WORKBENCH_ROOT / "manifests/local_assets_manifest.json"
MAP_PATH = WORKBENCH_ROOT / "generated/layout-migration-map.json"
REPORT_PATH = WORKBENCH_ROOT / "reports/layout-migration.json"
BLENDER_REWRITE = WORKBENCH_ROOT / "tools/rewrite_blend_paths.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKBENCH_ROOT.resolve()).as_posix()


def add_file(mapping: dict[Path, Path], source: Path, target: Path) -> None:
    if not source.is_file():
        return
    if source in mapping and mapping[source] != target:
        raise ValueError(f"Duplicate source mapping: {source}")
    mapping[source] = target


def add_tree(mapping: dict[Path, Path], source_root: Path, target_root: Path) -> None:
    if not source_root.exists():
        return
    for source in source_root.rglob("*"):
        if source.is_file():
            add_file(mapping, source, target_root / source.relative_to(source_root))


def add_version_tree(mapping: dict[Path, Path]) -> None:
    """Map a legacy version while removing its redundant ``blender/`` layer."""

    source_root = OLD_VERSIONS_ROOT / "no-animation"
    if not source_root.exists():
        return
    target_root = NEW_GWAYLOO_VERSIONS_ROOT / "no-animation"
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        if relative.parts and relative.parts[0] == "blender":
            relative = Path(*relative.parts[1:])
        add_file(mapping, source, target_root / relative)


def add_model_asset(mapping: dict[Path, Path], asset_name: str) -> None:
    source_root = OLD_MODEL_ROOT / asset_name
    if not source_root.exists():
        return
    target_root = NEW_MODELS_ROOT / asset_name
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        parts = relative.parts
        if asset_name == "Butterfly":
            if parts[0] == "blender":
                if len(parts) >= 2 and parts[1].startswith("Butterfly_Master.blend"):
                    target = target_root / "scenes" / "master" / Path(*parts[1:])
                else:
                    target = target_root / "scenes" / Path(*parts[1:])
            elif parts[0] == "manifests":
                target = target_root / "metadata" / Path(*parts[1:])
            else:
                target = target_root / Path(*parts)
        elif asset_name == "SpecimenFrame":
            if parts[0] == "blender":
                target = target_root / "scenes" / Path(*parts[1:])
            else:
                target = target_root / Path(*parts)
        elif asset_name in {"兰花", "杜鹃花"}:
            if source.suffix.lower() == ".blend" and len(parts) == 1:
                target = target_root / "scenes" / source.name
            else:
                target = target_root / "source" / Path(*parts)
        elif asset_name == "水":
            if source.suffix.lower() == ".blend" and len(parts) == 1:
                target = target_root / "scenes" / source.name
            else:
                target = target_root / "source" / Path(*parts)
        else:  # pragma: no cover - asset list is intentionally closed above.
            raise ValueError(f"Unsupported model asset: {asset_name}")
        add_file(mapping, source, target)


def build_mapping() -> dict[Path, Path]:
    mapping: dict[Path, Path] = {}
    add_file(
        mapping,
        OLD_BLENDER_ROOT / "GwayLoo_Scene_5_0.blend",
        NEW_GWAYLOO_FULL_ROOT / "GwayLoo_Scene_5_0.blend",
    )
    for source in OLD_BLENDER_ROOT.glob("GwayLoo_Scene_5_0.blend[12]"):
        add_file(mapping, source, NEW_GWAYLOO_FULL_ROOT / source.name)
    add_file(mapping, OLD_BLENDER_ROOT / ".gitkeep", NEW_GWAYLOO_FULL_ROOT / ".gitkeep")

    add_version_tree(mapping)
    add_file(mapping, OLD_VERSIONS_ROOT / "README.md", NEW_GWAYLOO_ROOT / "README.md")
    add_tree(mapping, OLD_SOURCE_SNAPSHOT, NEW_RUNTIME_ROOT / "source_snapshot")
    for asset_name in ("Butterfly", "SpecimenFrame", "兰花", "杜鹃花", "水"):
        add_model_asset(mapping, asset_name)
    return mapping


def load_local_asset_expectations() -> list[dict[str, object]]:
    if not LOCAL_ASSETS_MANIFEST.is_file():
        return []
    payload = json.loads(LOCAL_ASSETS_MANIFEST.read_text(encoding="utf-8"))
    return list(payload.get("files", []))


def verify_local_assets(expectations: Iterable[dict[str, object]], mapping: dict[Path, Path]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for item in expectations:
        old_path = WORKBENCH_ROOT / str(item["path"])
        source = old_path
        if not source.exists():
            source = next(
                (source for source in mapping if rel(source) == str(item["path"])),
                next(
                    (source for source, target in mapping.items() if rel(target) == str(item["path"])),
                    old_path,
                ),
            )
        target = mapping.get(source, source)
        expected_bytes = int(item["bytes"])
        expected_hash = str(item["sha256"]).upper()
        check_path = target if target.is_file() else source
        actual_bytes = check_path.stat().st_size if check_path.is_file() else None
        actual_hash = sha256(check_path) if check_path.is_file() else None
        results.append(
            {
                "old_path": str(item["path"]),
                "path": rel(target) if target.exists() else rel(source),
                "expected_bytes": expected_bytes,
                "bytes": actual_bytes,
                "expected_sha256": expected_hash,
                "sha256": actual_hash,
                "passed": actual_bytes == expected_bytes and actual_hash == expected_hash,
            }
        )
    return results


def check_plan(mapping: dict[Path, Path]) -> list[str]:
    failures: list[str] = []
    seen_targets: set[Path] = set()
    for source, target in mapping.items():
        if not source.is_file():
            failures.append(f"源文件不存在: {rel(source)}")
        if target in seen_targets:
            failures.append(f"目标路径重复: {rel(target)}")
        seen_targets.add(target)
        if target.exists() and target != source:
            failures.append(f"目标路径已存在: {rel(target)}")
    local_results = verify_local_assets(load_local_asset_expectations(), mapping)
    failures.extend(
        f"本地大文件校验失败: {item['old_path']}"
        for item in local_results
        if not item["passed"]
    )
    return failures


def print_plan(mapping: dict[Path, Path], failures: list[str]) -> None:
    print(json.dumps({
        "mode": "dry-run",
        "move_count": len(mapping),
        "moves": [{"from": rel(source), "to": rel(target)} for source, target in mapping.items()],
        "failures": failures,
        "writes_files": False,
    }, ensure_ascii=False, indent=2))


def remove_empty_legacy_dirs() -> list[str]:
    removed: list[str] = []
    for root in (OLD_BLENDER_ROOT, OLD_MODEL_ROOT, OLD_VERSIONS_ROOT, OLD_SOURCE_SNAPSHOT):
        if not root.exists():
            continue
        leftovers = [path for path in root.rglob("*") if path.is_file()]
        if leftovers:
            raise RuntimeError(f"迁移后旧目录仍有文件: {rel(leftovers[0])}")
        for directory in sorted([path for path in root.rglob("*") if path.is_dir()], key=lambda path: len(path.parts), reverse=True):
            directory.rmdir()
        root.rmdir()
        removed.append(rel(root))
    return removed


def load_resume_mapping() -> dict[Path, Path]:
    """Recover a mapping after a move completed but its wrapper was interrupted."""

    payload = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    mapping: dict[Path, Path] = {}
    for item in payload.get("moves", []):
        source = WORKBENCH_ROOT / str(item["from"])
        target_text = str(item["to"])
        target_text = target_text.replace(
            "scenes/GwayLoo/versions/no-animation/blender/",
            "scenes/GwayLoo/versions/no-animation/",
        )
        target = WORKBENCH_ROOT / target_text
        mapping[source] = target
    return mapping


def apply_moves(mapping: dict[Path, Path]) -> None:
    for source, target in mapping.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)


def invoke_blender_rewrite(blender: Path) -> dict[str, object]:
    command = [
        str(blender),
        "--background",
        "--factory-startup",
        "--python",
        str(BLENDER_REWRITE),
        "--",
        "--root",
        str(WORKBENCH_ROOT),
        "--map",
        str(MAP_PATH),
    ]
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Blender 路径元数据迁移失败:\n"
            + completed.stdout[-4000:]
            + "\n"
            + completed.stderr[-4000:]
        )
    lines = [line for line in completed.stdout.splitlines() if line.startswith("LAYOUT_REWRITE=")]
    if not lines:
        raise RuntimeError("Blender 路径迁移未返回结构化结果")
    return json.loads(lines[-1].split("=", 1)[1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate the keymemo_3dbench workbench layout.")
    parser.add_argument("--apply", action="store_true", help="Execute the migration; dry-run is the default.")
    parser.add_argument("--blender", type=Path, default=Path(r"F:\Blender\blender.exe"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mapping = build_mapping()
    resumed = bool(args.apply and not mapping and MAP_PATH.is_file())
    if resumed:
        mapping = load_resume_mapping()
    failures = [] if resumed else check_plan(mapping)
    if not args.apply:
        print_plan(mapping, failures)
        if failures:
            raise SystemExit(1)
        return
    if failures:
        raise RuntimeError("迁移预检失败:\n" + "\n".join(failures))

    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(
        json.dumps({"moves": [{"from": rel(source), "to": rel(target)} for source, target in mapping.items()]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    before_hashes = {
        rel(source): sha256(source) if source.is_file() else sha256(target)
        for source, target in mapping.items()
    }
    if not resumed:
        apply_moves(mapping)
    rewrite = invoke_blender_rewrite(args.blender.resolve())
    local_results = verify_local_assets(load_local_asset_expectations(), mapping)
    if not all(item["passed"] for item in local_results):
        raise RuntimeError(f"迁移后本地大文件校验失败: {local_results}")
    removed = remove_empty_legacy_dirs()
    after_hashes = {rel(target): sha256(target) for target in mapping.values() if target.is_file()}
    report = {
        "schema_version": 1,
        "mode": "apply",
        "move_count": len(mapping),
        "removed_legacy_dirs": removed,
        "source_hashes_before": before_hashes,
        "target_hashes_after": after_hashes,
        "local_assets": local_results,
        "blend_rewrite": rewrite,
        "passed": True,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
