import React from 'react';
import {useCurrentFrame} from 'remotion';
import {appear, schedule} from '../anim';
import {C, FONT_BODY, GROUP_COLORS, GROUP_LABEL} from '../theme';
import type {Group} from '../types';

type Node = {id: string; label: string; group?: Group};
type Edge = {from: string; to: string; label?: string};
type Box = {x: number; y: number; row: number};

/** Camadas por caminho mais longo (o roteiro garante DAG; ciclos são cortados). */
const layer = (nodes: Node[], edges: Edge[]) => {
  const ids = new Set(nodes.map((n) => n.id));
  const es = edges.filter((e) => ids.has(e.from) && ids.has(e.to) && e.from !== e.to);
  const lvl: Record<string, number> = {};
  nodes.forEach((n) => (lvl[n.id] = 0));
  for (let k = 0; k < nodes.length; k++) {
    let changed = false;
    for (const e of es) {
      if (lvl[e.to] < lvl[e.from] + 1 && lvl[e.from] + 1 < nodes.length) {
        lvl[e.to] = lvl[e.from] + 1;
        changed = true;
      }
    }
    if (!changed) break;
  }
  const layers: string[][] = [];
  nodes.forEach((n) => (layers[lvl[n.id]] ??= []).push(n.id));
  const L = layers.filter(Boolean);
  // uma passada de baricentro para reduzir cruzamentos
  const idx: Record<string, number> = {};
  L.forEach((ly) => ly.forEach((id, i) => (idx[id] = i)));
  for (let li = 1; li < L.length; li++) {
    const bc = (id: string) => {
      const ps = es.filter((e) => e.to === id).map((e) => idx[e.from]);
      return ps.length ? ps.reduce((a, b) => a + b) / ps.length : idx[id];
    };
    L[li].sort((a, b) => bc(a) - bc(b));
    L[li].forEach((id, i) => (idx[id] = i));
  }
  return {layers: L, es};
};

export const Graph: React.FC<{
  nodes: Node[];
  edges: Edge[];
  direction?: 'LR' | 'TB';
  w: number;
  h: number;
  audioFrames: number;
}> = ({nodes, edges, direction = 'LR', w, h, audioFrames}) => {
  const frame = useCurrentFrame();
  const {layers, es} = layer(nodes, edges);
  const L = layers.length;
  const maxPer = Math.max(...layers.map((l) => l.length));
  const longest = Math.max(...nodes.map((n) => n.label.length));

  // TB só quando é raso; cadeias longas viram "serpentina" da esquerda para a direita
  const tb = direction === 'TB' && L <= 5;
  const perRow = tb ? L : L <= 6 ? L : Math.ceil(L / Math.ceil(L / 6));
  const rows = tb ? 1 : Math.ceil(L / perRow);

  const pos: Record<string, Box> = {};
  let nodeW: number, nodeH: number;
  if (tb) {
    const mainStep = h / L;
    const crossStep = w / maxPer;
    nodeW = Math.min(crossStep * 0.82, 340);
    nodeH = Math.min(mainStep * 0.6, 96);
    layers.forEach((ids, li) => {
      const off = (maxPer - ids.length) * crossStep * 0.5;
      ids.forEach((id, k) => (pos[id] = {x: off + crossStep * (k + 0.5), y: mainStep * (li + 0.5), row: 0}));
    });
  } else {
    const colStep = w / perRow;
    const bandH = h / rows;
    const crossStep = bandH / maxPer;
    nodeW = Math.min(colStep * 0.8, 340);
    nodeH = Math.max(46, Math.min(crossStep * 0.68, 104));
    layers.forEach((ids, li) => {
      const row = Math.floor(li / perRow);
      const col = li % perRow;
      const off = (maxPer - ids.length) * crossStep * 0.5;
      ids.forEach((id, k) => (pos[id] = {x: colStep * (col + 0.5), y: row * bandH + off + crossStep * (k + 0.5), row}));
    });
  }
  // fonte que cabe: largura útil / (caracteres por linha), permitindo quebrar em 2 linhas
  const charsPerLine = Math.max(10, Math.ceil(longest / (nodeH > 70 ? 2 : 1.4)));
  const fontSize = Math.max(16, Math.min(28, (nodeW - 24) / (charsPerLine * 0.56)));

  const order = layers.flat();
  const at = schedule(order.length, audioFrames);
  const startOf: Record<string, number> = {};
  order.forEach((id, i) => (startOf[id] = at(i)));
  const groups = Array.from(new Set(nodes.map((n) => n.group ?? 'neutral'))).filter((g) => g !== 'neutral');

  const edgePath = (a: Box, b: Box) => {
    if (tb) {
      const x1 = a.x, y1 = a.y + nodeH / 2, x2 = b.x, y2 = b.y - nodeH / 2, m = (y1 + y2) / 2;
      return {d: `M${x1},${y1} C${x1},${m} ${x2},${m} ${x2},${y2}`, lx: x2 + 10, ly: y2 - 10, anchor: 'start' as const};
    }
    if (b.row > a.row) {
      // quebra de linha da serpentina: sai por baixo, entra por cima
      const x1 = a.x, y1 = a.y + nodeH / 2, x2 = b.x, y2 = b.y - nodeH / 2, m = (y1 + y2) / 2;
      return {d: `M${x1},${y1} C${x1},${m + 40} ${x2},${m - 40} ${x2},${y2}`, lx: x2 + 10, ly: y2 - 10, anchor: 'start' as const};
    }
    if (b.x <= a.x) {
      const x1 = a.x, y1 = a.y - nodeH / 2, x2 = b.x, y2 = b.y - nodeH / 2, top = Math.min(y1, y2) - 60;
      return {d: `M${x1},${y1} C${x1},${top} ${x2},${top} ${x2},${y2}`, lx: (x1 + x2) / 2, ly: top + 18, anchor: 'middle' as const};
    }
    const x1 = a.x + nodeW / 2, y1 = a.y, x2 = b.x - nodeW / 2, y2 = b.y, m = (x1 + x2) / 2;
    return {d: `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`, lx: m, ly: (y1 + y2) / 2 - 12, anchor: 'middle' as const};
  };

  return (
    <div style={{position: 'relative', width: w, height: h}}>
      <svg width={w} height={h} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
        <defs>
          <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill={C.gold} />
          </marker>
        </defs>
        {es.map((e, i) => {
          const p = appear(frame, Math.max(startOf[e.from], startOf[e.to]) + 6, 22);
          const {d, lx, ly, anchor} = edgePath(pos[e.from], pos[e.to]);
          const len = 2400;
          return (
            <g key={i} opacity={p > 0 ? 1 : 0}>
              <path d={d} fill="none" stroke={C.gold} strokeOpacity={0.55} strokeWidth={2.5} strokeDasharray={len} strokeDashoffset={(1 - p) * len} markerEnd={p > 0.95 ? 'url(#arr)' : undefined} />
            </g>
          );
        })}
      </svg>
      {nodes.map((n) => {
        const p = appear(frame, startOf[n.id] ?? 0, 16);
        const col = GROUP_COLORS[n.group ?? 'neutral'];
        const q = pos[n.id];
        return (
          <div
            key={n.id}
            style={{
              position: 'absolute',
              left: q.x - nodeW / 2,
              top: q.y - nodeH / 2,
              width: nodeW,
              height: nodeH,
              borderRadius: 14,
              background: `linear-gradient(180deg, ${col}2b, ${col}12), ${C.bg1}`,
              border: `2px solid ${col}`,
              boxShadow: `0 0 ${24 * p}px ${col}44`,
              color: C.text,
              fontFamily: FONT_BODY,
              fontWeight: 600,
              fontSize,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: '0 12px',
              lineHeight: 1.12,
              overflowWrap: 'anywhere',
              opacity: p,
              transform: `scale(${0.85 + 0.15 * p})`,
            }}
          >
            {n.label.replace(/_/g, '_​')}
          </div>
        );
      })}
      <svg width={w} height={h} style={{position: 'absolute', inset: 0, overflow: 'visible', pointerEvents: 'none'}}>
        {es.map((e, i) => {
          if (!e.label) return null;
          const p = appear(frame, Math.max(startOf[e.from], startOf[e.to]) + 10, 22);
          const {lx, ly, anchor} = edgePath(pos[e.from], pos[e.to]);
          return (
            <text key={i} x={lx} y={ly} fill={C.gold} fontFamily={FONT_BODY} fontWeight={600} fontSize={Math.max(15, Math.min(19, fontSize * 0.7))} textAnchor={anchor} opacity={p} style={{paintOrder: 'stroke', stroke: C.bg0, strokeWidth: 7}}>
              {e.label}
            </text>
          );
        })}
      </svg>
      {groups.length > 0 && (
        <div style={{position: 'absolute', right: 0, bottom: -44, display: 'flex', gap: 26, fontFamily: FONT_BODY, fontSize: 18, color: C.muted}}>
          {groups.map((g) => (
            <span key={g} style={{display: 'flex', alignItems: 'center', gap: 8}}>
              <span style={{width: 14, height: 14, borderRadius: 4, background: GROUP_COLORS[g as Group]}} />
              {GROUP_LABEL[g as Group]}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
