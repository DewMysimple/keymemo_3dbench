import { experienceCopy } from './experience';
import { fontAssets, sceneManifest, soundManifest, worldAssets } from './scenes';
import { tailCopy } from './tail';

export interface ExperienceDefinition {
  copy: typeof experienceCopy;
  scenes: typeof sceneManifest;
  sounds: typeof soundManifest;
  fonts: typeof fontAssets;
  world: typeof worldAssets;
  tail: typeof tailCopy;
}

export const experienceDefinition: ExperienceDefinition = {
  copy: experienceCopy,
  scenes: sceneManifest,
  sounds: soundManifest,
  fonts: fontAssets,
  world: worldAssets,
  tail: tailCopy,
};
