import { useProgress } from '@react-three/drei';
import { Canvas } from '@react-three/fiber';
import { Suspense, useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import type { ExperienceDefinition } from '../../../content/definition';
import { onBootComplete } from '../../../app/boot-loader';
import { OriginalExperienceTail } from '../OriginalExperienceTail';
import { SourceSoundControl } from '../SourceSoundControl';
import { useExperienceAudio } from '../runtime/audio';
import { progressWithinSection } from '../runtime/input';
import { detectPerformanceTier } from '../runtime/performance';
import { createInitialRuntimeState, experienceRuntimeReducer } from '../runtime/reducer';
import type { ExperienceRuntimeAction, ExperienceRuntimeActions } from '../runtime/types';
import type { ExperienceRuntimeProps } from '../runtime/contract';
import { LandscapeWorld } from './LandscapeWorld';
import { SourceAssetPipeline } from './SourceAssetPipeline';
import { VideoLandscape } from './VideoLandscape';

function AssetProgressReporter({ dispatch }: { dispatch: React.Dispatch<ExperienceRuntimeAction> }) {
  const { errors, progress } = useProgress();
  useEffect(() => {
    dispatch({ type: 'ASSET_PROGRESS', progress });
  }, [dispatch, progress]);
  useEffect(() => {
    if (errors.length > 0) dispatch({ type: 'FAIL', message: errors[0] });
  }, [dispatch, errors]);
  return null;
}

function RuntimeReady({ dispatch }: { dispatch: React.Dispatch<ExperienceRuntimeAction> }) {
  useEffect(() => {
    dispatch({ type: 'ASSETS_READY' });
  }, [dispatch]);
  return null;
}

function PoemOverlay({ definition, poemId }: { definition: ExperienceDefinition; poemId: 0 | 1 | 2 }) {
  return (
    <div className="r3f-poems" aria-live="polite">
      {definition.copy.poems.map((poem) => (
        <div
          className={`r3f-poem${poem.id === poemId ? ' is-active' : ''}`}
          data-section={poem.id}
          dangerouslySetInnerHTML={{ __html: poem.sourceMarkup }}
          key={poem.id}
        />
      ))}
    </div>
  );
}

function AssetLoader({ definition, progress }: { definition: ExperienceDefinition; progress: number }) {
  return (
    <div className="loader-experience r3f-asset-loader" data-component="LoaderExperience">
      <div className="center-wrapper">
        <div className="middle-w center">
          <svg className="loader-circle" viewBox="0 0 170 170" aria-hidden="true">
            <circle className="static-circle" cx="85" cy="85" fill="none" r="82" stroke="currentColor" />
            <circle
              className="animated-circle"
              cx="85"
              cy="85"
              fill="none"
              r="82"
              stroke="currentColor"
              style={{ strokeDashoffset: 515 - (515 * progress) / 100 }}
            />
          </svg>
          <p className="loading-text center">{definition.copy.loading}</p>
        </div>
        <p className="enter-description center is-visible">{definition.copy.intro}</p>
      </div>
    </div>
  );
}

export function R3FExperienceRuntime({ definition }: ExperienceRuntimeProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const soundTriggeredRef = useRef(false);
  const [soundVisible, setSoundVisible] = useState(false);
  const [state, dispatch] = useReducer(
    experienceRuntimeReducer,
    undefined,
    () => createInitialRuntimeState(detectPerformanceTier()),
  );
  const device = useMemo(
    () => window.matchMedia('(max-width: 767px)').matches ? 'mobile' as const : 'desktop' as const,
    [],
  );
  const activeScene = definition.scenes[state.activeScene - 1];
  const landscapeScene = state.landscapeScene
    ? definition.scenes[state.landscapeScene - 1]
    : null;
  const audio = useExperienceAudio(definition.sounds, state.muted, landscapeScene !== null);

  const unmuteFromGesture = useCallback(() => {
    if (soundTriggeredRef.current) return;
    soundTriggeredRef.current = true;
    audio.unmuteFromGesture();
    dispatch({ type: 'SET_MUTED', muted: false });
  }, [audio]);

  useEffect(() => onBootComplete(() => dispatch({ type: 'BOOT_COMPLETE' })), []);

  useEffect(() => {
    if (state.phase !== 'loading' || !state.assetsReady) return;
    const timeout = window.setTimeout(() => dispatch({ type: 'READY' }), 800);
    return () => window.clearTimeout(timeout);
  }, [state.assetsReady, state.phase]);

  useEffect(() => {
    if (state.phase !== 'exploring' && state.phase !== 'landscape' && state.phase !== 'tail') return;
    const timeout = window.setTimeout(() => setSoundVisible(true), 1_500);
    return () => window.clearTimeout(timeout);
  }, [state.phase]);

  useEffect(() => {
    const firstTrigger = () => unmuteFromGesture();
    document.addEventListener('click', firstTrigger, { once: true });
    return () => document.removeEventListener('click', firstTrigger);
  }, [unmuteFromGesture]);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const section = sectionRef.current;
      if (!section) return;
      const rect = section.getBoundingClientRect();
      const top = window.scrollY + rect.top;
      const progress = progressWithinSection(top, section.offsetHeight, window.innerHeight, window.scrollY);
      dispatch({ type: 'SCROLL_TO', progress });
      if (rect.bottom <= window.innerHeight + 1) dispatch({ type: 'ENTER_TAIL' });
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener('resize', onScroll);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', onScroll);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  const restart: ExperienceRuntimeActions['restart'] = () => {
    dispatch({ type: 'RESTART' });
    sectionRef.current?.scrollIntoView({ behavior: 'auto', block: 'start' });
  };

  const openLandscape = () => {
    audio.playLandscapeFeedback();
    dispatch({ type: 'OPEN_LANDSCAPE', scene: activeScene.id });
  };

  const closeLandscape: ExperienceRuntimeActions['leaveLandscape'] = () => {
    audio.playBackFeedback();
    dispatch({ type: 'CLOSE_LANDSCAPE' });
  };

  const toggleSound = () => {
    if (state.muted) audio.unmuteFromGesture();
    soundTriggeredRef.current = true;
    dispatch({ type: 'TOGGLE_SOUND' });
  };

  return (
    <main className="r3f-experience-shell" data-phase={state.phase} data-runtime="r3f">
      <section className="r3f-experience" ref={sectionRef}>
        <div className="r3f-stage">
          <Canvas
            dpr={state.performanceTier === 'low' ? 1 : [1, 1.5]}
            flat
            gl={{ alpha: false, antialias: state.performanceTier !== 'low' }}
          >
            <color args={['#e7e7e2']} attach="background" />
            <Suspense fallback={null}>
              <SourceAssetPipeline definition={definition} />
              <LandscapeWorld definition={definition} progress={state.scrollProgress} />
              <RuntimeReady dispatch={dispatch} />
            </Suspense>
          </Canvas>
          <AssetProgressReporter dispatch={dispatch} />
          <PoemOverlay definition={definition} poemId={state.activePoem} />
          <button className="r3f-scroll-hint" type="button"><span>{definition.copy.scrollHint}</span></button>
          <button className="r3f-scene-cta" onClick={openLandscape} type="button">
            <span aria-hidden="true">•</span> {definition.copy.landscapeCta}
          </button>
          <p className="r3f-scene-title" aria-hidden="true">{activeScene.title}</p>
        </div>
      </section>

      <SourceSoundControl
        hidden={!soundVisible}
        muted={state.muted}
        onClick={toggleSound}
        soundOffLabel={definition.copy.soundOff}
        soundOnLabel={definition.copy.soundOn}
      />

      <OriginalExperienceTail onRestart={restart} runtime="react" />

      {state.phase === 'boot' || state.phase === 'loading'
        ? <AssetLoader definition={definition} progress={state.assetProgress} />
        : null}
      {state.error ? <p className="runtime-error">{state.error}</p> : null}
      {landscapeScene ? (
        <VideoLandscape
          backLabel={definition.copy.back}
          device={device}
          onBack={closeLandscape}
          scene={landscapeScene}
        />
      ) : null}
    </main>
  );
}
