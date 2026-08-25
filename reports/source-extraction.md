# Source snapshot extraction report

- Snapshot files: 87
- Snapshot bytes: 78773545
- XP asset files: 53
- GLB meshes: 27
- GLB nodes: 37
- Camera animation samples: 3587
- Camera animation duration: 59.766666666666666 seconds
- Reference directory was read only: `C:\Users\Administrator\Desktop\网页(1)\wp-content\themes\davidwhyte\resources\assets\xp`

## Current snapshot versus read-only reference

| Path | Difference |
| --- | --- |
| `libs/basis/basis_transcoder.js` | newline-only |
| `lut/dry.3DL` | newline-only |
| `lut/ink.3DL` | newline-only |
| `msdf/CanelaText-Light/CanelaText-Light.json` | newline-only |

`newline-only` means decoded UTF-8 content is equal after CRLF/LF normalization. The Blender build always uses the current project snapshot copied into this isolated workbench.

## Legacy watercolor runtime extraction

- The minified runtime contains 26 ordered watercolor layer configurations, including start time, ground texture, ground color, edge width, depth and `hasGround` state.
- The visible atlas is the compact table bound by the runtime to `atlas/texture`; the metadata-rich table is bound to `atlas/sdf`. Keeping these roles separate fixes the previous black or incorrectly cropped Blender materials.
- Exactly 23 of the 26 layers enable a procedural ground component. The disabled source layers are: `land_back_5`, `background_2`, `viaduc_1`.
- Grass source parameters were extracted from the runtime: Poisson-disc spacing 1.8–2.8 with seven tries, 7–24 clustered blades per seed, ten blade-atlas regions, eight gradient groups with three columns each, eight vertical segments, global scale 5, wind displacement 3000, intensity 3 and speed 0.5.
- The Blender generator uses a fixed local seed for reproducibility while retaining the source algorithm and resources. Browser cursor reveal and an uncaptured `Math.random()` outcome cannot be mirrored exactly without recording a specific browser session.

The read-only reference directory was inspected but not written. All extraction and Blender generation use files copied into `blender_scenebench/source_snapshot/`.
