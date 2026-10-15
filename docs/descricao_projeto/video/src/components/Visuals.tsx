import React from 'react';
import {useCurrentFrame} from 'remotion';
import {appear, fadeUp, schedule} from '../anim';
import {C, FONT_BODY, FONT_MONO, FONT_TITLE, STAGE} from '../theme';
import type {Visual} from '../types';
import {Graph} from './Graph';

const Heading: React.FC<{text: string; color: string}> = ({text, color}) => {
  const f = useCurrentFrame();
  const p = appear(f, 0, 16);
  return (
    <div style={{...fadeUp(p, 14), fontFamily: FONT_TITLE, fontWeight: 700, fontSize: 52, color: C.text, marginBottom: 34, display: 'flex', alignItems: 'center', gap: 20}}>
      <span style={{width: 10, height: 46, background: color, borderRadius: 3, boxShadow: `0 0 18px ${color}`}} />
      {text}
    </div>
  );
};

const Panel: React.FC<{children: React.ReactNode; color?: string; style?: React.CSSProperties}> = ({children, color, style}) => (
  <div style={{background: C.panel, border: `1.5px solid ${color ? color + '66' : C.panelBorder}`, borderRadius: 18, padding: '22px 28px', ...style}}>{children}</div>
);

// --- realce de código simples (sem dependências) ---
const KW = /\b(def|class|return|if|elif|else|for|while|in|not|and|or|import|from|as|with|try|except|raise|None|True|False|lambda|yield|async|await|const|let|function|export|type|interface|new|SELECT|FROM|WHERE|INSERT|UPDATE|CREATE|TABLE|POLICY|ON|FOR|USING|RETURNING|AND|OR)\b/g;
const highlight = (line: string) => {
  const out: React.ReactNode[] = [];
  const re = /(#.*$|\/\/.*$|--.*$)|("[^"]*"|'[^']*'|`[^`]*`)|(\b\d+(?:\.\d+)?\b)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  const pushPlain = (s: string) => {
    const parts = s.split(KW);
    parts.forEach((p, i) => {
      if (!p) return;
      const isKw = new RegExp(`^${KW.source}$`).test(p);
      out.push(<span key={k++} style={{color: isKw ? '#d79bff' : C.text}}>{p}</span>);
      void i;
    });
  };
  while ((m = re.exec(line))) {
    pushPlain(line.slice(last, m.index));
    const color = m[1] ? '#7d8a76' : m[2] ? '#9fd38a' : '#f0b96b';
    out.push(<span key={k++} style={{color, fontStyle: m[1] ? 'italic' : 'normal'}}>{m[0]}</span>);
    last = m.index + m[0].length;
  }
  pushPlain(line.slice(last));
  return out;
};

export const VisualView: React.FC<{v: Visual; color: string; audioFrames: number}> = ({v, color, audioFrames}) => {
  const f = useCurrentFrame();

  if (v.type === 'title') {
    const p = appear(f, 4, 30);
    const q = appear(f, 22, 30);
    return (
      <div style={{width: '100%', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center'}}>
        <div style={{width: 160 * p, height: 3, background: color, marginBottom: 40, boxShadow: `0 0 20px ${color}`}} />
        <div style={{...fadeUp(p, 30), fontFamily: FONT_TITLE, fontWeight: 700, fontSize: 96, color: C.text, lineHeight: 1.1, maxWidth: 1500, textShadow: `0 0 40px ${color}55`}}>{v.heading}</div>
        {v.subheading && <div style={{...fadeUp(q, 20), fontFamily: FONT_BODY, fontSize: 38, color: C.muted, marginTop: 34, maxWidth: 1300, lineHeight: 1.35}}>{v.subheading}</div>}
        <div style={{width: 160 * q, height: 3, background: color, marginTop: 44, boxShadow: `0 0 20px ${color}`}} />
      </div>
    );
  }

  const body = (() => {
    switch (v.type) {
      case 'bullets': {
        const at = schedule(v.items.length, audioFrames);
        return (
          <div style={{display: 'flex', flexDirection: 'column', gap: 24}}>
            {v.items.map((it, i) => {
              const p = appear(f, at(i));
              return (
                <div key={i} style={{...fadeUp(p), display: 'flex', gap: 24, alignItems: 'flex-start', fontFamily: FONT_BODY, fontSize: 38, color: C.text, lineHeight: 1.3}}>
                  <span style={{color, fontFamily: FONT_TITLE, fontSize: 34, minWidth: 30, marginTop: 2}}>◆</span>
                  <span>{it}</span>
                </div>
              );
            })}
          </div>
        );
      }
      case 'graph':
        return <Graph nodes={v.nodes} edges={v.edges} direction={v.direction} w={STAGE.w} h={STAGE.h - 150} audioFrames={audioFrames} />;
      case 'flow': {
        const at = schedule(v.steps.length, audioFrames);
        const n = v.steps.length;
        const twoRows = n > 4;
        const perRow = twoRows ? Math.ceil(n / 2) : n;
        const cardW = (STAGE.w - (perRow - 1) * 36) / perRow;
        return (
          <div style={{display: 'flex', flexWrap: 'wrap', gap: '44px 36px'}}>
            {v.steps.map((s, i) => {
              const p = appear(f, at(i));
              return (
                <div key={i} style={{...fadeUp(p), width: cardW, position: 'relative'}}>
                  <Panel color={color} style={{minHeight: twoRows ? 170 : 260, display: 'flex', flexDirection: 'column', gap: 14}}>
                    <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
                      <span style={{fontFamily: FONT_TITLE, fontWeight: 700, fontSize: 30, color: C.bg0, background: color, borderRadius: 999, width: 50, height: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>{i + 1}</span>
                      <span style={{fontFamily: FONT_BODY, fontWeight: 700, fontSize: 28, color: C.text, lineHeight: 1.15}}>{s.label}</span>
                    </div>
                    {s.detail && <div style={{fontFamily: FONT_BODY, fontSize: 23, color: C.muted, lineHeight: 1.35}}>{s.detail}</div>}
                  </Panel>
                  {i < n - 1 && (i + 1) % perRow !== 0 && (
                    <div style={{position: 'absolute', right: -32, top: '42%', color, fontSize: 30, opacity: appear(f, at(i + 1))}}>➜</div>
                  )}
                </div>
              );
            })}
          </div>
        );
      }
      case 'code': {
        const lines = v.code.replace(/\t/g, '    ').split('\n');
        const at = schedule(lines.length, audioFrames * 0.6, 10);
        const fs = lines.length > 13 ? 25 : 29;
        return (
          <Panel color={color} style={{padding: 0, overflow: 'hidden'}}>
            {v.file && (
              <div style={{padding: '14px 26px', borderBottom: `1px solid ${C.panelBorder}`, fontFamily: FONT_MONO, fontSize: 22, color: C.muted, display: 'flex', gap: 12, alignItems: 'center'}}>
                <span style={{width: 12, height: 12, borderRadius: 99, background: '#d8574f'}} />
                <span style={{width: 12, height: 12, borderRadius: 99, background: '#e3b765'}} />
                <span style={{width: 12, height: 12, borderRadius: 99, background: '#6db96d'}} />
                <span style={{marginLeft: 14}}>{v.file}</span>
              </div>
            )}
            <div style={{padding: '22px 30px', fontFamily: FONT_MONO, fontSize: fs, lineHeight: 1.5, whiteSpace: 'pre', fontVariantLigatures: 'none'}}>
              {lines.map((ln, i) => (
                <div key={i} style={{opacity: appear(f, at(i), 10), display: 'flex'}}>
                  <span style={{color: C.dim, width: 48, textAlign: 'right', marginRight: 26, userSelect: 'none'}}>{i + 1}</span>
                  <span>{highlight(ln)}</span>
                </div>
              ))}
            </div>
          </Panel>
        );
      }
      case 'stats': {
        const at = schedule(v.items.length, audioFrames);
        const cols = v.items.length <= 3 ? v.items.length : Math.ceil(v.items.length / 2);
        return (
          <div style={{display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 34}}>
            {v.items.map((it, i) => {
              const p = appear(f, at(i));
              return (
                <Panel key={i} color={color} style={{...fadeUp(p), textAlign: 'center', padding: '40px 24px'}}>
                  <div style={{fontFamily: FONT_TITLE, fontWeight: 700, fontSize: 84, color, textShadow: `0 0 30px ${color}55`, lineHeight: 1}}>{it.value}</div>
                  <div style={{fontFamily: FONT_BODY, fontSize: 28, color: C.text, marginTop: 20, lineHeight: 1.3}}>{it.label}</div>
                </Panel>
              );
            })}
          </div>
        );
      }
      case 'compare': {
        const all = v.left.items.length + v.right.items.length;
        const at = schedule(all + 2, audioFrames);
        const side = (s: {title: string; items: string[]}, base: number, c: string) => (
          <Panel color={c} style={{flex: 1, ...fadeUp(appear(f, at(base)))}}>
            <div style={{fontFamily: FONT_TITLE, fontWeight: 700, fontSize: 38, color: c, marginBottom: 22}}>{s.title}</div>
            {s.items.map((it, i) => (
              <div key={i} style={{...fadeUp(appear(f, at(base + i + 1))), fontFamily: FONT_BODY, fontSize: 29, color: C.text, lineHeight: 1.35, marginBottom: 16, display: 'flex', gap: 14}}>
                <span style={{color: c}}>▸</span>
                <span>{it}</span>
              </div>
            ))}
          </Panel>
        );
        return (
          <div style={{display: 'flex', gap: 40, alignItems: 'stretch'}}>
            {side(v.left, 0, '#c9a46b')}
            <div style={{alignSelf: 'center', fontFamily: FONT_TITLE, fontSize: 40, color: C.dim}}>×</div>
            {side(v.right, v.left.items.length + 1, color)}
          </div>
        );
      }
      case 'table': {
        const at = schedule(v.rows.length + 1, audioFrames);
        const fs = v.rows.length > 5 ? 25 : 29;
        return (
          <Panel color={color} style={{padding: 0, overflow: 'hidden'}}>
            <table style={{width: '100%', borderCollapse: 'collapse', fontFamily: FONT_BODY, fontSize: fs}}>
              <thead>
                <tr style={{opacity: appear(f, at(0))}}>
                  {v.columns.map((c, i) => (
                    <th key={i} style={{textAlign: 'left', padding: '18px 26px', color, fontWeight: 700, borderBottom: `2px solid ${color}66`, background: `${color}14`}}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {v.rows.map((r, ri) => (
                  <tr key={ri} style={fadeUp(appear(f, at(ri + 1)), 10)}>
                    {r.map((cell, ci) => (
                      <td key={ci} style={{padding: '15px 26px', color: ci === 0 ? C.text : C.muted, fontWeight: ci === 0 ? 600 : 400, borderBottom: `1px solid ${C.panelBorder}`, lineHeight: 1.3}}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        );
      }
      case 'callout': {
        const p = appear(f, 10, 24);
        const c = v.kind === 'warn' ? '#e07a5f' : v.kind === 'key' ? C.gold : color;
        const icon = v.kind === 'warn' ? '⚠' : v.kind === 'key' ? '✦' : 'ℹ';
        return (
          <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: STAGE.h - 150}}>
            <Panel color={c} style={{...fadeUp(p), maxWidth: 1400, padding: '56px 70px', display: 'flex', gap: 46, alignItems: 'center', background: `${c}10`}}>
              <div style={{fontSize: 110, color: c, lineHeight: 1, textShadow: `0 0 30px ${c}`}}>{icon}</div>
              <div style={{fontFamily: FONT_BODY, fontSize: 42, color: C.text, lineHeight: 1.4}}>{v.text}</div>
            </Panel>
          </div>
        );
      }
      case 'example': {
        const at = schedule(v.lines.length, audioFrames);
        const fs = v.lines.length > 6 ? 28 : 33;
        return (
          <Panel color={color} style={{padding: '18px 0'}}>
            {v.lines.map((l, i) => {
              const p = appear(f, at(i));
              return (
                <div key={i} style={{...fadeUp(p, 10), display: 'flex', padding: '13px 40px', borderBottom: i < v.lines.length - 1 ? `1px solid ${C.panelBorder}` : 'none', fontSize: fs, alignItems: 'baseline'}}>
                  <span style={{fontFamily: FONT_BODY, color: C.muted, width: 560, flexShrink: 0}}>
                    <span style={{color, fontFamily: FONT_MONO, marginRight: 18}}>{String(i + 1).padStart(2, '0')}</span>
                    {l.label}
                  </span>
                  <span style={{fontFamily: FONT_MONO, color: C.text, fontWeight: 600, fontVariantLigatures: 'none'}}>{l.value}</span>
                </div>
              );
            })}
          </Panel>
        );
      }
      default:
        return null;
    }
  })();

  return (
    <div style={{width: '100%', height: '100%', display: 'flex', flexDirection: 'column'}}>
      <Heading text={v.heading} color={color} />
      <div style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: v.type === 'graph' || v.type === 'callout' ? 'flex-start' : 'center', paddingBottom: 40}}>{body}</div>
    </div>
  );
};
