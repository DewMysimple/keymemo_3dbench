# Blender mirror rendering boundaries

## What is mirrored exactly

- The byte-identical current runtime asset snapshot.
- The GLB hierarchy, 27 mesh objects, six title/hotspot nodes and source transforms.
- The imported perspective camera and baked `Camera_Action_Baked` animation, plus a directly usable `WEB_CAMERA_EDITABLE` copy sampled at all 3587 source frames.
- The 60 FPS timeline, 3587 source samples and 59.7666666667-second duration.
- The 26 watercolor layer names, atlas rectangles, SDF rectangles and reveal schedule.
- Six desktop and six mobile base/over video pairs, including their original resolution and duration.
- Source paper, noise, grass, LUT, MSDF, font and audio inputs.

## Editable Blender reconstruction

- Every watercolor layer has its own mesh and material.
- `ARTIST_EDIT` and `WEB_ANIMATION` link the same editable collection; the source GLB mirror lives only in the locked `SOURCE_REFERENCE` scene and cannot create viewport overlap.
- Atlas and mask transforms are extracted from the legacy `app.js`; no rectangle is inferred from screenshots. The runtime binds its compact remap table to visible `atlas/texture` and its metadata-rich table to `atlas/sdf`, so the Blender material preserves that semantic distinction even though the original table names are opaque after minification.
- Parent-space GLB transforms are evaluated before duplication, so all 26 editable layers retain the source world transforms after being detached for editing.
- WebGL's top-origin atlas rectangles are converted to Blender's bottom-origin image coordinates; the crops and orientation remain source-derived.
- Reveal timing is driven from the extracted schedule at 60 FPS: alpha 0.01 s, paper curvature 10 s, entry rotation 7 s, ink progress 15 s and cutout/ground opacity 0.4 s. The source shadow timing remains metadata only until its renderer effect is rebuilt. Layers sharing a start time keep the source 0.3 s stagger.
- The source vertex-shader paper bend is preserved as the driven `WEB_SOURCE_CURVE` shape key. The runtime properties remain exposed on each `EDIT_*` object for later art direction.
- The imported `land_back_5` contains one zero-area triangle. Only that invalid face is removed from the editable copy; all remaining faces stay triangulated and validation rejects N-Gons or further zero-area faces.
- Reveal opacity is mirrored onto object alpha and consumed by the material's `OBJECT_ALPHA` node. This keeps material previews opaque outside object context without changing animation renders.
- The legacy runtime creates grass procedurally rather than storing it in the GLB. Blender mirrors the 23 source-enabled ground layers with deterministic Poisson-disc clusters, 3141 editable triangle-ribbon blades, ten source blade atlas regions, 24 color-gradient columns, and wind/reveal channels. Layers with `hasGround: false` remain grass-free.
- `ARTIST_EDIT` enables the converted Ground atlas. No `SHADOW_*` cards are generated: the source WebGL shadow is a runtime rendering effect and is deferred until its SDF, screen-space shadow map, noise and custom GLSL behavior can be rebuilt accurately.
- The extracted `web_shadow_alpha` timing remains attached to watercolor runtime metadata for future shader work, but it has no Blender-visible shadow consumer in the current master file.
- Ground KTX2 is losslessly transcoded to an RGBA8 PNG for Blender while the KTX2 remains preserved.
- The converted Ground image retains black atlas padding from the KTX2 extraction. `WC_Ground_Atlas` derives a luminance alpha mask to hide that padding, while the ARTIST_EDIT world and viewport use a warm paper-gray background instead of black.
- Landscape `OVER_VIDEO` opacity is controlled by `OVER_MIX_CONTROL["mix"]`; it defaults to zero and no unverified transition timing is added.
- Canela WOFF is converted to a local TTF only for editable title annotations. Runtime MSDF title geometry remains the authoritative source.

## Deliberately not claimed as pixel-identical

- The legacy runtime uses custom WebGL GLSL, SDF watercolor edges, paper composition and LUT post-processing that do not have a one-to-one EEVEE/Cycles implementation.
- The runtime generates ink reveal points with `Math.random()` at load time. Blender preserves the reveal duration and source parameters, but a deterministic `.blend` cannot claim the same random ink field unless a particular browser run is captured first.
- Grass placement in the browser also uses `Math.random()` and reacts to cursor proximity. Blender uses a recorded deterministic seed so the workbench can be rebuilt exactly; it mirrors the source generator and authored resource mapping, not the random outcome of an uncaptured browser session.
- SDF, paper, noise and LUT inputs are preserved and labeled in the Blender file, but no visually guessed substitute is wired into the final shader.
- The GLB `Ground` mesh is preserved in `GROUND_AND_PAPER` and enabled only in `ARTIST_EDIT` through a converted atlas material. The source runtime hides the GLB object and rebuilds Ground through a custom shader, so the Blender version remains an editable approximation.
- Blender title objects are non-rendering annotations because the website uses MSDF canvas text rather than ordinary 3D text.
- Browser DOM, FAQ, subscription text and other page-tail UI are outside the three-dimensional workbench.

The browser legacy runtime remains the final pixel reference. The Blender file is a source-faithful, editable scene reconstruction and asset mirror, not a claim that two different renderers produce identical pixels.
