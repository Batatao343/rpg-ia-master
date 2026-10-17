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
