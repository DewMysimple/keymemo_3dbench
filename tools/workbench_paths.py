"""Canonical paths for the keymemo_3dbench Blender workbench.

Keep repository layout knowledge here so builders, validators and reports use
the same scene/model/runtime boundaries.
"""

from __future__ import annotations

from pathlib import Path


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]

SCENES_ROOT = WORKBENCH_ROOT / "scenes"
GWAYLOO_ROOT = SCENES_ROOT / "GwayLoo"
GWAYLOO_FULL_ROOT = GWAYLOO_ROOT / "full"
GWAYLOO_FULL_BLEND = GWAYLOO_FULL_ROOT / "GwayLoo_Scene_5_0.blend"
GWAYLOO_VERSIONS_ROOT = GWAYLOO_ROOT / "versions"

MODELS_ROOT = WORKBENCH_ROOT / "models"
MODEL_ROOTS = {
    "Butterfly": MODELS_ROOT / "Butterfly",
    "SpecimenFrame": MODELS_ROOT / "SpecimenFrame",
    "兰花": MODELS_ROOT / "兰花",
    "杜鹃花": MODELS_ROOT / "杜鹃花",
    "水": MODELS_ROOT / "水",
    "othermodel": MODELS_ROOT / "othermodel",
}

RUNTIME_ROOT = WORKBENCH_ROOT / "runtime"
SOURCE_SNAPSHOT = RUNTIME_ROOT / "source_snapshot"
PUBLIC_ASSETS = SOURCE_SNAPSHOT / "assets"

TOOLS_ROOT = WORKBENCH_ROOT / "tools"
MANIFESTS_ROOT = WORKBENCH_ROOT / "manifests"
REPORTS_ROOT = WORKBENCH_ROOT / "reports"
GENERATED_ROOT = WORKBENCH_ROOT / "generated"


def relative_path(path: Path) -> str:
    """Return a stable repository-relative path using forward slashes."""

    return path.resolve().relative_to(WORKBENCH_ROOT.resolve()).as_posix()


def model_root(asset_name: str) -> Path:
    try:
        return MODEL_ROOTS[asset_name]
    except KeyError as exc:
        raise KeyError(f"Unknown model asset: {asset_name}") from exc


def model_source(asset_name: str) -> Path:
    return model_root(asset_name) / "source"


def model_scenes(asset_name: str) -> Path:
    return model_root(asset_name) / "scenes"


def model_metadata(asset_name: str) -> Path:
    return model_root(asset_name) / "metadata"
