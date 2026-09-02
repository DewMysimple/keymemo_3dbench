import { useKTX2, useTexture } from '@react-three/drei';
import { useLoader } from '@react-three/fiber';
import { useEffect } from 'react';
import { LUT3dlLoader } from 'three/addons/loaders/LUT3dlLoader.js';
import type { ExperienceDefinition } from '../../../content/definition';

class SourceCompatibleLUT3dlLoader extends LUT3dlLoader {
  override parse(input: string) {
    const grid = /^[\d ]+$/m.exec(input)?.[0];
    if (!grid) return super.parse(input);
    const points = grid.trim().split(/\s+/).map(Number);
    const step = points[1] - points[0];
    const isUniform = points.every((point, index) => index === 0 || point - points[index - 1] === step);
    if (isUniform) return super.parse(input);

    // Photoshop's 8-point export alternates 146/147 after rounding. The
    // Three loader only uses this line to derive the cube size, but requires
    // an exactly uniform integer sequence before it accepts the data rows.
    const normalizedGrid = points.map((_, index) => index * step).join(' ');
    return super.parse(input.replace(grid, normalizedGrid));
  }
}

/**
 * Loads the source pipeline assets through Three's shared loading manager.
 * The current R3F renderer does not apply every shader input yet; keeping the
 * assets in the real loading graph makes the second source loader truthful and
 * exposes missing KTX2/LUT files before the legacy removal gate is considered.
 */
export function SourceAssetPipeline({ definition }: { definition: ExperienceDefinition }) {
  const { world } = definition;
  const textures = useTexture([
    world.atlasSdf,
    world.grassAtlas,
    world.grassGradients,
    world.grassTexture,
    world.leavesTexture,
    world.noiseTexture,
    world.greyscaleNoise,
    world.rgbNoise,
    world.compressedRgbNoise,
    world.rgbaNoise,
    world.paperTexture,
    world.paperNormal,
    world.paperMatcap,
    world.poemTexture,
    world.msdfFontAtlas,
  ]);
  const groundAtlas = useKTX2(world.groundAtlas, world.basisTranscoderPath);
  const luts = useLoader(SourceCompatibleLUT3dlLoader, [world.dryLut, world.inkLut]);

  useEffect(() => {
    groundAtlas.needsUpdate = true;
    textures.forEach((texture) => {
      texture.needsUpdate = true;
    });
    luts.forEach(({ texture3D }) => {
      texture3D.needsUpdate = true;
    });
  }, [groundAtlas, luts, textures]);

  return null;
}
