import { Canvas, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useState } from 'react';
import { LinearFilter, SRGBColorSpace, VideoTexture } from 'three';
import type { SceneAssetManifest } from '../../../content/scenes';

function useVideoTexture(source: string) {
  const video = useMemo(() => {
    const element = document.createElement('video');
    element.src = source;
    element.crossOrigin = 'anonymous';
    element.loop = true;
    element.muted = true;
    element.playsInline = true;
    element.preload = 'auto';
    return element;
  }, [source]);
  const texture = useMemo(() => {
    const next = new VideoTexture(video);
    next.colorSpace = SRGBColorSpace;
    next.minFilter = LinearFilter;
    next.magFilter = LinearFilter;
    return next;
  }, [video]);

  useEffect(() => {
    void video.play().catch(() => undefined);
    return () => {
      video.pause();
      video.removeAttribute('src');
      video.load();
      texture.dispose();
    };
  }, [texture, video]);

  return texture;
}

function FullscreenVideoPlane({ base, over, overOpacity }: { base: string; over: string; overOpacity: number }) {
  const baseTexture = useVideoTexture(base);
  const overTexture = useVideoTexture(over);
  const viewport = useThree((state) => state.viewport);

  return (
    <>
      <mesh scale={[viewport.width, viewport.height, 1]}>
        <planeGeometry args={[1, 1]} />
        <meshBasicMaterial map={baseTexture} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0, 0.01]} scale={[viewport.width, viewport.height, 1]}>
        <planeGeometry args={[1, 1]} />
        <meshBasicMaterial map={overTexture} opacity={overOpacity} toneMapped={false} transparent />
      </mesh>
    </>
  );
}

interface VideoLandscapeProps {
  backLabel: string;
  device: 'desktop' | 'mobile';
  onBack: () => void;
  scene: SceneAssetManifest;
}

export function VideoLandscape({ backLabel, device, onBack, scene }: VideoLandscapeProps) {
  const [overOpacity, setOverOpacity] = useState(0);
  const video = scene.videos[device];

  return (
    <div
      className="r3f-landscape"
      data-scene={scene.id}
      onPointerMove={(event) => setOverOpacity(Math.min(1, Math.max(0, event.clientX / window.innerWidth)))}
    >
      <Canvas flat orthographic camera={{ position: [0, 0, 2], zoom: 1 }}>
        <FullscreenVideoPlane base={video.base} over={video.over} overOpacity={overOpacity} />
      </Canvas>
      <button className="r3f-back" onClick={onBack} type="button"><span>{backLabel}</span></button>
    </div>
  );
}
