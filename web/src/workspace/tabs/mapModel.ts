// SPEC-210: helpers puros da aba Mapa (testaveis em Node, sem React/CSS).
export function periodsLabel(periods: number): string {
  if (periods <= 0) return "sem custo de tempo";
  return periods === 1 ? "1 período" : `${periods} períodos`;
}

/** Navegação por setas: foca o nó mais próximo na direção pressionada. */
export function nextNodeIndex(points: Array<{ x: number; y: number }>, from: number, key: string): number {
  const dir = ({ ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowDown: [0, 1], ArrowUp: [0, -1] } as Record<string, [number, number]>)[key];
  if (!dir || !points[from]) return -1;
  let best = -1;
  let bestScore = Infinity;
  points.forEach((p, i) => {
    if (i === from) return;
    const dx = p.x - points[from].x;
    const dy = p.y - points[from].y;
    const along = dx * dir[0] + dy * dir[1];
    if (along <= 0) return;
    const score = Math.hypot(dx, dy) + Math.abs(dx * dir[1] + dy * dir[0]);
    if (score < bestScore) { bestScore = score; best = i; }
  });
  return best;
}

export type LabelSide = "below" | "right" | "left" | "above" | "hidden";
export interface LabelItem { id: string; x: number; y: number; chars: number; priority: number }

const CHAR_PX = 7.6;     // itálico 0.9rem, folgado de propósito (melhor sobrar que colidir)
const LABEL_H = 20;
const ICON_PX = 24;      // ícone + espaço antes do nome
const DOT_HALF = 9;
const PAD = 3;

interface Box { x1: number; y1: number; x2: number; y2: number }
const hit = (a: Box, b: Box) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;

/** Posição do rótulo de cada nó sem colisão com outros rótulos nem com marcadores: tenta
 *  abaixo → direita → esquerda → acima; nó de menor prioridade que não cabe em lugar nenhum
 *  esconde o rótulo (o botão mantém o nome acessível). `canvas` em px. Determinístico e puro. */
export function placeLabels(items: LabelItem[], canvas: { w: number; h: number }): Record<string, LabelSide> {
  const px = items.map((n) => ({ ...n, px: (n.x / 100) * canvas.w, py: (n.y / 100) * canvas.h }));
  const dots: Box[] = px.map((n) => ({ x1: n.px - DOT_HALF, y1: n.py - DOT_HALF, x2: n.px + DOT_HALF, y2: n.py + DOT_HALF }));
  const placed: Box[] = [];
  const out: Record<string, LabelSide> = {};
  const order = [...px].sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  for (const n of order) {
    const w = n.chars * CHAR_PX + ICON_PX;
    const boxes: Array<[Exclude<LabelSide, "hidden">, Box]> = [
      ["below", { x1: n.px - w / 2, y1: n.py + DOT_HALF, x2: n.px + w / 2, y2: n.py + DOT_HALF + LABEL_H }],
      ["right", { x1: n.px + DOT_HALF, y1: n.py - LABEL_H / 2, x2: n.px + DOT_HALF + w, y2: n.py + LABEL_H / 2 }],
      ["left", { x1: n.px - DOT_HALF - w, y1: n.py - LABEL_H / 2, x2: n.px - DOT_HALF, y2: n.py + LABEL_H / 2 }],
      ["above", { x1: n.px - w / 2, y1: n.py - DOT_HALF - LABEL_H, x2: n.px + w / 2, y2: n.py - DOT_HALF }],
    ];
    out[n.id] = "hidden";
    for (const [side, b] of boxes) {
      const g: Box = { x1: b.x1 - PAD, y1: b.y1 - PAD, x2: b.x2 + PAD, y2: b.y2 + PAD };
      const own = px.indexOf(n);
      if (placed.some((p) => hit(g, p)) || dots.some((d, i) => i !== own && hit(g, d))) continue;
      out[n.id] = side;
      placed.push(g);
      break;
    }
  }
  return out;
}
