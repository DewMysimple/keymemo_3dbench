import { useAnimations, useGLTF, useTexture } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import {
  DoubleSide,
  Mesh,
  MeshBasicMaterial,
  PerspectiveCamera,
  SRGBColorSpace,
} from 'three';
import type { ExperienceDefinition } from '../../../content/definition';
import {
  watercolorAtlasRemaps,
  watercolorLayerSchedule,
} from '../../../content/atlas';

interface LandscapeWorldProps {
  definition: ExperienceDefinition;
  progress: number;
}

export function LandscapeWorld({ definition, progress }: LandscapeWorldProps) {
  const gltf = useGLTF(definition.world.model);
  const [atlas, mask] = useTexture([definition.world.atlas, definition.world.atlasMask]);
  const world = useMemo(() => gltf.scene.clone(true), [gltf.scene]);
  const { mixer } = useAnimations(gltf.animations, world);
  const set = useThree((state) => state.set);
  const previousCamera = useThree((state) => state.camera);
  const size = useThree((state) => state.size);

  const materials = useMemo(() => {
    atlas.flipY = false;
    atlas.colorSpace = SRGBColorSpace;
    mask.flipY = false;
    const next = new Map<string, MeshBasicMaterial>();
    Object.entries(watercolorAtlasRemaps).forEach(([name, remap]) => {
      const map = atlas.clone();
      const alphaMap = mask.clone();
      map.offset.set(remap.x, remap.y);
      map.repeat.set(remap.width, remap.height);
      alphaMap.offset.set(remap.x, remap.y);
      alphaMap.repeat.set(remap.width, remap.height);
      map.needsUpdate = true;
      alphaMap.needsUpdate = true;
      next.set(name, new MeshBasicMaterial({
        alphaMap,
        alphaTest: 0.015,
        map,
        side: DoubleSide,
        transparent: true,
      }));
    });
    return next;
  }, [atlas, mask]);

  const animatedCamera = useMemo(
    () => world.getObjectByName('Camera_Animation_Baked') as PerspectiveCamera | undefined,
    [world],
  );

  useEffect(() => {
    world.traverse((object) => {
      if (!(object instanceof Mesh)) return;
      if (object.name === 'Ground') {
        object.visible = false;
        return;
      }
      const material = materials.get(object.name);
      if (material) object.material = material;
    });
    return () => materials.forEach((material) => {
      material.map?.dispose();
      material.alphaMap?.dispose();
      material.dispose();
    });
  }, [materials, world]);

  useEffect(() => {
    if (!animatedCamera) return;
    animatedCamera.aspect = size.width / Math.max(1, size.height);
    animatedCamera.updateProjectionMatrix();
    set({ camera: animatedCamera });
    return () => set({ camera: previousCamera });
  }, [animatedCamera, previousCamera, set, size.height, size.width]);

  useFrame(() => {
    const time = progress * definition.world.cameraAnimationDuration;
    mixer.setTime(time);
    Object.entries(watercolorLayerSchedule).forEach(([name, start]) => {
      const object = world.getObjectByName(name) as Mesh | undefined;
      const material = materials.get(name);
      if (!object || !material) return;
      const reveal = start === 0 ? 1 : Math.min(1, Math.max(0, (time - start) / 1.25));
      object.visible = reveal > 0;
      material.opacity = reveal;
    });
    if (animatedCamera) {
      animatedCamera.aspect = size.width / Math.max(1, size.height);
      animatedCamera.updateProjectionMatrix();
    }
  });

  return <primitive object={world} />;
}

useGLTF.preload('/wp-content/themes/davidwhyte/resources/assets/xp/models/scene.glb');
