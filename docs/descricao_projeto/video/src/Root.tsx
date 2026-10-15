import React from 'react';
import {Audio, Composition, Sequence, interpolate, staticFile} from 'remotion';
import longJson from './data/timeline.json';
import shortJson from './data/timeline_linkedin.json';
import {SceneFrame} from './components/SceneFrame';
import type {Timeline} from './types';
import {Brag, BRAG_FRAMES} from './brag/Brag';

const Video: React.FC<{timeline: Timeline}> = ({timeline}) => {
  let from = 0;
  const T = timeline.totalFrames;
  return (
    <>
      {timeline.music && (
        // trilha de fundo: fade-in 1 s, fade-out 3 s
        <Audio src={staticFile(timeline.music)} volume={(f) => interpolate(f, [0, 30, T - 90, T], [0, 0.55, 0.55, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />
      )}
      {timeline.scenes.map((s, i) => {
        const start = from;
        from += s.durationInFrames;
        return (
          <Sequence key={s.id} from={start} durationInFrames={s.durationInFrames} name={`${s.id} ${s.title}`}>
            <SceneFrame scene={s} timeline={timeline} sceneNumber={i + 1} startFrame={start} />
          </Sequence>
        );
      })}
    </>
  );
};

const comp = (id: string, json: unknown) => {
  const timeline = json as Timeline;
  return <Composition id={id} component={Video} defaultProps={{timeline}} durationInFrames={Math.max(1, timeline.totalFrames)} fps={timeline.fps} width={1920} height={1080} />;
};

// Vídeo completo (~132 min) e corte de ~3 min para LinkedIn
export const Root: React.FC = () => (
  <>
    {comp('RpgIaExplicado', longJson)}
    {comp('RpgIaLinkedIn', shortJson)}
    <Composition id="Brag" component={Brag} durationInFrames={BRAG_FRAMES} fps={30} width={1920} height={1080} />
  </>
);
