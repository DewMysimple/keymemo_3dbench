export type DeviceKind = 'desktop' | 'mobile';
export type VideoLayer = 'base' | 'over';
export type SceneId = 1 | 2 | 3 | 4 | 5 | 6;

export interface SceneAssetManifest {
  id: SceneId;
  label: string;
  title: string;
  focusProgress: number;
  videos: Record<DeviceKind, Record<VideoLayer, string>>;
}

const assetRoot = '/wp-content/themes/davidwhyte/resources/assets/xp';
const sceneTitles = [
  'Dales with Cows',
  'Nidderdale Farm',
  'North York Moors',
  'Dales near Aysgarth',
  'Dales with Sheep',
  'Ribblehead Viaduct',
] as const;
const sceneFocusProgress = [0.02, 0.14, 0.26, 0.34, 0.55, 0.66] as const;

function createScene(id: SceneId): SceneAssetManifest {
  return {
    id,
    label: `场景 ${id}`,
    title: sceneTitles[id - 1],
    focusProgress: sceneFocusProgress[id - 1],
    videos: {
      desktop: {
        base: `${assetRoot}/videos/desktop/base/${id}.mp4`,
        over: `${assetRoot}/videos/desktop/over/${id}.mp4`
      },
      mobile: {
        base: `${assetRoot}/videos/mobile/base/${id}.mp4`,
        over: `${assetRoot}/videos/mobile/over/${id}.mp4`
      }
    }
  };
}

export const sceneManifest = [
  createScene(1),
  createScene(2),
  createScene(3),
  createScene(4),
  createScene(5),
  createScene(6)
] as const satisfies readonly SceneAssetManifest[];

export const soundManifest = [
  `${assetRoot}/sounds/loop-main.mp3`,
  `${assetRoot}/sounds/loop-poem.mp3`,
  `${assetRoot}/sounds/loop-painting.mp3`,
  `${assetRoot}/sounds/over-cta-back.mp3`,
  `${assetRoot}/sounds/over-cta-painting.mp3`
] as const;

export const fontAssets = {
  canelaThin: '/wp-content/themes/davidwhyte/resources/assets/fonts/CanelaText-Thin.woff2',
  roobertRegular: '/wp-content/themes/davidwhyte/resources/assets/fonts/Roobert-Regular.woff2',
} as const;

export const worldAssets = {
  model: `${assetRoot}/models/scene.glb`,
  atlas: `${assetRoot}/textures/atlas/texture.jpg`,
  atlasMask: `${assetRoot}/textures/atlas/texture_mask.jpg`,
  atlasSdf: `${assetRoot}/textures/atlas/sdf.png`,
  groundAtlas: `${assetRoot}/textures/grounds/atlas.ktx2`,
  grassAtlas: `${assetRoot}/textures/grass/atlas.png`,
  grassGradients: `${assetRoot}/textures/grass/color-gradients.jpg`,
  grassTexture: `${assetRoot}/textures/grassTest.png`,
  leavesTexture: `${assetRoot}/textures/leaves.png`,
  noiseTexture: `${assetRoot}/textures/noise.jpeg`,
  greyscaleNoise: `${assetRoot}/textures/noises/greyscale-fractal.png`,
  rgbNoise: `${assetRoot}/textures/noises/rgb-fractal.png`,
  compressedRgbNoise: `${assetRoot}/textures/noises/rgb-generated-compressed.png`,
  rgbaNoise: `${assetRoot}/textures/noises/rgba-pixel.png`,
  paperTexture: `${assetRoot}/textures/paper/texture.jpg`,
  paperNormal: `${assetRoot}/textures/paper/normal.jpg`,
  paperMatcap: `${assetRoot}/textures/paper/matcap.png`,
  dryLut: `${assetRoot}/lut/dry.3DL`,
  inkLut: `${assetRoot}/lut/ink.3DL`,
  poemTexture: `${assetRoot}/poem/text.png`,
  msdfFontData: `${assetRoot}/msdf/CanelaText-Light/CanelaText-Light.json`,
  msdfFontAtlas: `${assetRoot}/msdf/CanelaText-Light/CanelaText-Light.png`,
  basisTranscoderPath: `${assetRoot}/libs/basis/`,
  basisTranscoderScript: `${assetRoot}/libs/basis/basis_transcoder.js`,
  basisTranscoderWasm: `${assetRoot}/libs/basis/basis_transcoder.wasm`,
  cameraAnimationDuration: 59.766666666666666,
} as const;
