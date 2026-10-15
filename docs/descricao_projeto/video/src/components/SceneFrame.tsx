import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, interpolate} from 'remotion';
import {appear} from '../anim';
import {C, FONT_BODY, FONT_TITLE, STAGE} from '../theme';
import type {Scene, Timeline} from '../types';
import {VisualView} from './Visuals';

export const AUDIO_LEAD = 12; // frames de respiro antes da fala

/** Quebra a narração em legendas curtas (≤ ~115 chars), respeitando frases. */
const chunk = (text: string, max = 115) => {
  const sentences = text.replace(/\s+/g, ' ').trim().split(/(?<=[.!?;:])\s+/);
  const out: string[] = [];
  for (const s of sentences) {
    if (s.length <= max) {
      out.push(s);
      continue;
    }
    let cur = '';
    for (const w of s.split(' ')) {
      if ((cur + ' ' + w).trim().length > max - 10 && cur) {
        out.push(cur.trim());
        cur = w;
      } else cur += ' ' + w;
    }
    if (cur.trim()) out.push(cur.trim());
  }
  return out;
};

const Captions: React.FC<{text: string; audioFrames: number; silent?: boolean; color: string}> = ({text, audioFrames, silent, color}) => {
  const f = useCurrentFrame() - AUDIO_LEAD;
  const parts = chunk(text, silent ? 92 : 115);
  const total = parts.reduce((a, p) => a + p.length + 8, 0);
  let acc = 0;
  let idx = parts.length - 1;
  for (let i = 0; i < parts.length; i++) {
    const end = ((acc + parts[i].length + 8) / total) * audioFrames;
    if (f < end) {
      idx = i;
      break;
    }
    acc += parts[i].length + 8;
  }
  const startOf = parts.slice(0, idx).reduce((a, q) => a + q.length + 8, 0); // início do trecho atual
  if (f < 0 || (!silent && f > audioFrames + 20)) return null;
  if (silent) {
    // legenda como texto principal: maior, com acento da cor do capítulo e marcador de progresso
    const local = f - (startOf / total) * audioFrames;
    const p = Math.min(1, Math.max(0, local / 8));
    return (
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 46, display: 'flex', justifyContent: 'center'}}>
        <div style={{maxWidth: 1640, display: 'flex', gap: 22, alignItems: 'stretch', background: 'rgba(8,6,10,0.82)', padding: '18px 34px 18px 22px', borderRadius: 14, border: `1px solid ${color}55`, boxShadow: '0 10px 40px rgba(0,0,0,0.5)'}}>
          <div style={{width: 6, borderRadius: 3, background: color, boxShadow: `0 0 14px ${color}`}} />
          <div style={{display: 'flex', flexDirection: 'column', gap: 10}}>
            <div style={{fontFamily: FONT_BODY, fontWeight: 600, fontSize: 42, lineHeight: 1.32, color: '#fff7e8', opacity: p, transform: `translateY(${(1 - p) * 8}px)`}}>{parts[idx]}</div>
            {parts.length > 1 && (
              <div style={{display: 'flex', gap: 6}}>
                {parts.map((_, i) => <span key={i} style={{width: 26, height: 4, borderRadius: 2, background: i <= idx ? color : 'rgba(255,255,255,0.15)'}} />)}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 58, display: 'flex', justifyContent: 'center'}}>
      <div style={{maxWidth: 1560, textAlign: 'center', fontFamily: FONT_BODY, fontWeight: 500, fontSize: 34, lineHeight: 1.4, color: '#fff7e8', background: 'rgba(8,6,10,0.72)', padding: '12px 30px', borderRadius: 12, border: '1px solid rgba(232,200,140,0.12)'}}>
        {parts[idx]}
      </div>
    </div>
  );
};

export const SceneFrame: React.FC<{scene: Scene; timeline: Timeline; sceneNumber: number; startFrame: number}> = ({scene, timeline, sceneNumber, startFrame}) => {
  const f = useCurrentFrame();
  const color = scene.color;
  const fadeIn = appear(f, 0, 10);
  const fadeOut = interpolate(f, [scene.durationInFrames - 10, scene.durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const progress = (startFrame + f) / timeline.totalFrames;
  const drift = Math.sin((startFrame + f) / 240) * 40;

  return (
    <AbsoluteFill style={{background: C.bg0, overflow: 'hidden'}}>
      {/* fundo: brilho da cor do capítulo + vinheta */}
      <AbsoluteFill style={{background: `radial-gradient(circle at ${30 + drift / 10}% ${20 + drift / 20}%, ${color}22, transparent 55%), radial-gradient(circle at 85% 90%, ${color}14, transparent 50%), linear-gradient(180deg, ${C.bg1}, ${C.bg0})`}} />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.6) 100%)'}} />
      <AbsoluteFill style={{backgroundImage: 'linear-gradient(rgba(232,200,140,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(232,200,140,0.025) 1px, transparent 1px)', backgroundSize: '64px 64px'}} />

      {/* cabeçalho */}
      <div style={{position: 'absolute', top: 44, left: STAGE.x, right: STAGE.x, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontFamily: FONT_BODY, fontSize: 22, color: C.muted, letterSpacing: 1.5, textTransform: 'uppercase'}}>
        <span style={{display: 'flex', alignItems: 'center', gap: 14}}>
          <span style={{fontFamily: FONT_TITLE, color, fontWeight: 700}}>Capítulo {scene.chapterIndex + 1}</span>
          <span style={{color: C.dim}}>·</span>
          <span>{scene.chapterTitle}</span>
        </span>
        <span style={{fontFamily: FONT_TITLE, color: C.dim}}>rpg-ia-master · {sceneNumber}/{timeline.scenes.length}</span>
      </div>

      <div style={{position: 'absolute', left: STAGE.x, top: STAGE.y, width: STAGE.w, height: STAGE.h, opacity: fadeIn * fadeOut}}>
        <VisualView v={scene.visual} color={color} audioFrames={scene.audioFrames} />
      </div>

      <Captions text={scene.narration} audioFrames={scene.audioFrames} silent={timeline.silent} color={color} />

      {/* barra de progresso por capítulo */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 8, display: 'flex', gap: 3, background: 'rgba(0,0,0,0.5)'}}>
        {timeline.chapters.map((ch, i) => {
          const local = Math.min(1, Math.max(0, (progress * timeline.totalFrames - ch.startFrame) / ch.frames));
          return (
            <div key={i} style={{flex: ch.frames, background: 'rgba(255,255,255,0.07)', position: 'relative'}}>
              <div style={{position: 'absolute', inset: 0, width: `${local * 100}%`, background: ch.color}} />
            </div>
          );
        })}
      </div>

      {!timeline.silent && (<Sequence from={AUDIO_LEAD} layout="none">
        <Audio src={staticFile(`audio/${scene.id}.wav`)} />
      </Sequence>)}
    </AbsoluteFill>
  );
};
