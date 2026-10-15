/**
 * /brag — vídeo promocional do rpg-ia-master (25 s, sem narração).
 * Identidade copiada de web/src/styles.css: ardósia fria + pergaminho + bronze; Cinzel + EB Garamond.
 * Todo quadro é função pura do tempo (frame).
 */
import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame, random} from 'remotion';
import {createContext, useContext} from 'react';
import {loadFont as loadCinzel} from '@remotion/google-fonts/Cinzel';
import {loadFont as loadGaramond} from '@remotion/google-fonts/EBGaramond';

const CINZEL = loadCinzel('normal', {weights: ['400', '600', '700'], subsets: ['latin', 'latin-ext']}).fontFamily;
const GARAMOND = loadGaramond('normal', {weights: ['400', '500', '600'], subsets: ['latin', 'latin-ext']}).fontFamily;
const GARAMOND_IT = loadGaramond('italic', {weights: ['400'], subsets: ['latin', 'latin-ext']}).fontFamily;

// tokens do app (oklch → sRGB aproximado)
const BG = '#0a0d11';
const INK = '#ece3d1';
const MUTED = '#c3b69f';
const BRONZE = '#c9a25e';
const BRONZE_STRONG = '#b5864a';
const BLOOD = '#c0392f';
const SURFACE = '#2a2215';

const E = Easing.bezier(0.16, 1, 0.3, 1); // --ease do app
const ramp = (f: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(f, [a, b], [from, to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: E});

// Ritmo de leitura: cada cena tem duração própria (dur) e um fator k que desacelera suas animações.
const PLAN = [
  ['hook', 150, 1.4],
  ['dice', 150, 1.4],
  ['reveal', 180, 1.4],
  ['create', 220, 1.6],
  ['play', 280, 1.8],
  ['combat', 190, 1.5],
  ['outro', 170, 1.4],
] as const;
type Key = (typeof PLAN)[number][0];
const S = {} as Record<Key, [number, number]>;
const K = {} as Record<Key, number>;
let acc = 0;
for (const [k, dur, slow] of PLAN) { S[k] = [acc, acc + dur]; K[k] = slow; acc += dur; }
export const BRAG_FRAMES = acc;

const TimeScale = createContext(1);
/** Quadro "lento" da cena: desacelera entradas, digitação e rolagens sem mexer no mergulho de transição. */
const useF = () => useCurrentFrame() / useContext(TimeScale);

/** Mergulho no escuro: cada cena entra e sai do preto, sem crossfade sujo. */
const Dip: React.FC<{dur: number; children: React.ReactNode; inF?: number; outF?: number}> = ({dur, children, inF = 9, outF = 9}) => {
  const f = useCurrentFrame();
  const o = Math.min(ramp(f, 0, inF), 1 - ramp(f, dur - outF, dur));
  return <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>;
};

/** Brasas subindo — determinísticas por semente. */
const Embers: React.FC<{n?: number; color?: string}> = ({n = 38, color = '#e8a15a'}) => {
  const f = useF();
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {Array.from({length: n}).map((_, i) => {
        const x = random(`x${i}`) * 1920;
        const speed = 0.6 + random(`s${i}`) * 1.4;
        const y = 1120 - ((f * speed * 2.2 + random(`o${i}`) * 1200) % 1240);
        const sway = Math.sin((f + i * 30) / 26) * 14;
        const size = 2 + random(`z${i}`) * 3.5;
        const life = 0.25 + 0.6 * Math.abs(Math.sin((f + i * 17) / 40));
        return <div key={i} style={{position: 'absolute', left: x + sway, top: y, width: size, height: size, borderRadius: 99, background: color, opacity: life * 0.7, boxShadow: `0 0 ${size * 4}px ${color}`}} />;
      })}
    </AbsoluteFill>
  );
};

const Vignette: React.FC<{strength?: number}> = ({strength = 0.85}) => (
  <AbsoluteFill style={{background: `radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,${strength}) 100%)`, pointerEvents: 'none'}} />
);

/** Linha de texto que entra de baixo com desfoque e assenta. */
const Line: React.FC<{at: number; children: React.ReactNode; style?: React.CSSProperties}> = ({at, children, style}) => {
  const f = useF();
  const p = ramp(f, at, at + 16);
  return <div style={{opacity: p, transform: `translateY(${(1 - p) * 26}px)`, filter: `blur(${(1 - p) * 8}px)`, ...style}}>{children}</div>;
};

const Ornament: React.FC<{w: number; at: number}> = ({w, at}) => {
  const f = useF();
  const p = ramp(f, at, at + 20);
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 14, justifyContent: 'center', opacity: p}}>
      <span style={{height: 1, width: (w / 2) * p, background: `linear-gradient(90deg, transparent, ${BRONZE})`}} />
      <span style={{width: 9, height: 9, transform: 'rotate(45deg)', border: `1.5px solid ${BRONZE}`}} />
      <span style={{height: 1, width: (w / 2) * p, background: `linear-gradient(270deg, transparent, ${BRONZE})`}} />
    </div>
  );
};

/* ---------------- 1. Gancho ---------------- */
const Hook: React.FC = () => {
  const f = useF();
  const reveal = ramp(f, 0, 40);
  const scale = interpolate(f, [0, 96], [1.12, 1.02]);
  return (
    <AbsoluteFill style={{background: BG}}>
      <div style={{position: 'absolute', right: 20, top: -40, width: 760, height: 1140, transform: `scale(${scale})`, transformOrigin: '60% 40%', opacity: reveal}}>
        <Img src={staticFile('brag/arcanista.webp')} style={{width: '100%', height: '100%', objectFit: 'cover', maskImage: 'radial-gradient(ellipse 60% 65% at 50% 45%, black 40%, transparent 78%)', WebkitMaskImage: 'radial-gradient(ellipse 60% 65% at 50% 45%, black 40%, transparent 78%)'}} />
      </div>
      <Embers n={26} />
      <Vignette />
      <div style={{position: 'absolute', left: 150, top: 380, width: 980}}>
        <Line at={8} style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 82, color: INK, lineHeight: 1.12, letterSpacing: 1}}>E se o mestre do jogo</Line>
        <Line at={20} style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 82, color: BRONZE, lineHeight: 1.12, letterSpacing: 1}}>fosse uma IA…</Line>
      </div>
    </AbsoluteFill>
  );
};

/* ---------------- 2. Dados ---------------- */
const D10: React.FC<{value: number; landAt: number; seed: string; x: number}> = ({value, landAt, seed, x}) => {
  const f = useF();
  const landed = f >= landAt;
  const t = Math.min(1, f / landAt);
  const shown = landed ? value : 1 + Math.floor(random(`${seed}${Math.floor(f / 3)}`) * 10);
  const rot = landed ? 0 : (1 - t) * 720 * (seed === 'a' ? 1 : -1);
  const y = landed ? 0 : -Math.abs(Math.sin(t * Math.PI * 2.5)) * 160 * (1 - t);
  const settle = landed ? Math.sin(Math.min(1, (f - landAt) / 10) * Math.PI) * 6 : 0;
  return (
    <div style={{position: 'absolute', left: x, top: 330, width: 230, height: 250, transform: `translateY(${y - settle}px) rotate(${rot}deg)`}}>
      <svg viewBox="0 0 100 110" width="230" height="250">
        <defs>
          <linearGradient id={`g${seed}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3a2a17" /><stop offset="1" stopColor="#14100a" /></linearGradient>
        </defs>
        <polygon points="50,2 96,40 50,108 4,40" fill={`url(#g${seed})`} stroke={BRONZE} strokeWidth="2" />
        <polyline points="4,40 50,58 96,40" fill="none" stroke={BRONZE} strokeOpacity="0.55" strokeWidth="1.4" />
        <line x1="50" y1="58" x2="50" y2="108" stroke={BRONZE} strokeOpacity="0.4" strokeWidth="1.2" />
      </svg>
      <div style={{position: 'absolute', inset: 0, top: 18, display: 'flex', justifyContent: 'center', alignItems: 'flex-start', paddingTop: 34, fontFamily: CINZEL, fontWeight: 700, fontSize: 64, color: landed ? '#f3d395' : INK, textShadow: landed ? `0 0 24px ${BRONZE}` : 'none'}}>{shown}</div>
    </div>
  );
};

const Dice: React.FC = () => {
  const f = useF();
  const sum = ramp(f, 40, 52);
  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 50% 45%, #1d160d, ${BG} 60%)`}}>
      <D10 value={7} landAt={34} seed="a" x={690} />
      <D10 value={10} landAt={38} seed="b" x={1000} />
      <div style={{position: 'absolute', top: 610, width: '100%', textAlign: 'center', fontFamily: CINZEL, fontSize: 30, letterSpacing: 6, color: MUTED, opacity: sum}}>2d10 = 17</div>
      <div style={{position: 'absolute', top: 720, width: '100%', textAlign: 'center'}}>
        <Line at={30} style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 76, color: INK, letterSpacing: 1}}>…que não pode roubar nos dados?</Line>
      </div>
      <Embers n={14} />
      <Vignette strength={0.7} />
    </AbsoluteFill>
  );
};

/* ---------------- 3. Revelação ---------------- */
const RACES = ['humanos', 'elfos', 'anoes-fuligem', 'vrel', 'cinzeus', 'osshari'];
const Reveal: React.FC = () => {
  const f = useF();
  const drift = interpolate(f, [0, 120], [0, -60]);
  return (
    <AbsoluteFill style={{background: BG}}>
      <div style={{position: 'absolute', top: 70, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 22, transform: `translateX(${drift}px)`}}>
        {RACES.map((r, i) => {
          const p = ramp(f, 4 + i * 5, 26 + i * 5);
          return (
            <div key={r} style={{width: 270, height: 405, borderRadius: 6, overflow: 'hidden', border: `1.5px solid ${BRONZE}88`, boxShadow: '0 30px 60px -30px #000', opacity: p, transform: `translateY(${(1 - p) * 80}px)`}}>
              <Img src={staticFile(`brag/race-${r}.webp`)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            </div>
          );
        })}
      </div>
      <AbsoluteFill style={{background: `linear-gradient(180deg, transparent 30%, ${BG} 58%)`}} />
      <div style={{position: 'absolute', top: 560, width: '100%', textAlign: 'center'}}>
        <Line at={28} style={{fontFamily: CINZEL, fontSize: 26, letterSpacing: 10, color: BRONZE}}>DARK FANTASY · NARRAÇÃO POR IA</Line>
        <Line at={34} style={{fontFamily: CINZEL, fontWeight: 700, fontSize: 118, color: INK, letterSpacing: 4, marginTop: 12, textShadow: `0 0 40px ${BRONZE}44`}}>CRÔNICAS DE VALORIA</Line>
        <div style={{marginTop: 18}}><Ornament w={620} at={44} /></div>
        <Line at={48} style={{fontFamily: GARAMOND_IT, fontSize: 44, color: MUTED, marginTop: 18}}>Um RPG de texto em que a IA é o mestre do jogo.</Line>
      </div>
      <Embers n={20} />
      <Vignette strength={0.6} />
    </AbsoluteFill>
  );
};

/* ---------------- 4. Criação real (wizard + prólogo) ---------------- */
const Caption: React.FC<{at: number; kicker: string; title: string; sub?: string; subAt?: number}> = ({at, kicker, title, sub, subAt}) => (
  <div style={{position: 'absolute', left: 120, top: 330, width: 640}}>
    <Line at={at} style={{fontFamily: CINZEL, fontSize: 24, letterSpacing: 8, color: BRONZE}}>{kicker}</Line>
    <Line at={at + 6} style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 70, color: INK, lineHeight: 1.1, marginTop: 14}}>{title}</Line>
    {sub && <Line at={subAt ?? at + 30} style={{fontFamily: GARAMOND_IT, fontSize: 42, color: MUTED, marginTop: 22, lineHeight: 1.25}}>{sub}</Line>}
  </div>
);

const Crop: React.FC<{src: string; x: number; y: number; w: number; h: number; scale: number; style?: React.CSSProperties}> = ({src, x, y, w, h, scale, style}) => (
  <div style={{position: 'absolute', width: w * scale, height: h * scale, overflow: 'hidden', borderRadius: 8, ...style}}>
    <Img src={staticFile(src)} style={{position: 'absolute', left: -x * scale, top: -y * scale, width: 1920 * scale, height: 1080 * scale}} />
  </div>
);

const Create: React.FC = () => {
  const f = useF();
  const cardIn = ramp(f, 2, 22);
  const push = interpolate(f, [0, 120], [1, 1.06]);
  const proIn = ramp(f, 52, 70);
  const glow = 0.5 + 0.5 * Math.sin(f / 7);
  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 70% 50%, #1b1610, ${BG} 65%)`}}>
      <Caption at={6} kicker="FORJE SUA LENDA" title="Escolha quem você é." sub="A IA escreve o seu prólogo." subAt={56} />
      <div style={{position: 'absolute', left: 860, top: 70, transform: `scale(${push})`, transformOrigin: 'left top'}}>
        <Crop src="brag/vocacao.png" x={566} y={2} w={524} h={860} scale={1.08} style={{opacity: cardIn * (1 - proIn * 0.65), transform: `translateX(${(1 - cardIn) * 60}px)`, boxShadow: `0 0 ${40 * glow}px ${BRONZE}55, 0 40px 80px -30px #000`}} />
      </div>
      <Crop src="brag/prologo.png" x={660} y={146} w={600} h={788} scale={1.12} style={{left: 1080, top: 66, opacity: proIn, transform: `translateX(${(1 - proIn) * 120}px) rotate(${(1 - proIn) * 3}deg)`, boxShadow: `0 50px 100px -30px #000, 0 0 0 1px ${BRONZE}66`}} />
      <Vignette strength={0.55} />
    </AbsoluteFill>
  );
};

/* ---------------- 5. Jogando (tela do app remontada com a tipografia real) ---------------- */
const ACTION = 'Sigo o rastro de sangue até o beco do Anel de Lama';
const NARR = 'Tochas mortas forram o beco. O rastro termina numa porta de ferro marcada com o selo da Mão Sombria — e, atrás dela, alguém prende a respiração.';
const Play: React.FC = () => {
  const f = useF();
  const typed = ACTION.slice(0, Math.floor(ramp(f, 6, 34, 0, ACTION.length)));
  const bubble = ramp(f, 36, 46);
  const thinking = f > 40 && f < 54;
  const narr = NARR.slice(0, Math.floor(interpolate(f, [54, 104], [0, NARR.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})));
  const zoom = interpolate(f, [0, 126], [1, 1.05]);
  return (
    <AbsoluteFill style={{background: BG}}>
      <div style={{position: 'absolute', left: 160, top: 130, width: 1600, height: 900, borderRadius: 10, overflow: 'hidden', border: `1px solid ${BRONZE}55`, background: '#0d1116', transform: `scale(${zoom})`, boxShadow: '0 60px 120px -40px #000'}}>
        {/* topo do app */}
        <div style={{height: 56, display: 'flex', alignItems: 'center', gap: 16, padding: '0 26px', borderBottom: `1px solid ${BRONZE}33`}}>
          <span style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 22, color: BRONZE, letterSpacing: 2}}>ANEL DE LAMA</span>
          <span style={{fontFamily: GARAMOND, fontSize: 18, color: MUTED}}>Dia 1 · Anoitecer · Céu limpo</span>
        </div>
        {/* arte do local (catálogo real) */}
        <div style={{height: 260, position: 'relative', overflow: 'hidden'}}>
          <Img src={staticFile('brag/anel-lama.webp')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 40%', transform: `scale(${1.04 + f / 3000})`}} />
          <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, transparent 55%, #0d1116)'}} />
          <span style={{position: 'absolute', left: 30, bottom: 18, fontFamily: CINZEL, fontSize: 18, letterSpacing: 4, color: INK}}>ANEL DE LAMA</span>
        </div>
        {/* log */}
        <div style={{width: 1080, margin: '34px auto 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26}}>
          <div style={{opacity: bubble, transform: `translateY(${(1 - bubble) * 14}px)`, border: `1px solid ${BRONZE}55`, background: '#14110c', borderRadius: 8, padding: '14px 24px', textAlign: 'center'}}>
            <div style={{fontFamily: CINZEL, fontSize: 15, letterSpacing: 4, color: BRONZE}}>VOCÊ</div>
            <div style={{fontFamily: GARAMOND_IT, fontSize: 34, color: INK, marginTop: 4}}>{ACTION}</div>
          </div>
          {thinking && <div style={{fontFamily: GARAMOND_IT, fontSize: 24, color: MUTED}}><span style={{color: BRONZE}}>• • •</span> o narrador tece o destino…</div>}
          {narr && (
            <div style={{fontFamily: GARAMOND, fontSize: 44, lineHeight: 1.45, color: INK, alignSelf: 'stretch'}}>
              <span style={{float: 'left', fontFamily: CINZEL, fontSize: 108, lineHeight: 0.9, color: BRONZE, marginRight: 10, marginTop: 6}}>{narr[0]}</span>
              {narr.slice(1)}
              <span style={{opacity: f % 16 < 8 ? 1 : 0, color: BRONZE}}>▍</span>
            </div>
          )}
        </div>
        {/* barra de ação */}
        <div style={{position: 'absolute', left: 26, right: 26, bottom: 24, display: 'flex', gap: 12}}>
          <div style={{flex: 1, height: 58, border: `1.5px solid ${f < 36 ? BRONZE : BRONZE + '55'}`, borderRadius: 6, background: '#0a0d11', display: 'flex', alignItems: 'center', padding: '0 20px', fontFamily: GARAMOND, fontSize: 24, color: typed && f < 36 ? INK : '#7d7466'}}>
            {f < 36 ? (typed || 'O que você faz?') : 'O que você faz?'}
            {f < 36 && <span style={{opacity: f % 14 < 7 ? 1 : 0, color: BRONZE}}>|</span>}
          </div>
          <div style={{width: 120, height: 58, borderRadius: 6, background: `linear-gradient(180deg, ${BRONZE}, ${BRONZE_STRONG})`, display: 'grid', placeItems: 'center', fontFamily: CINZEL, fontWeight: 700, fontSize: 20, letterSpacing: 2, color: '#1a1206', transform: `scale(${f >= 34 && f < 38 ? 0.94 : 1})`}}>AGIR</div>
        </div>
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 36, display: 'flex', justifyContent: 'center'}}>
        <Line at={4} style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 52, color: INK, textShadow: '0 4px 20px #000'}}>Escreva qualquer ação. <span style={{color: BRONZE}}>O mundo responde.</span></Line>
      </div>
    </AbsoluteFill>
  );
};

/* ---------------- 6. Combate real + rolagem ---------------- */
const Combat: React.FC = () => {
  const f = useF();
  const shotIn = ramp(f, 0, 16);
  const push = interpolate(f, [0, 108], [1.0, 1.08]);
  const chip = ramp(f, 30, 44);
  const hit = ramp(f, 52, 60);
  return (
    <AbsoluteFill style={{background: '#120707'}}>
      <div style={{position: 'absolute', left: 110, top: 230, opacity: shotIn, transform: `scale(${push})`, transformOrigin: '20% 40%'}}>
        <Crop src="brag/combate.png" x={34} y={522} w={760} h={480} scale={1.5} style={{boxShadow: `0 0 0 1px ${BLOOD}88, 0 50px 100px -30px #000`}} />
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 70, textAlign: 'center', display: 'flex', justifyContent: 'center', gap: 22}}>
        <Line at={4} style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 62, color: INK}}>A IA narra.</Line>
        <Line at={18} style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 62, color: BRONZE}}>O Python rola os dados.</Line>
      </div>
      {/* painel de rolagem — fórmula real: 2d10 + Virtude contra a Esquiva */}
      <div style={{position: 'absolute', left: 1330, top: 300, width: 480, opacity: chip, transform: `translateX(${(1 - chip) * 40}px)`}}>
        <div style={{padding: '34px 40px', background: '#1a0f0a', border: `1.5px solid ${BRONZE}`, borderRadius: 12, boxShadow: `0 0 60px ${BLOOD}44`, fontFamily: CINZEL, color: INK}}>
          <div style={{fontSize: 20, letterSpacing: 6, color: BRONZE}}>ROLAGEM</div>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 22, fontSize: 32}}><span>2d10 <span style={{color: MUTED}}>+</span> Virtude</span><b style={{fontSize: 56, color: '#f3d395'}}>17</b></div>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 10, fontSize: 32, color: MUTED}}><span>Esquiva do alvo</span><b style={{fontSize: 40, color: INK}}>13</b></div>
          <div style={{height: 1, background: `${BRONZE}66`, margin: '24px 0'}} />
          <div style={{textAlign: 'center', fontWeight: 700, fontSize: 52, color: '#ff6b5c', letterSpacing: 8, opacity: hit, transform: `scale(${1 + (1 - hit) * 0.5})`, textShadow: `0 0 24px ${BLOOD}`}}>ACERTO</div>
        </div>
      </div>
      <Vignette strength={0.7} />
    </AbsoluteFill>
  );
};

/* ---------------- 7. Fechamento ---------------- */
const Outro: React.FC = () => {
  const f = useF();
  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 50% 45%, #1d160d, ${BG} 62%)`}}>
      <Embers n={34} />
      <div style={{position: 'absolute', top: 330, width: '100%', textAlign: 'center'}}>
        <Line at={4} style={{fontFamily: CINZEL, fontWeight: 600, fontSize: 64, color: INK}}>A IA narra. <span style={{color: BRONZE}}>O Python decide.</span></Line>
        <div style={{marginTop: 30}}><Ornament w={520} at={14} /></div>
        <Line at={18} style={{fontFamily: CINZEL, fontWeight: 700, fontSize: 96, color: INK, letterSpacing: 6, marginTop: 26, textShadow: `0 0 50px ${BRONZE}55`}}>rpg-ia-master</Line>
        <Line at={28} style={{fontFamily: GARAMOND, fontSize: 30, color: MUTED, marginTop: 18, letterSpacing: 2}}>LangGraph · FastAPI · React · mecânica 100% determinística</Line>
      </div>
      <div style={{position: 'absolute', bottom: 34, width: '100%', textAlign: 'center', fontFamily: GARAMOND, fontSize: 18, color: '#7d7466', opacity: ramp(f, 20, 34)}}>
        Música: “Crossing the Chasm” — Kevin MacLeod (incompetech.com) · CC BY 4.0
      </div>
      <Vignette strength={0.6} />
    </AbsoluteFill>
  );
};

/* ---------------- Som ---------------- */
const Sfx: React.FC<{at: number; src: string; vol: number}> = ({at, src, vol}) => (
  <Sequence from={at} layout="none">
    <Audio src={staticFile(`brag/${src}`)} volume={vol} />
  </Sequence>
);

export const Brag: React.FC = () => {
  const seq = (k: Key, el: React.ReactNode, inF?: number) => (
    <Sequence from={S[k][0]} durationInFrames={S[k][1] - S[k][0]} name={k}>
      <TimeScale.Provider value={K[k]}>
        <Dip dur={S[k][1] - S[k][0]} inF={inF}>{el}</Dip>
      </TimeScale.Provider>
    </Sequence>
  );
  const at = (k: Key, off: number) => S[k][0] + Math.round(off * K[k]);
  const MUSIC_START = Math.round((196.86 - BRAG_FRAMES / 30) * 30); // últimos 25 s: o final da música fecha o vídeo
  const keys = [7, 11, 15, 20, 24, 29].map((o) => at('play', o));
  return (
    <AbsoluteFill style={{background: BG}}>
      {seq('hook', <Hook />, 18)}
      {seq('dice', <Dice />)}
      {seq('reveal', <Reveal />)}
      {seq('create', <Create />)}
      {seq('play', <Play />)}
      {seq('combat', <Combat />)}
      {seq('outro', <Outro />)}
      <Audio src={staticFile('music/crossing_the_chasm.mp3')} startFrom={MUSIC_START} volume={(f) => interpolate(f, [0, 20, BRAG_FRAMES - 30, BRAG_FRAMES], [0, 0.85, 0.85, 0.7], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />
      <Sfx at={at('dice', 2)} src="dice-shake-1.ogg" vol={0.22} />
      <Sfx at={at('dice', 30)} src="dice-throw-1.ogg" vol={0.3} />
      <Sfx at={at('reveal', 6)} src="card-slide-1.ogg" vol={0.14} />
      <Sfx at={at('reveal', 34)} src="impactSoft_heavy_000.ogg" vol={0.22} />
      <Sfx at={at('create', 54)} src="card-place-1.ogg" vol={0.16} />
      {keys.map((k, i) => <Sfx key={k} at={k} src={`keypress-00${(i % 5) + 1}.wav`} vol={0.06} />)}
      <Sfx at={at('combat', 30)} src="dice-throw-1.ogg" vol={0.24} />
      <Sfx at={at('combat', 52)} src="impactSoft_heavy_000.ogg" vol={0.2} />
    </AbsoluteFill>
  );
};
