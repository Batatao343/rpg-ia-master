// SPEC-347: medição "visível e livre" SEM rolar antes (elementFromPoint + caixa dentro do viewport e do painel).
import type { Locator } from "@playwright/test";

export interface FreeBox { x: number; y: number; w: number; h: number; free: boolean; inView: boolean; lines: number; clipped: boolean }

export async function measure(loc: Locator): Promise<FreeBox> {
  return loc.evaluate((el) => {
    const r = el.getBoundingClientRect();
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    const panel = el.closest(".ws-panel")?.getBoundingClientRect();
    const inPanel = !panel || (r.top >= panel.top - 0.5 && r.bottom <= panel.bottom + 0.5);
    // Linhas por nó de texto VISÍVEL: o maior número de linhas entre eles (1 = nenhum quebrou).
    let lines = 0;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const parent = n.parentElement;
      if (!parent || !n.textContent?.trim() || getComputedStyle(parent).display === "none") continue;
      if (parent.getClientRects().length === 0) continue;
      const rg = document.createRange();
      rg.selectNodeContents(n);
      lines = Math.max(lines, new Set(Array.from(rg.getClientRects()).map((q) => Math.round(q.top))).size);
    }
    return {
      x: r.left, y: r.top, w: r.width, h: r.height,
      free: !!hit && (el === hit || el.contains(hit)),
      inView: r.left >= 0 && r.top >= 0 && r.right <= window.innerWidth && r.bottom <= window.innerHeight && inPanel,
      lines,
      clipped: el.scrollWidth > el.clientWidth + 1 || Array.from(el.querySelectorAll("span, small")).some((c) => { const q = c.getBoundingClientRect(); return q.width > 0 && (q.right > r.right + 0.5 || q.left < r.left - 0.5); }),
    };
  });
}

export const isFreeAndVisible = (b: FreeBox) => b.free && b.inView;
