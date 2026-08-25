# GwayLoo Scene Workbench

This directory is an isolated local art workspace for studying and rebuilding the webpage's watercolor scene in Blender. The application must never import assets from here.

## Delivered structure

- `source_snapshot/`: local-only byte copies of the current runtime assets, fonts, legacy runtime and extracted R3F configuration.
- `blender/Verminoble_Scene_Mirror_5_0.blend`: tracked Blender 5.0 master file. Its runtime media paths point to the tracked `public/.../xp` assets; the generated Ground PNG and converted annotation font are packed into the file so a normal repository checkout does not resolve through the ignored `source_snapshot/` or `generated/` directories. Automatic `.blend1/.blend2` backups remain ignored.
- `manifests/asset_manifest.json`: size, SHA-256, format, purpose and media metadata.
- `manifests/scene_manifest.json`: GLB structure, camera timing, watercolor UV/SDF rectangles, layer schedule and hotspots.
- `manifests/version_registry.json`: the full baseline and planned derivative-version records.
- `versions/`: version-layout rules; derivative files are created only by the explicit version-preparation tool.
- `tools/`: reproducible extraction, conversion, Blender build, validation and render scripts.
- `reports/`: source differences, Blender structure checks and rendering-boundary documentation.
- `generated/`: ignored KTX/font conversions, tool cache and validation renders.

The snapshot contains the complete `xp` directory: one GLB, 24 videos, 16 textures, one KTX2, two LUTs, MSDF data, poem texture, five audio files and Basis support files. It also includes 23 source font files and the relevant runtime/configuration snapshot.

## Blender organization

The single master file opens in the artist-facing scene and contains:

- `ARTIST_EDIT`: the default scene at frame 3586. `EDIT_tree_1` is selected, all 26 watercolor meshes are selectable, and the viewport is saved in Material Preview mode.
- `WEB_ANIMATION`: the complete 0–3586 source timeline. It shares the exact same editable mesh and material datablocks with `ARTIST_EDIT`.
- `SOURCE_REFERENCE`: the isolated, selection-locked `SOURCE_GLTF_MIRROR`. It is not linked into either artist-facing scene.
- Six `LANDSCAPE_01–06_DESKTOP` scenes at 1920×1080.
- Six `LANDSCAPE_01–06_MOBILE` scenes at 810×1080.

Use `ARTIST_EDIT` for mesh, UV and material work. Use `WEB_ANIMATION` to play the browser-derived motion. Because both scenes link the same collection, editing an `EDIT_*` mesh or `WC_*` material updates the animation scene without creating a second visible layer.

`SOURCE_GLTF_MIRROR` remains available only in `SOURCE_REFERENCE`. It is locked to prevent accidental changes and no longer overlaps the editable layers. The imported GLB contained one zero-area triangle in `land_back_5`; the editable copy removes only that invalid face while retaining the remaining source triangles, UVs and silhouette. Automated validation requires zero N-Gons and zero zero-area faces.

`WEB_CAMERA_EDITABLE` is the active camera. Its `WEB_CAMERA_ACTIVE_BAKED` action contains all 3587 source samples. `WEB_CAMERA_INTERACTION_CONTROL` exposes the separately measured browser loader/mouse offsets without baking them into the main scroll path.

Each of the 26 editable watercolor objects has its own `WEB_REVEAL_*` action. These actions reproduce the source schedule and animate opacity, paper curvature, entry rotation, reveal progress and cutout/ground opacity. The extracted source shadow timing remains stored as unused runtime metadata until the WebGL shadow shader is accurately rebuilt. Each landscape scene exposes `OVER_MIX_CONTROL["mix"]`: zero shows the base video, one shows the over video.

Watercolor opacity is carried by object alpha and read through `OBJECT_ALPHA` in each material. The material uses Blender 5.0's Principled BSDF surface with the atlas connected to Emission Color and a black diffuse Base Color, so a flat 2D painting does not change brightness when the camera rotates across its authored single normal. The mask and object alpha drive Principled Alpha directly. Watercolor cards, transparent Ground padding and grass cutouts use the Dithered render method, avoiding the per-object ordering limitation of Blended materials when one transparent card must reveal another surface behind it. Cards remain double-sided; local UVs are clamped before each atlas remap so a small source UV overshoot cannot sample a neighboring atlas region. Visible watercolor crops use the legacy runtime's `atlas/texture` remap table; the separate `atlas/sdf` table remains attached as reference metadata and is not substituted for the visible atlas.

Editable watercolor topology is cleaned conservatively during generation: imported float noise is flattened onto each card's authored local plane, coincident vertices are merged without collapsing UV seams, near-zero triangles are removed and face winding is normalized. The validator rejects duplicate vertices/faces, non-planar cards, inconsistent normals and extreme sliver triangles.

`PROCEDURAL_GRASS` contains the 23 layers for which the legacy runtime explicitly sets `hasGround: true`. The deterministic Blender mirror contains 3141 editable blade ribbons, the ten source atlas regions, 24 source color-gradient columns, source Poisson-disc spacing and wind/reveal animation channels. `land_back_5`, `background_2` and `viaduc_1` intentionally have no grass because their source configuration disables the ground component. Browser cursor-proximity reveal remains documented as an interaction boundary rather than being visually guessed.

`GROUND_AND_PAPER` is an artist-only collection visible by default in `ARTIST_EDIT`; it contains the converted Ground atlas and is excluded from `WEB_ANIMATION`. No standalone Blender shadow layer is generated: the source WebGL shadow is a runtime rendering effect, not a set of upright image cards. Its extracted timing remains available as source metadata, while the actual shader effect is deferred until it can be rebuilt accurately. Watercolor and grass use smooth blended transparency; watercolor masks clip dark atlas padding and the converted Ground atlas hides its black KTX2 padding by luminance.

The build and validation scripts never change or save Blender user preferences. Blender's built-in interface language therefore follows the user's existing installation settings. The generated project explicitly names its saved workspaces in Chinese so they match the Chinese startup UI; asset, object, material and script identifiers remain portable ASCII English. `--factory-startup` in the background commands isolates automated generation only and does not save factory preferences over the user's configuration.

## Version preparation

The current complete file remains the only source of truth. Future versions use independent files under `versions/<version-id>/blender/`, with their own reports and generated outputs. The planned future workbench root is `blender/_scenebench/`, but this directory is not created or migrated by the current preparation step.

Preview a registered version without writing anything:

```powershell
python blender_scenebench/tools/prepare_blend_version.py --version-id no-animation --dry-run
```

Creating a derivative requires an explicit `--create`; the tool opens the source and saves a separate target while rebasing portable asset paths. It does not remove animation or apply any artistic transformation.

Read [`reports/rendering-boundaries.md`](reports/rendering-boundaries.md) before changing materials. It distinguishes exact source data from renderer-specific approximations.

## Rebuild

Run from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File blender_scenebench/tools/prepare_support_assets.ps1
python blender_scenebench/tools/generate_manifests.py
& 'F:\Blender\blender.exe' --background --factory-startup --python blender_scenebench/tools/build_blender_scene.py
& 'F:\Blender\blender.exe' --background --factory-startup blender_scenebench/blender/Verminoble_Scene_Mirror_5_0.blend --python blender_scenebench/tools/validate_blend.py
```

If the master file was generated before the portable-asset change, repair its paths without rebuilding the scene:

```powershell
& 'F:\Blender\blender.exe' --background --factory-startup --python blender_scenebench/tools/repair_blend_assets.py
```

To regenerate 30 validation renders (seven source animation frames, one artist overview, five artist frames including the reported frame 690, one material preview, four face/oblique/grazing/back material-angle previews, one tree-and-grass preview, one background-card preview, four source-camera frames and six landscape frames):

```powershell
& 'F:\Blender\blender.exe' --background --factory-startup blender_scenebench/blender/Verminoble_Scene_Mirror_5_0.blend --python blender_scenebench/tools/render_validation.py
```

## Isolation and Git policy

- The workbench is outside `src/` and `public/`, so Vite does not serve it.
- `.gitignore` excludes the copied source assets, automatic `.blend1/.blend2` backups, generated conversions and render output.
- Documentation, manifests, scripts, reports and the main `.blend` are tracked.
- Original assets remain local experimental references and are not cleared for public or commercial redistribution.
