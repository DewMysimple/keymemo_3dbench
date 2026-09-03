"""Safely migrate the Butterfly asset into its canonical directory layout.

The default mode is a read-only plan. Use ``--apply`` only after reviewing the
plan. The migration preserves source bytes, refuses conflicting destinations,
and removes the known byte-identical ``source_assets`` duplicate only after all
18 source files have been verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from workbench_paths import WORKBENCH_ROOT, model_metadata, model_root, model_scenes, model_source

PROJECT_ROOT = WORKBENCH_ROOT
BUTTERFLY_ROOT = model_root("Butterfly")
SOURCE_ASSETS_ROOT = BUTTERFLY_ROOT / "source_assets"
SOURCE_ROOT = model_source("Butterfly")
BLENDER_ROOT = model_scenes("Butterfly")
MANIFEST_ROOT = model_metadata("Butterfly")
MANIFEST_PATH = MANIFEST_ROOT / "source-files.json"
LEGACY_ROOT = BUTTERFLY_ROOT
LEGACY_ARCHIVE_ROOT = BUTTERFLY_ROOT / "archive" / "legacy"


SOURCE_MIGRATIONS = (
    ("Read Me.txt", "source/Read Me.txt", "documentation"),
    (
        "Animated_Butterflies_Project_File_ Travis_Davids.c4d",
        "source/project/Animated_Butterflies_Project_File_ Travis_Davids.c4d",
        "project",
    ),
    (
        "Idle Animations (90 Frames)/Butterfly_Idle_1.fbx",
        "source/animations/idle/Butterfly_Idle_1.fbx",
        "animation",
    ),
    (
        "Idle Animations (90 Frames)/Butterfly_Idle_2.fbx",
        "source/animations/idle/Butterfly_Idle_2.fbx",
        "animation",
    ),
    (
        "Idle Animations (90 Frames)/Butterfly_Idle_3.fbx",
        "source/animations/idle/Butterfly_Idle_3.fbx",
        "animation",
    ),
    (
        "Idle Animations (90 Frames)/Butterfly_Idle_4.fbx",
        "source/animations/idle/Butterfly_Idle_4.fbx",
        "animation",
    ),
    (
        "Idle Animations (90 Frames)/Butterfly_Idle_5.fbx",
        "source/animations/idle/Butterfly_Idle_5.fbx",
        "animation",
    ),
    (
        "Idle Animations (90 Frames)/Butterfly_Idle_6.fbx",
        "source/animations/idle/Butterfly_Idle_6.fbx",
        "animation",
    ),
    (
        "Idle Animations (90 Frames)/Butterfly_Idle_7.fbx",
        "source/animations/idle/Butterfly_Idle_7.fbx",
        "animation",
    ),
    (
        "Single Butterfly Following A Path (90 Frames)/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.fbx",
        "source/animations/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.fbx",
        "animation",
    ),
    (
        "Single Butterfly Following A Path (90 Frames)/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.fbx",
        "source/animations/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.fbx",
        "animation",
    ),
    (
        "Slow Wing Flapping (120 Frames)/BUTTERFLY_IDLE_8_SLOW_FLAP_120_FRAMES.fbx",
        "source/animations/slow_flap/BUTTERFLY_IDLE_8_SLOW_FLAP_120_FRAMES.fbx",
        "animation",
    ),
    (
        "Textures And Butterfly Body/BASIC BUTTERFLY BODY_Travis_Davids.OBJ",
        "source/model/BASIC BUTTERFLY BODY_Travis_Davids.OBJ",
        "model",
    ),
    (
        "Textures And Butterfly Body/_Male_Dos_MHNT.jpg",
        "source/textures/_Male_Dos_MHNT.jpg",
        "texture",
    ),
    (
        "Textures And Butterfly Body/ALPHA_OR_OPACITY_MASK_Morpho_didius_Male_Dos_MHNT.jpg",
        "source/textures/ALPHA_OR_OPACITY_MASK_Morpho_didius_Male_Dos_MHNT.jpg",
        "texture",
    ),
    (
        "Textures And Butterfly Body/DIFFUSE_Morpho_didius_Male_Dos_MHNT.jpg",
        "source/textures/DIFFUSE_Morpho_didius_Male_Dos_MHNT.jpg",
        "texture",
    ),
    (
        "Textures And Butterfly Body/NORMAL_MAP_Morpho_didius_Male_Dos_MHNT_NRM.jpg",
        "source/textures/NORMAL_MAP_Morpho_didius_Male_Dos_MHNT_NRM.jpg",
        "texture",
    ),
    (
        "Textures And Butterfly Body/Read Me.txt",
        "source/textures/Read Me.txt",
        "documentation",
    ),
)


BLEND_MIGRATIONS = (
    ("Butterfly_Master.blend", "scenes/master/Butterfly_Master.blend"),
    ("Butterfly_Idle_1.blend", "scenes/idle/Butterfly_Idle_1.blend"),
    ("Butterfly_Idle_2.blend", "scenes/idle/Butterfly_Idle_2.blend"),
    ("Butterfly_Idle_3.blend", "scenes/idle/Butterfly_Idle_3.blend"),
    ("Butterfly_Idle_4.blend", "scenes/idle/Butterfly_Idle_4.blend"),
    ("Butterfly_Idle_5.blend", "scenes/idle/Butterfly_Idle_5.blend"),
    ("Butterfly_Idle_6.blend", "scenes/idle/Butterfly_Idle_6.blend"),
    ("Butterfly_Idle_7.blend", "scenes/idle/Butterfly_Idle_7.blend"),
    (
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend",
        "scenes/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_1.blend",
    ),
    (
        "BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend",
        "scenes/follow_path/BUTTERFLY_FLAP_FAST_FOLLOW_PATH_2.blend",
    ),
    (
        "BUTTERFLY_IDLE_8_SLOW_FLAP_120_FRAMES.blend",
        "scenes/slow_flap/BUTTERFLY_IDLE_8_SLOW_FLAP_120_FRAMES.blend",
    ),
)


LEGACY_MIGRATIONS = (
    ("Butterfly.blend", "Butterfly_legacy_master.blend"),
    ("Butterfly.blend1", "Butterfly_legacy_master.blend1"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def existing_source_candidates(legacy_relative: str, canonical_relative: str) -> list[Path]:
    return [
        BUTTERFLY_ROOT / Path(legacy_relative),
        SOURCE_ASSETS_ROOT / Path(legacy_relative),
        BUTTERFLY_ROOT / Path(canonical_relative),
    ]


def choose_source(legacy_relative: str, canonical_relative: str) -> tuple[Path, str]:
    candidates = [path for path in existing_source_candidates(legacy_relative, canonical_relative) if path.is_file()]
    ensure(candidates, f"找不到源文件: {legacy_relative}")
    hashes = {sha256(path) for path in candidates}
    ensure(len(hashes) == 1, f"源文件内容冲突，拒绝继续: {legacy_relative}")
    canonical = BUTTERFLY_ROOT / Path(canonical_relative)
    return next((path for path in candidates if path == canonical), candidates[0]), next(iter(hashes))


def validate_preconditions() -> dict:
    ensure(BUTTERFLY_ROOT.is_dir(), f"Butterfly 根目录不存在: {BUTTERFLY_ROOT}")
    source_records = []
    for legacy_relative, canonical_relative, role in SOURCE_MIGRATIONS:
        source, digest = choose_source(legacy_relative, canonical_relative)
        source_records.append({
            "legacy_path": legacy_relative,
            "canonical_path": canonical_relative,
            "role": role,
            "source_path": relative(source, BUTTERFLY_ROOT),
            "size": source.stat().st_size,
            "sha256": digest,
        })

    if SOURCE_ASSETS_ROOT.exists():
        archive_files = [path for path in SOURCE_ASSETS_ROOT.rglob("*") if path.is_file()]
        expected_archive = {legacy for legacy, _, _ in SOURCE_MIGRATIONS}
        actual_archive = {relative(path, SOURCE_ASSETS_ROOT) for path in archive_files}
        ensure(actual_archive == expected_archive, "source_assets 含有缺失或额外文件，拒绝删除重复目录")

    for source_name, target_relative in BLEND_MIGRATIONS:
        source = BUTTERFLY_ROOT / source_name
        target = BUTTERFLY_ROOT / target_relative
        if source.is_file() and target.is_file():
            ensure(sha256(source) == sha256(target), f"Blend 目标冲突，拒绝覆盖: {target_relative}")

    if (BUTTERFLY_ROOT / "Butterfly_README.md").is_file() and (BUTTERFLY_ROOT / "README.md").is_file():
        ensure(
            sha256(BUTTERFLY_ROOT / "Butterfly_README.md") == sha256(BUTTERFLY_ROOT / "README.md"),
            "README 目标冲突，拒绝覆盖",
        )

    legacy_records = []
    if LEGACY_ROOT.exists():
        legacy_files = [path for path in LEGACY_ROOT.rglob("*") if path.is_file()]
        ensure({path.name for path in legacy_files} == {name for name, _ in LEGACY_MIGRATIONS}, "旧路径含有未识别文件，拒绝迁移")
        for source_name, archive_name in LEGACY_MIGRATIONS:
            source = LEGACY_ROOT / source_name
            target = LEGACY_ARCHIVE_ROOT / archive_name
            if target.is_file():
                ensure(sha256(source) == sha256(target), f"历史归档目标冲突: {archive_name}")
            legacy_records.append({
                "source": str(source),
                "target": str(target),
                "size": source.stat().st_size,
                "sha256": sha256(source),
            })

    return {
        "source_records": source_records,
        "blend_migrations": [
            {
                "source": str(BUTTERFLY_ROOT / source_name),
                "target": str(BUTTERFLY_ROOT / target_relative),
            }
            for source_name, target_relative in BLEND_MIGRATIONS
            if (BUTTERFLY_ROOT / source_name).is_file()
        ],
        "legacy_records": legacy_records,
        "duplicate_source_assets": SOURCE_ASSETS_ROOT.exists(),
        "legacy_root_exists": LEGACY_ROOT.exists(),
    }


def relocate(source: Path, target: Path) -> None:
    if not source.exists():
        ensure(target.is_file(), f"迁移源和目标均不存在: {source}")
        return
    if target.exists():
        ensure(source.is_file() and target.is_file(), f"迁移目标类型冲突: {target}")
        ensure(sha256(source) == sha256(target), f"迁移目标内容冲突: {target}")
        source.unlink()
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


def remove_empty_ancestors(start: Path, stop: Path) -> None:
    current = start
    while current != stop and current != current.parent:
        if not current.exists():
            current = current.parent
            continue
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def write_manifest() -> None:
    records = []
    for path in sorted((path for path in SOURCE_ROOT.rglob("*") if path.is_file()), key=lambda item: str(item).lower()):
        records.append({
            "path": relative(path, SOURCE_ROOT),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        })
    ensure(len(records) == 18, f"整理后源文件数量错误: {len(records)}")
    payload = {
        "asset": "Butterfly",
        "source_root": "models/Butterfly/source",
        "source_file_count": len(records),
        "files": records,
    }
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_verified_source_duplicates() -> None:
    for legacy_relative, canonical_relative, _ in SOURCE_MIGRATIONS:
        target = BUTTERFLY_ROOT / Path(canonical_relative)
        ensure(target.is_file(), f"规范源文件缺失，拒绝清理重复副本: {canonical_relative}")
        expected_hash = sha256(target)
        for duplicate in (
            BUTTERFLY_ROOT / Path(legacy_relative),
            SOURCE_ASSETS_ROOT / Path(legacy_relative),
        ):
            if duplicate.is_file():
                ensure(sha256(duplicate) == expected_hash, f"重复源文件校验失败，拒绝删除: {duplicate}")
                duplicate.unlink()


def remove_active_backups() -> list[str]:
    output_by_name = {
        Path(target_relative).name: BUTTERFLY_ROOT / Path(target_relative)
        for _, target_relative in BLEND_MIGRATIONS
    }
    backups = [
        path
        for path in BUTTERFLY_ROOT.glob("*.blend[12]")
        if path.is_file()
    ]
    backups.extend(
        path
        for path in BLENDER_ROOT.rglob("*.blend[12]")
        if path.is_file()
    )
    removed = []
    for backup in sorted(set(backups), key=lambda path: str(path).lower()):
        if backup.parent == BUTTERFLY_ROOT:
            formal = output_by_name.get(backup.name[:-1])
        else:
            formal = backup.with_name(backup.name[:-1])
        ensure(formal is not None and formal.is_file(), f"自动备份没有对应正式文件，拒绝删除: {backup}")
        backup.unlink()
        removed.append(relative(backup, BUTTERFLY_ROOT))
    return removed


def apply_migration() -> dict:
    preflight = validate_preconditions()

    for legacy_relative, canonical_relative, _ in SOURCE_MIGRATIONS:
        source, expected_hash = choose_source(legacy_relative, canonical_relative)
        target = BUTTERFLY_ROOT / Path(canonical_relative)
        if target.is_file():
            ensure(sha256(target) == expected_hash, f"规范源文件校验失败: {canonical_relative}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            ensure(sha256(target) == expected_hash, f"规范源文件复制校验失败: {canonical_relative}")

    remove_verified_source_duplicates()

    for source_name, target_relative in BLEND_MIGRATIONS:
        relocate(BUTTERFLY_ROOT / source_name, BUTTERFLY_ROOT / target_relative)

    relocate(BUTTERFLY_ROOT / "Butterfly_README.md", BUTTERFLY_ROOT / "README.md")

    for source_name, archive_name in LEGACY_MIGRATIONS:
        source = LEGACY_ROOT / source_name
        target = LEGACY_ARCHIVE_ROOT / archive_name
        if source.exists():
            relocate(source, target)

    if SOURCE_ASSETS_ROOT.exists():
        ensure(
            len([path for path in SOURCE_ASSETS_ROOT.rglob("*") if path.is_file()]) == 0,
            "source_assets 清理前仍有未校验文件",
        )
        shutil.rmtree(SOURCE_ASSETS_ROOT)

    removed_backups = remove_active_backups()

    for path in (
        BUTTERFLY_ROOT / "Idle Animations (90 Frames)",
        BUTTERFLY_ROOT / "Single Butterfly Following A Path (90 Frames)",
        BUTTERFLY_ROOT / "Slow Wing Flapping (120 Frames)",
        BUTTERFLY_ROOT / "Textures And Butterfly Body",
    ):
        remove_empty_ancestors(path, BUTTERFLY_ROOT)

    remove_empty_ancestors(LEGACY_ROOT, PROJECT_ROOT / "models")
    write_manifest()
    return {
        "preflight": preflight,
        "manifest": str(MANIFEST_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_file_count": 18,
        "legacy_archive": str(LEGACY_ARCHIVE_ROOT.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "removed_active_backups": removed_backups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="执行迁移；默认只输出只读计划")
    args = parser.parse_args()
    preflight = validate_preconditions()
    if not args.apply:
        print(json.dumps({"mode": "dry-run", **preflight}, ensure_ascii=False, indent=2))
        return
    result = apply_migration()
    print(json.dumps({"mode": "apply", **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
